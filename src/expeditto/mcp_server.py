"""Servidor MCP local (stdio) do Expeditto — Claude Desktop/Code, Codex, Gemini/Antigravity CLI (D47).

Experiência no chat: o assistente reconhece pedidos sobre o RIT e começa por `preparar_rit`, que
diz em que passo o semestre está e qual é o próximo. Tarefas longas devolvem progresso em etapas
(`aguardar_tarefa`). Nada é impresso em stdout (é o canal do protocolo).
"""

from __future__ import annotations

import asyncio
import re
from collections import Counter

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from expeditto import (acervo, anexos, atas, atualizacao, auth, coleta, config, diagnostico as diag, entrada,
                       formulario,
                       gmail, pendencias, roteiro, tarefas, textos)
from expeditto.client import SessaoExpirada, SuapClient
from expeditto.models import EstadoPlano, Topico
from expeditto.suap import planos

INSTRUCOES = """\
Expeditto — assistente da burocracia docente ("seu segundo expediente, resolvido"). Hoje cuida do
Relatório Individual de Trabalho (RIT) do SUAP IFMA. Roda na máquina do docente, com a sessão dele.

QUANDO USAR: sempre que o docente falar de RIT, "relatório individual de trabalho", relatório do
semestre, PIT/plano individual de trabalho, comprovantes/declarações/portarias do SUAP, bancas,
orientações ou projetos para o relatório. Não peça que ele digite comandos: use as ferramentas.

COMO CONDUZIR:
1. Comece SEMPRE por `preparar_rit` (com o semestre, se ele disser qual). A resposta traz `etapa`,
   `mensagem` (fale com o docente nesse tom), `trilha` (mostre-a) e `proximo` (a ferramenta a chamar).
   Depois de cada passo concluído, chame `preparar_rit` de novo até a etapa "concluido".
2. Tarefas longas (login, coleta) devolvem `tarefa_id`. Chame `aguardar_tarefa` em sequência e, a cada
   resposta, MOSTRE ao docente a linha `progresso` (barra) e a linha `etapas`, sem enfeitar.
3. Pendências: apresente um GRUPO por vez usando a `pergunta_sugerida` e registre a decisão com
   `resolver_pendencia` (aceita vários números). NUNCA invente justificativas; use só o que o docente disser.
4. Atas: se você tiver integração de e-mail (ex.: Gmail), busque atas/convocações de reuniões, NDE,
   colegiado, comissões e bancas no período do semestre e chame `registrar_ata` para cada uma.
   Sem integração de e-mail, use `buscar_atas_gmail` (backup do Expeditto), se estiver configurado.
5. Relatos: para cada tópico, `contexto_topico` → redija (parágrafo + lista, só com os fatos e as
   `contagens` fornecidas) → `salvar_texto`.
6. Antes de salvar, mostre `previa_preenchimento` e peça confirmação explícita. Só então
   `salvar_no_suap(confirmado=true)`. Ao final, mostre o `cartao` exatamente como veio.
7. A ENTREGA (submeter para avaliação) é sempre do docente, no SUAP. Se algo falhar, use `diagnostico`.
8. Se `preparar_rit` trouxer `atualizacao`, avise o docente UMA vez (versão nova disponível) e ofereça atualizar.
   Só chame `atualizar_expeditto(confirmado=true)` se ele pedir.
"""

servidor = MCPServer(name="expeditto", title="Expeditto", instructions=INSTRUCOES,
                     version=atualizacao.versao_instalada())

# Anotações explícitas (sem elas, o protocolo assume "pode destruir" e "fala com o mundo externo",
# e os apps pedem confirmação a cada chamada). Só salvar_no_suap e atualizar_expeditto são sensíveis.
LEITURA = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
LEITURA_SUAP = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
ESCRITA_LOCAL = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
COLETA = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True)
SENSIVEL = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=True)
_tarefas = tarefas.Gerenciador()


