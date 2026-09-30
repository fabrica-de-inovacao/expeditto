"""Diagnóstico ("doctor"): o que está pronto, o que falta e como resolver.

Usado pela CLI (`expeditto doctor`), pela interface do terminal e pela ferramenta MCP `diagnostico`.
"""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import asdict, dataclass
from importlib import metadata
from pathlib import Path

from expeditto import acervo, auth, config, hosts


@dataclass
class Verificacao:
    id: str
    titulo: str
    estado: str  # ok | aviso | erro
    detalhe: str
    como_resolver: str = ""


def _versao() -> Verificacao:
    try:
        versao = metadata.version("expeditto")
    except metadata.PackageNotFoundError:
        versao = "desenvolvimento"
    return Verificacao("versao", "Expeditto", "ok", f"versão {versao} · Python {platform.python_version()}")


def _pasta() -> Verificacao:
    pasta = config.home()
    teste = pasta / ".escrita"
    try:
        teste.write_text("ok", encoding="utf-8")
        teste.unlink()
        return Verificacao("pasta", "Pasta de dados", "ok", str(pasta))
    except OSError as erro:
        return Verificacao("pasta", "Pasta de dados", "erro", f"{pasta}: {erro}",
                           "Defina outra pasta com a variável EXPEDITTO_HOME.")


def caminho_chrome() -> str | None:
    candidatos = []
    if platform.system() == "Windows":
        for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")):
            if base:
                candidatos.append(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe")
    elif platform.system() == "Darwin":
        candidatos.append(Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"))
    for nome in ("google-chrome", "google-chrome-stable", "chrome"):
        if achado := shutil.which(nome):
            candidatos.append(Path(achado))
    return next((str(c) for c in candidatos if c.exists()), None)


def _chromium_playwright() -> bool:
    base = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""))
    if not base.name:
        base = (Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright" if platform.system() == "Windows"
                else Path.home() / ("Library/Caches/ms-playwright" if platform.system() == "Darwin" else ".cache/ms-playwright"))
    return base.exists() and any(p.name.startswith("chromium") for p in base.iterdir())


def _navegador() -> Verificacao:
    if chrome := caminho_chrome():
        return Verificacao("navegador", "Navegador para o login", "ok", f"Google Chrome ({chrome})")
    if _chromium_playwright():
        return Verificacao("navegador", "Navegador para o login", "ok", "Chromium do Playwright")
    return Verificacao("navegador", "Navegador para o login", "erro", "Chrome não encontrado",
                       "Instale o Google Chrome ou rode `expeditto instalar` (baixa o Chromium).")


def _sessao(verificar_online: bool) -> Verificacao:
    cookies = auth.carregar_sessao()
    if not cookies:
        return Verificacao("sessao", "Sessão no SUAP", "aviso", "sem sessão",
                           "Faça login: `expeditto login` (ou peça ao assistente para entrar no SUAP).")
    if not verificar_online:
        return Verificacao("sessao", "Sessão no SUAP", "ok", "sessão guardada (não verificada)")
    from expeditto.client import SessaoExpirada, SuapClient
    from expeditto.suap.perfil import identificar
    try:
        with SuapClient(cookies) as client:
            nome, _, _ = identificar(client.html("/edu/professor/?tab=planoatividades", aba=True))
        return Verificacao("sessao", "Sessão no SUAP", "ok", f"ativa ({nome})")
    except SessaoExpirada:
        return Verificacao("sessao", "Sessão no SUAP", "aviso", "expirada (dura cerca de 90 min sem uso)",
                           "Faça login novamente: `expeditto login`.")
    except Exception as erro:  # noqa: BLE001
        return Verificacao("sessao", "Sessão no SUAP", "erro", f"SUAP inacessível: {erro}",
                           "Verifique a internet ou se o SUAP está no ar.")


def _perfil() -> Verificacao:
    perfil = acervo.carregar_perfil()
    if not perfil:
        return Verificacao("perfil", "Seu perfil", "aviso", "ainda não carregado", "Faça o primeiro login.")
    return Verificacao("perfil", "Seu perfil", "ok", f"{perfil.nome_usual or perfil.nome} · {perfil.campus or '?'}")


def _apps() -> list[Verificacao]:
    resultado = []
    for host in hosts.todos():
        if not host.instalado():
            continue
        if host.configurado():
            resultado.append(Verificacao(f"app-{host.id}", host.nome, "ok", "Expeditto conectado"))
        else:
            resultado.append(Verificacao(f"app-{host.id}", host.nome, "aviso", "instalado, mas sem o Expeditto",
                                         f"Rode `expeditto instalar` e marque {host.nome}."))
    if not resultado:
        resultado.append(Verificacao("apps", "Assistentes de IA", "aviso", "nenhum app compatível encontrado",
                                     "Instale o Claude Desktop (recomendado) e rode `expeditto instalar`."))
    return resultado


def _gmail() -> Verificacao:
    from expeditto import gmail
    contas = gmail.contas()
    if contas:
        return Verificacao("gmail", "E-mail (backup do Expeditto)", "ok", ", ".join(contas))
    return Verificacao("gmail", "E-mail", "ok",
                       "pelo conector do seu assistente (ex.: Gmail do Claude); backup próprio não configurado")


def executar(verificar_online: bool = True) -> list[Verificacao]:
    return [_versao(), _pasta(), _navegador(), _sessao(verificar_online), _perfil(), *_apps(), _gmail()]


def como_dict(verificacoes: list[Verificacao]) -> dict:
    estados = [v.estado for v in verificacoes]
    geral = "erro" if "erro" in estados else ("aviso" if "aviso" in estados else "ok")
    return {"geral": geral, "verificacoes": [asdict(v) for v in verificacoes]}
