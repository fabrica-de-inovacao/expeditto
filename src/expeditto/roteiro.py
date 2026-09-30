"""Roteiro do RIT: em que passo o semestre está e qual é o próximo (porta de entrada única).

O assistente (MCP) e a interface do terminal consultam `situacao()` em vez de adivinhar a
ordem das ferramentas. O roteiro só lê o acervo local, sem acessar o SUAP.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime

from expeditto import acervo, auth, explicacoes, links, textos
from expeditto.models import Manifest, Pendencia, Topico

ETAPAS = ["login", "escolher_semestre", "coletar", "pendencias", "anexos", "relatos", "alteracoes",
          "previa", "concluido"]
ROTULOS = {
    "login": "Entrar no SUAP", "escolher_semestre": "Escolher o semestre", "coletar": "Coletar comprovantes",
    "pendencias": "Decidir pendências", "anexos": "Montar anexos", "relatos": "Escrever relatos",
    "alteracoes": "Alterações de atividades", "previa": "Conferir e salvar no SUAP", "concluido": "Pronto",
}


@dataclass
class Passo:
    etapa: str
    mensagem: str  # para o docente, no tom do Expeditto
    proximo: dict | None = None  # {"ferramenta": ..., "argumentos": {...}}
    dados: dict = field(default_factory=dict)

    def como_dict(self) -> dict:
        indice = ETAPAS.index(self.etapa)
        trilha = "  ".join(("✓" if i < indice else "◐" if i == indice else "·") + " " + ROTULOS[e]
                           for i, e in enumerate(ETAPAS[1:], start=1))
        return {**asdict(self), "passo": f"{indice}/{len(ETAPAS) - 1}", "trilha": trilha}


# -- pendências agrupadas -------------------------------------------------------------------
def _distribuicao_lattes(itens: list[Pendencia], codigo: str) -> str:
    deste = sum(1 for p in itens if p.detalhes.get("semestre_provavel") == codigo)
    outro = sum(1 for p in itens if p.detalhes.get("semestre_provavel") not in (None, codigo))
    sem = len(itens) - deste - outro
    partes = [f"{deste} parece(m) ser deste semestre" if deste else "",
              f"{outro} parece(m) ser de outro semestre" if outro else "",
              f"{sem} sem data" if sem and (deste or outro) else ""]
    partes = [x for x in partes if x]
    return ("Pelas datas das publicações: " + ", ".join(partes) + ".") if partes else ""


def _pergunta(tipo: str, itens: list[Pendencia], manifest: Manifest) -> str:
    exp = explicacoes.explicar(tipo)
    n = len(itens)
    if tipo == "lattes_sem_comprovante":
        cats = Counter(p.detalhes.get("categoria") or "item" for p in itens)
        detalhe = ", ".join(f"{v} {k}" for k, v in cats.most_common())
        base = (f"Achei {n} item(ns) do seu Lattes de {manifest.semestre.ano} sem comprovante no SUAP ({detalhe}). "
                f"{_distribuicao_lattes(itens, manifest.semestre.codigo)}").strip()
        return base + " Quais são deste semestre? Para esses, coloque o comprovante na pasta de entrada; "                       "os outros ficam de fora."
    opcoes = " / ".join(o["rotulo"] for o in explicacoes.opcoes(tipo))
    return f"{exp.titulo}: {n} item(ns). O que prefere para eles: {opcoes}?"


def pendencias_agrupadas(manifest: Manifest) -> list[dict]:
    """Pendências em aberto por tipo, com explicação, opções (e o efeito de cada uma) e, por item:
    resumo, sugestão e links para conferir no SUAP ou na publicação."""
    abertas = [(n, explicacoes.completar_detalhes(p)) for n, p in enumerate(manifest.pendencias, 1) if not p.resolucao]
    grupos: dict[str, list] = {}
    for n, p in abertas:
        grupos.setdefault(p.tipo, []).append((n, p))
    saida = []
    for tipo, itens in grupos.items():
        exp = explicacoes.explicar(tipo)
        saida.append({
            "tipo": tipo, "titulo": exp.titulo, "quantidade": len(itens), "numeros": [n for n, _ in itens],
            "o_que_e": exp.o_que_e, "por_que_importa": exp.por_que_importa, "dica": exp.dica,
            "opcoes": explicacoes.opcoes(tipo),
            "pergunta_sugerida": _pergunta(tipo, [p for _, p in itens], manifest),
            "itens": [{"numero": n, "resumo": explicacoes.resumo_item(p),
                       "sugestao": explicacoes.sugestao_item(p),
                       "links": links.de_pendencia(manifest, p)} for n, p in itens[:40]],
        })
    return saida


# -- estado do salvamento -------------------------------------------------------------------
def registrar_salvamento(codigo: str, url: str, url_pdf: str) -> None:
    destino = acervo.pasta_semestre(codigo) / "salvo.json"
    destino.write_text(json.dumps({"quando": datetime.now().isoformat(timespec="seconds"), "url": url,
                                   "url_pdf": url_pdf}, ensure_ascii=False), encoding="utf-8")


def salvamento(codigo: str) -> dict | None:
    origem = acervo.pasta_semestre(codigo) / "salvo.json"
    return json.loads(origem.read_text(encoding="utf-8")) if origem.exists() else None


def _mudou_depois_de_salvar(codigo: str, salvo: dict) -> bool:
    quando = datetime.fromisoformat(salvo["quando"]).timestamp()
    pasta = acervo.pasta_semestre(codigo)
    arquivos = list((pasta / "textos").glob("*.html")) + list((pasta / "anexos").glob("*.pdf"))
    return any(a.stat().st_mtime > quando + 1 for a in arquivos)


# -- o roteiro ----------------------------------------------------------------------------
def situacao(semestre: str | None, seguir_sem_decidir: bool = False,
             semestres_a_preencher: list[str] | None = None, exigir_sessao: bool = True) -> Passo:
    if exigir_sessao and not auth.carregar_sessao():
        return Passo("login", "Preciso que você entre no SUAP. Vou abrir uma janela; é só fazer o login.",
                     {"ferramenta": "login", "argumentos": {}})
    if not semestre:
        lista = semestres_a_preencher or []
        mensagem = ("Qual semestre vamos preparar? " + (f"RITs a preencher: {', '.join(lista)}." if lista else ""))
        return Passo("escolher_semestre", mensagem.strip(), None, {"semestres_a_preencher": lista})

    manifest = acervo.carregar_manifest(semestre)
    if not manifest:
        return Passo("coletar", f"Vou buscar seus comprovantes de {semestre} no SUAP. Leva de 2 a 8 minutos.",
                     {"ferramenta": "coletar_semestre", "argumentos": {"semestre": semestre}})

    grupos = pendencias_agrupadas(manifest)
    tem_texto = any(textos.carregar(semestre, t.value) for t in Topico)
    if grupos and not seguir_sem_decidir and not tem_texto:
        total = sum(g["quantidade"] for g in grupos)
        return Passo("pendencias",
                     f"Organizei tudo. Antes de escrever, preciso de você em {total} ponto(s), em {len(grupos)} "
                     f"grupo(s). Vamos um grupo por vez.",
                     {"ferramenta": "resolver_pendencia", "argumentos": {"semestre": semestre}},
                     {"grupos": grupos,
                      "dica": "Se o docente preferir deixar para depois, chame preparar_rit com "
                              "seguir_sem_decidir=true."})

    if not manifest.anexos:
        return Passo("anexos", "Agora vou montar um PDF de comprovantes por tópico (até 10 MB cada).",
                     {"ferramenta": "montar_anexos", "argumentos": {"semestre": semestre}})

    com_itens = {t for i in manifest.itens for t in i.topicos}
    faltando = [t.value for t in Topico if t in com_itens and not textos.carregar(semestre, t.value)]
    if faltando:
        return Passo("relatos",
                     f"Faltam os relatos de {len(faltando)} tópico(s). Vou escrever a partir dos comprovantes.",
                     {"ferramenta": "contexto_topico", "argumentos": {"semestre": semestre, "topico": faltando[0]}},
                     {"topicos_faltando": faltando,
                      "como": "Para cada tópico: contexto_topico → redigir → salvar_texto."})

    justificadas = [p for p in manifest.pendencias if p.resolucao == "justificar" and p.justificativa]
    if justificadas and not textos.carregar(semestre, "alteracoes"):
        return Passo("alteracoes", "Vou montar 'Alterações de Atividades' com as justificativas que você me deu.",
                     {"ferramenta": "gerar_alteracoes", "argumentos": {"semestre": semestre}})

    salvo = salvamento(semestre)
    if salvo and not _mudou_depois_de_salvar(semestre, salvo):
        return Passo("concluido", f"O RIT de {semestre} está salvo como rascunho no SUAP. Falta só você conferir "
                                  f"e entregar.", None, {"cartao": cartao(manifest, salvo)})
    return Passo("previa", "Tudo pronto. Vou te mostrar o que vai para o SUAP; só salvo com o seu OK.",
                 {"ferramenta": "previa_preenchimento", "argumentos": {"semestre": semestre}})


# -- cartão final -----------------------------------------------------------------------------
def cartao(manifest: Manifest, salvo: dict | None = None) -> str:
    por_topico = Counter(t for i in manifest.itens for t in i.topicos)
    linhas = [f"### {'✅ RIT ' + manifest.semestre.codigo + ' salvo como rascunho no SUAP' if salvo else 'RIT ' + manifest.semestre.codigo}",
              "", "| Tópico | Itens | Anexo |", "|---|---:|---|"]
    for t in Topico:
        anexo = manifest.anexos.get(t.value)
        linhas.append(f"| {t.rotulo} | {por_topico.get(t, 0)} | "
                      f"{f'{anexo.documentos} docs · {anexo.bytes / 1048576:.1f} MB' if anexo else '—'} |")
    decididas = sum(1 for p in manifest.pendencias if p.resolucao)
    linhas += ["", f"Pendências: {decididas} decididas · {len(manifest.pendencias) - decididas} em aberto"]
    if salvo:
        linhas += ["", f"🔎 Conferir (PDF do RIT): {salvo['url_pdf']}",
                   f"✏️ Editar e entregar no SUAP: {salvo['url']}",
                   "", "A entrega (**Submeter Relatório para Avaliação**) é feita por você, no SUAP."]
    return "\n".join(linhas)
