"""Mascote do Expeditto: um despertador laranja em pixel art (v2 aprovada em docs/marca/).

O desenho é gerado por geometria numa grade de 34×32 "pixels" e desenhado com meios-blocos
(▀ ▄): cada caractere do terminal mostra dois pixels, com a cor de cima no texto e a de baixo
no fundo. Os quadros de animação variam olhos, boca, braços (ponteiros) e o martelinho do sino.
"""

from __future__ import annotations

import math
from functools import lru_cache

from rich.text import Text

PALETA = {
    ".": None,
    "o": "#A9501A",  # contorno
    "O": "#F28C28",  # corpo
    "L": "#FFC074",  # brilho
    "W": "#FFF3DC",  # mostrador
    "t": "#D9B98C",  # marcas das horas
    "K": "#2A1D14",  # olhos e boca
    "S": "#FFFFFF",  # reflexo dos olhos
    "P": "#F7A08F",  # bochechas
    "R": "#C8553D",  # língua (boca aberta)
    "H": "#6B3510",  # ponteiros (braços) e haste
    "G": "#FFF3DC",  # luvas
    "b": "#8E4516",  # pés
    "Y": "#FFD86B",  # faíscas
}
LARG, ALT = 34, 32
CX, CY = 17, 18

# pose → (olhos, boca, braço esquerdo, braço direito, martelo, faíscas)
POSES = {
    "normal": ("abertos", "sorriso", "baixo", "baixo", 0, False),
    "piscando": ("fechados", "sorriso", "baixo", "baixo", 0, False),
    "acenando": ("abertos", "sorriso", "acima", "baixo", 0, False),
    "acenando2": ("abertos", "sorriso", "alto", "baixo", 0, False),
    "trabalhando": ("abertos", "sorriso", "baixo", "acima", -1, False),
    "trabalhando2": ("abertos", "sorriso", "acima", "baixo", 1, False),
    "comemorando": ("fechados", "aberta", "alto", "alto", 0, True),
    "preocupado": ("abertos", "reta", "baixo", "baixo", 0, False),
}


class _Tela:
    def __init__(self, larg: int = LARG, alt: int = ALT) -> None:
        self.larg, self.alt = larg, alt
        self.px = [["." for _ in range(larg)] for _ in range(alt)]

    def ponto(self, x: int, y: int, cor: str) -> None:
        if 0 <= x < self.larg and 0 <= y < self.alt:
            self.px[y][x] = cor

    def circulo(self, cx: float, cy: float, r: float, cor: str) -> None:
        for y in range(self.alt):
            for x in range(self.larg):
                if math.hypot(x + 0.5 - cx, y + 0.5 - cy) < r:
                    self.px[y][x] = cor

    def linha(self, x0: int, y0: int, x1: int, y1: int, cor: str) -> None:
        n = max(abs(x1 - x0), abs(y1 - y0), 1)
        for i in range(n + 1):
            self.ponto(round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n), cor)

    def luva(self, x: int, y: int) -> None:
        for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            self.ponto(x + dx, y + dy, "G")
        self.ponto(x - 1, y, "o"), self.ponto(x + 2, y + 1, "o")


def _sinos(t: _Tela, martelo: int) -> None:
    for bx in (7, 27):
        t.circulo(bx, 6.5, 4.6, "o")
        t.circulo(bx, 6.5, 3.6, "O")
        t.ponto(bx - 2, 5, "L"), t.ponto(bx - 1, 4, "L")
    for y in range(9, 12):  # corta a base das cúpulas (sino = meia esfera)
        for x in range(LARG):
            if t.px[y][x] in "oOL":
                t.px[y][x] = "."
    mx = CX + martelo * 2
    t.linha(CX, 5, mx, 3, "H")
    for dx in (-1, 0, 1):
        t.ponto(mx + dx, 2, "o")


