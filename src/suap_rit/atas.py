"""E6 — atas/convocações encontradas no e-mail pelo conector do host (D41, D43).

O host (Claude, Codex, Gemini…) busca no e-mail com a própria integração e nos
entrega os dados. Guardamos em `AAAA.P/atas.json` + PDF, e a coleta reaplica
as atas registradas a cada nova execução.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import date

from fpdf import FPDF

from suap_rit import acervo, config
from suap_rit.anexos import _latin1
from suap_rit.html import parse_data
from suap_rit.models import Evidencia, ItemAcervo, Manifest, Pendencia, TipoEvidencia


def _arquivo(codigo: str):
    return acervo.pasta_semestre(codigo) / "atas.json"


def listar(codigo: str) -> list[dict]:
    origem = _arquivo(codigo)
    return json.loads(origem.read_text(encoding="utf-8")) if origem.exists() else []


def _pdf_registro(assunto: str, data: str, remetente: str, texto: str) -> bytes:
    """Sem o anexo original: registro do e-mail (vale como comprovante, preferir o assinado — D9)."""
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.multi_cell(0, 7, _latin1("Registro de e-mail (ata/convocação)"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for rotulo, valor in (("Assunto", assunto), ("Data", data), ("Remetente", remetente)):
        pdf.multi_cell(0, 5, _latin1(f"{rotulo}: {valor}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5, _latin1(texto or "(sem corpo de texto)"), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def registrar(codigo: str, assunto: str, data: str, remetente: str, id_mensagem: str, texto: str,
              anexo_base64: str | None = None, anexo_nome: str | None = None) -> dict:
    """Guarda a ata e o PDF (anexo original, se veio; senão, registro do e-mail)."""
    ident = hashlib.sha1((id_mensagem or f"{assunto}|{data}|{remetente}").encode()).hexdigest()[:12]
    pasta = acervo.pasta_semestre(codigo) / "atas"
    pasta.mkdir(parents=True, exist_ok=True)
    original = False
    if anexo_base64:
        conteudo = base64.b64decode(anexo_base64)
        if not conteudo.startswith(b"%PDF"):
            raise ValueError("o anexo enviado não é um PDF")
        original = True
    else:
        conteudo = _pdf_registro(assunto, data, remetente, texto)
    destino = pasta / f"ata-{ident}.pdf"
    destino.write_bytes(conteudo)
    ata = {"id": ident, "assunto": assunto, "data": data, "remetente": remetente, "id_mensagem": id_mensagem,
           "texto": (texto or "")[:4000], "anexo_original": original, "anexo_nome": anexo_nome,
           "arquivo": str(destino.relative_to(config.home()))}
    atas = [a for a in listar(codigo) if a["id"] != ident] + [ata]
    _arquivo(codigo).write_text(json.dumps(atas, ensure_ascii=False, indent=2), encoding="utf-8")
    return ata


def evidencia(ata: dict) -> Evidencia:
    return Evidencia(
        id=f"email:ata:{ata['id']}",
        fonte="email_host",
        tipo=TipoEvidencia.ATA,
        titulo=ata["assunto"],
        descricao=f"E-mail de {ata['remetente']}",
        data_evento=parse_data(ata["data"]) or date.today(),
        extras={"id_mensagem": ata.get("id_mensagem") or "", "texto": ata.get("texto", "")[:600],
                "anexo_original": str(ata["anexo_original"])},
    )


def aplicar(manifest: Manifest) -> None:
    """Inclui as atas registradas no manifest (idempotente)."""
    from suap_rit.classificar import classificar

    codigo = manifest.semestre.codigo
    for ata in listar(codigo):
        ev = evidencia(ata)
        if ev.id in manifest.evidencias:
            continue
        cls = classificar(ev)
        manifest.evidencias[ev.id] = ev
        manifest.itens.append(ItemAcervo(evidencia_id=ev.id, topicos=cls.topicos, motivo=cls.motivo,
                                         arquivo=ata["arquivo"]))
        if not ata["anexo_original"]:
            nome = f" ('{ata['anexo_nome']}')" if ata.get("anexo_nome") else ""
            manifest.pendencias.append(Pendencia(
                tipo="ata_sem_anexo", evidencia_id=ev.id,
                mensagem=f"Ata '{ata['assunto']}' registrada pelo corpo do e-mail; o PDF original{nome} "
                         f"não veio. Baixe-o e coloque na pasta de entrada, se houver versão assinada."))
