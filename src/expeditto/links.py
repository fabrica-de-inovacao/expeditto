"""Links de cada coisa que o Expeditto cita: página no SUAP, comprovante, arquivo no acervo, DOI.

Tudo o que aparece para o docente (chat, interface, relatos) deve vir com link para ele conferir.
Os links do SUAP pedem a sessão do próprio docente no navegador (são as mesmas telas que ele usa).
"""

from __future__ import annotations

from pathlib import Path

from expeditto import config
from expeditto.models import Evidencia, ItemAcervo, Manifest, Pendencia

ROTULOS = {"suap": "Ver no SUAP", "comprovante": "Ver comprovante", "arquivo": "Abrir o PDF no computador",
           "doi": "Ver a publicação (DOI)", "publicacao": "Ver a publicação"}


def absoluto(caminho: str | None) -> str | None:
    if not caminho:
        return None
    if caminho.startswith(("http://", "https://")):
        return caminho
    return config.BASE_URL + (caminho if caminho.startswith("/") else "/" + caminho)


def de_evidencia(ev: Evidencia, item: ItemAcervo | None = None) -> dict[str, str]:
    saida: dict[str, str] = {}
    if pagina := absoluto(ev.url_pagina):
        saida["suap"] = pagina
    if ev.url_comprovante and not ev.comprovante_assincrono and ev.url_comprovante != ev.url_pagina:
        saida["comprovante"] = absoluto(ev.url_comprovante)
    if item and item.arquivo:
        arquivo = config.home() / item.arquivo
        if arquivo.exists():
            saida["arquivo"] = arquivo.resolve().as_uri()
    if doi := ev.extras.get("doi"):
        saida["doi"] = f"https://doi.org/{doi}"
    return saida


def de_pendencia(manifest: Manifest, pendencia: Pendencia) -> dict[str, str]:
    saida = dict(pendencia.links)
    ev = manifest.evidencias.get(pendencia.evidencia_id or "")
    if ev:
        item = next((i for i in manifest.itens if i.evidencia_id == ev.id), None)
        saida = de_evidencia(ev, item) | saida
    return saida


def markdown(links: dict[str, str]) -> str:
    """'[Ver no SUAP](…) · [Ver comprovante](…)' para o chat."""
    return " · ".join(f"[{ROTULOS.get(tipo, tipo)}]({url})" for tipo, url in links.items())


def permitido(url: str) -> bool:
    """Só abrimos no navegador o que é do docente: telas do SUAP, DOI e arquivos do acervo."""
    if url.startswith((config.BASE_URL + "/", "https://doi.org/")):
        return True
    if url.startswith("file:"):
        from urllib.parse import urlparse
        from urllib.request import url2pathname

        caminho = Path(url2pathname(urlparse(url).path))
        try:
            caminho.resolve().relative_to(config.home().resolve())
            return True
        except ValueError:
            return False
    return False
