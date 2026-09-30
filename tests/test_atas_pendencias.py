"""E6 atas por e-mail e E4 decisões/alterações."""

import base64
from datetime import date, datetime

import pytest

from suap_rit import acervo, atas, pendencias, textos
from suap_rit.models import Evidencia, ItemAcervo, Manifest, Pendencia, Semestre, TipoEvidencia, Topico


@pytest.fixture
def manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("SUAP_RIT_HOME", str(tmp_path))
    ev = Evidencia(id="p1", fonte="t", tipo=TipoEvidencia.PROJETO_PESQUISA, titulo="Projeto Inativo")
    m = Manifest(semestre=Semestre(ano=2025, periodo=1), gerado_em=datetime.now(), evidencias={"p1": ev},
                 itens=[ItemAcervo(evidencia_id="p1", topicos=[Topico.PESQUISA], motivo="")],
                 pendencias=[Pendencia(tipo="sem_comprovante", evidencia_id="p1", mensagem="sem comprovante"),
                             Pendencia(tipo="diario_incompleto", evidencia_id="d1", mensagem="38%")])
    acervo.salvar_manifest(m)
    return m


def test_ata_sem_anexo_gera_pdf_de_registro_e_pendencia(manifest):
    atas.registrar("2025.1", "Ata da reunião do NDE", "12/03/2025", "coord@ifma.edu.br", "msg-1", "Pauta: PPC")
    atas.aplicar(manifest)
    ev = manifest.evidencias["email:ata:" + atas.listar("2025.1")[0]["id"]]
    assert ev.data_evento == date(2025, 3, 12)
    item = next(i for i in manifest.itens if i.evidencia_id == ev.id)
    assert item.topicos == [Topico.REUNIOES] and item.arquivo.endswith(".pdf")
    assert any(p.tipo == "ata_sem_anexo" for p in manifest.pendencias)
    atas.aplicar(manifest)  # idempotente
    assert sum(1 for i in manifest.itens if i.evidencia_id == ev.id) == 1


def test_ata_com_anexo_pdf_original(manifest):
    pdf = base64.b64encode(b"%PDF-1.4 ata assinada").decode()
    ata = atas.registrar("2025.1", "Convocação - Colegiado", "2025-04-02", "x@ifma.edu.br", "msg-2", "", pdf, "ata.pdf")
    assert ata["anexo_original"]
    with pytest.raises(ValueError):
        atas.registrar("2025.1", "x", "2025-04-02", "x", "msg-3", "", base64.b64encode(b"nao-pdf").decode())


def test_decisoes_persistem_e_geram_alteracoes(manifest):
    pendencias.resolver(manifest, 1, "remover_item")
    assert not any(i.evidencia_id == "p1" for i in manifest.itens)
    with pytest.raises(ValueError):
        pendencias.resolver(manifest, 2, "justificar")  # sem justificativa do docente
    pendencias.resolver(manifest, 2, "justificar", "Diário dividido: a carga foi ministrada em 2025.2.")
    html = pendencias.gerar_alteracoes(manifest)
    assert "Diário dividido" in html and textos.carregar("2025.1", "alteracoes") == html

    # nova coleta: pendências recriadas sem decisão → decisões reaplicadas pela chave estável
    novo = Manifest(semestre=manifest.semestre, gerado_em=datetime.now(), evidencias=manifest.evidencias,
                    itens=[ItemAcervo(evidencia_id="p1", topicos=[Topico.PESQUISA], motivo="")],
                    pendencias=[Pendencia(tipo="sem_comprovante", evidencia_id="p1", mensagem="sem comprovante")])
    pendencias.aplicar(novo)
    assert novo.pendencias[0].resolucao == "remover_item" and not novo.itens
