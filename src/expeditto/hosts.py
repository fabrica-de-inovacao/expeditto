"""Apps de IA que rodam o servidor MCP do Expeditto: detecção, instalação e remoção.

Cada app guarda a configuração de MCP num lugar diferente. Antes de alterar um arquivo
de configuração, fazemos backup (`<arquivo>.expeditto-bak`), e a remoção restaura o original.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

NOME_SERVIDOR = "expeditto"


def comando_mcp() -> list[str]:
    """Comando que os apps executam para iniciar o servidor (o Python do próprio ambiente do Expeditto)."""
    return [sys.executable, "-m", "expeditto", "mcp"]


def _home() -> Path:
    return Path(os.environ.get("EXPEDITTO_HOSTS_HOME", Path.home()))


def _local_appdata() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", _home() / "AppData" / "Local"))


def _pacote_claude_msix() -> Path | None:
    """Claude Desktop instalado como pacote MSIX (Microsoft Store/instalador novo): o app enxerga uma pasta
    AppData virtualizada dentro do pacote, e é lá que ele lê o claude_desktop_config.json."""
    pacotes = _local_appdata() / "Packages"
    achados = sorted(pacotes.glob("Claude_*")) if pacotes.exists() else []
    return achados[0] if achados else None


def _config_claude_desktop() -> Path:
    sistema = platform.system()
    if sistema == "Windows":
        if pacote := _pacote_claude_msix():
            return pacote / "LocalCache" / "Roaming" / "Claude" / "claude_desktop_config.json"
        base = Path(os.environ.get("APPDATA", _home() / "AppData" / "Roaming"))
        return base / "Claude" / "claude_desktop_config.json"
    if sistema == "Darwin":
        return _home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    return _home() / ".config" / "Claude" / "claude_desktop_config.json"


@dataclass
class Host:
    id: str
    nome: str

    # -- estado -------------------------------------------------------------------------
    def instalado(self) -> bool:
        raise NotImplementedError

    def configurado(self) -> bool:
        raise NotImplementedError

    # -- ações --------------------------------------------------------------------------
    def configurar(self) -> str:
        raise NotImplementedError

    def remover(self) -> str:
        raise NotImplementedError

    def revisar(self) -> str:
        """Reaplica ajustes da versão atual num app já conectado (permissões, opções). Idempotente."""
        return "ok"


def _backup(arquivo: Path) -> None:
    copia = arquivo.with_name(arquivo.name + ".expeditto-bak")
    if arquivo.exists() and not copia.exists():
        shutil.copy2(arquivo, copia)


def _ler_json(arquivo: Path) -> dict:
    if not arquivo.exists() or not arquivo.read_text(encoding="utf-8").strip():
        return {}
    return json.loads(arquivo.read_text(encoding="utf-8"))


def _gravar_json(arquivo: Path, dados: dict) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


class HostJson(Host):
    """Apps configurados por um JSON com a chave `mcpServers` (Claude Desktop, Gemini, Antigravity)."""

    def __init__(self, id: str, nome: str, arquivo: Path, pasta_app: Path, executavel: str | None = None,
                 extras: dict | None = None, extensoes: Path | None = None, indicios: list[Path] | None = None):
        super().__init__(id, nome)
        self.arquivo, self.pasta_app, self.executavel, self.extras = arquivo, pasta_app, executavel, extras or {}
        self.indicios = indicios or []  # outras pastas que mostram que o app está instalado (mesmo nunca aberto)
        self.extensoes = extensoes  # Gemini CLI: pasta de extensões (guia do Expeditto como contexto)

    def instalado(self) -> bool:
        return (self.pasta_app.exists() or any(i.exists() for i in self.indicios)
                or bool(self.executavel and shutil.which(self.executavel)))

    def configurado(self) -> bool:
        return NOME_SERVIDOR in _ler_json(self.arquivo).get("mcpServers", {})

    def configurar(self) -> str:
        _backup(self.arquivo)
        dados = _ler_json(self.arquivo)
        comando, *args = comando_mcp()
        dados.setdefault("mcpServers", {})[NOME_SERVIDOR] = {"command": comando, "args": args, **self.extras}
        _gravar_json(self.arquivo, dados)
        if self.extensoes:
            from expeditto import conhecimento

            conhecimento.instalar_extensao_gemini(self.extensoes)
        return f"adicionado em {self.arquivo}"

    def revisar(self) -> str:
        return self.configurar()

    def remover(self) -> str:
        if self.extensoes:
            from expeditto import conhecimento

            conhecimento.remover_extensao_gemini(self.extensoes)
        dados = _ler_json(self.arquivo)
        if dados.get("mcpServers", {}).pop(NOME_SERVIDOR, None) is None:
            return "não estava configurado"
        _gravar_json(self.arquivo, dados)
        return f"removido de {self.arquivo}"


class HostCli(Host):
    """Apps configurados pela própria linha de comando (Claude Code, Codex)."""

    def __init__(self, id: str, nome: str, executavel: str, adicionar: list[str], remover: list[str],
                 arquivo: Path, marcador: str, permissoes: Path | None = None, skills: Path | None = None):
        super().__init__(id, nome)
        self.executavel, self._adicionar, self._remover = executavel, adicionar, remover
        self.arquivo, self.marcador, self.permissoes, self.skills = arquivo, marcador, permissoes, skills

    def instalado(self) -> bool:
        return shutil.which(self.executavel) is not None

    def configurado(self) -> bool:
        return self.arquivo.exists() and re.search(self.marcador, self.arquivo.read_text(encoding="utf-8")) is not None

    def _rodar(self, args: list[str]) -> str:
        exe = shutil.which(self.executavel)
        r = subprocess.run([exe, *args], capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or r.stdout).strip()[:300])
        return (r.stdout or "ok").strip().splitlines()[-1] if (r.stdout or "").strip() else "ok"

    def configurar(self) -> str:
        resultado = self._rodar([*self._adicionar, "--", *comando_mcp()])
        self._ajustes()
        return resultado

    def _ajustes(self) -> None:
        if self.permissoes:
            permitir_no_claude_code(self.permissoes)
        if self.skills:
            from expeditto import conhecimento

            conhecimento.instalar_skill(self.skills)

    def revisar(self) -> str:
        self._ajustes()
        return "permissões e guia atualizados" if (self.permissoes or self.skills) else "ok"

    def remover(self) -> str:
        if self.skills:
            from expeditto import conhecimento

            conhecimento.remover_skill(self.skills)
        if self.permissoes:
            permitir_no_claude_code(self.permissoes, remover=True)
        return self._rodar(self._remover)


# Claude Code: libera as ferramentas do Expeditto de uma vez, mas continua perguntando nas sensíveis.
# ("ask" vale mais que "allow" nas regras de permissão do Claude Code.)
PERMITIR = [f"mcp__{NOME_SERVIDOR}"]
PERGUNTAR = [f"mcp__{NOME_SERVIDOR}__salvar_no_suap", f"mcp__{NOME_SERVIDOR}__atualizar_expeditto"]


def permitir_no_claude_code(arquivo: Path, remover: bool = False) -> None:
    _backup(arquivo)
    dados = _ler_json(arquivo)
    permissoes = dados.setdefault("permissions", {})
    for chave, regras in (("allow", PERMITIR), ("ask", PERGUNTAR)):
        atuais = [r for r in permissoes.get(chave, []) if r not in regras]
        permissoes[chave] = atuais if remover else atuais + regras
        if not permissoes[chave]:
            del permissoes[chave]
    _gravar_json(arquivo, dados)


def todos() -> list[Host]:
    home = _home()
    return [
        HostJson("claude-desktop", "Claude Desktop", _config_claude_desktop(), _config_claude_desktop().parent,
                 indicios=[_local_appdata() / "AnthropicClaude", Path("/Applications/Claude.app"),
                           *filter(None, [_pacote_claude_msix()])]),
        HostCli("claude-code", "Claude Code", "claude",
                ["mcp", "add", NOME_SERVIDOR, "-s", "user"], ["mcp", "remove", NOME_SERVIDOR, "-s", "user"],
                home / ".claude.json", r'"expeditto"\s*:', permissoes=home / ".claude" / "settings.json",
                skills=home / ".claude" / "skills"),
        HostCli("codex", "Codex (OpenAI)", "codex",
                ["mcp", "add", NOME_SERVIDOR], ["mcp", "remove", NOME_SERVIDOR],
                home / ".codex" / "config.toml", r"\[mcp_servers\.expeditto\]"),
        # trust: o Gemini CLI não pede confirmação a cada ferramenta (salvar_no_suap ainda exige confirmado=true)
        HostJson("gemini", "Gemini CLI", home / ".gemini" / "settings.json", home / ".gemini", "gemini",
                 extras={"timeout": 600000, "trust": True}, extensoes=home / ".gemini" / "extensions"),
        HostJson("antigravity", "Antigravity CLI", home / ".gemini" / "config" / "mcp_config.json",
                 home / ".gemini" / "config", "agy", extras={"timeout": 600000}),
    ]


def por_id(host_id: str) -> Host:
    return next(h for h in todos() if h.id == host_id)