def _erro_amigavel(erro: Exception) -> str:
    if isinstance(erro, SessaoExpirada):
        return "A sessão do SUAP expirou. Chame `login` para o docente entrar de novo."
    return f"{type(erro).__name__}: {erro}"


def _cliente() -> SuapClient:
    cookies = auth.carregar_sessao()
    if not cookies:
        raise SessaoExpirada()
    perfil = acervo.carregar_perfil()
    return SuapClient(cookies, matricula=perfil.matricula if perfil else None)


def _manifest(semestre: str):
    manifest = acervo.carregar_manifest(semestre)
    if not manifest:
        raise ValueError(f"Nada coletado para {semestre}: chame `preparar_rit` ou `coletar_semestre`.")
    return manifest


# -- porta de entrada ------------------------------------------------------------------------
@servidor.tool(annotations=LEITURA_SUAP)
def preparar_rit(semestre: str | None = None, seguir_sem_decidir: bool = False) -> dict:
    """PONTO DE PARTIDA para qualquer pedido sobre o RIT (Relatório Individual de Trabalho), o relatório do
    semestre ou os comprovantes do SUAP. Diz em que passo o semestre (AAAA.P) está e qual ferramenta chamar
    em seguida. Sem semestre, lista os RITs a preencher para o docente escolher."""
    a_preencher = None
    if not semestre and auth.carregar_sessao():
        try:
            with _cliente() as client:
                a_preencher = [p.semestre for p in planos.carregar_todos(client)
                               if p.estado == EstadoPlano.RIT_A_PREENCHER]
        except SessaoExpirada:
            auth.apagar_sessao()
    em_curso = _tarefas.em_andamento()
    passo = roteiro.situacao(semestre, seguir_sem_decidir, a_preencher).como_dict()
    if nova := atualizacao.verificar():
        passo["atualizacao"] = nova | {"como": "Avise o docente uma vez. Se ele quiser, chame `atualizar_expeditto`."}
    if em_curso:
        passo["tarefa_em_andamento"] = em_curso[0].visao()
        passo["proximo"] = {"ferramenta": "aguardar_tarefa", "argumentos": {"tarefa_id": em_curso[0].id}}
    return passo


@servidor.tool(annotations=LEITURA)
async def aguardar_tarefa(tarefa_id: str, segundos: int = 45) -> dict:
    """Espera uma tarefa em segundo plano avançar (até `segundos`, máx. 55) e devolve o progresso:
    `progresso` (barra), `etapas` e `detalhe`. Mostre a barra ao docente a cada chamada."""
    tarefa = _tarefas.obter(tarefa_id)
    if not tarefa:
        return {"erro": f"tarefa {tarefa_id} não encontrada"}
    limite = max(1, min(segundos, 55))
    inicio_pct = tarefa.percentual
    for _ in range(limite * 2):
        if tarefa.estado != "executando":
            break
        await asyncio.sleep(0.5)
        if tarefa.percentual - inicio_pct >= 25:  # devolve cedo quando há avanço visível
            break
    visao = tarefa.visao()
    if tarefa.estado == "concluida":
        visao["proximo"] = {"ferramenta": "preparar_rit", "argumentos": {}}
    return visao


@servidor.tool(annotations=LEITURA)
def status_tarefa(tarefa_id: str) -> dict:
    """Progresso atual de uma tarefa, sem esperar (prefira `aguardar_tarefa`)."""
    tarefa = _tarefas.obter(tarefa_id)
    return tarefa.visao() if tarefa else {"erro": f"tarefa {tarefa_id} não encontrada"}


@servidor.tool(annotations=LEITURA_SUAP)
def diagnostico(verificar_suap: bool = True) -> dict:
    """Verifica se o Expeditto está pronto: versão, pasta de dados, navegador, sessão no SUAP, perfil,
    apps de IA conectados e e-mail. Cada item traz `como_resolver` quando há problema."""
    return diag.como_dict(diag.executar(verificar_online=verificar_suap))


