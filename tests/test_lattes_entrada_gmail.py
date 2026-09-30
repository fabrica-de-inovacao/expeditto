"""E7 Lattes (lacunas), E8 pasta de entrada e D42 backup Gmail (API simulada)."""

import base64

from datetime import date, datetime

import httpx
import pytest

from expeditto import acervo, entrada, gmail, lattes
from expeditto.models import Evidencia, Manifest, Semestre, TipoEvidencia, Topico


def _acc(secao, subsecao, linhas):
    trs = "".join(f"<tr><td>{i}</td><td>{t}</td></tr>" for i, t in enumerate(linhas, 1))
    return (f'<h4>{secao}</h4><div class="accordion"><div class="accordion-item"><h2>{subsecao}</h2>'
            f'<div class="accordion-body"><table>{trs}</table></div></div></div>')


LATTES = "<html><body>" + _acc("Produções", "Capítulos de livros publicados", [
    "SILVA, F. . Robótica educativa no ensino médio. In: Livro X. Editora, 2025.",
    "SILVA, F. . Outro capítulo antigo sobre redes. In: Livro Y. Editora, 2023.",
]) + _acc("Orientações e Supervisões em Andamento", "Iniciação Científica", [
    "Aluno A. Mulheres na tecnologia: análise cienciométrica da produção. Início: 2025. Iniciação Científica",
]) + _acc("Participação em Bancas de Trabalhos de Conclusão", "Graduação", [
    "SILVA, F. Participação em banca de Aluno B. Sistema de gestão de chamados web. 2025. TCC",
]) + "</body></html>"


def test_lattes_parse_e_lacunas():
    itens = lattes.parse(LATTES)
    assert [(i.categoria, i.ano, i.andamento) for i in itens] == [
        ("capítulo de livro", 2025, False), ("capítulo de livro", 2023, False),
        ("orientação em andamento", 2025, True), ("participação em banca", 2025, False)]
    ev = Evidencia(id="b", fonte="t", tipo=TipoEvidencia.BANCA, titulo="Sistema de gestão de chamados web")
    m = Manifest(semestre=Semestre(ano=2025, periodo=1), gerado_em=datetime.now(), evidencias={"b": ev})
    pend = lattes.lacunas(m, itens)
    textos = " | ".join(p.mensagem for p in pend)
    assert len(pend) == 2  # capítulo 2025 + orientação IC; banca coberta; capítulo 2023 fora do ano
    assert "Robótica educativa" in textos and "cienciométrica" in textos and "chamados" not in textos


