"""E1 — servidor MCP local (stdio) para Claude Desktop/Code, Codex e Gemini/Antigravity CLI (D47).

Ferramentas de alto nível sobre o núcleo. Operações longas (login, coleta)
rodam em segundo plano e devolvem um `tarefa_id` para `status_tarefa`.
Nada é impresso em stdout (é o canal do protocolo).
"""

from __future__ import annotations

import re
import threading
import traceback
import uuid
from collections import Counter
from datetime import datetime
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from expeditto import acervo, anexos, atas, auth, coleta, config, entrada, formulario, gmail, pendencias, textos
from expeditto.client import SessaoExpirada, SuapClient
from expeditto.models import Topico
from expeditto.suap import planos

INSTRUCOES = """\
Expeditto — assistente da burocracia docente ("seu segundo expediente, resolvido"). Hoje cuida do
Relatório Individual de Trabalho (RIT) do SUAP IFMA. Roda na máquina do docente, com a sessão dele.

Fluxo típico:
1. `status_sessao`; se não houver sessão, `login` (abre janela do SUAP; o docente loga) e acompanhe com `status_tarefa`.
2. `listar_semestres` → escolha com o docente o semestre (formato AAAA.P).
3. `coletar_semestre` (tarefa em segundo plano) → `status_tarefa` até concluir → `resumo_semestre`.
4. Atas por e-mail: se você tiver uma integração de e-mail (ex.: Gmail), busque atas/convocações de reuniões,
   NDE, colegiado, comissões e bancas no período do semestre, nas contas institucional e acadêmica do docente,
   e chame `registrar_ata` para cada uma (envie o PDF em base64 se conseguir ler o anexo).
5. Pendências: apresente cada uma ao docente e registre a decisão dele com `resolver_pendencia`.
   NUNCA invente justificativas: use apenas o que o docente disser.
6. `montar_anexos` → para cada tópico, `contexto_topico` e redija o Relato (parágrafo-síntese + lista com
   título, papel, período e "Doc. N do anexo"), usando só os fatos fornecidos; grave com `salvar_texto`.
   Alternativa rápida: `gerar_rascunhos`. Depois `gerar_alteracoes`.
7. `previa_preenchimento` → mostre ao docente → só com confirmação explícita dele, `salvar_no_suap(confirmado=true)`.
8. Entregue os links devolvidos. A ENTREGA (submeter para avaliação) é sempre feita pelo docente no SUAP.
"""

servidor = MCPServer(name="expeditto", title="Expeditto", instructions=INSTRUCOES, version="0.2.0")

# -- tarefas em segundo plano ------------------------------------------------------
_tarefas: dict[str, dict[str, Any]] = {}
_trava = threading.Lock()


def _iniciar(descricao: str, alvo) -> dict:
    tarefa_id = uuid.uuid4().hex[:8]
    registro = {"id": tarefa_id, "descricao": descricao, "estado": "executando", "progresso": [],
                "inicio": datetime.now().isoformat(timespec="seconds"), "resultado": None, "erro": None}
    with _trava:
        _tarefas[tarefa_id] = registro

    def executar():
        try:
            registro["resultado"] = alvo(lambda msg: registro["progresso"].append(msg))
            registro["estado"] = "concluida"
        except SessaoExpirada:
            registro["estado"], registro["erro"] = "erro", "Sessão do SUAP expirada: chame `login`."
        except Exception as erro:  # noqa: BLE001 — erro vai para o host, não derruba o servidor
            registro["estado"], registro["erro"] = "erro", f"{type(erro).__name__}: {erro}"
            registro["detalhe"] = traceback.format_exc(limit=3)

    threading.Thread(target=executar, daemon=True).start()
    return {"tarefa_id": tarefa_id, "estado": "executando", "descricao": descricao}


def _cliente() -> SuapClient:
    cookies = auth.carregar_sessao()
    if not cookies:
        raise SessaoExpirada()
    perfil = acervo.carregar_perfil()
    return SuapClient(cookies, matricula=perfil.matricula if perfil else None)


def _manifest(semestre: str):
    manifest = acervo.carregar_manifest(semestre)
    if not manifest:
        raise ValueError(f"Nada coletado para {semestre}: chame `coletar_semestre` primeiro.")
    return manifest


