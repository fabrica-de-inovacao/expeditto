"""Componentes visuais reutilizados pelas telas: mascote animado, trilha e painel de progresso."""

from __future__ import annotations

import re
from datetime import datetime

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Label, ProgressBar, Static

from expeditto import roteiro
from expeditto.tarefas import ICONES, Tarefa
from expeditto.tui import mascote
from expeditto.tui.tema import COR


class Mascote(Static):
    """O despertador do Expeditto, animado. Troque `animacao` para mudar o humor."""

    animacao: reactive[str] = reactive("ocioso")

    DEFAULT_CSS = """
    Mascote { width: 34; height: 16; }
    Mascote.pequeno { width: 16; height: 7; }
    """

    def __init__(self, animacao: str = "ocioso", tamanho: str = "grande", **kwargs) -> None:
        super().__init__(classes=tamanho, **kwargs)
        self.tamanho = tamanho
        self._quadro = 0
        self._timer = None
        self.set_reactive(Mascote.animacao, animacao)

    def on_mount(self) -> None:
        self._desenhar()
        self._agendar()

    def watch_animacao(self, _antiga: str, _nova: str) -> None:
        self._quadro = 0
        if self.is_mounted:
            self._desenhar()
            self._agendar()

    def _sequencia(self) -> list[tuple[str, float]]:
        return mascote.ANIMACOES.get(self.animacao, mascote.ANIMACOES["ocioso"])

    def _desenhar(self) -> None:
        pose, _ = self._sequencia()[self._quadro % len(self._sequencia())]
        self.update(mascote.render(pose, tamanho=self.tamanho))

    def _agendar(self) -> None:
        if self._timer:
            self._timer.stop()
        _, duracao = self._sequencia()[self._quadro % len(self._sequencia())]
        self._timer = self.set_timer(duracao, self._avancar)

    def _avancar(self) -> None:
        sequencia = self._sequencia()
        self._quadro += 1
        if self._quadro >= len(sequencia) and self.animacao in ("acenando", "comemorando"):
            if self.animacao == "acenando":  # aceno é uma vez só; depois volta ao normal
                self.animacao = "ocioso"
                return
        self._desenhar()
        self._agendar()


ROTULOS_CURTOS = {"login": "Login", "escolher_semestre": "Semestre", "coletar": "Coleta", "pendencias": "Pendências",
                  "anexos": "Anexos", "relatos": "Relatos", "alteracoes": "Alterações", "previa": "Salvar",
                  "concluido": "Pronto"}


TOPICO_CURTO = {"apoio_ensino": "Apoio ao ensino", "programas_projetos_ensino": "Programas e projetos de ensino",
                "orientacao_alunos": "Orientação de alunos", "reunioes": "Reuniões", "pesquisa": "Pesquisa",
                "extensao": "Extensão", "gestao": "Gestão e representação", "alteracoes": "Alterações de atividades"}


def mascotes(animacao: str = "ocioso") -> list[Mascote]:
    """O mascote nos dois tamanhos; o CSS mostra um ou outro conforme a altura do terminal."""
    return [Mascote(animacao, "grande"), Mascote(animacao, "pequeno")]


def humor(tela, animacao: str) -> None:
    for m in tela.query(Mascote):
        m.animacao = animacao


class Trilha(Static):
    """As etapas do roteiro do RIT com ✓ ◐ ·, como no chat."""

    def mostrar(self, etapa: str) -> None:
        indice = roteiro.ETAPAS.index(etapa)
        texto = Text()
        for i, e in enumerate(roteiro.ETAPAS[2:], start=2):  # login e semestre já estão resolvidos aqui
            if i < indice:
                texto.append("✓ ", style=f"bold {COR['verde']}").append(ROTULOS_CURTOS[e], style=COR["verde"])
            elif i == indice:
                texto.append(f" ◐ {ROTULOS_CURTOS[e]} ", style=f"bold #16110D on {COR['laranja']}")
            else:
                texto.append("· ", style=COR["apagado"]).append(ROTULOS_CURTOS[e], style=COR["apagado"])
            if i < len(roteiro.ETAPAS) - 1:
                texto.append("  ", style=COR["apagado"])
        self.update(texto)


class PainelTarefa(Vertical):
    """Barra geral + uma linha por etapa (ícone, rótulo, barra) + detalhe, alimentado por uma Tarefa."""

    DEFAULT_CSS = """
    PainelTarefa { height: auto; padding: 0 1; }
    PainelTarefa .geral { margin-bottom: 1; }
    PainelTarefa .linha { height: 1; }
    PainelTarefa .icone { width: 3; }
    PainelTarefa .rotulo { width: 32; }
    PainelTarefa .detalhe { color: $text-muted; margin-top: 1; height: 2; }
    """

    def __init__(self, tarefa: Tarefa, **kwargs) -> None:
        super().__init__(**kwargs)
        self.tarefa = tarefa

    def compose(self) -> ComposeResult:
        yield Label(self.tarefa.descricao, classes="titulo")
        yield ProgressBar(total=100, show_eta=False, classes="geral", id="geral")
        for i, etapa in enumerate(self.tarefa.etapas):
            with Horizontal(classes="linha"):
                yield Label(ICONES["pendente"], classes="icone", id=f"icone-{i}")
                yield Label(etapa.rotulo, classes="rotulo")
                yield ProgressBar(total=100, show_eta=False, show_percentage=False, id=f"barra-{i}")
        yield Label("", classes="detalhe", id="detalhe")

    def atualizar(self) -> None:
        t = self.tarefa
        self.query_one("#geral", ProgressBar).update(progress=100 if t.estado == "concluida" else t.percentual)
        cores = {"ok": COR["verde"], "andamento": COR["laranja"], "erro": COR["coral"], "pendente": COR["apagado"]}
        for i, etapa in enumerate(t.etapas):
            self.query_one(f"#icone-{i}", Label).update(Text(ICONES[etapa.estado], style=f"bold {cores[etapa.estado]}"))
            fracao = 1.0 if etapa.estado == "ok" else etapa.fracao
            self.query_one(f"#barra-{i}", ProgressBar).update(progress=round(fracao * 100))
        detalhe = t.erro if t.estado == "erro" else t.detalhe
        self.query_one("#detalhe", Label).update(("✗ " if t.estado == "erro" else "↳ ") + (detalhe or "…")[:160])


def saudacao(nome: str | None) -> str:
    hora = datetime.now().hour
    parte = "Bom dia" if 5 <= hora < 12 else "Boa tarde" if hora < 18 else "Boa noite"
    return f"{parte}, {nome.split()[0].title()}!" if nome else f"{parte}!"


def html_para_texto(conteudo: str) -> str:
    """Relato em HTML simples (p, ul, li, strong) → Markdown para a prévia."""
    t = re.sub(r"\s+", " ", conteudo or "")
    t = re.sub(r"</?strong>|</?b>", "**", t)
    t = re.sub(r"<li[^>]*>\s*", "\n- ", t)
    t = re.sub(r"</p>|<br\s*/?>|</ul>|</ol>", "\n\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\n{3,}", "\n\n", t).strip()