def _braco(t: _Tela, lado: int, pose: str) -> None:
    """lado = -1 (esquerdo) ou 1 (direito). O ponteiro sai da borda do corpo."""
    x0 = CX + lado * 13 - (1 if lado > 0 else 0)
    alvos = {"baixo": (3, 4), "acima": (3, -4), "alto": (2, -8)}
    dx, dy = alvos[pose]
    y0 = CY + (2 if pose == "baixo" else 0)
    x1, y1 = x0 + lado * dx, y0 + dy
    t.linha(x0, y0, x1, y1, "H")
    t.luva(x1 - (1 if lado > 0 else 0), y1 + (1 if dy > 0 else -2))


@lru_cache(maxsize=None)
def pixels(pose: str = "normal", tamanho: str = "grande") -> tuple[str, ...]:
    if tamanho == "pequeno":
        return _pequeno(pose)
    olhos, boca, esq, dir_, martelo, faiscas = POSES[pose]
    t = _Tela()
    _sinos(t, martelo)
    # corpo e mostrador
    t.circulo(CX, CY, 13, "o")
    t.circulo(CX, CY, 12, "O")
    t.circulo(CX, CY, 9.6, "W")
    for x, y in ((8, 12), (9, 11), (10, 10), (8, 13)):
        t.ponto(x, y, "L")
    for x, y in ((CX, CY - 8), (CX, CY + 8), (CX - 8, CY), (CX + 8, CY)):
        t.ponto(x, y, "t")
    # olhos
    for ex in (CX - 4, CX + 4):
        if olhos == "abertos":
            for y in range(CY - 4, CY):
                t.ponto(ex, y, "K"), t.ponto(ex + 1, y, "K")
            t.ponto(ex, CY - 4, "S")
        else:  # fechados, sorrindo (^ ^)
            t.ponto(ex, CY - 3, "K"), t.ponto(ex + 1, CY - 3, "K")
            t.ponto(ex - 1, CY - 2, "K"), t.ponto(ex + 2, CY - 2, "K")
    # bochechas
    for px in (CX - 7, CX + 6):
        t.ponto(px, CY + 1, "P"), t.ponto(px + 1, CY + 1, "P")
    # boca
    if boca == "sorriso":
        for x, y in ((CX - 3, CY + 2), (CX - 2, CY + 3), (CX - 1, CY + 3), (CX, CY + 3), (CX + 1, CY + 3),
                     (CX + 2, CY + 3), (CX + 3, CY + 2)):
            t.ponto(x, y, "K")
    elif boca == "aberta":
        t.linha(CX - 3, CY + 2, CX + 3, CY + 2, "K")
        t.linha(CX - 2, CY + 3, CX + 2, CY + 3, "K")
        t.linha(CX - 1, CY + 4, CX + 1, CY + 4, "K")
        t.ponto(CX, CY + 3, "R"), t.ponto(CX - 1, CY + 3, "R")
    else:  # reta, um pouco torta
        t.linha(CX - 2, CY + 3, CX + 1, CY + 3, "K")
        t.ponto(CX + 2, CY + 2, "K")
    # braços (ponteiros) e pés
    _braco(t, -1, esq)
    _braco(t, 1, dir_)
    for px in (CX - 6, CX + 4):
        for x in range(px, px + 3):
            t.ponto(x, CY + 13, "b")
        t.ponto(px + 1, CY + 12, "b")
    if faiscas:
        for x, y in ((1, 1), (2, 2), (32, 1), (31, 2), (0, 14), (33, 14)):
            t.ponto(x, y, "Y")
    return tuple("".join(linha) for linha in t.px)


# Versão pequena (16×14 pixels = 16×7 caracteres) para terminais de altura média.
# Grade simétrica em torno de x = 8: o pixel x espelha em 15 - x.
PEQ_LARG, PEQ_ALT = 16, 14


