"""Tela inicial: mascote, saudação, sessão, semestres e atalhos."""

from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Label, Static

from expeditto import acervo, auth, roteiro
from expeditto.client import SessaoExpirada, SuapClient
from expeditto.models import EstadoPlano, PlanoSemestre
from expeditto.suap import planos
from expeditto.tui.componentes import Mascote, saudacao

SITUACOES = {
    EstadoPlano.SEM_PLANO: "sem plano",
    EstadoPlano.PLANO_NAO_ENVIADO: "plano não enviado",
    EstadoPlano.PLANO_EM_AVALIACAO: "plano em avaliação",
    EstadoPlano.RIT_A_PREENCHER: "RIT a preencher",
    EstadoPlano.RIT_EM_AVALIACAO: "RIT em avaliação",
    EstadoPlano.RIT_APROVADO: "RIT aprovado",
    EstadoPlano.RIT_PUBLICADO: "publicado",
}


class Inicio(Screen):
    BINDINGS = [
        Binding("p", "preparar", "Preparar RIT"),
        Binding("l", "login", "Entrar no SUAP"),
        Binding("d", "diagnostico", "Diagnóstico"),
        Binding("r", "recarregar", "Atualizar"),
        Binding("q", "app.quit", "Sair"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.planos: list[PlanoSemestre] = []
        self._cursor_posto = False

    def compose(self) -> ComposeResult:
        with Horizontal(id="topo"):
            yield Mascote("acenando", id="mascote")
            with Vertical(id="boas-vindas"):
                yield Label("Expeditto", id="marca")
                yield Label("seu segundo expediente, resolvido", id="lema")
                yield Label("", id="saudacao")
                yield Label("", id="resumo")
                yield Label("", id="sessao")
                with Horizontal(id="acoes"):
                    yield Button("▸ Preparar RIT", id="preparar", variant="primary")
                    yield Button("Entrar no SUAP", id="login")
                    yield Button("Diagnóstico", id="diagnostico")
        yield Label("Seus semestres", classes="secao")
        yield DataTable(id="semestres", cursor_type="row", zebra_stripes=True)
        yield Static("Ferramenta independente, não oficial. Roda no seu computador, com a sua sessão. "
                     "Nunca entrega o relatório por você.", id="aviso")
        yield Footer()

    def on_mount(self) -> None:
        tabela = self.query_one(DataTable)
        tabela.add_columns("Semestre", "Situação no SUAP", "Comprovantes", "Pendências", "Passo", "Rascunho no SUAP")
        self.action_recarregar()

    # -- dados -------------------------------------------------------------------------
    def action_recarregar(self) -> None:
        perfil = acervo.carregar_perfil()
        self.query_one("#saudacao", Label).update(saudacao(perfil.nome_usual or perfil.nome if perfil else None))
        tem_sessao = bool(auth.carregar_sessao())
        self.query_one("#login", Button).label = "Entrar de novo" if tem_sessao else "Entrar no SUAP"
        self._sessao("verificando…" if tem_sessao else "sem sessão · clique em Entrar no SUAP", "aviso")
        self._preencher_tabela()
        if tem_sessao:
            self._carregar_planos()

    def _sessao(self, texto: str, estado: str) -> None:
        icone = {"ok": "●", "aviso": "○", "erro": "✗"}[estado]
        rotulo = self.query_one("#sessao", Label)
        rotulo.update(f"{icone} SUAP: {texto}")
        rotulo.set_classes(f"sessao-{estado}")

    @work(thread=True, exclusive=True, group="planos")
    def _carregar_planos(self) -> None:
        perfil = acervo.carregar_perfil()
        try:
            with SuapClient(auth.carregar_sessao() or {}, matricula=perfil.matricula if perfil else None) as client:
                lista = planos.carregar_todos(client)
            self.app.call_from_thread(self._planos_carregados, lista)
        except SessaoExpirada:
            self.app.call_from_thread(self._sessao, "sessão expirada · clique em Entrar de novo", "aviso")
        except Exception as erro:  # noqa: BLE001 — sem internet/SUAP fora: segue com o acervo local
            self.app.call_from_thread(self._sessao, f"inacessível ({type(erro).__name__})", "erro")

    def _planos_carregados(self, lista: list[PlanoSemestre]) -> None:
        self.planos = lista
        perfil = acervo.carregar_perfil()
        self._sessao(f"sessão ativa · {perfil.campus if perfil and perfil.campus else 'IFMA'}", "ok")
        self._preencher_tabela()

    def _preencher_tabela(self) -> None:
        tabela = self.query_one(DataTable)
        linha_atual = tabela.cursor_row
        tabela.clear()
        por_semestre = {p.semestre: p for p in self.planos}
        codigos = sorted(set(por_semestre) | set(acervo.semestres_locais()), reverse=True)
        a_preencher = [c for c in codigos if c in por_semestre
                       and por_semestre[c].estado == EstadoPlano.RIT_A_PREENCHER]
        for codigo in codigos:
            plano = por_semestre.get(codigo)
            manifest = acervo.carregar_manifest(codigo)
            situacao = SITUACOES.get(plano.estado, plano.estado.value) if plano else "—"
            comprovantes = str(len(manifest.itens)) if manifest else "—"
            abertas = sum(1 for p in manifest.pendencias if not p.resolucao) if manifest else 0
            pendencias = ("✓" if not abertas else f"⚠ {abertas}") if manifest else "—"
            passo = roteiro.ROTULOS[roteiro.situacao(codigo, exigir_sessao=False).etapa] if manifest else (
                "começar" if codigo in a_preencher else "—")
            salvo = roteiro.salvamento(codigo) if manifest else None
            rascunho = f"✓ {salvo['quando'][8:10]}/{salvo['quando'][5:7]} {salvo['quando'][11:16]}" if salvo else "—"
            tabela.add_row(codigo, situacao, comprovantes, pendencias, passo, rascunho, key=codigo)
        if codigos:
            if not self._cursor_posto and a_preencher:  # primeira vez: começa no RIT a preencher mais recente
                linha_atual = codigos.index(a_preencher[0])
                self._cursor_posto = bool(self.planos)
            tabela.move_cursor(row=min(max(linha_atual, 0), len(codigos) - 1))
            tabela.focus()
        n = len(a_preencher)
        self.query_one("#resumo", Label).update(
            f"{n} RIT{'s' if n != 1 else ''} esperando por você." if n else
            ("Escolha um semestre abaixo." if codigos else "Entre no SUAP para eu encontrar seus semestres."))

    # -- ações -------------------------------------------------------------------------
    def _semestre_selecionado(self) -> str | None:
        tabela = self.query_one(DataTable)
        if not tabela.row_count:
            return None
        return tabela.coordinate_to_cell_key((tabela.cursor_row, 0)).row_key.value

    @on(DataTable.RowSelected)
    def _linha_escolhida(self, evento: DataTable.RowSelected) -> None:
        self._abrir(evento.row_key.value)

    def _abrir(self, semestre: str) -> None:
        plano = next((p for p in self.planos if p.semestre == semestre), None)
        if plano and plano.estado != EstadoPlano.RIT_A_PREENCHER and not acervo.carregar_manifest(semestre):
            self.notify(f"O RIT de {semestre} não está aberto para preenchimento ({SITUACOES[plano.estado]}).",
                        severity="warning")
            return
        self.app.abrir_preparo(semestre)

    @on(Button.Pressed, "#preparar")
    def action_preparar(self) -> None:
        if not auth.carregar_sessao() and not acervo.semestres_locais():
            self.action_login()
            return
        if semestre := self._semestre_selecionado():
            self._abrir(semestre)
        else:
            self.notify("Entre no SUAP para eu listar seus semestres.", severity="warning")

    @on(Button.Pressed, "#login")
    def action_login(self) -> None:
        self.app.entrar()

    @on(Button.Pressed, "#diagnostico")
    def action_diagnostico(self) -> None:
        self.app.abrir_diagnostico()

    def on_screen_resume(self) -> None:
        if self.query_one(DataTable).columns:  # voltando de outra tela: dados podem ter mudado
            self.action_recarregar()
