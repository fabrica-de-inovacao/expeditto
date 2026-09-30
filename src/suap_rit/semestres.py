"""Alocação de evidências em semestres (decisões D17–D19)."""

from __future__ import annotations

from datetime import date, timedelta

from suap_rit.models import Evidencia, Semestre


def estimar(codigo: str) -> Semestre:
    """Fallback quando não há diários semestrais: semestre civil, marcado como estimativa."""
    s = Semestre.de_codigo(codigo)
    if s.periodo == 1:
        s.inicio, s.fim = date(s.ano, 1, 1), date(s.ano, 6, 30)
    else:
        s.inicio, s.fim = date(s.ano, 7, 1), date(s.ano, 12, 31)
    s.fonte_datas = "estimativa"
    return s


def janelas(semestres: dict[str, Semestre]) -> dict[str, tuple[date, date]]:
    """Janela de alocação de cada semestre: do início dele até a véspera do
    próximo. Atividades nas férias entre semestres caem no semestre anterior."""
    ordenados = sorted((s for s in semestres.values() if s.inicio and s.fim),
                       key=lambda s: s.inicio)
    resultado = {}
    for atual, proximo in zip(ordenados, ordenados[1:] + [None]):
        fim = proximo.inicio - timedelta(days=1) if proximo else atual.fim
        resultado[atual.codigo] = (atual.inicio, max(fim, atual.fim))
    return resultado


def intervalo(ev: Evidencia, hoje: date | None = None) -> tuple[date, date] | None:
    if ev.data_evento:  # D18: banca vale pela data da defesa
        return ev.data_evento, ev.data_evento
    if ev.inicio:  # sem término (vigência aberta) → vale até hoje
        return ev.inicio, ev.fim or hoje or date.today()
    return None


def pertence(ev: Evidencia, codigo: str, janela: tuple[date, date], hoje: date | None = None) -> bool:
    if ev.data_evento is None and ev.semestre_letivo:
        return ev.semestre_letivo == codigo
    periodo = intervalo(ev, hoje)
    if periodo is None:
        return False
    inicio, fim = periodo
    return inicio <= janela[1] and fim >= janela[0]  # D19: interseção → entra em todos
