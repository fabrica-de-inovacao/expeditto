"""Regras de negócio: portarias, classificação, semestres e política de rotas."""

from datetime import date

import httpx
import pytest

from suap_rit import semestres
from suap_rit.classificar import classificar
from suap_rit.client import RotaNaoPermitida, SessaoExpirada, SuapClient
from suap_rit.models import Evidencia, Semestre, TipoEvidencia, Topico
from suap_rit.suap import portaria


# -- portarias -------------------------------------------------------------------
def test_portaria_vigencia_e_papel_presidente():
    d = portaria.parse(
        "PORTARIA Nº 12/2025 - X, DE 3 DE MARÇO DE 2025 RESOLVE: Art. 1º Designar I - Presidente: "
        "Fulana de Tal, SIAPE 999 II - Membros: Outro. Art. 2º vigência no período de 01/03/2025 a 30/06/2025.",
        nome="Fulana de Tal")
    assert d.numero == "12/2025" and d.data == date(2025, 3, 3)
    assert d.papel == "Presidente"
    assert (d.inicio, d.fim) == (date(2025, 3, 1), date(2025, 6, 30))


def test_portaria_vice_presidente_nao_vira_presidente():
    d = portaria.parse("RESOLVE: Art. 1º Presidente: A; Vice-presidente: Fulana de Tal", nome="Fulana de Tal")
    assert d.papel == "Vice-presidente"


def test_portaria_nde_bienio_em_anos():
    d = portaria.parse("RESOLVE: Art. 1º Núcleo Docente Estruturante (NDE) do Curso / 2025 a 2027: Fulana",
                       nome="Fulana")
    assert (d.inicio, d.fim) == (date(2025, 1, 1), date(2027, 12, 31))


def test_portaria_a_partir_desta_data_e_indeterminada():
    d = portaria.parse("PORTARIA N° 5/2023 - X, DE 19 DE ABRIL DE 2023 RESOLVE: Art. 1º Alterar, a partir "
                       "desta data, a composição do NDE: Fulana", nome="Fulana")
    assert d.vigencia_indeterminada and d.inicio == date(2023, 4, 19) and d.fim is None


# -- classificação ---------------------------------------------------------------
def _portaria(descricao: str, tipo_arquivo="Designação para compor comissões/conselhos/bancas") -> Evidencia:
    return Evidencia(id="p", fonte="t", tipo=TipoEvidencia.PORTARIA, titulo="PORTARIA",
                     descricao=descricao, extras={"tipo_arquivo": tipo_arquivo})


@pytest.mark.parametrize("descricao,esperado", [
    ("Banca de Monografia - Aluno", Topico.ORIENTACAO_ALUNOS),
    ("Núcleo Docente Estruturante (NDE) do Curso de Sistemas de Informação", Topico.REUNIOES),
    ("Comissão do Plano de Transição Curricular do Curso Técnico", Topico.APOIO_ENSINO),
    ("Comissão Organizadora: IFMA de Portas Abertas", Topico.GESTAO),
    ("Coordenação do laboratório Fábrica de Inovação", Topico.GESTAO),
])
def test_classificacao_portarias(descricao, esperado):
    assert classificar(_portaria(descricao)).topicos == [esperado]


def test_tipo_generico_comissoes_bancas_nao_forca_banca():
    cls = classificar(_portaria("Comissão de Avaliação de Desempenho"))
    assert cls.topicos == [Topico.GESTAO]


def test_tipo_de_arquivo_define_programa_institucional():
    cls = classificar(_portaria("Bolsista supervisora", "Portaria de Designação em Programas Institucionais "
                                                        "(PRONATEC/MEDIOTEC/ETEC/OUTROS)"))
    assert cls.topicos == [Topico.PROGRAMAS_PROJETOS_ENSINO]


def test_capacitacao_vai_para_dois_topicos():
    ev = Evidencia(id="c", fonte="t", tipo=TipoEvidencia.CAPACITACAO, titulo="Encontro Pedagógico")
    assert classificar(ev).topicos == [Topico.REUNIOES, Topico.APOIO_ENSINO]


def test_portaria_sem_regra_e_incerta():
    assert classificar(_portaria("Assunto qualquer")).incerta


# -- semestres -------------------------------------------------------------------
SEMS = {
    "2025.1": Semestre(ano=2025, periodo=1, inicio=date(2025, 2, 3), fim=date(2025, 6, 26)),
    "2025.2": Semestre(ano=2025, periodo=2, inicio=date(2025, 8, 4), fim=date(2025, 12, 17)),
}


def test_janela_estende_ate_vespera_do_proximo():
    assert semestres.janelas(SEMS)["2025.1"] == (date(2025, 2, 3), date(2025, 8, 3))


