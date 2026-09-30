"""Parsers sobre HTML sintético que reproduz a estrutura das telas do SUAP IFMA."""

from datetime import date

from suap_rit import html as h
from suap_rit.models import EstadoPlano, Perfil, TipoEvidencia
from suap_rit.suap import ensino, perfil, planos, servidor


def _acc(titulo: str, corpo: str) -> str:
    return (f'<div class="accordion-item"><h2 class="accordion-header"><button>{titulo}</button></h2>'
            f'<div class="accordion-collapse"><div class="accordion-body">{corpo}</div></div></div>')


def _dl(pares: dict[str, str]) -> str:
    itens = "".join(f'<div class="list-item"><dt>{k}</dt><dd>{v}</dd></div>' for k, v in pares.items())
    return f'<dl class="definition-list flex">{itens}</dl>'


def _tabela(cabecalhos, linhas, caption="") -> str:
    th = "".join(f"<th>{c}</th>" for c in cabecalhos)
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in linha) + "</tr>" for linha in linhas)
    cap = f"<caption>{caption}</caption>" if caption else ""
    return f"<table>{cap}<thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"


PLANO = "<html><body>" + (
    '<select name="ano-periodo"><option>2025.2</option><option value="2025.1">2025.1</option></select>'
    '<p>40,0 horas C.H. Total Semanal</p>'
    '<a href="/pit_rit_v2/criar_plano/999/">Criar</a>'
    '<a href="/pit_rit_v2/plano_atividade_docente_pdf/90001/">Imprimir</a>'
    '<a href="/pit_rit_v2/preencher_relatorio_individual_trabalho/90001/">Preencher</a>'
) + _acc("Dados da Avaliação", _dl({
    "Avaliador do Plano": "Chefia", "Plano Enviado": "Sim 16 de Setembro de 2026 às 09:34",
    "Plano Aprovado": "Sim 16 de Setembro de 2026 às 14:43", "Relatório Enviado": "Não",
    "Relatório Aprovado": "Não", "Relatório Publicado": "Não",
    "Histórico": "PIT - 16/09/2026 14:43:29 - Plano em conformidade. (Chefia - 1)",
}) + _tabela(["ATIVIDADE", "CH"], [["PESQUISA", "8 h"]])) + _acc("1. Atividades de Ensino",
    _tabela(["#", "Descrição"], [["1", "Preparação de aulas"], ["2", "Registro de informações"]],
            caption="PREPARAÇÃO, MANUTENÇÃO E APOIO AO ENSINO")
) + _acc("2. Atividades de Pesquisa", _tabela(["#", "Descrição"], [["1", "Coordenação de projeto"]])) \
    + "</body></html>"


def test_plano_estado_e_links():
    p = planos.parse_plano(PLANO, "2025.1")
    assert p.estado == EstadoPlano.RIT_A_PREENCHER
    assert p.plano_id == 90001
    assert p.links["preencher_relatorio"].endswith("/90001/")
    assert p.ch_total == "40,0"
    assert p.quadro_resumo["PESQUISA"] == "8 h"
    assert p.atividades_pit["PREPARAÇÃO, MANUTENÇÃO E APOIO AO ENSINO"] == [
        "Preparação de aulas", "Registro de informações"]
    assert p.atividades_pit["2. Atividades de Pesquisa"] == ["Coordenação de projeto"]
    assert p.historico[0].startswith("PIT - 16/09/2026")
    assert planos.listar_periodos(PLANO) == ["2025.2", "2025.1"]


def test_estado_publicado():
    html = PLANO.replace("<dd>Não</dd>", "<dd>Sim 1 de Março de 2026 às 10:00</dd>")
    assert planos.parse_plano(html, "2025.1").estado == EstadoPlano.RIT_PUBLICADO


def test_parse_data_formatos():
    assert h.parse_data("6 de Janeiro de 2025") == date(2025, 1, 6)
    assert h.parse_data("05/03/2024 17:00:00") == date(2024, 3, 5)
    assert h.parse_data("18.08.2026") == date(2026, 8, 18)
    assert h.parse_data("2025-02-03") == date(2025, 2, 3)
    assert h.parse_data("Sim 16 de Setembro de 2026 às 09:34") == date(2026, 9, 16)
    assert h.parse_data("-") is None


