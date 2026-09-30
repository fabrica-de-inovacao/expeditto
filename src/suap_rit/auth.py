"""Login humano em janela efêmera e guarda da sessão no keyring do sistema.

O SUAP exige CAPTCHA, código de verificação ou Gov.br no login, então o
usuário loga numa janela pequena; ao detectar sucesso, capturamos só os
cookies de sessão e fechamos a janela. A senha nunca passa pela ferramenta.
"""

from __future__ import annotations

import json

import keyring

from suap_rit.config import BASE_URL, KEYRING_SERVICE

COOKIES_SESSAO = ("__Host-sessionid", "__Host-csrftoken")
_TEMPO_LOGIN_MS = 10 * 60 * 1000


def login_interativo(base_url: str = BASE_URL) -> dict[str, str]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=False,
                                        args=["--window-size=520,760"])
        except Exception:
            browser = p.chromium.launch(headless=False, args=["--window-size=520,760"])
        context = browser.new_context(viewport={"width": 500, "height": 680})
        page = context.new_page()
        page.goto(f"{base_url}/accounts/login/?next=/edu/professor/")
        # Sucesso = voltar ao domínio do SUAP fora das telas de login (inclui retorno do Gov.br).
        page.wait_for_url(
            lambda url: url.startswith(base_url) and "/accounts/login" not in url
            and "/login/govbr" not in url,
            timeout=_TEMPO_LOGIN_MS,
        )
        cookies = {c["name"]: c["value"] for c in context.cookies(base_url)
                   if c["name"] in COOKIES_SESSAO}
        browser.close()
    if "__Host-sessionid" not in cookies:
        raise RuntimeError("login não concluído: cookie de sessão ausente")
    salvar_sessao(cookies, base_url)
    return cookies


def salvar_sessao(cookies: dict[str, str], base_url: str = BASE_URL) -> None:
    keyring.set_password(KEYRING_SERVICE, base_url, json.dumps(cookies))


def carregar_sessao(base_url: str = BASE_URL) -> dict[str, str] | None:
    bruto = keyring.get_password(KEYRING_SERVICE, base_url)
    return json.loads(bruto) if bruto else None


def apagar_sessao(base_url: str = BASE_URL) -> None:
    try:
        keyring.delete_password(KEYRING_SERVICE, base_url)
    except keyring.errors.PasswordDeleteError:
        pass