def test_evidencia_multissemestre_entra_nos_dois():
    ev = Evidencia(id="p", fonte="t", tipo=TipoEvidencia.PROJETO_PESQUISA, titulo="P",
                   inicio=date(2025, 3, 1), fim=date(2025, 10, 31))
    j = semestres.janelas(SEMS)
    assert semestres.pertence(ev, "2025.1", j["2025.1"]) and semestres.pertence(ev, "2025.2", j["2025.2"])


def test_banca_vale_pela_data_da_defesa():
    ev = Evidencia(id="b", fonte="t", tipo=TipoEvidencia.BANCA, titulo="B",
                   data_evento=date(2025, 7, 10), semestre_letivo="2025.2")
    j = semestres.janelas(SEMS)
    assert semestres.pertence(ev, "2025.1", j["2025.1"])  # julho: férias → semestre anterior
    assert not semestres.pertence(ev, "2025.2", j["2025.2"])


def test_vigencia_aberta_vale_ate_hoje():
    ev = Evidencia(id="f", fonte="t", tipo=TipoEvidencia.FUNCAO, titulo="Coord", inicio=date(2023, 4, 5))
    j = semestres.janelas(SEMS)
    assert semestres.pertence(ev, "2025.2", j["2025.2"], hoje=date(2026, 9, 29))


def test_estimativa_civil():
    s = semestres.estimar("2026.2")
    assert (s.inicio, s.fim, s.fonte_datas) == (date(2026, 7, 1), date(2026, 12, 31), "estimativa")


# -- cliente ---------------------------------------------------------------------
def test_allowlist_de_rotas():
    c = SuapClient({}, matricula="1234567")
    c.verificar_rota("/edu/professor/?tab=banca")
    c.verificar_rota("/rh/servidor/1234567/?tab=pasta_funcional")
    for proibida in ("/rh/servidor/9999999/", "/admin/edu/diario/", "/pit_rit_v2/entregar_relatorio/1/",
                     "/djtools/breadcrumbs_reset/x/", "/comum/minha_conta/"):
        with pytest.raises(RotaNaoPermitida):
            c.verificar_rota(proibida)


def test_sessao_expirada_detectada_pelo_redirect():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/edu/professor/":
            return httpx.Response(302, headers={"Location": "/accounts/login/?next=/edu/professor/"})
        return httpx.Response(200, text="login")
    c = SuapClient({}, transport=httpx.MockTransport(handler), base_url="https://suap.test")
    with pytest.raises(SessaoExpirada):
        c.html("/edu/professor/")


