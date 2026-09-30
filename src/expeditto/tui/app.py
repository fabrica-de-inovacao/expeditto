"""Aplicativo Textual do Expeditto (tela cheia)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from textual.app import App

from expeditto import tarefas
from expeditto.tui.inicio import Inicio
from expeditto.tui.preparo import Preparo
from expeditto.tui.telas import Diagnostico, Login
from expeditto.tui.tema import ALTO_CONTRASTE, EXPEDITTO


class ExpedittoApp(App):
    TITLE = "Expeditto"
    SUB_TITLE = "seu segundo expediente, resolvido"
    CSS_PATH = Path(__file__).with_name("estilo.tcss")
    ENABLE_COMMAND_PALETTE = False
    HORIZONTAL_BREAKPOINTS = [(0, "-estreito"), (100, "-largo")]
    VERTICAL_BREAKPOINTS = [(0, "-baixo"), (38, "-alto")]

    def __init__(self, alto_contraste: bool = False, semestre: str | None = None) -> None:
        super().__init__()
        self.gerenciador = tarefas.Gerenciador()
        self._alto_contraste = alto_contraste
        self._semestre = semestre

    def on_mount(self) -> None:
        self.register_theme(EXPEDITTO)
        self.register_theme(ALTO_CONTRASTE)
        self.theme = ALTO_CONTRASTE.name if self._alto_contraste else EXPEDITTO.name
        self.push_screen(Inicio())
        if self._semestre:
            self.abrir_preparo(self._semestre)

    def abrir_preparo(self, semestre: str) -> None:
        self.push_screen(Preparo(semestre))

    def abrir_diagnostico(self) -> None:
        self.push_screen(Diagnostico())

    def entrar(self, depois: Callable[[], None] | None = None) -> None:
        def ao_fechar(ok: bool | None) -> None:
            if ok:
                if isinstance(self.screen, Inicio):
                    self.screen.action_recarregar()
                if depois:
                    depois()

        self.push_screen(Login(), ao_fechar)


def rodar(alto_contraste: bool = False, semestre: str | None = None) -> None:
    ExpedittoApp(alto_contraste=alto_contraste, semestre=semestre).run()