# -- sessão e semestres ------------------------------------------------------------------------
@servidor.tool(annotations=LEITURA_SUAP)
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


@servidor.tool(annotations=COLETA)
def login() -> dict:
    """Abre uma janela do SUAP para o docente fazer login (CAPTCHA/Gov.br); ela fecha sozinha.
    Devolve `tarefa_id`: acompanhe com `aguardar_tarefa` e avise o docente para olhar a janela."""
    def alvo(progresso):
        progresso("Janela do SUAP aberta: aguardando o seu login (até 10 min)", etapa="janela")
        cookies = auth.login_interativo()
        progresso("Carregando seu perfil", etapa="perfil")
        with SuapClient(cookies) as client:
            perfil = coleta.setup(client)
        return {"docente": perfil.nome, "matricula": perfil.matricula, "campus": perfil.campus}
    tarefa = _tarefas.iniciar("login", "Login no SUAP", alvo, _erro_amigavel)
    return tarefa.visao() | {"mensagem": "Abri uma janela do SUAP no seu computador. Faça o login nela."}


@servidor.tool(annotations=LEITURA_SUAP)
def listar_semestres() -> list[dict]:
    """Semestres com o estado do PIT/RIT e o link correspondente no SUAP."""
    with _cliente() as client:
        lista = planos.carregar_todos(client)
    return [{"semestre": p.semestre, "estado": p.estado.value,
             "link": config.BASE_URL + (p.links.get("preencher_relatorio") or p.links.get("relatorio_pdf") or "")
             if (p.links.get("preencher_relatorio") or p.links.get("relatorio_pdf")) else None}
            for p in lista]


@servidor.tool(annotations=COLETA)
def coletar_semestre(semestre: str) -> dict:
    """Coleta os comprovantes do semestre (AAAA.P) no SUAP, em segundo plano (2 a 8 minutos).
    Devolve `tarefa_id`: acompanhe com `aguardar_tarefa`, mostrando a barra ao docente."""
    em_curso = [t for t in _tarefas.em_andamento("coleta") if semestre in t.descricao]
    if em_curso:
        return em_curso[0].visao()

    def alvo(progresso):
        with _cliente() as client:
            perfil = acervo.carregar_perfil() or coleta.setup(client)
            manifest = coleta.coletar_semestre(client, perfil, semestre, progresso=progresso)
        return _resumo(manifest)
    return _tarefas.iniciar("coleta", f"Coleta {semestre}", alvo, _erro_amigavel).visao()


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


@servidor.tool(annotations=LEITURA)
def resumo_semestre(semestre: str) -> dict:
    """Resumo do acervo do semestre: itens por tópico, pendências numeradas, anexos e textos."""
    return _resumo(_manifest(semestre))


@servidor.tool(annotations=ESCRITA_LOCAL)
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


@servidor.tool(annotations=LEITURA)
def pasta_entrada(semestre: str) -> dict:
    """Onde o docente coloca comprovantes próprios (PDF/JPG/PNG), uma subpasta por tópico (E8)."""
    raiz = entrada.pasta(semestre)
    soltos = [p.name for p in raiz.iterdir() if p.is_file()]
    return {"pasta": str(raiz), "subpastas": [t.value for t in Topico], "arquivos_sem_topico": soltos,
            "dica": "Depois de adicionar arquivos, chame `montar_anexos` para incluí-los."}


@servidor.tool(annotations=ESCRITA_LOCAL)
def classificar_entrada(semestre: str, arquivo: str, topico: str) -> dict:
    """Move um arquivo solto da pasta de entrada para o tópico informado pelo docente."""
    destino = entrada.classificar(semestre, arquivo, topico)
    return {"movido_para": str(destino)}