# -- ferramentas ----------------------------------------------------------------------
@servidor.tool(annotations=ToolAnnotations(readOnlyHint=True))
def status_sessao() -> dict:
    """Verifica se há sessão válida no SUAP e quem é o docente."""
    try:
        with _cliente() as client:
            pagina = client.html("/edu/professor/?tab=planoatividades", aba=True)
        from expeditto.suap.perfil import identificar
        nome, matricula, _ = identificar(pagina)
        return {"sessao": "ativa", "docente": nome, "matricula": matricula, "acervo": str(config.home())}
    except (SessaoExpirada, ValueError):
        return {"sessao": "ausente_ou_expirada", "acao": "chame `login` e peça ao docente para entrar no SUAP"}


@servidor.tool()
def login() -> dict:
    """Abre uma janela do SUAP para o docente fazer login (CAPTCHA/Gov.br). A janela fecha sozinha."""
    def alvo(progresso):
        progresso("janela de login aberta; aguardando o docente (até 10 min)")
        cookies = auth.login_interativo()
        with SuapClient(cookies) as client:
            perfil = coleta.setup(client)
        return {"docente": perfil.nome, "matricula": perfil.matricula, "campus": perfil.campus}
    return _iniciar("login no SUAP", alvo)


@servidor.tool(annotations=ToolAnnotations(readOnlyHint=True))
def status_tarefa(tarefa_id: str) -> dict:
    """Estado de uma tarefa em segundo plano (login, coleta)."""
    registro = _tarefas.get(tarefa_id)
    if not registro:
        return {"erro": f"tarefa {tarefa_id} não encontrada"}
    return {k: v for k, v in registro.items() if k != "detalhe"} | {"progresso": registro["progresso"][-8:]}


@servidor.tool(annotations=ToolAnnotations(readOnlyHint=True))
def listar_semestres() -> list[dict]:
    """Semestres com o estado do PIT/RIT e o link correspondente no SUAP."""
    with _cliente() as client:
        lista = planos.carregar_todos(client)
    return [{"semestre": p.semestre, "estado": p.estado.value,
             "link": config.BASE_URL + (p.links.get("preencher_relatorio") or p.links.get("relatorio_pdf") or "")
             if (p.links.get("preencher_relatorio") or p.links.get("relatorio_pdf")) else None}
            for p in lista]


@servidor.tool()
def coletar_semestre(semestre: str) -> dict:
    """Coleta evidências e comprovantes do semestre (AAAA.P) no SUAP. Roda em segundo plano (alguns minutos)."""
    def alvo(progresso):
        with _cliente() as client:
            perfil = acervo.carregar_perfil() or coleta.setup(client)
            manifest = coleta.coletar_semestre(client, perfil, semestre, progresso=progresso)
        return _resumo(manifest)
    return _iniciar(f"coleta {semestre}", alvo)


_LATTES = re.compile(r"Lattes \((?P<cat>[^,]+), (?P<ano>\d{4})\): (?P<tit>.+?) — sem comprovante")


def _pendencia_resumida(n: int, p) -> dict:
    if p.tipo == "lattes_sem_comprovante" and (m := _LATTES.search(p.mensagem)):
        return {"numero": n, "tipo": p.tipo, "categoria": m["cat"], "titulo": m["tit"], "decisao": p.resolucao}
    return {"numero": n, "tipo": p.tipo, "mensagem": p.mensagem, "decisao": p.resolucao}


def _resumo(manifest) -> dict:
    por_topico = Counter(t.value for i in manifest.itens for t in i.topicos)
    lattes = Counter(m["cat"] for p in manifest.pendencias
                     if p.tipo == "lattes_sem_comprovante" and not p.resolucao and (m := _LATTES.search(p.mensagem)))
    return {
        "semestre": manifest.semestre.codigo,
        "periodo": f"{manifest.semestre.inicio} a {manifest.semestre.fim} ({manifest.semestre.fonte_datas})",
        "estado_plano": manifest.plano.estado.value if manifest.plano else None,
        "itens_por_topico": {t.value: por_topico.get(t.value, 0) for t in Topico},
        "pendencias_por_tipo": dict(Counter(p.tipo for p in manifest.pendencias if not p.resolucao)),
        "lattes_sem_comprovante_por_categoria": dict(lattes),
        "orientacao_lattes": ("Itens do Lattes do ano sem comprovante no SUAP (o Lattes só informa o ano). "
                              "Pergunte ao docente, por categoria, quais são deste semestre: com comprovante → "
                              "pasta de entrada + 'manter'; fora do semestre ou sem comprovante → 'ignorar'.")
        if lattes else None,
        "pendencias": [_pendencia_resumida(n, p) for n, p in enumerate(manifest.pendencias, 1)],
        "anexos": {k: {"documentos": a.documentos, "paginas": a.paginas, "mb": round(a.bytes / 1048576, 2)}
                   for k, a in manifest.anexos.items()},
        "textos_prontos": [t.value for t in Topico if textos.carregar(manifest.semestre.codigo, t.value)],
    }


