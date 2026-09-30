"""Mascote do Expeditto v2: gerado por geometria (círculos, arcos) em vez de desenho à mão."""
import math
import sys
from pathlib import Path

from rich.columns import Columns
from rich.console import Console
from rich.text import Text

PALETA = {
    ".": None, "o": "#A9501A", "O": "#F28C28", "L": "#FFC074", "W": "#FFF3DC",
    "t": "#D9B98C", "K": "#2A1D14", "S": "#FFFFFF", "P": "#F7A08F", "H": "#6B3510",
    "b": "#8E4516", "G": "#FFF3DC",
}
LARG, ALT = 34, 32


def canvas():
    return [["." for _ in range(LARG)] for _ in range(ALT)]


def ponto(c, x, y, cor):
    if 0 <= x < LARG and 0 <= y < ALT:
        c[y][x] = cor


def circulo(c, cx, cy, r, cor, anel=None):
    for y in range(ALT):
        for x in range(LARG):
            d = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
            if anel is not None:
                if r - anel <= d < r:
                    c[y][x] = cor
            elif d < r:
                c[y][x] = cor


def linha(c, x0, y0, x1, y1, cor):
    n = max(abs(x1 - x0), abs(y1 - y0), 1)
    for i in range(n + 1):
        ponto(c, round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n), cor)


def mascote(olhos="abertos", bracos="acenando"):
    c = canvas()
    cx, cy = 17, 18
    # sinos (cúpulas) atrás do corpo + martelinho
    for bx in (7, 27):
        circulo(c, bx, 6.5, 4.6, "o")
        circulo(c, bx, 6.5, 3.6, "O")
        ponto(c, bx - 2, 5, "L"); ponto(c, bx - 1, 4, "L")
    for y in range(9, 12):  # corta a base das cúpulas (sino = meia esfera)
        for x in range(LARG):
            if c[y][x] in "oOL":
                c[y][x] = "."
    linha(c, 7, 9, 7, 9, "o"); linha(c, 27, 9, 27, 9, "o")
    linha(c, cx, 3, cx, 5, "H"); ponto(c, cx, 2, "o"); ponto(c, cx - 1, 2, "o"); ponto(c, cx + 1, 2, "o")
    # corpo
    circulo(c, cx, cy, 13, "o")
    circulo(c, cx, cy, 12, "O")
    circulo(c, cx, cy, 9.6, "W")
    for (x, y) in [(8, 12), (9, 11), (10, 10), (8, 13)]:
        ponto(c, x, y, "L")
    # marcas das horas
    for (x, y) in [(cx, cy - 8), (cx, cy + 8), (cx - 8, cy), (cx + 8, cy)]:
        ponto(c, x, y, "t")
    # olhos
    for ex in (cx - 4, cx + 4):
        if olhos == "abertos":
            for y in range(cy - 4, cy):
                ponto(c, ex, y, "K"); ponto(c, ex + 1, y, "K")
            ponto(c, ex, cy - 4, "S")
        else:
            ponto(c, ex, cy - 2, "K"); ponto(c, ex + 1, cy - 2, "K")
            ponto(c, ex - 1, cy - 3, "K"); ponto(c, ex + 2, cy - 3, "K")
    # bochechas
    for px in (cx - 7, cx + 6):
        ponto(c, px, cy + 1, "P"); ponto(c, px + 1, cy + 1, "P")
    # sorriso
    for (x, y) in [(cx - 3, cy + 2), (cx - 2, cy + 3), (cx - 1, cy + 3), (cx, cy + 3), (cx + 1, cy + 3),
                   (cx + 2, cy + 3), (cx + 3, cy + 2)]:
        ponto(c, x, y, "K")
    # braços = ponteiros do relógio
    if bracos == "acenando":
        linha(c, cx - 13, cy + 1, cx - 16, cy - 3, "H"); ponto(c, cx - 16, cy - 4, "G"); ponto(c, cx - 17, cy - 4, "G")
    else:
        linha(c, cx - 13, cy + 2, cx - 16, cy + 4, "H"); ponto(c, cx - 16, cy + 5, "G")
    linha(c, cx + 13, cy + 2, cx + 16, cy + 4, "H"); ponto(c, cx + 16, cy + 5, "G")
    # pés
    for px in (cx - 6, cx + 5):
        for x in range(px, px + 3):
            ponto(c, x, cy + 13, "b")
        ponto(c, px + 1, cy + 12, "b")
    return ["".join(l) for l in c]


def render(pixels):
    texto = Text()
    if len(pixels) % 2:
        pixels = pixels + ["." * LARG]
    for y in range(0, len(pixels), 2):
        for x in range(LARG):
            cima, baixo = PALETA[pixels[y][x]], PALETA[pixels[y + 1][x]]
            if cima is None and baixo is None:
                texto.append(" ")
            elif cima is None:
                texto.append("▄", style=baixo)
            elif baixo is None:
                texto.append("▀", style=cima)
            else:
                texto.append("▀", style=f"{cima} on {baixo}")
        texto.append("\n")
    return texto


if __name__ == "__main__":
    destino = Path(sys.argv[1])
    console = Console(record=True, width=120, color_system="truecolor")
    console.print(Columns([render(mascote()), render(mascote("piscando", "parado"))], padding=(0, 8)))
    console.print("[bold #F28C28]Expeditto[/] · [#FFF3DC]seu segundo expediente, resolvido[/]")
    console.save_svg(str(destino), title="Expeditto — mascote v2")
