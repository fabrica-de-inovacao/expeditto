"""Aviso de nova versão e atualização (CLI, interface do terminal e MCP).

A versão mais recente é a última *release* do GitHub. A consulta fica em cache por um dia
(`~/expeditto/.atualizacao.json`) e nunca atrasa o uso: sem internet, simplesmente não há aviso.
Desligue com `EXPEDITTO_SEM_ATUALIZACAO=1`.

No Windows, os arquivos do Expeditto ficam travados enquanto ele roda (inclusive o próprio comando
`expeditto atualizar` e o servidor MCP). Por isso a atualização roda num processo separado, que espera
o Expeditto fechar antes de reinstalar.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import time
from importlib import metadata

import httpx

from expeditto import config

REPOSITORIO = "vnschneider/expeditto"
_UM_DIA = 24 * 3600


def versao_instalada() -> str:
    try:
        return metadata.version("expeditto")
    except metadata.PackageNotFoundError:
        return "0.0.0"


def _numeros(versao: str) -> tuple[int, ...]:
    partes = []
    for p in versao.lstrip("vV").split("."):
        digitos = "".join(c for c in p if c.isdigit())
        partes.append(int(digitos or 0))
    return tuple(partes)


def mais_nova(candidata: str, atual: str) -> bool:
    return _numeros(candidata) > _numeros(atual)


def _cache():
    return config.home() / ".atualizacao.json"


def _buscar_release(timeout: float) -> dict | None:
    r = httpx.get(f"https://api.github.com/repos/{REPOSITORIO}/releases/latest", timeout=timeout,
                  headers={"Accept": "application/vnd.github+json", "User-Agent": "expeditto"})
    if r.status_code != 200:
        return None
    dados = r.json()
    return {"versao": dados["tag_name"].lstrip("vV"), "url": dados.get("html_url", ""),
            "notas": (dados.get("body") or "").strip()[:1500]}


def ultima_release(forcar: bool = False, timeout: float = 2.5) -> dict | None:
    """Última release (com cache de um dia). None sem internet, sem release ou com o aviso desligado."""
    if os.environ.get("EXPEDITTO_SEM_ATUALIZACAO"):
        return None
    cache = _cache()
    if not forcar and cache.exists():
        try:
            salvo = json.loads(cache.read_text(encoding="utf-8"))
            if time.time() - salvo.get("consultado", 0) < _UM_DIA:
                return salvo.get("release")
        except (OSError, ValueError):
            pass
    try:
        release = _buscar_release(timeout)
    except (httpx.HTTPError, KeyError, ValueError):
        release = None
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"consultado": time.time(), "release": release}), encoding="utf-8")
    except OSError:
        pass
    return release


def verificar(forcar: bool = False) -> dict | None:
    """Se houver versão mais nova: {"instalada", "disponivel", "url", "notas", "mensagem"}."""
    release = ultima_release(forcar)
    atual = versao_instalada()
    if not release or not mais_nova(release["versao"], atual):
        return None
    return {"instalada": atual, "disponivel": release["versao"], "url": release["url"], "notas": release["notas"],
            "mensagem": f"Há uma versão nova do Expeditto: {release['versao']} (você tem a {atual})."}


# -- atualizar ------------------------------------------------------------------------------
def origem(versao: str) -> str:
    return f"expeditto @ https://github.com/{REPOSITORIO}/archive/refs/tags/v{versao}.zip"


def comando(versao: str) -> list[str] | None:
    uv = shutil.which("uv")
    if not uv:
        return None
    return [uv, "tool", "install", "--force", "--python", "3.12", "--reinstall-package", "expeditto", origem(versao)]


def arquivo_log():
    return config.home() / "atualizacao.log"


def _ps(texto: str) -> str:
    return "'" + texto.replace("'", "''") + "'"


def atualizar(versao: str, aguardar_pid: int | None = None, visivel: bool = False) -> dict:
    """Instala a versão pedida. No Windows, agenda num processo separado que espera `aguardar_pid` fechar."""
    cmd = comando(versao)
    if cmd is None:
        return {"ok": False, "mensagem": "Não encontrei o uv. Rode o instalador de novo pelo site."}
    log = arquivo_log()
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        _cache().unlink()
    except OSError:
        pass

    if platform.system() != "Windows":
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        log.write_text((r.stdout or "") + (r.stderr or ""), encoding="utf-8")
        if r.returncode != 0:
            return {"ok": False, "mensagem": f"A atualização falhou. Detalhes em {log}."}
        return {"ok": True, "agendada": False, "mensagem": f"Expeditto atualizado para a versão {versao}."}

    espera = f"Wait-Process -Id {aguardar_pid} -ErrorAction SilentlyContinue; " if aguardar_pid else ""
    instalar = "& " + " ".join(_ps(p) for p in cmd)
    if visivel:
        script = (f"{espera}Write-Host 'Atualizando o Expeditto para a versao {versao}...' -ForegroundColor Yellow; "
                  f"{instalar}; if ($LASTEXITCODE -eq 0) {{ Write-Host 'Pronto! Pode fechar esta janela.' "
                  f"-ForegroundColor Green }} else {{ Write-Host 'A atualizacao falhou.' -ForegroundColor Red }}")
        flags = subprocess.CREATE_NEW_CONSOLE
        args = ["powershell", "-NoProfile", "-NoExit", "-Command", script]
    else:
        script = f"{espera}{instalar} *> {_ps(str(log))}"
        # sem DETACHED_PROCESS: o PowerShell sem console fecha na hora sem rodar o script
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        args = ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script]
    _iniciar_fora_do_job(args, flags, script, visivel)
    return {"ok": True, "agendada": True, "mensagem": f"Atualização para a versão {versao} agendada."}


def _iniciar_fora_do_job(args: list[str], flags: int, script: str, visivel: bool) -> None:
    """O processo precisa sobreviver ao Expeditto. `uv` e os apps de IA rodam o Expeditto num *job* do
    Windows que encerra os filhos junto; CREATE_BREAKAWAY_FROM_JOB escapa dele quando o job permite.
    Se não permitir, o processo é criado pelo WMI, que o inicia fora de qualquer job."""
    try:
        subprocess.Popen(args, creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB, close_fds=True)
        return
    except OSError:
        pass
    import base64

    codificado = base64.b64encode(script.encode("utf-16-le")).decode()
    janela = "-NoExit" if visivel else "-WindowStyle Hidden"
    linha = f"powershell -NoProfile {janela} -EncodedCommand {codificado}"
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    f"Invoke-CimMethod -ClassName Win32_Process -MethodName Create "
                    f"-Arguments @{{CommandLine={_ps(linha)}}} | Out-Null"],
                   creationflags=subprocess.CREATE_NO_WINDOW, check=False, timeout=60)
