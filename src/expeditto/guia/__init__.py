"""Guia do Expeditto para assistentes de IA. Fonte única: vira a ferramenta/recursos `guia` do MCP,
a skill do Claude Code e o contexto da extensão do Gemini CLI."""

from __future__ import annotations

from pathlib import Path

PASTA = Path(__file__).parent
ASSUNTOS = ["indice", "fluxo", "topicos", "pendencias", "relatos", "lattes", "regras"]


def ler(assunto: str = "indice") -> str:
    assunto = assunto.strip().lower().removesuffix(".md")
    if assunto not in ASSUNTOS:
        return ler("indice") + f"\n\n(Assunto '{assunto}' não existe. Use um dos listados acima.)"
    return (PASTA / f"{assunto}.md").read_text(encoding="utf-8")


def completo() -> str:
    return "\n\n---\n\n".join(ler(a) for a in ASSUNTOS)