def test_pdf_assincrono(monkeypatch):
    chamadas = {"progresso": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p == "/documento_eletronico/imprimir_documento_pdf/1/carta/":
            return httpx.Response(302, headers={"Location": "/djtools/process2/ab-12/"})
        if p == "/djtools/process2/ab-12/":
            return httpx.Response(200, text="<html>tarefa</html>")
        if p == "/djtools/process_progress2/0/ab-12/":
            chamadas["progresso"] += 1
            pronto = chamadas["progresso"] > 1
            return httpx.Response(200, text="100::ok::x.pdf::..::" if pronto else "40::::::")
        if p == "/djtools/process_progress2/1/ab-12/":
            return httpx.Response(200, content=b"%PDF-1.4 conteudo")
        return httpx.Response(404)

    monkeypatch.setattr("suap_rit.client.time.sleep", lambda _: None)
    c = SuapClient({}, transport=httpx.MockTransport(handler), base_url="https://suap.test")
    assert c.pdf_assincrono("/documento_eletronico/imprimir_documento_pdf/1/carta/").startswith(b"%PDF")
    assert chamadas["progresso"] == 2


# -- substituição de portarias ---------------------------------------------------
def test_nova_composicao_do_nde_encerra_a_anterior():
    from suap_rit.coleta import _encerrar_substituidas

    antiga = Evidencia(id="a", fonte="t", tipo=TipoEvidencia.PORTARIA, titulo="P 65/2023",
                       descricao="Alterar a composição do Núcleo Docente Estruturante do Curso de Sistemas de Informação",
                       inicio=date(2023, 4, 19), vigencia_indeterminada=True)
    nova = Evidencia(id="b", fonte="t", tipo=TipoEvidencia.PORTARIA, titulo="P 121/2025",
                     descricao="Núcleo Docente Estruturante (NDE) do Curso de Sistemas de Informação / 2025 a 2027",
                     inicio=date(2025, 5, 8), fim=date(2027, 5, 7))
    colegiado = Evidencia(id="c", fonte="t", tipo=TipoEvidencia.PORTARIA, titulo="P 64/2023",
                          descricao="Composição do Colegiado do Curso de Sistemas de Informação",
                          inicio=date(2023, 4, 18), vigencia_indeterminada=True)
    _encerrar_substituidas([nova, antiga, colegiado])
    assert antiga.fim == date(2025, 5, 7) and antiga.extras["substituida_por"] == "b"
    assert not antiga.vigencia_indeterminada
    assert colegiado.fim is None  # outro órgão: não é afetado


@pytest.mark.parametrize("texto", [
    "colegiado do curso de sistemas de informação / 2025 a 2027",
    "designar para compor o colegiado do curso bacharelado em sistemas de informação do ifma campus exemplo",
    "alterar a composição do colegiado do curso de sistemas de informação do ifma campus exemplo",
    "nde do curso bacharelado em sistemas de informação, ",
])
def test_nome_do_curso_normalizado(texto):
    from suap_rit.coleta import _curso

    assert _curso(texto) == "sistemas-de-informacao"


def test_orientacao_em_projeto_de_pesquisa_vai_para_dois_topicos():
    ev = Evidencia(id="o", fonte="t", tipo=TipoEvidencia.ORIENTACAO_PROJETO, titulo="O",
                   extras={"tipo_projeto": "projeto_pesquisa"})
    assert classificar(ev).topicos == [Topico.ORIENTACAO_ALUNOS, Topico.PESQUISA]
    ev.extras["tipo_projeto"] = "projeto_extensao"
    assert classificar(ev).topicos == [Topico.ORIENTACAO_ALUNOS]


def test_estagio_usa_declaracao_do_ano_do_semestre():
    from suap_rit.coleta import _declaracao_de_estagio

    ev = Evidencia(id="e", fonte="t", tipo=TipoEvidencia.ESTAGIO, titulo="E",
                   extras={"declaracao_2025": "/d/2025/", "declaracao_2024": "/d/2024/"})
    _declaracao_de_estagio(ev, Semestre(ano=2025, periodo=1))
    assert ev.url_comprovante == "/d/2025/"


def test_portaria_de_designacao_individual_pega_a_funcao():
    d = portaria.parse("RESOLVE: Art. 1º Designar o (a) servidor (a) Fulana de Tal , Professor Ens Basico, "
                       "para desempenhar a Função de Coordenador (a) do Curso Técnico em Informática.",
                       nome="Fulana de Tal")
    assert d.papel == "Coordenador (a)"


def test_curso_com_sufixo_do_campus():
    from suap_rit.coleta import _curso

    assert _curso("nde do curso bacharelado em sistemas de informação do campus exemplo") == "sistemas-de-informacao"


def test_projeto_que_comeca_nas_ferias_e_do_semestre_seguinte():
    j = semestres.janelas(SEMS)
    letivo = (SEMS["2025.1"].inicio, SEMS["2025.1"].fim)
    projeto = Evidencia(id="p", fonte="t", tipo=TipoEvidencia.PROJETO_PESQUISA, titulo="P",
                        inicio=date(2025, 7, 1), fim=date(2025, 12, 31))
    assert not semestres.pertence(projeto, "2025.1", j["2025.1"], letivo=letivo)
    banca = Evidencia(id="b", fonte="t", tipo=TipoEvidencia.BANCA, titulo="B", data_evento=date(2025, 7, 10))
    assert semestres.pertence(banca, "2025.1", j["2025.1"], letivo=letivo)  # evento pontual: janela


def test_portaria_papel_como_coordenadora():
    d = portaria.parse("RESOLVE: Art. 1º - Designar a servidora Fulana de Tal , matrícula 1234567, para atuar "
                       "como Coordenadora do Projeto Aurora. Art. 2º vigência de 07/11/2025 a 07/11/2026.",
                       nome="Fulana de Tal", matricula="1234567")
    assert d.papel == "Coordenadora"


def test_ata_classificada_pelo_assunto_e_departamento_nao_pelo_corpo():
    ev = Evidencia(id="a", fonte="t", tipo=TipoEvidencia.ATA, titulo="Reunião com bolsistas premiados",
                   descricao="E-mail do Departamento de Pesquisa, Pós-Graduação, Inovação e Extensão",
                   extras={"texto": "Prezados coordenadores e bolsistas..."})
    assert classificar(ev).topicos == [Topico.PESQUISA]


@pytest.mark.parametrize("bruto,padrao", [
    ("Coordenadora", "Coordenador(a)"),
    ("Coordenador (a)", "Coordenador(a)"),
    ("COORDENADOR(A) DE CURSOS", "Coordenador(a) de cursos"),
    ("Subcoordenador(a)", "Subcoordenador(a)"),
    ("Coordenador de Projeto", "Coordenador(a) de projeto"),
    ("Presidente", "Presidente"),
    ("Membro", "Membro"),
    ("  ", None),
])
def test_papel_padronizado(bruto, padrao):
    from suap_rit.models import normalizar_papel

    assert normalizar_papel(bruto) == padrao
    ev = Evidencia(id="x", fonte="t", tipo=TipoEvidencia.PORTARIA, titulo="P", papel=bruto)
    assert ev.papel == padrao
