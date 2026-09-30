"""Parsers genéricos para o HTML do SUAP (tabelas, listas de definição, datas).

As telas do SUAP são regulares: tabelas com `caption`/`thead`/`tbody` e blocos
`dl > div.list-item > dt/dd`. Os coletores localizam tabelas pelos cabeçalhos
em vez de seletores frágeis de posição.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from lxml import html as lhtml

MESES = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}


def documento(texto_html: str) -> lhtml.HtmlElement:
    return lhtml.fromstring(texto_html)


def texto(el: lhtml.HtmlElement | None) -> str:
    if el is None:
        return ""
    # Junta os nós com espaço: text_content() colaria "2025.1" e "40,0" em "2025.140,0".
    return re.sub(r"\s+", " ", " ".join(el.itertext())).strip()


@dataclass
class Celula:
    texto: str
    links: list[str] = field(default_factory=list)

    def link(self, contem: str) -> str | None:
        return next((h for h in self.links if contem in h), None)


@dataclass
class Tabela:
    caption: str
    cabecalhos: list[str]
    linhas: list[list[Celula]]

    def registros(self) -> list[dict[str, Celula]]:
        return [dict(zip(self.cabecalhos, linha)) for linha in self.linhas]

    def links(self, contem: str) -> list[str]:
        return [h for linha in self.linhas for c in linha for h in c.links if contem in h]


def tabelas(doc: lhtml.HtmlElement) -> list[Tabela]:
    resultado = []
    for t in doc.iter("table"):
        caption = texto(t.find("caption"))
        cabecalhos = [texto(th) for th in t.xpath("./thead//th")]
        linhas = []
        for tr in t.xpath("./tbody/tr"):
            celulas = [
                Celula(texto(td), [a.get("href") for a in td.iter("a") if a.get("href")])
                for td in tr.xpath("./td")
            ]
            if celulas:
                linhas.append(celulas)
        resultado.append(Tabela(caption, cabecalhos, linhas))
    return resultado


def tabelas_com(doc: lhtml.HtmlElement, *cabecalhos: str) -> list[Tabela]:
    """Tabelas cujos cabeçalhos contêm todos os termos informados."""
    return [
        t for t in tabelas(doc)
        if all(any(c in h for h in t.cabecalhos) for c in cabecalhos)
    ]


def definicoes(el: lhtml.HtmlElement, somente: set[str] | None = None) -> dict[str, str]:
    """Pares dt→dd (primeira ocorrência de cada rótulo).

    Com `somente`, lê apenas os rótulos da allowlist — os demais valores nem
    são extraídos (usado no perfil do servidor, que tem dados sensíveis)."""
    pares: dict[str, str] = {}
    for dt in el.iter("dt"):
        rotulo = texto(dt)
        if somente is not None and rotulo not in somente:
            continue
        dd = dt.getnext()
        if dd is not None and dd.tag == "dd":
            pares.setdefault(rotulo, texto(dd))
    return pares


def secoes_accordion(doc: lhtml.HtmlElement) -> dict[str, lhtml.HtmlElement]:
    """Mapa título → corpo de cada `div.accordion-item`."""
    secoes = {}
    for item in doc.xpath('//div[contains(concat(" ", @class, " "), " accordion-item ")]'):
        titulo = texto(item.find(".//h2"))
        corpo = item.xpath('.//div[contains(@class, "accordion-body")]')
        if titulo and corpo:
            secoes[titulo] = corpo[0]
    return secoes


def parse_data(valor: str | None) -> date | None:
    """Aceita '05/03/2024', '05/03/2024 17:00:00', '18.08.2026', '2025-02-03',
    '6 de Janeiro de 2025' e 'Sim 16 de Setembro de 2026 às 09:34'."""
    if not valor:
        return None
    v = valor.strip()
    if m := re.search(r"(\d{4})-(\d{2})-(\d{2})", v):
        return date(int(m[1]), int(m[2]), int(m[3]))
    if m := re.search(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", v):
        return date(int(m[3]), int(m[2]), int(m[1]))
    if m := re.search(r"(\d{1,2})º?\s+de\s+([A-Za-zçÇ]+)\s+de\s+(\d{4})", v, re.IGNORECASE):
        mes = MESES.get(m[2].lower())
        if mes:
            return date(int(m[3]), mes, int(m[1]))
    return None


def id_da_url(url: str | None, prefixo: str) -> str | None:
    """Extrai o primeiro segmento após `prefixo` (ex.: '/pesquisa/projeto/')."""
    if not url or prefixo not in url:
        return None
    resto = url.split(prefixo, 1)[1]
    return resto.strip("/").split("/")[0] or None
