"""E3 — "Relatos" dos tópicos do RIT (D4, D5, D7).

O PDF do RIT já imprime, por tópico, a CH e as atividades do catálogo marcadas
no PIT; o relato deve dizer **o que foi feito**: itens concretos, papel,
período e onde está o comprovante no anexo. Nada é afirmado sem evidência.

- `contexto_topico`: fatos estruturados para o LLM do host redigir (MCP).
- `rascunho_html`: rascunho determinístico (CLI e fallback): parágrafo + lista.
"""

from __future__ import annotations

import html
import re
from collections import Counter
from pathlib import Path

from expeditto import acervo
from expeditto.anexos import _periodo, documentos_do_topico
from expeditto.coleta import CATEGORIAS_PIT
from expeditto.models import Manifest, TipoEvidencia, Topico

_ROTULO_TIPO = {
    TipoEvidencia.DIARIO: ("componente curricular ministrado", "componentes curriculares ministrados"),
    TipoEvidencia.ESTAGIO: ("orientação de estágio", "orientações de estágio"),
    TipoEvidencia.ORIENTACAO_TCC: ("orientação de trabalho de conclusão", "orientações de trabalho de conclusão"),
    TipoEvidencia.COORIENTACAO_TCC: ("coorientação de trabalho de conclusão", "coorientações de trabalho de conclusão"),
    TipoEvidencia.BANCA: ("participação em banca", "participações em bancas"),
    TipoEvidencia.ORIENTACAO_PROJETO: ("orientação de discentes em projeto", "orientações de discentes em projetos"),
    TipoEvidencia.PROJETO_PESQUISA: ("projeto de pesquisa", "projetos de pesquisa"),
    TipoEvidencia.PROJETO_EXTENSAO: ("projeto de extensão", "projetos de extensão"),
    TipoEvidencia.PROJETO_ENSINO: ("projeto de ensino", "projetos de ensino"),
    TipoEvidencia.PORTARIA: ("designação por portaria", "designações por portaria"),
    TipoEvidencia.FUNCAO: ("função exercida", "funções exercidas"),
    TipoEvidencia.CAPACITACAO: ("formação/encontro pedagógico", "formações/encontros pedagógicos"),
    TipoEvidencia.ATA: ("ata/convocação de reunião", "atas/convocações de reuniões"),
    TipoEvidencia.MANUAL: ("comprovante adicional", "comprovantes adicionais"),
}


def atividades_do_pit(manifest: Manifest, topico: Topico) -> list[str]:
    if not manifest.plano:
        return []
    for categoria, atividades in manifest.plano.atividades_pit.items():
        if next((t for padrao, t in CATEGORIAS_PIT if re.search(padrao, categoria, re.I)), None) == topico:
            return atividades
    return []


def contexto_topico(manifest: Manifest, topico: Topico) -> dict:
    """Fatos do tópico, com a referência de cada comprovante no anexo (documento nº e página)."""
    docs = documentos_do_topico(manifest, topico)
    ref_por_arquivo = {str(d.arquivo): i for i, d in enumerate(docs, 1)}
    itens = []
    for item in manifest.itens:
        if topico not in item.topicos:
            continue
        ev = manifest.evidencias[item.evidencia_id]
        arquivo = str(acervo.config.home() / item.arquivo) if item.arquivo else None
        itens.append({
            "id": ev.id,
            "tipo": ev.tipo.value,
            "titulo": ev.titulo,
            "descricao": ev.descricao,
            "papel": ev.papel,
            "periodo": _periodo(ev),
            "carga_horaria": ev.extras.get("carga_horaria"),
            "comprovante_no_anexo": ref_por_arquivo.get(str(Path(arquivo))) if arquivo else None,
            "motivo_classificacao": item.motivo,
            "comprovado_por": ev.extras.get("comprovada_por"),
        })
    # função comprovada por portaria de designação: aponta o documento da portaria
    doc_por_evidencia = {it["id"]: it["comprovante_no_anexo"] for it in itens if it.get("id")}
    for it in itens:
        if it["comprovado_por"]:
            it["comprovado_por_doc"] = doc_por_evidencia.get(it["comprovado_por"])
    plano = manifest.plano
    return {
        "semestre": manifest.semestre.codigo,
        "periodo_letivo": f"{manifest.semestre.inicio} a {manifest.semestre.fim}",
        "topico": topico.rotulo,
        "ch_prevista_no_pit": plano.quadro_resumo.get(topico.rotulo.upper()) if plano else None,
        "atividades_previstas_no_pit": atividades_do_pit(manifest, topico),
        "contagens": _contagens(itens),
        "itens": itens,
        "instrucoes": ("Redija o 'Relato' deste tópico em português formal: um parágrafo-síntese e depois uma "
                       "lista dos itens (título, papel, período e 'Doc. N do anexo'). Use apenas os fatos "
                       "fornecidos; não invente atividades, números ou resultados. Para quantidades, use "
                       "EXATAMENTE os números de 'contagens' (não conte você mesmo). HTML simples: <p>, <ul>, "
                       "<li>, <strong>."),
    }