@servidor.tool(annotations=ToolAnnotations(readOnlyHint=True))
def resumo_semestre(semestre: str) -> dict:
    """Resumo do acervo do semestre: itens por tópico, pendências numeradas, anexos e textos."""
    return _resumo(_manifest(semestre))


@servidor.tool()
def registrar_ata(semestre: str, assunto: str, data: str, remetente: str, id_mensagem: str = "",
                  texto: str = "", anexo_base64: str | None = None, anexo_nome: str | None = None) -> dict:
    """Registra uma ata/convocação encontrada no e-mail (pela integração de e-mail do host).
    `data` em dd/mm/aaaa ou aaaa-mm-dd. Envie o PDF anexo em base64 se tiver acesso a ele."""
    ata = atas.registrar(semestre, assunto, data, remetente, id_mensagem, texto, anexo_base64, anexo_nome)
    manifest = acervo.carregar_manifest(semestre)
    if manifest:
        atas.aplicar(manifest)
        pendencias.aplicar(manifest)
        acervo.salvar_manifest(manifest)
    return {"registrada": ata["id"], "anexo_original": ata["anexo_original"],
            "observacao": None if ata["anexo_original"] else "gerado PDF com o corpo do e-mail; pendência criada"}


@servidor.tool(annotations=ToolAnnotations(readOnlyHint=True))
def pasta_entrada(semestre: str) -> dict:
    """Onde o docente coloca comprovantes próprios (PDF/JPG/PNG), uma subpasta por tópico (E8)."""
    raiz = entrada.pasta(semestre)
    soltos = [p.name for p in raiz.iterdir() if p.is_file()]
    return {"pasta": str(raiz), "subpastas": [t.value for t in Topico], "arquivos_sem_topico": soltos,
            "dica": "Depois de adicionar arquivos, chame `montar_anexos` para incluí-los."}


@servidor.tool()
def classificar_entrada(semestre: str, arquivo: str, topico: str) -> dict:
    """Move um arquivo solto da pasta de entrada para o tópico informado pelo docente."""
    destino = entrada.classificar(semestre, arquivo, topico)
    return {"movido_para": str(destino)}


@servidor.tool()
def buscar_atas_gmail(semestre: str) -> dict:
    """BACKUP para hosts SEM integração de e-mail: busca atas no Gmail das contas autorizadas
    na CLI (`expeditto gmail-login`). Devolve candidatas numeradas; o docente escolhe quais registrar."""
    manifest = _manifest(semestre)
    if not gmail.contas():
        return {"erro": "nenhuma conta Gmail autorizada; peça ao docente para rodar `expeditto gmail-login`"}
    cand = gmail.buscar(manifest.semestre)
    return {"candidatas": [{"numero": n, "assunto": c.assunto, "data": c.data, "remetente": c.remetente,
                            "trecho": c.trecho[:200], "pdfs": c.anexos_pdf} for n, c in enumerate(cand, 1)]}


@servidor.tool()
def registrar_atas_gmail(semestre: str, numeros: list[int]) -> dict:
    """Registra as candidatas escolhidas pelo docente (números de `buscar_atas_gmail`), baixando o PDF anexo."""
    registradas = gmail.registrar(semestre, numeros)
    manifest = _manifest(semestre)
    atas.aplicar(manifest)
    pendencias.aplicar(manifest)
    acervo.salvar_manifest(manifest)
    return {"registradas": [{"assunto": a["assunto"], "anexo_original": a["anexo_original"]} for a in registradas]}


