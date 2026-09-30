"""Extração de metadados do texto de portarias (documento eletrônico do SUAP).

Exemplo de texto real (resumido):
    PORTARIA N° 123/2026 - DGP-XYZ/..., DE 20 DE AGOSTO DE 2026 ... RESOLVE:
    Art. 1º - A Comissão Organizadora ... fica composta conforme segue:
    I - Presidente: Fulano, SIAPE: 1 ... II - Membros: a) ... g) Nome, SIAPE: 1234567
    Art. 2º A Comissão terá vigência no período de 18.08.2026 a 18.11.2026.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from expeditto.html import parse_data

_DATA = r"(\d{1,2}[./]\d{1,2}[./]\d{4}|\d{1,2}º? de [A-Za-zç]+ de \d{4})"
_PAPEIS = [
    ("Presidente", r"(?<!vice-)(?<!vice )presidente"),
    ("Vice-presidente", r"vice[- ]presidente"),
    ("Coordenador(a)", r"coordenador(?:a)?(?:\(a\))?"),
    ("Secretário(a)", r"secret[áa]ri[oa]"),
    ("Suplente", r"suplentes?"),
    ("Membro", r"membros?|integrantes?|titulares?"),
]


@dataclass
class DadosPortaria:
    numero: str | None
    data: date | None
    assunto: str
    papel: str | None
    inicio: date | None
    fim: date | None
    vigencia_indeterminada: bool
    data_evento: date | None  # ex.: data da defesa numa portaria de banca


def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


def parse(texto: str, nome: str | None = None, matricula: str | None = None) -> DadosPortaria:
    t = _normalizar(texto)
    numero = m[1] if (m := re.search(r"PORTARIA\s+N[°ºo.]*\s*([\d./]+)", t, re.I)) else None
    data = parse_data(m[1]) if (m := re.search(r"PORTARIA[^,]{0,120},\s*DE\s+" + _DATA, t, re.I)) else None

    partes = re.split(r"RESOLVE", t, maxsplit=1, flags=re.I)
    corpo = partes[-1].lstrip(": ")
    assunto_m = re.search(r"Art\.?\s*1[º°o]?\s*[-–.]?\s*(.+?)(?=Art\.?\s*2|$)", corpo, re.I)
    assunto = (assunto_m[1] if assunto_m else corpo)[:400].strip()

    inicio = fim = None
    if m := re.search(r"vig[êe]ncia[^.]{0,60}?(?:de|a partir de)\s+" + _DATA + r"\s+(?:a|até)\s+" + _DATA, t, re.I):
        inicio, fim = parse_data(m[1]), parse_data(m[2])
    elif m := re.search(r"(?:per[íi]odo|mandato|bi[êe]nio)[^.]{0,40}?(\d{4})\s*(?:a|-|/|até)\s*(\d{4})", t, re.I):
        inicio, fim = date(int(m[1]), 1, 1), date(int(m[2]), 12, 31)
    elif m := re.search(r"/\s*(\d{4})\s*a\s*(\d{4})\b", t):
        inicio, fim = date(int(m[1]), 1, 1), date(int(m[2]), 12, 31)

    data_evento = None
    if re.search(r"banca", t, re.I) and (m := re.search(r"(?:defesa|apresenta[çc][ãa]o|realizad[ao])[^.]{0,80}?" + _DATA, t, re.I)):
        data_evento = parse_data(m[1])

    indeterminada = inicio is None and data_evento is None and bool(
        re.search(r"a partir d(?:esta|a) data|prazo indeterminado|a contar de", t, re.I))
    if indeterminada:
        inicio = data

    return DadosPortaria(
        numero=numero,
        data=data,
        assunto=assunto,
        papel=_papel(corpo, nome, matricula),
        inicio=inicio,
        fim=fim,
        vigencia_indeterminada=indeterminada,
        data_evento=data_evento,
    )


def _papel(corpo: str, nome: str | None, matricula: str | None) -> str | None:
    """Papel do usuário: o último rótulo de papel que aparece antes do nome dele."""
    posicao = -1
    for alvo in (matricula, nome):
        if alvo and (i := corpo.lower().find(alvo.lower())) >= 0:
            posicao = i
            break
    if posicao < 0:
        return None
    # Designação individual: "Designar Fulana ... para desempenhar a Função de Coordenador(a) do Curso..."
    depois = corpo[posicao:posicao + 400]
    if m := re.search(r"(?:fun[çc][ãa]o|cargo)\s+de\s+(.{4,60}?)(?=\s+(?:do|da|de|no|na)\s|[,.;]|$)", depois, re.I):
        return re.sub(r"\s+", " ", m[1]).strip().capitalize()
    # "... para atuar como Coordenadora do Projeto X" / "como membro titular"
    if m := re.search(r"\bcomo\s+((?:vice[- ])?coordenador\w*|presidente|secret[áa]ri\w+|supervisor\w*|"
                      r"orientador\w*|avaliador\w*|membro\w*)", depois, re.I):
        return m[1].capitalize()
    anterior = corpo[:posicao].lower()
    melhor, melhor_pos = None, -1
    for rotulo, padrao in _PAPEIS:
        for m in re.finditer(padrao, anterior):
            if m.start() > melhor_pos:
                melhor, melhor_pos = rotulo, m.start()
    return melhor or "Membro"