def _contagens(itens: list[dict]) -> dict:
    por_tipo = Counter(i["tipo"] for i in itens)
    por_papel = Counter(f"{i['tipo']}|{i['papel']}" for i in itens if i["papel"])
    return {"total_itens": len(itens), "por_tipo": dict(por_tipo),
            "por_tipo_e_papel": {k: v for k, v in por_papel.items()},
            "documentos_no_anexo": len({i["comprovante_no_anexo"] for i in itens if i["comprovante_no_anexo"]})}


def _item_html(i: dict) -> str:
    partes = [f"<strong>{html.escape(i['titulo'])}</strong>"]
    if i["descricao"] and i["tipo"] in ("estagio", "orientacao_tcc", "coorientacao_tcc", "banca", "portaria"):
        descricao = i["descricao"] if len(i["descricao"]) <= 160 else i["descricao"][:157].rsplit(" ", 1)[0] + "..."
        partes.append(html.escape(descricao))
    papel = i["papel"] if i["papel"] and i["papel"].lower() != i["titulo"].lower() else None
    detalhes = [x for x in (papel, i["periodo"], i["carga_horaria"]) if x]
    if detalhes:
        partes.append(html.escape(", ".join(detalhes)))
    if i["comprovante_no_anexo"]:
        partes.append(f"Doc. {i['comprovante_no_anexo']} do anexo")
    elif i.get("comprovado_por_doc"):
        partes.append(f"comprovada pelo Doc. {i['comprovado_por_doc']} do anexo")
    return "<li>" + " — ".join(partes) + "</li>"


def rascunho_html(manifest: Manifest, topico: Topico) -> str:
    ctx = contexto_topico(manifest, topico)
    if not ctx["itens"]:
        return ""
    contagem = Counter(i["tipo"] for i in ctx["itens"])
    partes = []
    for tipo, n in contagem.most_common():
        singular, plural = _ROTULO_TIPO.get(TipoEvidencia(tipo), (tipo, tipo))
        partes.append(f"{n} {singular if n == 1 else plural}")
    resumo = ", ".join(partes[:-1]) + (" e " if len(partes) > 1 else "") + partes[-1]
    s = manifest.semestre
    periodo = (f" ({s.inicio.strftime('%d/%m/%Y')} a {s.fim.strftime('%d/%m/%Y')})"
               if s.inicio and s.fim else "")
    paragrafo = (f"<p>No semestre {s.codigo}{periodo}, as atividades deste eixo compreenderam {resumo}, "
                 f"conforme detalhado abaixo. Os comprovantes estão reunidos no arquivo anexo a este tópico, "
                 f"na ordem do índice da primeira página.</p>")
    itens = sorted(ctx["itens"], key=lambda i: (i["tipo"], i["titulo"]))
    return paragrafo + "<ul>" + "".join(_item_html(i) for i in itens) + "</ul>"


def pasta_textos(codigo: str) -> Path:
    pasta = acervo.pasta_semestre(codigo) / "textos"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def salvar(codigo: str, topico: str, conteudo: str) -> Path:
    destino = pasta_textos(codigo) / f"{topico}.html"
    destino.write_text(conteudo, encoding="utf-8")
    return destino


def carregar(codigo: str, topico: str) -> str | None:
    origem = pasta_textos(codigo) / f"{topico}.html"
    return origem.read_text(encoding="utf-8") if origem.exists() else None


def gerar_rascunhos(manifest: Manifest, sobrescrever: bool = False) -> dict[str, Path]:
    """Gera rascunhos para os tópicos sem texto (não sobrescreve texto revisado)."""
    gerados = {}
    for topico in Topico:
        if not sobrescrever and carregar(manifest.semestre.codigo, topico.value) is not None:
            continue
        conteudo = rascunho_html(manifest, topico)
        if conteudo:
            gerados[topico.value] = salvar(manifest.semestre.codigo, topico.value, conteudo)
    return gerados
