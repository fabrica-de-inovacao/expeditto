"""Tarefas em segundo plano com etapas, percentual e "barra" textual.

Usado pelo MCP (o assistente mostra o andamento ao docente) e pela interface do terminal.
As notificações de progresso do protocolo MCP não aparecem em todos os apps (ex.: Claude
Code), então o progresso vai no próprio resultado das ferramenta `aguardar_tarefa`.
"""

from __future__ import annotations

import threading
import time
import traceback
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

# (id, rótulo, peso) — os pesos refletem o tempo típico de cada etapa.
ETAPAS: dict[str, list[tuple[str, str, int]]] = {
    "coleta": [
        ("plano", "Plano do semestre", 4),
        ("calendario", "Calendário (diários)", 6),
        ("ensino", "Estágios, TCCs e bancas", 10),
        ("servidor", "Pasta funcional e projetos", 35),
        ("lattes", "Lattes", 5),
        ("comprovantes", "Baixando comprovantes", 35),
        ("organizacao", "Organizando o acervo", 5),
    ],
    "login": [("janela", "Aguardando seu login no SUAP", 90), ("perfil", "Carregando seu perfil", 10)],
}

ICONES = {"pendente": "·", "andamento": "◐", "ok": "✓", "erro": "✗"}


def barra(percentual: float, largura: int = 20) -> str:
    cheio = round(max(0.0, min(1.0, percentual / 100)) * largura)
    return "▓" * cheio + "░" * (largura - cheio)


class Progresso:
    """Assinatura aceita pelos fluxos: `progresso(mensagem, etapa=None, fracao=None)`."""

    def __call__(self, mensagem: str, etapa: str | None = None, fracao: float | None = None) -> None: ...


def nada(mensagem: str, etapa: str | None = None, fracao: float | None = None) -> None:
    pass


@dataclass
class Etapa:
    id: str
    rotulo: str
    peso: int
    estado: str = "pendente"
    fracao: float = 0.0


@dataclass
class Tarefa:
    id: str
    tipo: str
    descricao: str
    etapas: list[Etapa]
    estado: str = "executando"  # executando | concluida | erro
    detalhe: str = ""
    inicio: float = field(default_factory=time.monotonic)
    iniciada_em: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    fim: float | None = None
    resultado: object = None
    erro: str | None = None
    rastro: str | None = None

    # -- reporte vindo do fluxo ------------------------------------------------------
    def reportar(self, mensagem: str, etapa: str | None = None, fracao: float | None = None) -> None:
        self.detalhe = mensagem
        if etapa is None:
            return
        alvo = next((e for e in self.etapas if e.id == etapa), None)
        if alvo is None:
            return
        for e in self.etapas:  # etapas anteriores ficam concluídas
            if e is alvo:
                break
            if e.estado != "ok":
                e.estado, e.fracao = "ok", 1.0
        alvo.estado = "andamento"
        if fracao is not None:
            alvo.fracao = max(alvo.fracao, min(1.0, fracao))

    def concluir(self, resultado: object) -> None:
        for e in self.etapas:
            e.estado, e.fracao = "ok", 1.0
        self.estado, self.resultado, self.fim = "concluida", resultado, time.monotonic()

    def falhar(self, erro: str, rastro: str | None = None) -> None:
        for e in self.etapas:
            if e.estado == "andamento":
                e.estado = "erro"
        self.estado, self.erro, self.rastro, self.fim = "erro", erro, rastro, time.monotonic()

    # -- leitura ------------------------------------------------------------------------
    @property
    def percentual(self) -> float:
        total = sum(e.peso for e in self.etapas) or 1
        feito = sum(e.peso * (1.0 if e.estado == "ok" else e.fracao) for e in self.etapas)
        return round(100 * feito / total, 1)

    def visao(self) -> dict:
        atual = next((i for i, e in enumerate(self.etapas) if e.estado in ("andamento", "erro")), None)
        if atual is None:
            atual = len(self.etapas) - 1 if self.estado == "concluida" else 0
        etapa = self.etapas[atual]
        decorrido = int((self.fim or time.monotonic()) - self.inicio)
        pct = 100.0 if self.estado == "concluida" else self.percentual
        linha = (f"{self.descricao}  {barra(pct)}  {pct:.0f}%  · etapa {atual + 1}/{len(self.etapas)} · "
                 f"{etapa.rotulo}")
        visao = {
            "tarefa_id": self.id,
            "estado": self.estado,
            "percentual": pct,
            "progresso": linha,
            "etapas": "  ".join(f"{ICONES[e.estado]} {e.rotulo}" for e in self.etapas),
            "detalhe": self.detalhe,
            "decorrido_s": decorrido,
        }
        if self.estado == "concluida":
            visao["resultado"] = self.resultado
        if self.erro:
            visao["erro"] = self.erro
        return visao


class Gerenciador:
    def __init__(self) -> None:
        self._tarefas: dict[str, Tarefa] = {}
        self._trava = threading.Lock()

    def iniciar(self, tipo: str, descricao: str, alvo: Callable[[Callable], object],
                ao_erro: Callable[[Exception], str] | None = None) -> Tarefa:
        tarefa = Tarefa(id=uuid.uuid4().hex[:8], tipo=tipo, descricao=descricao,
                        etapas=[Etapa(i, r, p) for i, r, p in ETAPAS.get(tipo, [(tipo, descricao, 1)])])
        with self._trava:
            self._tarefas[tarefa.id] = tarefa

        def executar() -> None:
            try:
                tarefa.concluir(alvo(tarefa.reportar))
            except Exception as erro:  # noqa: BLE001 — erro volta para quem acompanha a tarefa
                mensagem = ao_erro(erro) if ao_erro else f"{type(erro).__name__}: {erro}"
                tarefa.falhar(mensagem, traceback.format_exc(limit=3))

        threading.Thread(target=executar, daemon=True).start()
        return tarefa

    def obter(self, tarefa_id: str) -> Tarefa | None:
        return self._tarefas.get(tarefa_id)

    def em_andamento(self, tipo: str | None = None) -> list[Tarefa]:
        return [t for t in self._tarefas.values() if t.estado == "executando" and (tipo is None or t.tipo == tipo)]
