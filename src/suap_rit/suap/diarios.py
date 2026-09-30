"""Diários do professor via API (`/api/edu/meus-diarios/{ano}/{periodo}/`)."""

from __future__ import annotations

from suap_rit.client import SuapClient
from suap_rit.html import parse_data
from suap_rit.models import Evidencia, Semestre, TipoEvidencia

# Diários com mais dias que isto são anuais (técnico integrado) e não definem o semestre.
_MAX_DIAS_SEMESTRAL = 220


def parse_diarios(dados: list[dict], codigo: str) -> list[Evidencia]:
    evidencias = []
    for d in dados:
        aulas = d.get("aulas") or []
        evidencias.append(Evidencia(
            id=f"suap_api:diario:{d['id']}",
            fonte="suap_api",
            tipo=TipoEvidencia.DIARIO,
            titulo=d.get("componente_curricular", "Diário"),
            descricao=f"{len(aulas)} aulas registradas",
            papel="Professor(a)",
            inicio=parse_data(d.get("data_inicio")),
            fim=parse_data(d.get("data_fim")),
            semestre_letivo=codigo,
            url_pagina=f"/edu/meu_diario/{d['id']}/1/",
            extras={"diario_id": str(d["id"])},
        ))
    return evidencias


def datas_semestre(diarios: list[Evidencia], codigo: str) -> Semestre:
    """Calendário do campus inferido dos diários semestrais (decisão D17)."""
    semestre = Semestre.de_codigo(codigo)
    semestrais = [d for d in diarios if d.inicio and d.fim
                  and (d.fim - d.inicio).days <= _MAX_DIAS_SEMESTRAL]
    if semestrais:
        semestre.inicio = min(d.inicio for d in semestrais)
        semestre.fim = max(d.fim for d in semestrais)
        semestre.fonte_datas = "diarios"
    return semestre


def carregar(client: SuapClient, codigo: str) -> tuple[list[Evidencia], Semestre]:
    ano, periodo = codigo.split(".")
    diarios = parse_diarios(client.json(f"/api/edu/meus-diarios/{ano}/{periodo}/"), codigo)
    return diarios, datas_semestre(diarios, codigo)