def test_perfil_allowlist_descarta_dados_sensiveis():
    pagina = "<html><body>" + _dl({
        "Nome usual": "Fulana", "E-mail institucional": "fulana@ifma.edu.br",
        "CPF": "000.000.000-00", "Conta corrente": "123", "Setor SUAP": "DEPX-XYZ (campus: CAMP-XYZ)",
        "Jornada Trabalho": "DEDICACAO EXCLUSIVA", "Participa do PGD": "Não",
    }) + '<a href="/cnpq/curriculo/9003/">Lattes</a></body></html>'
    p = perfil.parse_dados_gerais(pagina, "Fulana de Tal", "1234567", 999)
    dump = p.model_dump_json()
    assert "000.000.000-00" not in dump and "123" not in dump.replace("1234567", "")
    assert p.campus == "CAMP-XYZ" and p.participa_pgd is False
    assert p.lattes_suap == "/cnpq/curriculo/9003/"


def test_identificar_professor():
    pagina = ('<html><body><h2>Professor(a): Fulana de Tal (1234567)</h2>'
              '<a href="/pit_rit_v2/criar_plano/999/">x</a></body></html>')
    assert perfil.identificar(pagina) == ("Fulana de Tal", "1234567", 999)


def test_bancas_papel_e_data_da_defesa():
    pagina = "<html><body>" + _tabela(
        ["Ações", "Ano Período Letivo", "Tipo", "Título", "Aluno", "Nota", "Data da Apresentação", "Opções"],
        [['<a href="/edu/visualizar_projeto_final/9004/">Ver</a>', "2024.1", "Monografia", "Sistema X",
          "Aluno A", "900", "05/03/2024",
          '<a href="/edu/declaracao_participacao_projeto_final_pdf/9004/examinador_interno/">Declaração</a>']]
    ) + "</body></html>"
    [ev] = ensino.parse_bancas(pagina)
    assert ev.tipo == TipoEvidencia.BANCA
    assert ev.extras["papel"] == "examinador_interno"
    assert ev.data_evento == date(2024, 3, 5) and ev.semestre_letivo == "2024.1"
    assert ev.url_comprovante.endswith("/examinador_interno/")


def test_estagio_sem_colunas_de_data_usa_datas_do_texto():
    pagina = "<html><body>" + _tabela(
        ["Ações", "Aluno", "Concedente", "Datas sugeridas como limite para visitas trimestrais", "C.H. Final"],
        [['<a href="/estagios/aprendizagem/77/">Ver</a>', "Aluno B", "Empresa",
          "Módulo I: de 16 de Outubro de 2023 até 20 de Dezembro de 2023", "-"]]
    ) + "</body></html>"
    [ev] = ensino.parse_estagios(pagina)
    assert ev.id == "suap_professor:estagio:aprendizagem:77"
    assert (ev.inicio, ev.fim) == (date(2023, 10, 16), date(2023, 12, 20))


def test_projetos_dedup_entre_abas_e_comprovante():
    linha = ['<a href="/pesquisa/projeto/9006/">Ver</a>', "EDITAL PIBIC", "Projeto Y", "Concluído",
             '<a href="/pesquisa/emitir_certificado_pdf/1/">Cert</a>'
             '<a href="/pesquisa/emitir_declaracao_participacao_pdf/9005/">Decl</a>']
    tabela = _tabela(["Ações", "Edital", "Projeto", "Situação", "Opções"], [linha])
    evs = servidor.parse_projetos(f"<html><body>{tabela}{tabela}</body></html>")
    assert len(evs) == 1
    assert evs[0].tipo == TipoEvidencia.PROJETO_PESQUISA
    assert evs[0].url_comprovante == "/pesquisa/emitir_declaracao_participacao_pdf/9005/"


def test_datas_projeto():
    pagina = ("<html><body><table><tr><td>Início da Execução</td><td>15/08/2022</td></tr>"
              "<tr><td>Término da Execução</td><td>15/12/2022</td></tr></table></body></html>")
    assert servidor.datas_projeto(pagina) == (date(2022, 8, 15), date(2022, 12, 15))


def test_funcao_atual_desde():
    pagina = "<html><body>" + _tabela(
        ["Função", "Nível", "Atividade", "Setor SUAP", "Período"],
        [["FUNCAO COMISSIONADA DE COORD. CURSO", "0001", "2066 - COORDENADOR(A) DE CURSOS", "DEPX-XYZ",
          "Desde 05/04/2023"]]) + "</body></html>"
    [ev] = servidor.parse_funcoes(pagina)
    assert ev.titulo == "COORDENADOR(A) DE CURSOS"
    assert ev.inicio == date(2023, 4, 5) and ev.fim is None


