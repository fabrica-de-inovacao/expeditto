"""Links do SUAP, pendências explicadas, publicações do Lattes, guia para agentes e progresso no chat."""

import asyncio
import json
import time
from datetime import date, datetime

import httpx
import pytest
import respx

from expeditto import acervo, conhecimento, config, explicacoes, guia, links, publicacoes, roteiro, tarefas
from expeditto.models import (Evidencia, EstadoPlano, ItemAcervo, Manifest, Pendencia, PlanoSemestre, Semestre,
                              TipoEvidencia, Topico)

SEMESTRE = Semestre(ano=2025, periodo=2, inicio=date(2025, 8, 4), fim=date(2025, 12, 17))


@pytest.fixture
def casa(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPEDITTO_HOME", str(tmp_path))
    return tmp_path


def _manifest(casa):
    pdf = casa / "_cache" / "decl.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4")
    ev = Evidencia(id="d1", fonte="t", tipo=TipoEvidencia.DIARIO, titulo="Programação Web II",
                   url_pagina="/edu/meu_diario/77/1/", url_comprovante="/edu/declaracaodocencia_pdf/5/2025/")
    return Manifest(semestre=SEMESTRE, gerado_em=datetime.now(), evidencias={"d1": ev},
                    itens=[ItemAcervo(evidencia_id="d1", topicos=[Topico.APOIO_ENSINO], motivo="",
                                      arquivo="_cache/decl.pdf")],
                    plano=PlanoSemestre(semestre="2025.2", plano_id=1, estado=EstadoPlano.RIT_A_PREENCHER),
                    pendencias=[
                        Pendencia(tipo="diario_incompleto", evidencia_id="d1",
                                  mensagem="Programação Web II: 8% da carga horária ministrada registrada no SUAP "
                                           "(atribuído 1%). Completar o registro de aulas antes de enviar o RIT."),
                        Pendencia(tipo="lattes_sem_comprovante",
                                  mensagem="Lattes (capítulo de livro, 2025): Robótica educativa no ensino médio — "
                                           "sem comprovante no acervo."),
                    ])


# -- links -----------------------------------------------------------------------------------
def test_links_de_evidencia_e_pendencia(casa):
    m = _manifest(casa)
    lk = links.de_pendencia(m, m.pendencias[0])
    assert lk["suap"] == config.BASE_URL + "/edu/meu_diario/77/1/"
    assert lk["comprovante"].endswith("/edu/declaracaodocencia_pdf/5/2025/")
    assert lk["arquivo"].startswith("file:")
    assert "[Ver no SUAP](" in links.markdown(lk)


def test_so_abre_links_do_docente(casa):
    assert links.permitido(config.BASE_URL + "/edu/meu_diario/1/")
    assert links.permitido("https://doi.org/10.1000/xyz")
    assert links.permitido((casa / "2025.2" / "a.pdf").as_uri())
    assert not links.permitido("https://site-qualquer.example/phishing")
    assert not links.permitido("file:///C:/Windows/System32/cmd.exe")


# -- explicações -----------------------------------------------------------------------------
def test_pendencias_antigas_ganham_detalhes_e_explicacao(casa):
    m = _manifest(casa)
    acervo.salvar_manifest(m)
    grupos = {g["tipo"]: g for g in roteiro.pendencias_agrupadas(m)}
    diario = grupos["diario_incompleto"]
    assert diario["titulo"] == "Diário com aulas faltando no SUAP" and diario["o_que_e"] and diario["dica"]
    assert [o["decisao"] for o in diario["opcoes"]] == ["manter", "justificar"]
    item = diario["itens"][0]
    assert item["resumo"] == "Programação Web II: 8% das aulas registradas"  # sem cortar no meio
    assert "Menos da metade" in item["sugestao"] and "suap" in item["links"]
    lattes = grupos["lattes_sem_comprovante"]["itens"][0]
    assert lattes["resumo"].startswith("Robótica educativa no ensino médio")


# -- publicações do Lattes -------------------------------------------------------------------------
def test_doi_datas_e_semestre():
    assert publicacoes.extrair_doi("SILVA, F. Título. Anais, 2025. DOI: 10.5753/wei.2025.1234.") == "10.5753/wei.2025.1234"
    assert publicacoes._data_crossref({"issued": {"date-parts": [[2025]]},
                                       "published-online": {"date-parts": [[2025, 10, 3]]}}) == "2025-10-03"
    assert publicacoes.semestre_da_data("2025-10-03", SEMESTRE) == "2025.2"
    assert publicacoes.semestre_da_data("2025-03-10", SEMESTRE) == "2025.1"
    assert publicacoes.semestre_da_data("2025-07-20", SEMESTRE) == "2025.1"  # férias antes do início de 2025.2
    assert publicacoes.semestre_da_data("2026-01-15", SEMESTRE) == "2026.1"
    assert publicacoes.semestre_da_data("2025", SEMESTRE) is None
    assert publicacoes.data_legivel("2025-10") == "out/2025"


