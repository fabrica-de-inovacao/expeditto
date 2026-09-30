"""Telas menores: login no SUAP (janela sobreposta) e diagnóstico."""

from __future__ import annotations

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Label, Static

from expeditto import auth, coleta, diagnostico
from expeditto.client import SuapClient
from expeditto.tui.componentes import PainelTarefa, humor, mascotes
from expeditto.tui.tema import COR


class Login(ModalScreen[bool]):
    """Abre a janela do SUAP (login humano: CAPTCHA/Gov.br) e acompanha até carregar o perfil."""

    BINDINGS = [Binding("escape", "fechar", "Fechar")]

    def compose(self) -> ComposeResult:
        with Horizontal(id="caixa-login"):
            yield from mascotes("acenando")
            with Vertical():
                yield Label("Entrar no SUAP", classes="titulo-caixa")
                yield Static("Abri uma janela do SUAP no seu computador. Faça o login nela (CAPTCHA ou Gov.br); "
                             "ela fecha sozinha. Sua senha fica só no navegador.", id="instrucao")
                yield Vertical(id="painel-login")
                yield Button("Fechar", id="fechar")

    def on_mount(self) -> None:
        def alvo(progresso):
            progresso("Janela do SUAP aberta: aguardando o seu login (até 10 min)", etapa="janela")
            cookies = auth.login_interativo()
            progresso("Carregando seu perfil", etapa="perfil")
            with SuapClient(cookies) as client:
                return coleta.setup(client)

        self.tarefa = self.app.gerenciador.iniciar("login", "Login no SUAP", alvo)
        self.query_one("#painel-login").mount(PainelTarefa(self.tarefa))
        self._vigia = self.set_interval(0.3, self._acompanhar)

    def _acompanhar(self) -> None:
        for painel in self.query(PainelTarefa):
            painel.atualizar()
        if self.tarefa.estado == "executando":
            return
        self._vigia.stop()
        if self.tarefa.estado == "concluida":
            perfil = self.tarefa.resultado
            humor(self, "comemorando")
            nome = (perfil.nome_usual or perfil.nome).split()[0].title()
            self.query_one("#instrucao", Static).update(f"Olá, {nome}! Sessão ativa · {perfil.campus or 'IFMA'}.")
            self.set_timer(1.6, self._fechar_com_sucesso)
        else:
            humor(self, "preocupado")
            self.query_one("#instrucao", Static).update(f"Não deu certo: {self.tarefa.erro}")

    def _fechar_com_sucesso(self) -> None:
        self.dismiss(True)  # sem `return`: o timer aguardaria o retorno e o Textual proíbe isso

    @on(Button.Pressed, "#fechar")
    def action_fechar(self) -> None:
        self.dismiss(self.tarefa.estado == "concluida")


class Diagnostico(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Voltar"), Binding("r", "verificar", "Verificar de novo"),
                Binding("q", "app.quit", "Sair")]

    def compose(self) -> ComposeResult:
        with Horizontal(id="cabecalho"):
            yield from mascotes()
            with Vertical(id="roteiro"):
                yield Label("Diagnóstico", id="titulo")
                yield Static("Vou conferir se está tudo pronto para trabalhar.", id="fala")
                with Horizontal(id="acoes"):
                    yield Button("Verificar de novo", id="verificar", variant="primary")
                    yield Button("‹ Voltar", id="voltar")
        yield VerticalScroll(id="verificacoes")
        yield Footer()

    def on_mount(self) -> None:
        self._mostrar(diagnostico.executar(verificar_online=False), final=False)
        self.action_verificar()

    @on(Button.Pressed, "#verificar")
    def action_verificar(self) -> None:
        humor(self, "trabalhando")
        self._verificar()

    @on(Button.Pressed, "#voltar")
    def _voltar(self) -> None:
        self.app.pop_screen()

    @work(thread=True, exclusive=True)
    def _verificar(self) -> None:
        self.app.call_from_thread(self._mostrar, diagnostico.executar(verificar_online=True), True)

    def _mostrar(self, verificacoes, final: bool) -> None:
        estilos = {"ok": ("✓", COR["verde"]), "aviso": ("!", COR["ambar"]), "erro": ("✗", COR["coral"])}
        linhas = Text()
        for v in verificacoes:
            icone, cor = estilos[v.estado]
            linhas.append(f" {icone} ", style=f"bold {cor}").append(f"{v.titulo:<28}", style="bold")
            linhas.append(v.detalhe + "\n")
            if v.como_resolver:
                linhas.append(" " * 31 + "↳ " + v.como_resolver + "\n", style=COR["ambar"])
        self.query_one("#verificacoes").remove_children()
        self.query_one("#verificacoes").mount(Static(linhas))
        if not final:
            return
        geral = diagnostico.como_dict(verificacoes)["geral"]
        fala = {"ok": "Tudo pronto para trabalhar!", "aviso": "Quase tudo certo. Veja os pontos em amarelo.",
                "erro": "Encontrei um problema. Veja como resolver logo abaixo dele."}[geral]
        self.query_one("#fala", Static).update(f"“{fala}”")
        humor(self, {"ok": "comemorando", "aviso": "ocioso", "erro": "preocupado"}[geral])