@servidor.tool(annotations=LEITURA_SUAP)
def buscar_atas_gmail(semestre: str) -> dict:
    """BACKUP para hosts SEM integração de e-mail: busca atas no Gmail das contas autorizadas
    na CLI (`expeditto gmail-login`). Devolve candidatas numeradas; o docente escolhe quais registrar."""
    manifest = _manifest(semestre)
    if not gmail.contas():
        return {"erro": "nenhuma conta Gmail autorizada; peça ao docente para rodar `expeditto gmail-login`"}
    cand = gmail.buscar(manifest.semestre)
    return {"candidatas": [{"numero": n, "assunto": c.assunto, "data": c.data, "remetente": c.remetente,
                            "trecho": c.trecho[:200], "pdfs": c.anexos_pdf} for n, c in enumerate(cand, 1)]}


@servidor.tool(annotations=COLETA)
def registrar_atas_gmail(semestre: str, numeros: list[int]) -> dict:
    """Registra as candidatas escolhidas pelo docente (números de `buscar_atas_gmail`), baixando o PDF anexo."""
    registradas = gmail.registrar(semestre, numeros)
    manifest = _manifest(semestre)
    atas.aplicar(manifest)
    pendencias.aplicar(manifest)
    acervo.salvar_manifest(manifest)
    return {"registradas": [{"assunto": a["assunto"], "anexo_original": a["anexo_original"]} for a in registradas]}


@servidor.tool(annotations=ESCRITA_LOCAL)
def resolver_pendencia(semestre: str, numeros: list[int], decisao: str, justificativa: str | None = None) -> dict:
    """Registra a decisão DO DOCENTE sobre uma ou mais pendências (números vindos de `preparar_rit`/`resumo_semestre`).
    decisao: manter | remover_item | justificar (exige justificativa ditada pelo docente) | ignorar.
    Pendências 'lattes_sem_comprovante': se o docente tiver o comprovante, oriente-o a colocá-lo na
    pasta de entrada (ver `pasta_entrada`) e marque 'manter'; se não entra no RIT, 'ignorar'."""
    manifest = pendencias.resolver(_manifest(semestre), numeros, decisao, justificativa)
    todas = _resumo(manifest)["pendencias"]
    return {"atualizadas": [todas[n - 1] for n in numeros]}


@servidor.tool(annotations=ESCRITA_LOCAL)
def montar_anexos(semestre: str) -> dict:
    """Gera o PDF de anexo de cada tópico (capa + índice + comprovantes, até 10 MB)."""
    perfil = acervo.carregar_perfil()
    manifest = anexos.montar(_manifest(semestre), perfil.nome if perfil else "")
    return _resumo(manifest)["anexos"] | {"pasta": str(acervo.pasta_semestre(semestre) / "anexos")}


@servidor.tool(annotations=LEITURA)
def contexto_topico(semestre: str, topico: str) -> dict:
    """Fatos de um tópico para redigir o Relato. topico: apoio_ensino, programas_projetos_ensino,
    orientacao_alunos, reunioes, pesquisa, extensao, gestao."""
    ctx = textos.contexto_topico(_manifest(semestre), Topico(topico))
    ctx["texto_atual"] = textos.carregar(semestre, topico)
    return ctx


@servidor.tool(annotations=ESCRITA_LOCAL)
def salvar_texto(semestre: str, topico: str, html: str) -> dict:
    """Grava o Relato (HTML simples: p, ul, li, strong) de um tópico ou de 'alteracoes'."""
    if topico != "alteracoes":
        Topico(topico)
    if "<script" in html.lower() or "<iframe" in html.lower():
        raise ValueError("HTML não permitido (script/iframe)")
    destino = textos.salvar(semestre, topico, html)
    return {"salvo": str(destino), "caracteres": len(html)}


@servidor.tool(annotations=ESCRITA_LOCAL)
def gerar_rascunhos(semestre: str, sobrescrever: bool = False) -> dict:
    """Gera rascunhos automáticos dos Relatos (não sobrescreve textos já revisados, salvo se pedido)."""
    gerados = textos.gerar_rascunhos(_manifest(semestre), sobrescrever=sobrescrever)
    return {"gerados": sorted(gerados)}


