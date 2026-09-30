"""E2 — um PDF por tópico do RIT: capa + índice + comprovantes, até 10 MB (D8).

O formulário do RIT aceita UM arquivo por tópico; juntamos os comprovantes do
acervo numa ordem cronológica, com índice que aponta a página de cada documento.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pikepdf
from fpdf import FPDF
from pypdf import PdfReader, PdfWriter

from suap_rit import acervo, config
from suap_rit.models import AnexoTopico, Evidencia, Manifest, Pendencia, TipoEvidencia, Topico

LIMITE_BYTES = 10 * 1024 * 1024  # "Tamanho máximo permitido: 10,0 MB."

# Documentos anuais que comprovam vários itens de uma vez.
_DOCUMENTO_COLETIVO = {
    TipoEvidencia.DIARIO: "Declaração de docência",
    TipoEvidencia.ESTAGIO: "Declaração de orientação de estágios",
}


@dataclass
class Documento:
    arquivo: Path
    titulo: str
    detalhe: str
    data: date | None
    itens: list[str] = field(default_factory=list)
    pagina_inicial: int = 0


def _latin1(texto: str) -> str:
    """As fontes padrão do PDF (Helvetica) só cobrem latin-1."""
    trocas = {"–": "-", "—": "-", "“": '"', "”": '"', "’": "'", "‘": "'", "…": "...", "•": "-", "→": "->"}
    for de, para in trocas.items():
        texto = texto.replace(de, para)
    return texto.encode("latin-1", "replace").decode("latin-1")


def _data(ev: Evidencia) -> date | None:
    return ev.data_evento or ev.inicio


def _periodo(ev: Evidencia) -> str:
    if ev.data_evento:
        return ev.data_evento.strftime("%d/%m/%Y")
    if ev.inicio and ev.fim:
        return f"{ev.inicio.strftime('%d/%m/%Y')} a {ev.fim.strftime('%d/%m/%Y')}"
    if ev.inicio:
        return f"desde {ev.inicio.strftime('%d/%m/%Y')} (em vigor)"
    return ""


def documentos_do_topico(manifest: Manifest, topico: Topico) -> list[Documento]:
    """Comprovantes (PDFs distintos) do tópico, em ordem cronológica."""
    por_arquivo: dict[str, Documento] = {}
    for item in manifest.itens:
        if topico not in item.topicos or not item.arquivo:
            continue
        ev = manifest.evidencias[item.evidencia_id]
        doc = por_arquivo.get(item.arquivo)
        if doc is None:
            coletivo = _DOCUMENTO_COLETIVO.get(ev.tipo)
            titulo = f"{coletivo} ({manifest.semestre.ano})" if coletivo else ev.titulo
            detalhe = "" if coletivo else " · ".join(x for x in (ev.papel, _periodo(ev)) if x)
            doc = por_arquivo[item.arquivo] = Documento(config.home() / item.arquivo, titulo, detalhe, _data(ev))
        doc.itens.append(ev.titulo)
        if _data(ev) and (doc.data is None or _data(ev) < doc.data):
            doc.data = _data(ev)
    return sorted(por_arquivo.values(), key=lambda d: (d.data or date.max, d.titulo))


def _capa(manifest: Manifest, topico: Topico, docs: list[Documento], nome: str, offset: int) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(0, 8, _latin1(f"Relatório Individual de Trabalho - {manifest.semestre.codigo}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 12)
    pdf.multi_cell(0, 7, _latin1(topico.rotulo), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, _latin1(f"Docente: {nome}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, _latin1(f"Índice de comprovantes ({len(docs)} documentos)"), new_x="LMARGIN", new_y="NEXT")
    for i, doc in enumerate(docs, 1):
        pdf.set_font("Helvetica", "B", 9)
        pdf.multi_cell(0, 5, _latin1(f"{i}. {doc.titulo}  ....  pág. {doc.pagina_inicial + offset}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 8)
        if doc.detalhe:
            pdf.multi_cell(0, 4, _latin1(f"   {doc.detalhe}"), new_x="LMARGIN", new_y="NEXT")
        if len(doc.itens) > 1:
            listados = "; ".join(doc.itens[:6]) + (f"; e mais {len(doc.itens) - 6}" if len(doc.itens) > 6 else "")
            pdf.multi_cell(0, 4, _latin1(f"   Comprova {len(doc.itens)} itens: {listados}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
    return bytes(pdf.output())


def _paginas(pdf: bytes) -> int:
    return len(PdfReader(io.BytesIO(pdf)).pages)


def montar_topico(manifest: Manifest, topico: Topico, nome: str) -> tuple[AnexoTopico | None, list[Pendencia]]:
    docs = documentos_do_topico(manifest, topico)
    if not docs:
        return None, []
    pendencias: list[Pendencia] = []
    paginas_docs = []
    for doc in docs:
        paginas_docs.append(len(PdfReader(doc.arquivo).pages))
    # A capa desloca a numeração: calcula as páginas iniciais relativas e depois soma a capa.
    acumulado = 1
    for doc, n in zip(docs, paginas_docs):
        doc.pagina_inicial = acumulado
        acumulado += n
    paginas_capa = _paginas(_capa(manifest, topico, docs, nome, 0))
    capa = _capa(manifest, topico, docs, nome, paginas_capa)

    escritor = PdfWriter()
    escritor.append(io.BytesIO(capa))
    for doc in docs:
        escritor.append(str(doc.arquivo), outline_item=_latin1(doc.titulo)[:80])
    destino = acervo.pasta_semestre(manifest.semestre.codigo) / "anexos" / f"{topico.pasta}.pdf"
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("wb") as f:
        escritor.write(f)

    comprimido = False
    if destino.stat().st_size > LIMITE_BYTES:
        comprimido = True
        with pikepdf.open(destino, allow_overwriting_input=True) as pdf:
            pdf.save(destino, compress_streams=True, recompress_flate=True,
                     object_stream_mode=pikepdf.ObjectStreamMode.generate)
    tamanho = destino.stat().st_size
    if tamanho > LIMITE_BYTES:
        maiores = sorted(zip(docs, (d.arquivo.stat().st_size for d in docs)), key=lambda x: -x[1])[:5]
        lista = "; ".join(f"{d.titulo} ({b // 1024} KB)" for d, b in maiores)
        pendencias.append(Pendencia(tipo="anexo_grande",
                                    mensagem=f"Anexo de '{topico.rotulo}' tem {tamanho / 1048576:.1f} MB "
                                             f"(limite 10 MB) mesmo comprimido. Maiores: {lista}."))
    return AnexoTopico(topico=topico, arquivo=str(destino.relative_to(config.home())), bytes=tamanho,
                       paginas=paginas_capa + sum(paginas_docs), documentos=len(docs),
                       comprimido=comprimido), pendencias


def montar(manifest: Manifest, nome: str) -> Manifest:
    from suap_rit import entrada, pendencias as decisoes

    entrada.aplicar(manifest)  # inclui o que o docente acabou de colocar na pasta de entrada
    decisoes.aplicar(manifest)
    manifest.anexos = {}
    manifest.pendencias = [p for p in manifest.pendencias if p.tipo != "anexo_grande"]
    for topico in Topico:
        anexo, pendencias = montar_topico(manifest, topico, nome)
        if anexo:
            manifest.anexos[topico.value] = anexo
        manifest.pendencias += pendencias
    acervo.salvar_manifest(manifest)
    return manifest
