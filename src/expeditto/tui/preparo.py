"""Preparar o RIT de um semestre: roteiro no topo e uma aba por etapa (coleta → salvar)."""

from __future__ import annotations

import re
import time
import webbrowser
from collections import Counter

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (Button, Footer, Input, Label, Markdown, OptionList, ProgressBar, SelectionList,
                             Static, TabbedContent, TabPane)
from textual.widgets.option_list import Option

from expeditto import acervo, anexos, auth, coleta, entrada, formulario, pendencias, roteiro, textos
from expeditto.client import SessaoExpirada, SuapClient
from expeditto.models import Topico
from expeditto.tui.componentes import TOPICO_CURTO, PainelTarefa, Trilha, html_para_texto, humor, mascotes

ABA_DA_ETAPA = {"coletar": "coleta", "pendencias": "pendencias", "alteracoes": "pendencias", "anexos": "anexos",
                "relatos": "relatos", "previa": "salvar", "concluido": "salvar"}
BOTAO_DA_ETAPA = {"login": "Entrar no SUAP", "coletar": "Coletar comprovantes", "pendencias": "Ver pendências",
                  "alteracoes": "Montar Alterações", "anexos": "Montar anexos", "relatos": "Escrever relatos",
                  "previa": "Conferir e salvar", "concluido": "Ver links"}
TITULOS_PENDENCIA = {
    "lattes_sem_comprovante": "Lattes sem comprovante", "diario_incompleto": "Diários incompletos",
    "sem_comprovante": "Atividades sem comprovante", "ata_sem_anexo": "Atas sem o PDF original",
    "datas": "Portarias sem vigência", "afastamento": "Afastamentos", "divergencia_pit": "Diferenças em relação ao PIT",
    "entrada_sem_topico": "Arquivos sem tópico", "anexo_grande": "Anexo acima de 10 MB",
}
LIMITE_MB = 10


def _com_links(markdown: str) -> str:
    return re.sub(r"(https?://\S+)", r"[\1](\1)", markdown)


def _abrir(caminho) -> None:
    webbrowser.open(caminho.resolve().as_uri())


