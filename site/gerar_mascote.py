"""Gera os SVGs do mascote para o site a partir do mesmo desenho da interface do terminal.

Uso: uv run python site/gerar_mascote.py
"""

from pathlib import Path

from expeditto.tui import mascote

DESTINO = Path(__file__).parent


def svg(pose: str, tamanho: str = "grande") -> str:
    px = mascote.pixels(pose, tamanho)
    larg, alt = len(px[0]), len(px)
    rects = [f'<rect x="{x}" y="{y}" width="1" height="1" fill="{mascote.PALETA[c]}"/>'
             for y, linha in enumerate(px) for x, c in enumerate(linha) if mascote.PALETA[c]]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {larg} {alt}" shape-rendering="crispEdges" '
            f'role="img" aria-label="Mascote do Expeditto: um despertador laranja">{"".join(rects)}</svg>\n')


if __name__ == "__main__":
    for pose in ("acenando", "comemorando", "trabalhando", "normal"):
        (DESTINO / f"mascote-{pose}.svg").write_text(svg(pose), encoding="utf-8")
    (DESTINO / "favicon.svg").write_text(svg("normal", "pequeno"), encoding="utf-8")
    print("SVGs gerados em", DESTINO)