def _pequeno(pose: str) -> tuple[str, ...]:
    olhos, boca, esq, dir_, martelo, faiscas = POSES[pose]
    t = _Tela(PEQ_LARG, PEQ_ALT)
    for bx in (2.6, 13.4):  # sinos, afastados do corpo
        t.circulo(bx, 2.2, 2.0, "o")
        t.circulo(bx, 2.2, 1.1, "O")
    for x in range(PEQ_LARG):  # sino = meia esfera
        if t.px[3][x] in "oO":
            t.px[3][x] = "."
    t.ponto(7 + (1 if martelo > 0 else 0), 0, "o"), t.ponto(8 - (1 if martelo < 0 else 0), 0, "o")
    t.circulo(8, 7.5, 5.7, "o")  # corpo (linhas 2 a 12)
    t.circulo(8, 7.5, 4.8, "O")
    t.circulo(8, 7.5, 3.8, "W")
    t.ponto(4, 4, "L"), t.ponto(5, 3, "L")
    for ex in (5, 10):  # olhos
        if olhos == "abertos":
            t.ponto(ex, 6, "K"), t.ponto(ex, 7, "K")
        else:
            t.ponto(ex, 7, "K"), t.ponto(ex + (1 if ex == 5 else -1), 7, "K")
    t.ponto(4, 8, "P"), t.ponto(11, 8, "P")
    if boca == "sorriso":
        for x, y in ((6, 9), (7, 10), (8, 10), (9, 9)):
            t.ponto(x, y, "K")
    elif boca == "aberta":
        t.linha(6, 9, 9, 9, "K"), t.ponto(7, 10, "R"), t.ponto(8, 10, "R")
    else:
        t.ponto(7, 10, "K"), t.ponto(8, 10, "K")
    for x, pose_braco in ((1, esq), (14, dir_)):  # braços (ponteiros) e luvas
        if pose_braco == "baixo":
            t.ponto(x, 9, "H"), t.ponto(x, 10, "G")
        elif pose_braco == "acima":
            t.ponto(x, 6, "H"), t.ponto(x, 5, "G")
        else:
            t.ponto(x, 5, "H"), t.ponto(x, 4, "H"), t.ponto(x, 3, "G")
    for x in (5, 6, 9, 10):  # pés, abaixo do corpo
        t.ponto(x, 13, "b")
    if faiscas:
        for x, y in ((0, 0), (15, 0), (0, 12), (15, 12)):
            t.ponto(x, y, "Y")
    return tuple("".join(linha) for linha in t.px)


@lru_cache(maxsize=None)
def render(pose: str = "normal", fundo: str | None = None, tamanho: str = "grande") -> Text:
    """Desenha a pose com meios-blocos; `fundo` pinta os pixels transparentes (opcional)."""
    px = list(pixels(pose, tamanho))
    largura = len(px[0])
    if len(px) % 2:
        px.append("." * largura)
    texto = Text(no_wrap=True, overflow="crop")
    for y in range(0, len(px), 2):
        for x in range(largura):
            cima, baixo = PALETA[px[y][x]] or fundo, PALETA[px[y + 1][x]] or fundo
            if cima is None and baixo is None:
                texto.append(" ")
            elif cima is None:
                texto.append("▄", style=baixo)
            elif baixo is None:
                texto.append("▀", style=cima)
            else:
                texto.append("▀", style=f"{cima} on {baixo}")
        if y + 2 < len(px):
            texto.append("\n")
    return texto


# Sequências de animação: (pose, duração em segundos)
ANIMACOES: dict[str, list[tuple[str, float]]] = {
    "ocioso": [("normal", 3.2), ("piscando", 0.18), ("normal", 2.4), ("piscando", 0.15), ("normal", 0.2),
               ("piscando", 0.15)],
    "acenando": [("acenando", 0.35), ("acenando2", 0.35)] * 3 + [("normal", 1.0)],
    "trabalhando": [("trabalhando", 0.28), ("trabalhando2", 0.28)],
    "comemorando": [("comemorando", 0.5), ("acenando2", 0.3)],
    "preocupado": [("preocupado", 2.5), ("piscando", 0.15)],
}
