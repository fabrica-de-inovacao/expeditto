"""Planos Individuais de Trabalho por semestre (`/edu/professor/?tab=planoatividades`)."""

from __future__ import annotations

import re

from expeditto import html as h
from expeditto.client import SuapClient
from expeditto.models import EstadoPlano, PlanoSemestre

_ACOES = {
    "cadastrar": "cadastrar_plano_individual_trabalho",
    "enviar_plano": "enviar_plano",
    "plano_pdf": "plano_atividade_docente_pdf",
    "preencher_relatorio": "preencher_relatorio_individual_trabalho",
    "entregar_relatorio": "entregar_relatorio",
    "relatorio_pdf": "relatorio_atividade_docente_pdf",
}


def _sim(valor: str | None) -> bool:
    return bool(valor) and valor.strip().lower().startswith("sim")


def listar_periodos(pagina: str) -> list[str]:
    doc = h.documento(pagina)
    # As <option> do SUAP não têm atributo value: o período está no texto.
    valores = [o.get("value") or h.texto(o) for o in doc.xpath('//select[@name="ano-periodo"]/option')]
    return [v for v in valores if re.fullmatch(r"\d{4}\.\d", v)]


def estado(p: PlanoSemestre) -> EstadoPlano:
    if p.plano_id is None:
        return EstadoPlano.SEM_PLANO
    if not p.plano_enviado:
        return EstadoPlano.PLANO_NAO_ENVIADO
    if not p.plano_aprovado:
        return EstadoPlano.PLANO_EM_AVALIACAO
    if not p.relatorio_enviado:
        return EstadoPlano.RIT_A_PREENCHER
    if not p.relatorio_aprovado:
        return EstadoPlano.RIT_EM_AVALIACAO
    if not p.relatorio_publicado:
        return EstadoPlano.RIT_APROVADO
    return EstadoPlano.RIT_PUBLICADO


def _ch_total(doc) -> str | None:
    # Procura perto do rótulo: text_content() cola textos vizinhos ("2025.1" + "40,0").
    for el in doc.xpath("//*[contains(text(), 'C.H. Total')]"):
        for alvo in (el, el.getparent()):
            if alvo is not None and (m := re.search(r"(?<![\d.])(\d+(?:,\d+)?)\s*horas\s*C\.H\. Total",
                                                    h.texto(alvo))):
                return m[1]
    return None


def parse_plano(pagina: str, semestre: str) -> PlanoSemestre:
    doc = h.documento(pagina)
    secoes = h.secoes_accordion(doc)

    links: dict[str, str] = {}
    for a in doc.iter("a"):
        href = a.get("href") or ""
        if "/pit_rit_v2/" not in href:
            continue
        for chave, trecho in _ACOES.items():
            if f"/{trecho}/" in href:
                links.setdefault(chave, href)
    plano_id = next((int(m[1]) for chave in ("plano_pdf", "enviar_plano", "preencher_relatorio")
                     if (m := re.search(r"/(\d+)/$", links.get(chave, "")))), None)

    aval = secoes.get("Dados da Avaliação")
    dados = h.definicoes(aval) if aval is not None else {}
    historico = []
    if aval is not None:
        historico = [linha.strip() for linha in
                     re.split(r"(?=\b(?:PIT|RIT) - \d{2}/\d{2}/\d{4})", dados.get("Histórico", ""))
                     if linha.strip()]

    quadro: dict[str, str] = {}
    for t in h.tabelas_com(doc, "ATIVIDADE", "CH"):
        for linha in t.linhas:
            if len(linha) >= 2:
                quadro[linha[0].texto] = linha[1].texto
    ch_total = _ch_total(doc)

    atividades: dict[str, list[str]] = {}
    for titulo, corpo in secoes.items():
        if not re.match(r"\d\. Atividades", titulo):
            continue
        for t in h.tabelas(corpo):
            if "Descrição" not in t.cabecalhos:
                continue
            chave = t.caption or titulo
            idx = t.cabecalhos.index("Descrição")
            atividades[chave] = [linha[idx].texto for linha in t.linhas if len(linha) > idx]

    plano = PlanoSemestre(
        semestre=semestre,
        plano_id=plano_id,
        estado=EstadoPlano.SEM_PLANO,
        plano_enviado=_sim(dados.get("Plano Enviado")),
        plano_aprovado=_sim(dados.get("Plano Aprovado")),
        relatorio_enviado=_sim(dados.get("Relatório Enviado")),
        relatorio_aprovado=_sim(dados.get("Relatório Aprovado")),
        relatorio_publicado=_sim(dados.get("Relatório Publicado")),
        avaliador_plano=dados.get("Avaliador do Plano") or None,
        historico=historico,
        ch_total=ch_total,
        quadro_resumo=quadro,
        atividades_pit=atividades,
        links=links,
    )
    plano.estado = estado(plano)
    return plano


def carregar(client: SuapClient, semestre: str) -> PlanoSemestre:
    pagina = client.html(f"/edu/professor/?tab=planoatividades&ano-periodo={semestre}", aba=True)
    return parse_plano(pagina, semestre)


def carregar_todos(client: SuapClient) -> list[PlanoSemestre]:
    periodos = listar_periodos(client.html("/edu/professor/?tab=planoatividades", aba=True))
    return [carregar(client, p) for p in periodos]
