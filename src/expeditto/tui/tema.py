"""Temas do Expeditto: "noite de expediente" (padrão) e alto contraste."""

from __future__ import annotations

from textual.theme import Theme

COR = {
    "laranja": "#F28C28",
    "ambar": "#FFC074",
    "creme": "#FFF3DC",
    "verde": "#7BC47F",
    "coral": "#E0694F",
    "apagado": "#8A7A6C",
}

EXPEDITTO = Theme(
    name="expeditto",
    primary="#F28C28",
    secondary="#FFC074",
    accent="#FFC074",
    foreground="#FFF3DC",
    background="#16110D",
    surface="#211913",
    panel="#2C2119",
    success="#7BC47F",
    warning="#FFC074",
    error="#E0694F",
    dark=True,
    variables={
        "footer-key-foreground": "#F28C28",
        "block-cursor-background": "#F28C28",
        "block-cursor-foreground": "#16110D",
        "input-selection-background": "#F28C28 40%",
    },
)

ALTO_CONTRASTE = Theme(
    name="expeditto-contraste",
    primary="#FFB000",
    secondary="#FFFFFF",
    accent="#FFD700",
    foreground="#FFFFFF",
    background="#000000",
    surface="#000000",
    panel="#1A1A1A",
    success="#00FF66",
    warning="#FFD700",
    error="#FF5555",
    dark=True,
)
