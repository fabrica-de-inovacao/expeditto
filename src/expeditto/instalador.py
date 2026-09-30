"""Instalação, desinstalação e atualização: a lógica por trás de `expeditto instalar/desinstalar/atualizar`.

O script de uma linha (install.ps1 / install.sh) instala o uv, faz `uv tool install expeditto` e chama
`expeditto instalar`, que prepara o navegador, conecta o Expeditto aos apps de IA, faz o login no SUAP
e roda o diagnóstico. Nada aqui apaga dados sem o docente pedir.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import keyring
import keyring.errors

from expeditto import auth, config, diagnostico, hosts

PACOTE = "expeditto"


@dataclass
class Resultado:
    alvo: str
    ok: bool
    mensagem: str


# -- como o Expeditto foi instalado ---------------------------------------------------------
def modo_instalacao(prefixo: str | None = None) -> str:
    """'uv-tool' (instalador oficial), 'desenvolvimento' (pasta do código com .venv) ou 'outro'."""
    caminho = Path(prefixo or sys.prefix).resolve()
    partes = [p.lower() for p in caminho.parts]
    if (caminho / "uv-receipt.toml").exists() or ("uv" in partes and "tools" in partes):
        return "uv-tool"
    if caminho.name == ".venv" and (caminho.parent / "pyproject.toml").exists():
        return "desenvolvimento"
    return "outro"


# -- navegador --------------------------------------------------------------------------------
def navegador_pronto() -> bool:
    return diagnostico._navegador().estado == "ok"


def instalar_chromium() -> Resultado:
    """Baixa o Chromium do Playwright (~150 MB), usado só quando não há Google Chrome."""
    r = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], capture_output=True, text=True,
                       timeout=900)
    if r.returncode != 0:
        return Resultado("navegador", False, (r.stderr or r.stdout).strip()[-300:])
    return Resultado("navegador", True, "Chromium baixado")


# -- apps de IA -------------------------------------------------------------------------------
def apps_detectados() -> list[hosts.Host]:
    return [h for h in hosts.todos() if h.instalado()]


def conectar(apps: list[hosts.Host]) -> list[Resultado]:
    resultados = []
    for app in apps:
        try:
            resultados.append(Resultado(app.nome, True, app.configurar()))
        except Exception as erro:  # noqa: BLE001 — um app com problema não impede os outros
            resultados.append(Resultado(app.nome, False, str(erro)))
    return resultados


def desconectar_todos() -> list[Resultado]:
    resultados = []
    for app in hosts.todos():
        if not (app.instalado() and app.configurado()):
            continue
        try:
            resultados.append(Resultado(app.nome, True, app.remover()))
        except Exception as erro:  # noqa: BLE001
            resultados.append(Resultado(app.nome, False, str(erro)))
    return resultados


# -- dados --------------------------------------------------------------------------------------
def apagar_dados() -> list[Resultado]:
    """Apaga a sessão do SUAP, os tokens do Gmail (backup) e a pasta de dados (acervo, perfil, navegador)."""
    from expeditto import gmail

    resultados = []
    auth.apagar_sessao()
    resultados.append(Resultado("sessão do SUAP", True, "apagada do cofre de senhas"))
    for conta in gmail.contas():
        try:
            keyring.delete_password(config.KEYRING_SERVICE, f"gmail:{conta}")
        except keyring.errors.PasswordDeleteError:
            pass
        resultados.append(Resultado(f"Gmail {conta}", True, "autorização apagada"))
    pasta = config.home()
    if pasta.exists():
        shutil.rmtree(pasta, ignore_errors=True)
        resultados.append(Resultado("pasta de dados", not pasta.exists(), str(pasta)))
    return resultados


# -- remoção ----------------------------------------------------------------------------------------
def comando_remover_programa() -> str:
    return {"uv-tool": f"uv tool uninstall {PACOTE}",
            "desenvolvimento": "apague a pasta do código-fonte"}.get(modo_instalacao(), f"pip uninstall {PACOTE}")