@servidor.tool()
def resolver_pendencia(semestre: str, numeros: list[int], decisao: str, justificativa: str | None = None) -> dict:
    """Registra a decisão DO DOCENTE sobre uma ou mais pendências (números de resumo_semestre).
    decisao: manter | remover_item | justificar (exige justificativa ditada pelo docente) | ignorar.
    Pendências 'lattes_sem_comprovante': se o docente tiver o comprovante, oriente-o a colocá-lo na
    pasta de entrada (ver `pasta_entrada`) e marque 'manter'; se não entra no RIT, 'ignorar'."""
    manifest = pendencias.resolver(_manifest(semestre), numeros, decisao, justificativa)
    todas = _resumo(manifest)["pendencias"]
    return {"atualizadas": [todas[n - 1] for n in numeros]}


@servidor.tool()
def montar_anexos(semestre: str) -> dict:
    """Gera o PDF de anexo de cada tópico (capa + índice + comprovantes, até 10 MB)."""
    perfil = acervo.carregar_perfil()
    manifest = anexos.montar(_manifest(semestre), perfil.nome if perfil else "")
    return _resumo(manifest)["anexos"] | {"pasta": str(acervo.pasta_semestre(semestre) / "anexos")}


@servidor.tool(annotations=ToolAnnotations(readOnlyHint=True))
def contexto_topico(semestre: str, topico: str) -> dict:
    """Fatos de um tópico para redigir o Relato. topico: apoio_ensino, programas_projetos_ensino,
    orientacao_alunos, reunioes, pesquisa, extensao, gestao."""
    ctx = textos.contexto_topico(_manifest(semestre), Topico(topico))
    ctx["texto_atual"] = textos.carregar(semestre, topico)
    return ctx


@servidor.tool()
def salvar_texto(semestre: str, topico: str, html: str) -> dict:
    """Grava o Relato (HTML simples: p, ul, li, strong) de um tópico ou de 'alteracoes'."""
    if topico != "alteracoes":
        Topico(topico)
    if "<script" in html.lower() or "<iframe" in html.lower():
        raise ValueError("HTML não permitido (script/iframe)")
    destino = textos.salvar(semestre, topico, html)
    return {"salvo": str(destino), "caracteres": len(html)}


@servidor.tool()
def gerar_rascunhos(semestre: str, sobrescrever: bool = False) -> dict:
    """Gera rascunhos automáticos dos Relatos (não sobrescreve textos já revisados, salvo se pedido)."""
    gerados = textos.gerar_rascunhos(_manifest(semestre), sobrescrever=sobrescrever)
    return {"gerados": sorted(gerados)}


@servidor.tool()
def gerar_alteracoes(semestre: str) -> dict:
    """Monta 'Alterações de Atividades' a partir das pendências justificadas pelo docente."""
    conteudo = pendencias.gerar_alteracoes(_manifest(semestre))
    return {"alteracoes": conteudo or "(nenhuma pendência justificada)"}


@servidor.tool(annotations=ToolAnnotations(readOnlyHint=True))
def previa_preenchimento(semestre: str) -> dict:
    """O que será enviado ao formulário do RIT (textos e anexos) — mostre ao docente antes de salvar."""
    manifest = _manifest(semestre)
    envio = formulario.preparar(manifest)
    return {"plano_id": manifest.plano.plano_id if manifest.plano else None, "resumo": envio.resumo(),
            "pendencias_sem_decisao": sum(1 for p in manifest.pendencias if not p.resolucao)}


@servidor.tool(annotations=ToolAnnotations(destructiveHint=True, idempotentHint=True))
def salvar_no_suap(semestre: str, confirmado: bool = False) -> dict:
    """Grava textos e anexos no formulário do RIT como RASCUNHO ("Salvar"). Nunca entrega.
    Só chame com confirmado=true depois que o docente aprovar a prévia explicitamente."""
    if not confirmado:
        return {"salvo": False, "motivo": "confirmação do docente necessária (confirmado=true)"}
    with _cliente() as client:
        r = formulario.salvar_semestre(client, semestre)
    return {"salvo": True, "textos_conferidos": r.textos_conferem, "anexos_no_formulario": sorted(r.anexos_depois),
            "link_previa_pdf": r.url_relatorio_pdf, "link_formulario": r.url,
            "proximo_passo": "O docente confere e, se estiver de acordo, clica em 'Submeter Relatório para "
                             "Avaliação' no SUAP."}


def main() -> None:
    import logging

    logging.getLogger("httpx").setLevel(logging.WARNING)  # não expor URLs do SUAP nos logs do host
    servidor.run("stdio")


if __name__ == "__main__":
    main()