def test_pasta_de_entrada(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPEDITTO_HOME", str(tmp_path))
    m = Manifest(semestre=Semestre(ano=2025, periodo=1, inicio=date(2025, 2, 3)), gerado_em=datetime.now())
    raiz = entrada.pasta("2025.1")
    (raiz / "pesquisa" / "artigo_publicado.pdf").write_bytes(b"%PDF-1.4 x")
    (raiz / "gestao" / "ata.png").write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="))
    (raiz / "solto.pdf").write_bytes(b"%PDF-1.4 y")
    entrada.aplicar(m)
    topicos = sorted((i.topicos[0].value, i.arquivo.endswith(".pdf")) for i in m.itens)
    assert topicos == [("gestao", True), ("pesquisa", True)]
    assert [p.tipo for p in m.pendencias] == ["entrada_sem_topico"]
    entrada.aplicar(m)
    assert len(m.itens) == 2  # idempotente
    entrada.classificar("2025.1", "solto.pdf", "extensao")
    entrada.aplicar(m)
    assert len(m.itens) == 3 and not m.pendencias


def _gmail_api(pdf_bytes):
    msg = {"id": "m1", "snippet": "Segue a ata da reunião do NDE",
           "payload": {"headers": [{"name": "Subject", "value": "Ata NDE março"},
                                   {"name": "From", "value": "coord@ifma.edu.br"},
                                   {"name": "Date", "value": "Wed, 12 Mar 2025 10:00:00 -0300"}],
                       "parts": [{"mimeType": "text/plain",
                                  "body": {"data": base64.urlsafe_b64encode("Pauta: PPC".encode()).decode()}},
                                 {"filename": "ata.pdf", "mimeType": "application/pdf",
                                  "body": {"attachmentId": "a1"}}]}}

    def handler(req: httpx.Request):
        assert req.headers["Authorization"] == "Bearer tok"
        if req.url.path.endswith("/messages"):
            assert "after:2025/01/19" in req.url.params["q"]
            return httpx.Response(200, json={"messages": [{"id": "m1"}]})
        if req.url.path.endswith("/attachments/a1"):
            return httpx.Response(200, json={"data": base64.urlsafe_b64encode(pdf_bytes).decode().rstrip("=")})
        return httpx.Response(200, json=msg)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_gmail_buscar_e_registrar(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPEDITTO_HOME", str(tmp_path))
    monkeypatch.setattr(gmail, "contas", lambda: ["prof@ifma.edu.br"])
    monkeypatch.setattr(gmail, "_token", lambda conta: "tok")
    sem = Semestre(ano=2025, periodo=1, inicio=date(2025, 2, 3), fim=date(2025, 6, 26))
    cliente = _gmail_api(b"%PDF-1.4 ata assinada")
    [c] = gmail.buscar(sem, cliente)
    assert c.assunto == "Ata NDE março" and c.anexos_pdf == ["ata.pdf"]
    [ata] = gmail.registrar("2025.1", [1], cliente)
    assert ata["anexo_original"] and ata["data"] == "2025-03-12" and "PPC" in ata["texto"]


@pytest.mark.parametrize("texto,titulo", [
    ("SOUZA, Â. C. ; SILVA, F. . Panorama de mulheres em games. In: Anais X, 2025.",
     "Panorama de mulheres em games"),
    ("Aluno C. Mulheres na Tecnologia no Brasil. Início: 2025. Iniciação Científica", "Mulheres na Tecnologia no Brasil"),
])
def test_titulo_sem_autores(texto, titulo):
    assert lattes.titulo_do_item(texto) == titulo


@pytest.mark.parametrize("texto,titulo", [
    ("COSTA, E. ; SILVA, F. . Participação em banca de Fulana Souza. Sistema de chamados web. 2025. TCC",
     "Sistema de chamados web"),
    ("SILVA, F; COSTA, A; PEREIRA, G. V.; Meninas em Rede: Desafio de Programação. 2025.",
     "Meninas em Rede: Desafio de Programação"),
])
def test_titulos_de_banca_e_evento(texto, titulo):
    assert lattes.titulo_do_item(texto) == titulo


def test_lacuna_ignora_item_ja_registrado_em_outro_semestre():
    itens = [lattes.ItemLattes("participação em banca", Topico.ORIENTACAO_ALUNOS,
                               "X . Participação em banca de A. Sistema de gestão de chamados web. 2025.", 2025, False)]
    m = Manifest(semestre=Semestre(ano=2025, periodo=2), gerado_em=datetime.now())
    de_2025_1 = Evidencia(id="b", fonte="t", tipo=TipoEvidencia.BANCA, titulo="Sistema de gestão de chamados web")
    assert lattes.lacunas(m, itens) and not lattes.lacunas(m, itens, [de_2025_1])


@pytest.mark.parametrize("bruto,limpo", [
    ("Contos em jogo: a criação de Grandma?s Tales (País: Brasil)",
     "Contos em jogo: a criação de Grandma's Tales"),
    ("ESTUDO DO APLICATIVO ¿EXEMPLÂNDIA¿ EM SALA DE AULA", "ESTUDO DO APLICATIVO “EXEMPLÂNDIA” EM SALA DE AULA"),
    ("Por que agora? Um estudo", "Por que agora? Um estudo"),
])
def test_limpar_titulo_lattes(bruto, limpo):
    assert lattes.limpar_titulo(bruto) == limpo
