"""E2 — montagem do PDF de anexo por tópico."""

from datetime import date, datetime

from fpdf import FPDF
from pypdf import PdfReader

from suap_rit import anexos
from suap_rit.models import Evidencia, ItemAcervo, Manifest, Semestre, TipoEvidencia, Topico


def _pdf(caminho, paginas=1):
    pdf = FPDF()
    for i in range(paginas):
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(0, 10, f"doc {caminho.stem} p{i + 1}")
    pdf.output(str(caminho))


def test_montar_topico_agrupa_documento_coletivo_e_ordena(tmp_path, monkeypatch):
    monkeypatch.setenv("SUAP_RIT_HOME", str(tmp_path))
    (tmp_path / "_cache").mkdir()
    _pdf(tmp_path / "_cache" / "estagios.pdf", paginas=2)
    _pdf(tmp_path / "_cache" / "banca.pdf")
    evs = {
        "e1": Evidencia(id="e1", fonte="t", tipo=TipoEvidencia.ESTAGIO, titulo="Estágio A", inicio=date(2025, 3, 1)),
        "e2": Evidencia(id="e2", fonte="t", tipo=TipoEvidencia.ESTAGIO, titulo="Estágio B", inicio=date(2025, 4, 1)),
        "b": Evidencia(id="b", fonte="t", tipo=TipoEvidencia.BANCA, titulo="Banca X", papel="Presidente",
                       data_evento=date(2025, 2, 10)),
    }
    manifest = Manifest(
        semestre=Semestre(ano=2025, periodo=1), gerado_em=datetime.now(), evidencias=evs,
        itens=[ItemAcervo(evidencia_id="e1", topicos=[Topico.ORIENTACAO_ALUNOS], motivo="", arquivo="_cache/estagios.pdf"),
               ItemAcervo(evidencia_id="e2", topicos=[Topico.ORIENTACAO_ALUNOS], motivo="", arquivo="_cache/estagios.pdf"),
               ItemAcervo(evidencia_id="b", topicos=[Topico.ORIENTACAO_ALUNOS], motivo="", arquivo="_cache/banca.pdf")],
    )
    docs = anexos.documentos_do_topico(manifest, Topico.ORIENTACAO_ALUNOS)
    assert [d.titulo for d in docs] == ["Banca X", "Declaração de orientação de estágios (2025)"]
    assert docs[1].itens == ["Estágio A", "Estágio B"]

    anexo, pendencias = anexos.montar_topico(manifest, Topico.ORIENTACAO_ALUNOS, "Fulana")
    assert not pendencias and anexo.documentos == 2
    leitor = PdfReader(tmp_path / anexo.arquivo)
    assert len(leitor.pages) == anexo.paginas == 1 + 1 + 2  # capa + banca + estágios
    capa = leitor.pages[0].extract_text()
    assert "pág. 2" in capa and "pág. 3" in capa and "Comprova 2 itens" in capa


def test_topico_sem_comprovante_nao_gera_anexo(tmp_path, monkeypatch):
    monkeypatch.setenv("SUAP_RIT_HOME", str(tmp_path))
    manifest = Manifest(semestre=Semestre(ano=2025, periodo=1), gerado_em=datetime.now())
    assert anexos.montar_topico(manifest, Topico.GESTAO, "Fulana") == (None, [])