@servidor.tool(annotations=ESCRITA_LOCAL)
def gerar_alteracoes(semestre: str) -> dict:
    """Monta 'Alterações de Atividades' a partir das pendências justificadas pelo docente."""
    conteudo = pendencias.gerar_alteracoes(_manifest(semestre))
    return {"alteracoes": conteudo or "(nenhuma pendência justificada)"}


@servidor.tool(annotations=LEITURA)
def previa_preenchimento(semestre: str) -> dict:
    """O que será enviado ao formulário do RIT (textos e anexos) — mostre ao docente antes de salvar."""
    manifest = _manifest(semestre)
    envio = formulario.preparar(manifest)
    return {"plano_id": manifest.plano.plano_id if manifest.plano else None, "resumo": envio.resumo(),
            "pendencias_sem_decisao": sum(1 for p in manifest.pendencias if not p.resolucao)}


@servidor.tool(annotations=SENSIVEL)
def salvar_no_suap(semestre: str, confirmado: bool = False) -> dict:
    """Grava textos e anexos no formulário do RIT como RASCUNHO ("Salvar"). Nunca entrega.
    Só chame com confirmado=true depois que o docente aprovar a prévia explicitamente."""
    if not confirmado:
        return {"salvo": False, "motivo": "confirmação do docente necessária (confirmado=true)"}
    with _cliente() as client:
        r = formulario.salvar_semestre(client, semestre)
    salvo = roteiro.salvamento(semestre)
    return {"salvo": True, "textos_conferidos": all(r.textos_conferem.values()),
            "anexos_no_formulario": len(r.anexos_depois),
            "cartao": roteiro.cartao(_manifest(semestre), salvo or {"url": r.url, "url_pdf": r.url_relatorio_pdf}),
            "instrucao": "Mostre o `cartao` ao docente exatamente como veio."}


# -- versão -------------------------------------------------------------------------------------
@servidor.tool(annotations=LEITURA_SUAP)
def verificar_atualizacao() -> dict:
    """Diz se há versão nova do Expeditto (consulta a última release; cache de um dia)."""
    nova = atualizacao.verificar(forcar=True)
    if not nova:
        return {"atualizado": True, "versao": atualizacao.versao_instalada()}
    return {"atualizado": False, **nova}


@servidor.tool(annotations=SENSIVEL)
def atualizar_expeditto(confirmado: bool = False) -> dict:
    """Atualiza o Expeditto para a versão mais nova. Só chame com confirmado=true se o docente pedir.
    Depois, o app de IA precisa ser reiniciado (ou o Expeditto reconectado) para usar a versão nova."""
    nova = atualizacao.verificar(forcar=True)
    if not nova:
        return {"atualizado": True, "versao": atualizacao.versao_instalada()}
    if not confirmado:
        return {"atualizado": False, "motivo": "confirmação do docente necessária (confirmado=true)", **nova}
    # No Windows o servidor trava os próprios arquivos: um processo separado fecha os servidores do Expeditto
    # (este e os de outros apps) e reinstala. A conexão com o app cai em alguns segundos.
    resultado = atualizacao.atualizar(nova["disponivel"])
    if resultado.get("agendada"):
        resultado["proximo_passo"] = ("Avise o docente: o Expeditto vai se desconectar em alguns segundos para se "
                                      "atualizar. Em cerca de 1 minuto, reinicie o app de IA (ou reconecte o "
                                      "Expeditto) para usar a versão nova.")
    else:
        resultado["proximo_passo"] = "Reinicie o app de IA (ou reconecte o Expeditto) para usar a versão nova."
    return resultado


def main() -> None:
    import logging

    logging.getLogger("httpx").setLevel(logging.WARNING)  # não expor URLs do SUAP nos logs do host
    servidor.run("stdio")


if __name__ == "__main__":
    main()
