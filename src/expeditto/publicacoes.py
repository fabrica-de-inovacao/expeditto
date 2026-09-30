"""Completa itens do Lattes com dados de bases públicas de publicações (Crossref e OpenAlex).

O Lattes (e a cópia dele no SUAP) só informa o ano. As bases de publicações costumam ter a data
completa, o tipo (artigo, capítulo, anais), o veículo e o DOI. Com a data, o Expeditto sugere se o
item é deste semestre. Só consultamos títulos que já são públicos no Lattes; sem internet ou sem
correspondência segura, o item fica como estava.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import date
from difflib import SequenceMatcher

import httpx

from expeditto import config
from expeditto.models import Pendencia, Semestre

_AGENTE = "Expeditto (https://github.com/fabrica-de-inovacao/expeditto)"
_DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>]+)", re.I)
_SIMILARIDADE_MINIMA = 0.9
PARALELO = 4

TIPOS = {
    # Crossref
    "journal-article": "artigo em periódico", "proceedings-article": "artigo em anais de evento",
    "book-chapter": "capítulo de livro", "book": "livro", "edited-book": "livro (organização)",
    "monograph": "livro", "posted-content": "preprint", "dissertation": "dissertação ou tese",
    "report": "relatório", "dataset": "conjunto de dados",
    # OpenAlex
    "article": "artigo", "preprint": "preprint", "review": "artigo de revisão", "paratext": "texto",
    "conference-paper": "artigo em anais de evento", "book-series": "livro", "letter": "carta",
    "editorial": "editorial", "other": "outro",
}
_MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


@dataclass
class Publicacao:
    titulo: str
    tipo: str
    veiculo: str
    data: str  # AAAA-MM-DD, AAAA-MM ou AAAA
    doi: str
    fonte: str


def extrair_doi(texto: str) -> str | None:
    m = _DOI.search(texto or "")
    return m[1].rstrip(".,;)]") if m else None


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", sem_acento.lower()).strip()


def similaridade(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalizar(a), _normalizar(b)).ratio()


def _data_crossref(obra: dict) -> str:
    melhores = []
    for campo in ("published-print", "published-online", "issued", "published"):
        partes = (obra.get(campo) or {}).get("date-parts") or [[]]
        if partes and partes[0] and partes[0][0]:
            melhores.append(partes[0])
    if not melhores:
        return ""
    # a mais precisa (dia > mês > ano); entre iguais, a mais antiga (primeira publicação)
    partes = sorted(melhores, key=lambda p: (-len(p), p))[0]
    return "-".join(f"{n:02d}" if i else str(n) for i, n in enumerate(partes[:3]))


def _de_crossref(obra: dict) -> Publicacao:
    return Publicacao(titulo=(obra.get("title") or [""])[0], tipo=TIPOS.get(obra.get("type", ""), obra.get("type", "")),
                      veiculo=(obra.get("container-title") or [""])[0], data=_data_crossref(obra),
                      doi=obra.get("DOI", ""), fonte="Crossref")


def _de_openalex(obra: dict) -> Publicacao:
    data = obra.get("publication_date") or ""
    if data.endswith("-01-01"):  # o OpenAlex usa 1º de janeiro quando só conhece o ano
        data = data[:4]
    fonte = ((obra.get("primary_location") or {}).get("source") or {})
    return Publicacao(titulo=obra.get("title") or obra.get("display_name") or "",
                      tipo=TIPOS.get(obra.get("type", ""), obra.get("type", "")),
                      veiculo=fonte.get("display_name") or "", data=data,
                      doi=(obra.get("doi") or "").removeprefix("https://doi.org/"), fonte="OpenAlex")


def _melhor(candidatas: list[Publicacao], titulo: str, ano: int | None) -> Publicacao | None:
    boas = [(similaridade(c.titulo, titulo), c) for c in candidatas if c.titulo]
    boas = [(s, c) for s, c in boas if s >= _SIMILARIDADE_MINIMA and (not ano or not c.data or c.data[:4] == str(ano))]
    return max(boas, key=lambda x: x[0])[1] if boas else None


def _consultar(http: httpx.Client, titulo: str, ano: int | None, doi: str | None) -> Publicacao | None:
    if doi:
        r = http.get(f"https://api.crossref.org/works/{doi}")
        if r.status_code == 200:
            return _de_crossref(r.json()["message"])
    filtro = f"from-pub-date:{ano},until-pub-date:{ano}" if ano else None
    r = http.get("https://api.crossref.org/works", params={"query.bibliographic": titulo, "rows": 5,
                                                          **({"filter": filtro} if filtro else {})})
    if r.status_code == 200:
        achada = _melhor([_de_crossref(o) for o in r.json()["message"].get("items", [])], titulo, ano)
        if achada:
            return achada
    r = http.get("https://api.openalex.org/works", params={"search": titulo, "per-page": 5,
                                                          **({"filter": f"publication_year:{ano}"} if ano else {})})
    if r.status_code == 200:
        return _melhor([_de_openalex(o) for o in r.json().get("results", [])], titulo, ano)
    return None


def buscar(titulo: str, ano: int | None, doi: str | None = None, http: httpx.Client | None = None) -> Publicacao | None:
    """Publicação correspondente (cache local, inclusive dos "não achei"). None se não houver segurança."""
    chave = hashlib.sha1(f"{_normalizar(titulo)}|{ano}|{doi or ''}".encode()).hexdigest()[:20]
    cache = config.cache_dir() / "publicacoes" / f"{chave}.json"
    if cache.exists():
        dados = json.loads(cache.read_text(encoding="utf-8"))
        return Publicacao(**dados) if dados else None
    proprio = http is None
    http = http or httpx.Client(timeout=8, headers={"User-Agent": _AGENTE}, follow_redirects=True)
    try:
        achada = _consultar(http, titulo, ano, doi)
    except (httpx.HTTPError, ValueError, KeyError):
        return None  # sem rede ou resposta estranha: tenta de novo na próxima coleta (não grava cache)
    finally:
        if proprio:
            http.close()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(asdict(achada) if achada else None, ensure_ascii=False), encoding="utf-8")
    return achada


def data_legivel(data: str) -> str:
    partes = data.split("-")
    if len(partes) == 3:
        return f"{int(partes[2])}/{partes[1]}/{partes[0]}"
    if len(partes) == 2:
        return f"{_MESES[int(partes[1]) - 1]}/{partes[0]}"
    return data


def _vizinho(semestre: Semestre, passo: int) -> str:
    ano, periodo = semestre.ano, semestre.periodo + passo
    if periodo == 0:
        ano, periodo = ano - 1, 2
    elif periodo == 3:
        ano, periodo = ano + 1, 1
    return f"{ano}.{periodo}"


def semestre_da_data(data: str, semestre: Semestre) -> str | None:
    """'AAAA.P' provável da data (com mês): o semestre atual se cair no período letivo dele; antes do início,
    o semestre anterior; depois do fim, o seguinte. None se a data não tiver mês."""
    partes = [int(p) for p in data.split("-") if p]
    if len(partes) < 2:
        return None
    quando = date(partes[0], partes[1], partes[2] if len(partes) > 2 else 15)
    if semestre.inicio and semestre.fim:
        dentro = semestre.inicio <= quando <= semestre.fim
    else:
        dentro = quando.year == semestre.ano and (quando.month <= 6) == (semestre.periodo == 1)
    if dentro:
        return semestre.codigo
    if semestre.inicio and semestre.fim:
        return _vizinho(semestre, -1 if quando < semestre.inicio else 1)
    return f"{quando.year}.{1 if quando.month <= 6 else 2}"


def enriquecer(pendencias: list[Pendencia], semestre: Semestre, progresso=lambda m, f=None: None) -> int:
    """Completa as pendências do Lattes com tipo, veículo, data e DOI. Devolve quantas foram completadas."""
    alvos = [p for p in pendencias if p.tipo == "lattes_sem_comprovante" and p.detalhes.get("titulo")]
    if not alvos:
        return 0

    def um(p: Pendencia) -> Publicacao | None:
        ano = int(p.detalhes["ano"]) if p.detalhes.get("ano", "").isdigit() else None
        return buscar(p.detalhes["titulo"], ano, p.detalhes.get("doi"), http)

    completadas = 0
    with httpx.Client(timeout=8, headers={"User-Agent": _AGENTE}, follow_redirects=True) as http:
        with ThreadPoolExecutor(PARALELO) as pool:
            for n, (p, pub) in enumerate(zip(alvos, pool.map(um, alvos)), 1):
                progresso(f"Publicações do Lattes ({n}/{len(alvos)})", n / len(alvos))
                if not pub:
                    continue
                completadas += 1
                p.detalhes.update({"tipo_publicacao": pub.tipo, "veiculo": pub.veiculo, "fonte_dados": pub.fonte})
                if pub.data:
                    p.detalhes["data"] = data_legivel(pub.data)
                    if provavel := semestre_da_data(pub.data, semestre):
                        p.detalhes["semestre_provavel"] = provavel
                        p.detalhes["semestre_atual"] = semestre.codigo
                if pub.doi:
                    p.detalhes["doi"] = pub.doi
                    p.links["doi"] = f"https://doi.org/{pub.doi}"
    return completadas
