"""Decisões do docente sobre pendências e o texto de "Alterações de Atividades" (E4, D6).

As decisões ficam em `AAAA.P/decisoes.json` (chave estável da pendência) e são
reaplicadas depois de cada coleta, para não perguntar de novo.
"""

from __future__ import annotations

import html
import json

from suap_rit import acervo, textos
from suap_rit.models import Manifest

DECISOES = ("manter", "remover_item", "justificar", "ignorar")


def _arquivo(codigo: str):
    return acervo.pasta_semestre(codigo) / "decisoes.json"


def _carregar(codigo: str) -> dict[str, dict]:
    origem = _arquivo(codigo)
    return json.loads(origem.read_text(encoding="utf-8")) if origem.exists() else {}


def resolver(manifest: Manifest, numero: int, decisao: str, justificativa: str | None = None) -> Manifest:
    """`numero` é a posição (1..N) na lista de pendências do manifest."""
    if decisao not in DECISOES:
        raise ValueError(f"decisão inválida: {decisao} (use {', '.join(DECISOES)})")
    if decisao == "justificar" and not (justificativa or "").strip():
        raise ValueError("'justificar' exige o texto da justificativa (escrito/confirmado pelo docente)")
    pendencia = manifest.pendencias[numero - 1]
    decisoes = _carregar(manifest.semestre.codigo)
    decisoes[pendencia.chave] = {"resolucao": decisao, "justificativa": justificativa}
    _arquivo(manifest.semestre.codigo).write_text(json.dumps(decisoes, ensure_ascii=False, indent=2),
                                                  encoding="utf-8")
    aplicar(manifest)
    acervo.salvar_manifest(manifest)
    return manifest


def aplicar(manifest: Manifest) -> None:
    decisoes = _carregar(manifest.semestre.codigo)
    remover = set()
    for p in manifest.pendencias:
        d = decisoes.get(p.chave)
        if d:
            p.resolucao, p.justificativa = d["resolucao"], d.get("justificativa")
            if p.resolucao == "remover_item" and p.evidencia_id:
                remover.add(p.evidencia_id)
    manifest.itens = [i for i in manifest.itens if i.evidencia_id not in remover]


def gerar_alteracoes(manifest: Manifest) -> str:
    """Texto de 'Alterações de Atividades' a partir das pendências justificadas pelo docente.
    Nunca inventa justificativa: só usa o que foi informado em `resolver(..., 'justificar', ...)`."""
    itens = [p for p in manifest.pendencias if p.resolucao == "justificar" and p.justificativa]
    if not itens:
        return ""
    corpo = "".join(f"<li>{html.escape(p.justificativa.strip())}</li>" for p in itens)
    conteudo = (f"<p>Registram-se as seguintes alterações em relação ao Plano Individual de Trabalho "
                f"de {manifest.semestre.codigo}:</p><ul>{corpo}</ul>")
    textos.salvar(manifest.semestre.codigo, "alteracoes", conteudo)
    return conteudo