@respx.mock
def test_busca_por_titulo_crossref_e_cache(casa):
    rota = respx.get("https://api.crossref.org/works").mock(return_value=httpx.Response(200, json={"message": {"items": [
        {"title": ["Robotica educativa no ensino medio"], "type": "book-chapter", "container-title": ["Livro X"],
         "published-print": {"date-parts": [[2025, 9]]}, "DOI": "10.1000/cap"},
        {"title": ["Outra coisa bem diferente"], "type": "journal-article", "DOI": "10.1000/outra"}]}}))
    achada = publicacoes.buscar("Robótica educativa no ensino médio", 2025)
    assert achada.tipo == "capítulo de livro" and achada.data == "2025-09" and achada.doi == "10.1000/cap"
    publicacoes.buscar("Robótica educativa no ensino médio", 2025)
    assert rota.call_count == 1  # segunda vez veio do cache


@respx.mock
def test_sem_correspondencia_segura_cai_no_openalex_e_depois_desiste(casa):
    respx.get("https://api.crossref.org/works").mock(return_value=httpx.Response(200, json={"message": {"items": [
        {"title": ["Um título que não tem nada a ver"], "type": "journal-article"}]}}))
    respx.get("https://api.openalex.org/works").mock(return_value=httpx.Response(200, json={"results": [
        {"title": "Jogos educativos no ensino de lógica", "type": "article", "publication_date": "2025-11-20",
         "doi": "https://doi.org/10.1000/jogos", "primary_location": {"source": {"display_name": "Anais Y"}}}]}))
    achada = publicacoes.buscar("Jogos educativos no ensino de lógica", 2025)
    assert achada.fonte == "OpenAlex" and achada.data == "2025-11-20" and achada.veiculo == "Anais Y"
    assert publicacoes.buscar("Título inexistente", 2025) is None


def test_enriquecer_sugere_o_semestre(casa, monkeypatch):
    pub = publicacoes.Publicacao("Robótica educativa", "capítulo de livro", "Livro X", "2025-03", "10.1000/cap", "Crossref")
    monkeypatch.setattr(publicacoes, "buscar", lambda *a, **k: pub)
    p = explicacoes.completar_detalhes(Pendencia(
        tipo="lattes_sem_comprovante", mensagem="Lattes (capítulo de livro, 2025): Robótica educativa — sem comprovante"))
    assert publicacoes.enriquecer([p], SEMESTRE) == 1
    assert p.detalhes["semestre_provavel"] == "2025.1" and p.links["doi"] == "https://doi.org/10.1000/cap"
    assert "2025.1" in explicacoes.sugestao_item(p) and "mar/2025" in explicacoes.resumo_item(p)


# -- guia para os agentes ------------------------------------------------------------------------
def test_guia_e_skill(tmp_path):
    assert "preparar_rit" in guia.ler("fluxo") and "Assunto 'xyz' não existe" in guia.ler("xyz")
    destino = conhecimento.instalar_skill(tmp_path / "skills")
    skill = (destino / "SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith("---\nname: expeditto-rit\ndescription: ")
    assert (destino / "references" / "pendencias.md").exists()
    conhecimento.remover_skill(tmp_path / "skills")
    assert not destino.exists()


def test_skill_de_outra_pessoa_nao_e_sobrescrita(tmp_path):
    alheia = tmp_path / "skills" / "expeditto-rit"
    alheia.mkdir(parents=True)
    (alheia / "SKILL.md").write_text("minha skill", encoding="utf-8")
    with pytest.raises(RuntimeError):
        conhecimento.instalar_skill(tmp_path / "skills")
    conhecimento.remover_skill(tmp_path / "skills")
    assert (alheia / "SKILL.md").read_text(encoding="utf-8") == "minha skill"


def test_extensao_do_gemini(tmp_path):
    destino = conhecimento.instalar_extensao_gemini(tmp_path)
    assert json.loads((destino / "gemini-extension.json").read_text(encoding="utf-8"))["contextFileName"] == "GEMINI.md"
    assert "Os 7 tópicos do RIT" in (destino / "GEMINI.md").read_text(encoding="utf-8")


# -- MCP --------------------------------------------------------------------------------------
def _texto(resultado):
    return json.loads(resultado.content[0].text)


def test_aguardar_tarefa_volta_ao_mudar_de_etapa(monkeypatch):
    from expeditto import mcp_server

    def alvo(progresso):
        progresso("plano", etapa="plano")
        time.sleep(0.6)
        progresso("calendário", etapa="calendario")
        time.sleep(5)
        return True

    tarefa = mcp_server._tarefas.iniciar("coleta", "Coleta teste", alvo)
    time.sleep(0.1)
    inicio = time.monotonic()
    resposta = _texto(asyncio.run(mcp_server.servidor.call_tool("aguardar_tarefa", {"tarefa_id": tarefa.id})))
    assert time.monotonic() - inicio < 3  # não espera os 10 s: a etapa mudou
    assert resposta["estado"] == "executando" and resposta["proximo"]["ferramenta"] == "aguardar_tarefa"
    assert "Calendário" in resposta["progresso"]


def test_detalhar_pendencia_e_guia_pelo_mcp(casa):
    from expeditto import mcp_server

    acervo.salvar_manifest(_manifest(casa))
    d = _texto(asyncio.run(mcp_server.servidor.call_tool("detalhar_pendencia", {"semestre": "2025.2", "numero": 1})))
    assert d["titulo"].startswith("Diário") and "[Ver no SUAP](" in d["links_markdown"]
    recusa = _texto(asyncio.run(mcp_server.servidor.call_tool("abrir_no_navegador", {"url": "https://example.com/x"})))
    assert recusa["aberto"] is False
