"""Leva o guia do Expeditto para dentro dos apps de IA, no formato de cada um.

- Claude Code (terminal e aba Code do Claude Desktop): skill em `~/.claude/skills/expeditto-rit/`.
- Gemini CLI: extensão só de contexto em `~/.gemini/extensions/expeditto/` (GEMINI.md).
- Claude Desktop (chat), Codex, OpenCode e outros: o guia chega pelo próprio servidor MCP (instruções,
  ferramenta `guia` e recursos `expeditto://guia/...`), sem instalar nada.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from expeditto import atualizacao, guia

NOME_SKILL = "expeditto-rit"
_DESCRICAO = ("Use quando o docente falar do RIT (Relatório Individual de Trabalho) do SUAP IFMA, do relatório "
              "do semestre, do PIT, de comprovantes, pendências, relatos ou itens do Lattes. Explica o fluxo do "
              "Expeditto, os tópicos do RIT, como decidir pendências e como escrever os relatos, usando as "
              "ferramentas MCP do Expeditto.")
_MARCA = "<!-- gerado pelo Expeditto: não edite, é substituído a cada instalação -->"


def _skill_md() -> str:
    referencias = "\n".join(f"- `references/{a}.md`: {a}" for a in guia.ASSUNTOS if a != "indice")
    return (f"---\nname: {NOME_SKILL}\ndescription: {_DESCRICAO}\n---\n{_MARCA}\n\n"
            f"{guia.ler('indice')}\n\n## Referências (leia sob demanda)\n\n{referencias}\n")


def instalar_skill(pasta_skills: Path) -> Path:
    destino = pasta_skills / NOME_SKILL
    if destino.exists() and _MARCA not in (destino / "SKILL.md").read_text(encoding="utf-8", errors="ignore"):
        raise RuntimeError(f"{destino} já existe e não foi criada pelo Expeditto; não vou sobrescrever.")
    (destino / "references").mkdir(parents=True, exist_ok=True)
    (destino / "SKILL.md").write_text(_skill_md(), encoding="utf-8")
    for assunto in guia.ASSUNTOS:
        if assunto != "indice":
            (destino / "references" / f"{assunto}.md").write_text(guia.ler(assunto), encoding="utf-8")
    return destino


def remover_skill(pasta_skills: Path) -> None:
    destino = pasta_skills / NOME_SKILL
    if (destino / "SKILL.md").exists() and _MARCA in (destino / "SKILL.md").read_text(encoding="utf-8", errors="ignore"):
        shutil.rmtree(destino, ignore_errors=True)


def instalar_extensao_gemini(pasta_extensoes: Path) -> Path:
    destino = pasta_extensoes / "expeditto"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "gemini-extension.json").write_text(json.dumps({
        "name": "expeditto", "version": atualizacao.versao_instalada(), "contextFileName": "GEMINI.md",
    }, indent=2), encoding="utf-8")
    (destino / "GEMINI.md").write_text(f"{_MARCA}\n\n{guia.completo()}\n", encoding="utf-8")
    return destino


def remover_extensao_gemini(pasta_extensoes: Path) -> None:
    destino = pasta_extensoes / "expeditto"
    if (destino / "GEMINI.md").exists() and _MARCA in (destino / "GEMINI.md").read_text(encoding="utf-8", errors="ignore"):
        shutil.rmtree(destino, ignore_errors=True)