def test_portaria_da_pasta_funcional():
    perfil_ = Perfil(matricula="1234567", nome="Fulana de Tal")
    linha = {
        "Ações": h.Celula("Visualizar", ["/documento_eletronico/visualizar_documento/900002/"]),
        "Tipo de Arquivo": h.Celula("Designação para compor comissões/conselhos/bancas"),
        "Nome": h.Celula("PORTARIA N° 123/2026 - DGP-XYZ"),
        "Inserido em": h.Celula("25 de Agosto de 2026 às 16:12"),
        "Descrição": h.Celula("Adicionar Descrição"),
    }
    texto = ("PORTARIA N° 123/2026 - DGP-XYZ, DE 20 DE AGOSTO DE 2026 RESOLVE: Art. 1º - A Comissão "
             "Organizadora fica composta: I - Presidente: Outro, SIAPE: 1 II - Membros: a) Fulana de Tal, "
             "SIAPE: 1234567 Art. 2º A Comissão terá vigência no período de 18.08.2026 a 18.11.2026.")
    ev = servidor.evidencia_portaria(linha, texto, perfil_)
    assert ev.id == "suap_pasta:portaria:900002"
    assert (ev.inicio, ev.fim) == (date(2026, 8, 18), date(2026, 11, 18))
    assert ev.papel == "Membro"
    assert ev.comprovante_assincrono
    assert ev.url_comprovante == "/documento_eletronico/imprimir_documento_pdf/900002/carta/"


# -- equipe de projetos e declarações de estágio ---------------------------------
def test_equipe_em_tabela_pesquisa():
    pagina = "<html><body>" + _tabela(
        ["Ações", "Membro", "Situação", "Categoria/Titulação", "Bolsista", "Coordenador", "Carga Horária", "Opções"],
        [["Ver", 'Nome: Fulana (<a href="/rh/servidor/1234567/">1234567</a>)', "Ativo", "DOCENTE", "Não", "Sim",
          "4 h/s", '<a href="/pesquisa/emitir_declaracao_orientacao_pdf/99/">Declaração de Orientação</a>'],
         ["Ver", 'Outro (<a href="/rh/servidor/1/">1</a>)', "Ativo", "DOCENTE", "Não", "Sub", "4 h/s", ""]]
    ) + "</body></html>"
    info = servidor.parse_equipe(pagina, "1234567")
    assert info == {"papel": "Coordenador(a)", "carga_horaria": "4 h/s",
                    "declaracao_orientacao": "/pesquisa/emitir_declaracao_orientacao_pdf/99/"}


def test_equipe_em_cartoes_extensao():
    pagina = ('<html><body><div class="general-box"><div class="primary-info">'
              '<span class="status status-info">Subcoordenador</span><span class="status">Voluntário</span>'
              '<h4 class="title">Fulana <a href="/rh/servidor/1234567/">1234567</a></h4>'
              '<dl><dt>Carga Horária Semanal:</dt><dd>5 horas/aula</dd><dt>Função:</dt><dd>Coordenador de Projeto</dd></dl>'
              '</div></div></body></html>')
    assert servidor.parse_equipe(pagina, "1234567") == {"papel": "Subcoordenador(a)", "carga_horaria": "5 horas/aula"}


def test_declaracoes_anuais_de_estagio():
    pagina = ('<html><body><a class="btn" href="#">Emitir Declaração de Orientação de Estágios</a>'
              '<a href="/edu/emitir_declaracao_de_orientacao_pdf/999/estagios/0/">Todos</a>'
              '<a href="/edu/emitir_declaracao_de_orientacao_pdf/999/estagios/2025/">2025</a>'
              '<a href="/edu/emitir_declaracao_de_orientacao_pdf/999/aprendizagens/2024/">2024</a></body></html>')
    decl = ensino.declaracoes_orientacao(pagina)
    assert decl == {"estagios": {"2025": "/edu/emitir_declaracao_de_orientacao_pdf/999/estagios/2025/"},
                    "aprendizagens": {"2024": "/edu/emitir_declaracao_de_orientacao_pdf/999/aprendizagens/2024/"}}
    ev = ensino.Evidencia(id="e", fonte="t", tipo=TipoEvidencia.ESTAGIO, titulo="E",
                          extras={"modalidade": "pratica_profissional"})
    ensino.anexar_declaracoes([ev], decl)
    assert ev.extras["declaracao_2025"].endswith("/estagios/2025/")


def test_declaracao_de_docencia_links_e_percentuais():
    pagina = ('<html><body><a class="btn" href="#">Emitir Declaração de Docência</a>'
              '<a href="/edu/declaracaodocencia_pdf/999/">Todos</a>'
              '<a href="/edu/declaracaodocencia_pdf/999/2025/">2025</a></body></html>')
    assert ensino.declaracoes_docencia(pagina) == {"2025": "/edu/declaracaodocencia_pdf/999/2025/"}
    texto = ("1 Atividade Curricular de Extensão I 2025/1 90 6 900101 \n(Semestral) 100% 38%\n"
             "6 Estágio Supervisionado 2025/1 360 0 900102 (Anual) 100% 100%")
    assert ensino.percentuais_docencia(texto) == {"900101": (100, 38), "900102": (100, 100)}
