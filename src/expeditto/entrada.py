"""E8 — comprovantes adicionados manualmente pelo docente (D11).

Estrutura: `AAAA.P/entrada/<topico>/arquivo.pdf` (topico = apoio_ensino, …, gestao;
aceita também o nome da pasta do acervo, ex. "05-pesquisa"). Arquivos soltos em
`entrada/` viram pendência para o docente dizer o tópico (`classificar`).
Imagens (jpg/png) são convertidas para PDF.
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import date
from pathlib import Path

from fpdf import FPDF

from expeditto import acervo, config
from expeditto.models import Evidencia, ItemAcervo, Manifest, Pendencia, TipoEvidencia, Topico

EXTENSOES = {".pdf", ".jpg", ".jpeg", ".png"}


def pasta(codigo: str) -> Path:
    destino = acervo.pasta_semestre(codigo) / "entrada"
    destino.mkdir(parents=True, exist_ok=True)
    for t in Topico:
        (destino / t.value).mkdir(exist_ok=True)
    return destino


def _topico_da_pasta(nome: str) -> Topico | None:
    for t in Topico:
        if nome in (t.value, t.pasta):
            return t
    return None


def _como_pdf(arquivo: Path) -> Path:
    if arquivo.suffix.lower() == ".pdf":
        return arquivo
    destino = config.cache_dir() / f"entrada-{hashlib.sha1(arquivo.read_bytes()).hexdigest()[:12]}.pdf"
    if not destino.exists():
        pdf = FPDF(format="A4")
        pdf.add_page()
        pdf.image(str(arquivo), x=10, y=10, w=190)
        pdf.output(str(destino))
    return destino


def aplicar(manifest: Manifest) -> None:
    """Inclui os arquivos da pasta de entrada no manifest (idempotente)."""
    raiz = pasta(manifest.semestre.codigo)
    manifest.pendencias = [p for p in manifest.pendencias if p.tipo != "entrada_sem_topico"]
    for arquivo in sorted(p for p in raiz.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSOES):
        topico = _topico_da_pasta(arquivo.parent.name) if arquivo.parent != raiz else None
        if topico is None:
            manifest.pendencias.append(Pendencia(
                tipo="entrada_sem_topico", mensagem=f"Arquivo '{arquivo.name}' na pasta de entrada sem tópico. "
                                                    f"Informe o tópico para incluí-lo no RIT."))
            continue
        ident = hashlib.sha1(arquivo.read_bytes()).hexdigest()[:12]
        ev_id = f"manual:{topico.value}:{ident}"
        if ev_id in manifest.evidencias:
            continue
        pdf = _como_pdf(arquivo)
        manifest.evidencias[ev_id] = Evidencia(
            id=ev_id, fonte="manual", tipo=TipoEvidencia.MANUAL, titulo=arquivo.stem.replace("_", " "),
            descricao="Comprovante adicionado pelo docente", data_evento=manifest.semestre.inicio or date.today(),
            extras={"arquivo_original": arquivo.name})
        manifest.itens.append(ItemAcervo(evidencia_id=ev_id, topicos=[topico], motivo="adicionado pelo docente (E8)",
                                         arquivo=str(pdf.relative_to(config.home()))))


def classificar(codigo: str, nome_arquivo: str, topico: str) -> Path:
    """Move um arquivo solto de `entrada/` para a subpasta do tópico."""
    raiz = pasta(codigo)
    origem = raiz / nome_arquivo
    if not origem.is_file():
        raise FileNotFoundError(f"'{nome_arquivo}' não está na raiz da pasta de entrada")
    destino = raiz / Topico(topico).value / origem.name
    shutil.move(origem, destino)
    return destino