class Preparo(Screen):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Voltar"),
        Binding("n", "proximo", "Próximo passo"),
        Binding("1", "aba('coleta')", "Coleta", show=False),
        Binding("2", "aba('pendencias')", "Pendências", show=False),
        Binding("3", "aba('anexos')", "Anexos", show=False),
        Binding("4", "aba('relatos')", "Relatos", show=False),
        Binding("5", "aba('salvar')", "Salvar", show=False),
        Binding("q", "app.quit", "Sair"),
    ]

    def __init__(self, semestre: str) -> None:
        super().__init__()
        self.semestre = semestre
        self.passo: roteiro.Passo | None = None
        self._grupos: list[dict] = []
        self._tarefa = None
        self._vigia = None
        self._confirmar_ate = 0.0

    # -- estrutura ---------------------------------------------------------------------
    def compose(self) -> ComposeResult:
        with Horizontal(id="cabecalho"):
            yield from mascotes()
            with Vertical(id="roteiro"):
                yield Label(f"RIT {self.semestre}", id="titulo")
                yield Static("", id="fala")
                yield Trilha(id="trilha")
                with Horizontal(id="acoes"):
                    yield Button("▸ Próximo passo", id="proximo", variant="primary")
                    yield Button("‹ Semestres", id="voltar")
        with TabbedContent(id="abas"):
            with TabPane("1 Coleta", id="coleta"):
                with VerticalScroll():
                    yield Static("Busco no SUAP seus diários, estágios, TCCs, bancas, portarias, projetos e o Lattes, "
                                 "baixo os comprovantes e organizo por tópico do RIT.", classes="explica")
                    with Horizontal(classes="botoes"):
                        yield Button("Coletar comprovantes", id="coletar", variant="primary")
                    yield Vertical(id="painel-coleta", classes="vazio-painel")
                    yield Static("", id="coleta-resumo")
            with TabPane("2 Pendências", id="pendencias"):
                yield VerticalScroll(id="cartoes")
            with TabPane("3 Anexos", id="anexos"):
                with VerticalScroll():
                    yield Static("Um PDF por tópico com capa, índice e os comprovantes (limite do SUAP: 10 MB). "
                                 "Tem um comprovante que não está no SUAP? Coloque na pasta de entrada, na subpasta "
                                 "do tópico, e monte de novo.", classes="explica")
                    with Horizontal(classes="botoes"):
                        yield Button("Montar anexos", id="montar", variant="primary")
                        yield Button("Abrir pasta dos anexos", id="abrir-anexos")
                        yield Button("Pasta de entrada", id="abrir-entrada")
                    yield Vertical(id="medidores")
            with TabPane("4 Relatos", id="relatos"):
                with Horizontal():
                    with Vertical(id="lista-relatos"):
                        yield OptionList(id="topicos")
                        yield Button("Gerar rascunhos", id="rascunhos", variant="primary")
                        yield Button("Editar no editor", id="editar")
                        yield Static("Dica: para relatos mais caprichados, peça ao seu assistente de IA: "
                                     f"“escreva os relatos do meu RIT {self.semestre}”.", classes="dica")
                    with VerticalScroll(id="previa-relato"):
                        yield Markdown("", id="relato")
            with TabPane("5 Salvar", id="salvar"):
                with VerticalScroll():
                    yield Static("", id="envio")
                    with Horizontal(classes="botoes"):
                        yield Button("Salvar no SUAP como rascunho", id="salvar-suap", variant="warning")
                    yield Static("Eu só salvo como rascunho. A entrega (Submeter Relatório para Avaliação) é "
                                 "sempre sua, no SUAP.", classes="dica")
                    yield Markdown("", id="cartao")
        yield Footer()

    def on_mount(self) -> None:
        self.atualizar(ir_para_etapa=True)

    # -- estado ------------------------------------------------------------------------
    def atualizar(self, ir_para_etapa: bool = False) -> None:
        self.passo = roteiro.situacao(self.semestre)
        manifest = acervo.carregar_manifest(self.semestre)
        self.query_one("#fala", Static).update(f"“{self.passo.mensagem}”")
        self.query_one(Trilha).mostrar(self.passo.etapa)
        self.query_one("#proximo", Button).label = f"▸ {BOTAO_DA_ETAPA[self.passo.etapa]}"
        if not self._tarefa or self._tarefa.estado != "executando":
            humor(self, "comemorando" if self.passo.etapa == "concluido" else "ocioso")
        self.query_one("#coletar", Button).label = "Coletar de novo" if manifest else "Coletar comprovantes"
        self._resumo_coleta(manifest)
        self.run_worker(self._cartoes_pendencias(manifest), exclusive=True, group="cartoes")
        self.run_worker(self._medidores(manifest), exclusive=True, group="medidores")
        self._lista_relatos(manifest)
        self._previa_envio(manifest)
        if ir_para_etapa and self.passo.etapa in ABA_DA_ETAPA:
            self.query_one(TabbedContent).active = ABA_DA_ETAPA[self.passo.etapa]

    def action_aba(self, aba: str) -> None:
        self.query_one(TabbedContent).active = aba

    @on(Button.Pressed, "#voltar")
    def _voltar(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#proximo")
    def action_proximo(self) -> None:
        etapa = self.passo.etapa if self.passo else "coletar"
        if etapa == "login":
            self.app.entrar(depois=lambda: self.atualizar(ir_para_etapa=True))
        elif etapa == "alteracoes":
            self._gerar_alteracoes()
        else:
            self.query_one(TabbedContent).active = ABA_DA_ETAPA[etapa]
            if etapa == "coletar":
                self._coletar()
            elif etapa == "anexos":
                self._montar()

    # -- coleta ------------------------------------------------------------------------
    def _resumo_coleta(self, manifest) -> None:
        if not manifest:
            self.query_one("#coleta-resumo", Static).update("")
            return
        por_topico = Counter(t for i in manifest.itens for t in i.topicos)
        com_pdf = Counter(t for i in manifest.itens if i.arquivo for t in i.topicos)
        linhas = [f"[b]Acervo de {manifest.semestre.codigo}[/b] · {manifest.semestre.inicio:%d/%m/%Y} a "
                  f"{manifest.semestre.fim:%d/%m/%Y}" if manifest.semestre.inicio and manifest.semestre.fim
                  else f"[b]Acervo de {manifest.semestre.codigo}[/b]", ""]
        for t in Topico:
            linhas.append(f"  {TOPICO_CURTO[t.value]:<32} [b]{por_topico[t]:>3}[/b] itens · {com_pdf[t]:>3} PDFs")
        self.query_one("#coleta-resumo", Static).update("\n".join(linhas))

    @on(Button.Pressed, "#coletar")
    def _coletar(self) -> None:
        if not auth.carregar_sessao():
            self.app.entrar(depois=self._coletar)
            return
        if self._tarefa and self._tarefa.estado == "executando":
            return
        semestre = self.semestre

        def alvo(progresso):
            perfil = acervo.carregar_perfil()
            with SuapClient(auth.carregar_sessao() or {}, matricula=perfil.matricula if perfil else None) as client:
                perfil = perfil or coleta.setup(client)
                coleta.coletar_semestre(client, perfil, semestre, progresso=progresso)
            return True

        def erro(e: Exception) -> str:
            return "A sessão do SUAP expirou: entre de novo." if isinstance(e, SessaoExpirada) else f"{e}"

        self._tarefa = self.app.gerenciador.iniciar("coleta", f"Coleta {semestre}", alvo, erro)
        painel = self.query_one("#painel-coleta", Vertical)
        painel.remove_children()
        painel.mount(PainelTarefa(self._tarefa))
        painel.remove_class("vazio-painel")
        self.query_one("#coletar", Button).disabled = True
        humor(self, "trabalhando")
        self._vigia = self.set_interval(0.25, self._acompanhar)

    def _acompanhar(self) -> None:
        tarefa = self._tarefa
        for painel in self.query(PainelTarefa):
            painel.atualizar()
        if tarefa.estado == "executando":
            return
        self._vigia.stop()
        self.query_one("#coletar", Button).disabled = False
        if tarefa.estado == "concluida":
            self.notify(f"Coleta de {self.semestre} concluída.", title="Pronto!")
            self.atualizar(ir_para_etapa=True)
            humor(self, "comemorando")
        else:
            humor(self, "preocupado")
            self.notify(tarefa.erro or "Algo deu errado.", title="A coleta parou", severity="error", timeout=10)

    # -- pendências --------------------------------------------------------------------
    async def _cartoes_pendencias(self, manifest) -> None:
        caixa = self.query_one("#cartoes", VerticalScroll)
        await caixa.remove_children()
        if not manifest:
            await caixa.mount(Static("Colete os comprovantes primeiro.", classes="vazio"))
            return
        self._grupos = roteiro.pendencias_agrupadas(manifest)
        decididas = [p for p in manifest.pendencias if p.resolucao]
        widgets = []
        if not self._grupos:
            widgets.append(Static("✓ Nenhuma pendência em aberto.", classes="vazio ok"))
        else:
            widgets.append(Static("Marque os itens e escolha o que fazer. Justificativas vão para "
                                  "“Alterações de Atividades” exatamente como você escrever.", classes="explica"))
        for i, grupo in enumerate(self._grupos):
            itens = SelectionList[int](*[(f"{it['numero']:>3}. {it['resumo'][:110]}", it["numero"], True)
                                         for it in grupo["itens"]], id=f"itens-{i}", classes="itens")
            cartao = Vertical(
                Label(f"{TITULOS_PENDENCIA.get(grupo['tipo'], grupo['tipo'])} · {grupo['quantidade']}",
                      classes="cartao-titulo"),
                Static(grupo["pergunta_sugerida"], classes="pergunta"),
                itens,
                Horizontal(Button("Manter", id=f"manter-{i}", variant="success"),
                           Button("Deixar de fora", id=f"ignorar-{i}"),
                           Button("Remover do relato", id=f"remover_item-{i}", variant="error"),
                           classes="botoes"),
                Horizontal(Input(placeholder="Justificativa (vai para Alterações de Atividades)", id=f"texto-{i}"),
                           Button("Justificar", id=f"justificar-{i}", variant="warning"), classes="justificar"),
                classes="cartao")
            widgets.append(cartao)
        if decididas:
            contagem = Counter(p.resolucao for p in decididas)
            nomes = {"manter": "mantidas", "ignorar": "de fora", "remover_item": "removidas", "justificar": "justificadas"}
            resumo = " · ".join(f"{n} {nomes.get(k, k)}" for k, n in contagem.items())
            widgets.append(Static(f"Já decididas: {resumo}", classes="decididas"))
            if contagem.get("justificar"):
                widgets.append(Horizontal(Button("Montar Alterações de Atividades", id="alteracoes"),
                                          classes="botoes"))
        await caixa.mount_all(widgets)

    @on(Button.Pressed, ".cartao Button")
    def _decidir(self, evento: Button.Pressed) -> None:
        decisao, indice = evento.button.id.rsplit("-", 1)
        i = int(indice)
        numeros = list(self.query_one(f"#itens-{i}", SelectionList).selected)
        if not numeros:
            self.notify("Marque ao menos um item.", severity="warning")
            return
        justificativa = self.query_one(f"#texto-{i}", Input).value.strip() or None
        if decisao == "justificar" and not justificativa:
            self.notify("Escreva a justificativa antes.", severity="warning")
            self.query_one(f"#texto-{i}", Input).focus()
            return
        manifest = acervo.carregar_manifest(self.semestre)
        pendencias.resolver(manifest, numeros, decisao, justificativa)
        self.notify(f"{len(numeros)} pendência(s) registrada(s).")
        self.atualizar()

    @on(Button.Pressed, "#alteracoes")
    def _gerar_alteracoes(self) -> None:
        conteudo = pendencias.gerar_alteracoes(acervo.carregar_manifest(self.semestre))
        self.notify("Alterações de Atividades montadas." if conteudo else "Nenhuma pendência justificada.")
        self.atualizar(ir_para_etapa=True)

    # -- anexos ------------------------------------------------------------------------
    async def _medidores(self, manifest) -> None:
        caixa = self.query_one("#medidores", Vertical)
        await caixa.remove_children()
        if not manifest:
            return
        linhas = []
        for t in Topico:
            anexo = manifest.anexos.get(t.value)
            mb = anexo.bytes / 1048576 if anexo else 0
            barra = ProgressBar(total=LIMITE_MB * 10, show_eta=False, show_percentage=False,
                                classes="medidor" + (" estourou" if mb > LIMITE_MB else ""))
            barra.progress = min(mb, LIMITE_MB) * 10
            info = (f"{anexo.documentos} docs · {anexo.paginas} págs · {mb:.1f} MB"
                    + (" · comprimido" if anexo.comprimido else "")) if anexo else "—"
            linhas.append(Horizontal(Label(TOPICO_CURTO[t.value], classes="rotulo"), barra, Label(info, classes="info"),
                                     classes="linha-anexo"))
        await caixa.mount_all(linhas)

    @on(Button.Pressed, "#montar")
    def _montar(self) -> None:
        if not acervo.carregar_manifest(self.semestre):
            self.notify("Colete os comprovantes primeiro.", severity="warning")
            return
        self.query_one("#montar", Button).disabled = True
        humor(self, "trabalhando")
        self._montar_em_segundo_plano()

    @work(thread=True, exclusive=True, group="montar")
    def _montar_em_segundo_plano(self) -> None:
        perfil = acervo.carregar_perfil()
        try:
            anexos.montar(acervo.carregar_manifest(self.semestre), perfil.nome if perfil else "")
            self.app.call_from_thread(self._montado, None)
        except Exception as erro:  # noqa: BLE001
            self.app.call_from_thread(self._montado, str(erro))

    def _montado(self, erro: str | None) -> None:
        self.query_one("#montar", Button).disabled = False
        if erro:
            humor(self, "preocupado")
            self.notify(erro, title="Não consegui montar os anexos", severity="error")
            return
        self.notify("Anexos montados.", title="Pronto!")
        self.atualizar(ir_para_etapa=True)
        humor(self, "comemorando")

    @on(Button.Pressed, "#abrir-anexos")
    def _abrir_anexos(self) -> None:
        pasta = acervo.pasta_semestre(self.semestre) / "anexos"
        pasta.mkdir(exist_ok=True)
        _abrir(pasta)

    @on(Button.Pressed, "#abrir-entrada")
    def _abrir_entrada(self) -> None:
        _abrir(entrada.pasta(self.semestre))

    # -- relatos -----------------------------------------------------------------------
    def _lista_relatos(self, manifest) -> None:
        lista = self.query_one("#topicos", OptionList)
        destacado = lista.highlighted
        lista.clear_options()
        com_itens = {t for i in manifest.itens for t in i.topicos} if manifest else set()
        for t in Topico:
            texto = textos.carregar(self.semestre, t.value)
            icone = "✓" if texto else ("·" if t in com_itens else "–")
            lista.add_option(Option(f"{icone} {TOPICO_CURTO[t.value]}", id=t.value))
        lista.add_option(Option(("✓" if textos.carregar(self.semestre, "alteracoes") else "–")
                                + " " + TOPICO_CURTO["alteracoes"], id="alteracoes"))
        lista.highlighted = destacado if destacado is not None else 0

    @on(OptionList.OptionHighlighted, "#topicos")
    def _mostrar_relato(self, evento: OptionList.OptionHighlighted) -> None:
        topico = evento.option.id
        texto = textos.carregar(self.semestre, topico)
        rotulo = "Alterações de Atividades" if topico == "alteracoes" else Topico(topico).rotulo
        corpo = html_para_texto(texto) if texto else (
            "_Sem relato ainda._ Clique em **Gerar rascunhos** ou peça ao seu assistente de IA.")
        self.query_one("#relato", Markdown).update(f"## {rotulo}\n\n{corpo}")

    @on(Button.Pressed, "#rascunhos")
    def _rascunhos(self) -> None:
        manifest = acervo.carregar_manifest(self.semestre)
        if not manifest:
            self.notify("Colete os comprovantes primeiro.", severity="warning")
            return
        gerados = textos.gerar_rascunhos(manifest)
        self.notify(f"{len(gerados)} rascunho(s) gerado(s)." if gerados else
                    "Os tópicos com comprovantes já têm relato (não sobrescrevo o que você revisou).")
        self.atualizar()

    @on(Button.Pressed, "#editar")
    def _editar(self) -> None:
        import click

        opcao = self.query_one("#topicos", OptionList).highlighted_option
        if opcao is None:
            return
        caminho = textos.pasta_textos(self.semestre) / f"{opcao.id}.html"
        if not caminho.exists():
            caminho.write_text("<p></p>", encoding="utf-8")
        with self.app.suspend():
            click.edit(filename=str(caminho))
        self.atualizar()

    # -- salvar ------------------------------------------------------------------------
    def _previa_envio(self, manifest) -> None:
        envio_widget = self.query_one("#envio", Static)
        botao = self.query_one("#salvar-suap", Button)
        if not manifest or not manifest.plano or not manifest.plano.plano_id:
            envio_widget.update("Colete os comprovantes primeiro: preciso do plano do semestre.")
            botao.disabled = True
            return
        envio = formulario.preparar(manifest)
        abertas = sum(1 for p in manifest.pendencias if not p.resolucao)
        linhas = [f"[b]O que vai para o formulário do RIT {self.semestre}[/b]", ""]
        linhas += [f"  • {linha}" for linha in envio.resumo()]
        if abertas:
            linhas += ["", f"[b]⚠ {abertas} pendência(s) sem decisão.[/b] Dá para salvar assim e decidir depois."]
        envio_widget.update("\n".join(linhas))
        botao.disabled = False
        salvo = roteiro.salvamento(self.semestre)
        if salvo:
            self.query_one("#cartao", Markdown).update(_com_links(roteiro.cartao(manifest, salvo)))

    @on(Button.Pressed, "#salvar-suap")
    def _salvar(self) -> None:
        botao = self.query_one("#salvar-suap", Button)
        if time.monotonic() > self._confirmar_ate:  # 1º clique: pede confirmação
            self._confirmar_ate = time.monotonic() + 10
            botao.label = "Tem certeza? Clique de novo para gravar o rascunho"
            botao.variant = "error"
            self.set_timer(10, self._desarmar)
            return
        if not auth.carregar_sessao():
            self.app.entrar()
            return
        self._confirmar_ate = 0
        botao.disabled = True
        botao.label = "Salvando no SUAP…"
        humor(self, "trabalhando")
        self._salvar_em_segundo_plano()

    def _desarmar(self) -> None:
        if time.monotonic() >= self._confirmar_ate:
            botao = self.query_one("#salvar-suap", Button)
            botao.label, botao.variant = "Salvar no SUAP como rascunho", "warning"

    @work(thread=True, exclusive=True, group="salvar")
    def _salvar_em_segundo_plano(self) -> None:
        perfil = acervo.carregar_perfil()
        try:
            with SuapClient(auth.carregar_sessao() or {}, matricula=perfil.matricula if perfil else None) as client:
                resultado = formulario.salvar_semestre(client, self.semestre)
            self.app.call_from_thread(self._salvo, resultado, None)
        except SessaoExpirada:
            self.app.call_from_thread(self._salvo, None, "A sessão do SUAP expirou: entre de novo e salve outra vez.")
        except Exception as erro:  # noqa: BLE001
            self.app.call_from_thread(self._salvo, None, str(erro))

    def _salvo(self, resultado, erro: str | None) -> None:
        botao = self.query_one("#salvar-suap", Button)
        botao.disabled, botao.label, botao.variant = False, "Salvar no SUAP como rascunho", "warning"
        if erro:
            humor(self, "preocupado")
            self.notify(erro, title="Não salvei", severity="error", timeout=10)
            return
        manifest = acervo.carregar_manifest(self.semestre)
        salvo = roteiro.salvamento(self.semestre) or {"url": resultado.url, "url_pdf": resultado.url_relatorio_pdf}
        self.query_one("#cartao", Markdown).update(_com_links(roteiro.cartao(manifest, salvo)))
        if not all(resultado.textos_conferem.values()):
            self.notify("Salvei, mas algum texto ficou diferente no SUAP. Confira pelo link.", severity="warning")
        self.atualizar()
        humor(self, "comemorando")

    @on(Markdown.LinkClicked)
    def _link(self, evento: Markdown.LinkClicked) -> None:
        self.app.open_url(evento.href)
