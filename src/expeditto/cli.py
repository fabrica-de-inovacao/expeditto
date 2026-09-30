"""CLI `expeditto` — casca fina sobre o núcleo (o MCP usará as mesmas funções)."""

from __future__ import annotations

from collections import Counter

import typer

from expeditto import acervo, auth, coleta, config
from expeditto.client import SessaoExpirada, SuapClient
from expeditto.models import Perfil, Topico
from expeditto.suap import planos

app = typer.Typer(help="Expeditto · seu segundo expediente, resolvido. Prepara o RIT do SUAP IFMA a partir dos seus "
                       "comprovantes. Sem comando, abre a interface visual.",
                  invoke_without_command=True)


def _avisar_atualizacao() -> None:
    from expeditto import atualizacao

    if nova := atualizacao.verificar():
        typer.secho(f"{nova['mensagem']} Para atualizar: expeditto atualizar", fg="yellow", err=True)


@app.callback()
def inicio(ctx: typer.Context,
           alto_contraste: bool = typer.Option(False, "--alto-contraste", help="Cores de alto contraste."),
           semestre: str = typer.Option(None, "--semestre", help="Abre direto no RIT deste semestre (AAAA.P)."),
           sem_tui: bool = typer.Option(False, "--sem-tui", help="Só mostra a ajuda, sem a interface visual.")) -> None:
    if ctx.invoked_subcommand is not None:
        if ctx.invoked_subcommand not in ("mcp", "atualizar", "doctor"):
            _avisar_atualizacao()
        return
    import sys

    if sem_tui or not sys.stdout.isatty():
        typer.echo(ctx.get_help())
        return
    from expeditto.tui.app import rodar

    rodar(alto_contraste=alto_contraste, semestre=semestre)


@app.command()
def instalar(sim: bool = typer.Option(False, "--sim", help="Aceita tudo sem perguntar (apps detectados, login)."),
             apps: str = typer.Option(None, help="Só estes apps, ex.: claude-desktop,claude-code."),
             sem_login: bool = typer.Option(False, "--sem-login", help="Pula o login no SUAP.")) -> None:
    """Prepara tudo: navegador, pasta de dados, conexão com os apps de IA, login no SUAP e diagnóstico."""
    from expeditto import assistente

    escolhidos = [a.strip() for a in apps.split(",")] if apps else None
    raise typer.Exit(assistente.instalar(automatico=sim, apps_escolhidos=escolhidos, com_login=not sem_login))


@app.command()
def desinstalar(apagar_dados: bool = typer.Option(None, "--apagar-dados/--manter-dados",
                                                  help="Apaga também o acervo e a sessão (pergunta se omitido)."),
                sim: bool = typer.Option(False, "--sim", help="Não perguntar (mantém os dados, salvo --apagar-dados).")) -> None:
    """Remove o Expeditto dos apps de IA e, se você pedir, apaga seus dados."""
    from expeditto import assistente

    raise typer.Exit(assistente.desinstalar(apagar=apagar_dados, automatico=sim))


@app.command()
def atualizar() -> None:
    """Atualiza o Expeditto para a versão mais recente."""
    from expeditto import assistente

    raise typer.Exit(assistente.atualizar())


@app.command()
def doctor(json_: bool = typer.Option(False, "--json", help="Saída em JSON."),
           offline: bool = typer.Option(False, "--offline", help="Não consulta o SUAP.")) -> None:
    """Diagnóstico: o que está pronto, o que falta e como resolver."""
    import json

    from expeditto import diagnostico

    verificacoes = diagnostico.executar(verificar_online=not offline)
    if json_:
        typer.echo(json.dumps(diagnostico.como_dict(verificacoes), ensure_ascii=False, indent=2))
        return
    cores = {"ok": ("✓", "green"), "aviso": ("!", "yellow"), "erro": ("✗", "red")}
    for v in verificacoes:
        icone, cor = cores[v.estado]
        typer.secho(f" {icone} ", fg=cor, bold=True, nl=False)
        typer.echo(f"{v.titulo:<28}{v.detalhe}")
        if v.como_resolver:
            typer.secho(f"{'':31}↳ {v.como_resolver}", fg="yellow")
    geral = diagnostico.como_dict(verificacoes)["geral"]
    raise typer.Exit(1 if geral == "erro" else 0)


def _cliente() -> tuple[SuapClient, Perfil | None]:
    cookies = auth.carregar_sessao()
    if not cookies:
        typer.secho("Sem sessão. Rode `expeditto login`.", fg="red")
        raise typer.Exit(1)
    perfil = acervo.carregar_perfil()
    return SuapClient(cookies, matricula=perfil.matricula if perfil else None), perfil


@app.command()
def login() -> None:
    """Abre uma janela do SUAP para login e carrega o perfil (setup)."""
    typer.echo("Faça login na janela que vai abrir (CAPTCHA/Gov.br). Ela fecha sozinha.")
    cookies = auth.login_interativo()
    with SuapClient(cookies) as client:
        perfil = coleta.setup(client)
    typer.secho(f"Sessão ativa: {perfil.nome} ({perfil.matricula}) — campus {perfil.campus}", fg="green")
    typer.echo(f"Acervo em: {config.home()}")


@app.command()
def semestres() -> None:
    """Lista os semestres com o estado do PIT e do RIT."""
    client, _ = _cliente()
    with client:
        try:
            lista = planos.carregar_todos(client)
        except SessaoExpirada:
            typer.secho("Sessão expirada. Rode `expeditto login`.", fg="red")
            raise typer.Exit(1)
    for p in lista:
        destaque = "yellow" if p.estado.value == "rit_a_preencher" else None
        link = p.links.get("preencher_relatorio") or p.links.get("relatorio_pdf") or ""
        typer.secho(f"{p.semestre}  {p.estado.value:<20} {config.BASE_URL + link if link else ''}",
                    fg=destaque)


@app.command()
def coletar(semestre: str = typer.Argument(..., help="Ex.: 2025.1"),
            sem_download: bool = typer.Option(False, help="Só metadados, sem baixar PDFs.")) -> None:
    """Coleta e organiza as evidências de um semestre no acervo local."""
    client, perfil = _cliente()
    with client:
        try:
            perfil = perfil or coleta.setup(client)
            manifest = coleta.coletar_semestre(client, perfil, semestre, baixar=not sem_download,
                                               progresso=lambda m, etapa=None, fracao=None: typer.echo(f"  · {m}"))
        except SessaoExpirada:
            typer.secho("Sessão expirada. Rode `expeditto login`.", fg="red")
            raise typer.Exit(1)
    _resumo(manifest)


@app.command()
def status(semestre: str) -> None:
    """Mostra o resumo do acervo já coletado de um semestre."""
    manifest = acervo.carregar_manifest(semestre)
    if not manifest:
        typer.secho(f"Nada coletado para {semestre}. Rode `expeditto coletar {semestre}`.", fg="red")
        raise typer.Exit(1)
    _resumo(manifest)


def _resumo(manifest) -> None:
    s = manifest.semestre
    typer.secho(f"\n{s.codigo}: {s.inicio} → {s.fim} (datas: {s.fonte_datas})", bold=True)
    if manifest.plano:
        typer.echo(f"Plano: {manifest.plano.estado.value}")
    por_topico = Counter(t for i in manifest.itens for t in i.topicos)
    com_pdf = Counter(t for i in manifest.itens if i.arquivo for t in i.topicos)
    for topico in Topico:
        typer.echo(f"  {topico.rotulo:<72} {por_topico[topico]:>3} itens, {com_pdf[topico]:>3} PDFs")
    if manifest.pendencias:
        typer.secho(f"\nPendências ({len(manifest.pendencias)}):", fg="yellow")
        for (tipo, mensagem), n in Counter((p.tipo, p.mensagem) for p in manifest.pendencias).items():
            typer.echo(f"  [{tipo}] {mensagem}" + (f"  (×{n})" if n > 1 else ""))
    typer.echo(f"\nAcervo: {acervo.pasta_semestre(s.codigo)}")


@app.command()
def montar(semestre: str) -> None:
    """Gera o PDF de anexo de cada tópico (capa + índice + comprovantes, ≤ 10 MB)."""
    from expeditto import anexos

    manifest = acervo.carregar_manifest(semestre)
    if not manifest:
        typer.secho(f"Nada coletado para {semestre}. Rode `expeditto coletar {semestre}`.", fg="red")
        raise typer.Exit(1)
    perfil = acervo.carregar_perfil()
    manifest = anexos.montar(manifest, perfil.nome if perfil else "")
    for topico in Topico:
        a = manifest.anexos.get(topico.value)
        info = (f"{a.documentos:>3} docs, {a.paginas:>3} págs, {a.bytes / 1048576:5.2f} MB"
                + (" (comprimido)" if a.comprimido else "")) if a else "  — sem comprovantes"
        typer.echo(f"  {topico.rotulo:<72} {info}")
    for p in (p for p in manifest.pendencias if p.tipo == "anexo_grande"):
        typer.secho(f"  [anexo_grande] {p.mensagem}", fg="yellow")
    typer.echo(f"\nAnexos em: {acervo.pasta_semestre(semestre) / 'anexos'}")


@app.command()
def textos(semestre: str, sobrescrever: bool = typer.Option(False, help="Refaz textos já revisados.")) -> None:
    """Gera rascunhos dos 'Relatos' por tópico (HTML) a partir do acervo."""
    from expeditto import textos as txt

    manifest = acervo.carregar_manifest(semestre)
    if not manifest:
        typer.secho(f"Nada coletado para {semestre}.", fg="red")
        raise typer.Exit(1)
    gerados = txt.gerar_rascunhos(manifest, sobrescrever=sobrescrever)
    for topico in Topico:
        situacao = "gerado" if topico.value in gerados else (
            "mantido" if txt.carregar(semestre, topico.value) else "sem itens")
        typer.echo(f"  {topico.rotulo:<72} {situacao}")
    typer.echo(f"\nTextos em: {txt.pasta_textos(semestre)}")


@app.command()
def preencher(semestre: str,
              salvar: bool = typer.Option(False, "--salvar", help="Grava no SUAP (Salvar). Nunca entrega."),
              sim: bool = typer.Option(False, "--sim", help="Não pedir confirmação.")) -> None:
    """Mostra o que será enviado ao formulário do RIT; com --salvar, grava como rascunho no SUAP."""
    from expeditto import formulario

    manifest = acervo.carregar_manifest(semestre)
    if not manifest or not manifest.plano or not manifest.plano.plano_id:
        typer.secho(f"Sem acervo/plano para {semestre}.", fg="red")
        raise typer.Exit(1)
    envio = formulario.preparar(manifest)
    typer.secho(f"Prévia do RIT {semestre} (plano {manifest.plano.plano_id}):", bold=True)
    for linha in envio.resumo():
        typer.echo(f"  {linha}")
    if not salvar:
        typer.echo("\n(prévia apenas — use --salvar para gravar no SUAP como rascunho)")
        return
    if not sim and not typer.confirm("\nGravar no SUAP (Salvar, sem entregar)?"):
        raise typer.Exit(1)
    client, _ = _cliente()
    with client:
        try:
            r = formulario.salvar(client, manifest.plano.plano_id, envio)
        except SessaoExpirada:
            typer.secho("Sessão expirada. Rode `expeditto login`.", fg="red")
            raise typer.Exit(1)
    for m in r.mensagens:
        typer.echo(f"  SUAP: {m}")
    divergentes = [c for c, ok in r.textos_conferem.items() if not ok]
    typer.secho("Textos conferidos após salvar: " + ("todos OK" if not divergentes else f"divergem {divergentes}"),
                fg="green" if not divergentes else "yellow")
    typer.echo(f"Anexos vistos no formulário: {sorted(r.anexos_depois) or 'nenhum link exibido'}")
    typer.secho(f"\nPrévia formatada (PDF do RIT): {r.url_relatorio_pdf}", bold=True)
    typer.secho(f"Conferir/editar e entregar no SUAP: {r.url}", bold=True)


@app.command("gmail-login")
def gmail_login(conta: str = typer.Option(None, help="E-mail sugerido (institucional ou acadêmico).")) -> None:
    """Autoriza leitura do Gmail (backup para hosts sem conector de e-mail). Repita para outra conta."""
    from expeditto import gmail

    typer.echo(f"Conta autorizada: {gmail.login(conta)}  (contas: {', '.join(gmail.contas())})")


@app.command("gmail-atas")
def gmail_atas(semestre: str, registrar: str = typer.Option(None, help="Números a registrar, ex.: 1,3,4")) -> None:
    """Lista e-mails candidatos a ata no período do semestre; com --registrar, registra os escolhidos."""
    from expeditto import gmail

    if registrar:
        feitas = gmail.registrar(semestre, [int(n) for n in registrar.split(",")])
        for a in feitas:
            typer.echo(f"  registrada: {a['assunto']} ({'PDF original' if a['anexo_original'] else 'registro do e-mail'})")
        typer.echo("Rode `expeditto coletar` ou `expeditto montar` para incluir no acervo.")
        return
    manifest = acervo.carregar_manifest(semestre)
    if not manifest:
        typer.secho(f"Rode `expeditto coletar {semestre}` antes (datas do semestre).", fg="red")
        raise typer.Exit(1)
    for n, c in enumerate(gmail.buscar(manifest.semestre), 1):
        typer.echo(f"{n:>3}. {c.data[:16]}  {c.assunto[:70]}  [{', '.join(c.anexos_pdf) or 'sem PDF'}]")


@app.command()
def entrada(semestre: str) -> None:
    """Mostra a pasta de entrada (comprovantes próprios, uma subpasta por tópico)."""
    from expeditto import entrada as ent

    raiz = ent.pasta(semestre)
    typer.echo(f"Coloque PDFs/fotos em uma subpasta por tópico de: {raiz}")
    typer.echo(f"  subpastas: {', '.join(p.name for p in sorted(raiz.iterdir()) if p.is_dir())}")
    typer.echo(f"Depois rode `expeditto montar {semestre}`.")


@app.command()
def mcp() -> None:
    """Inicia o servidor MCP (stdio) para Claude Desktop/Code, Codex ou Gemini/Antigravity CLI."""
    from expeditto.mcp_server import main as servir

    servir()


@app.command()
def logout() -> None:
    """Apaga a sessão do keyring e o perfil do navegador de login (que também guarda a sessão)."""
    import shutil

    auth.apagar_sessao()
    shutil.rmtree(config.home() / "_navegador", ignore_errors=True)
    typer.echo("Sessão e perfil do navegador removidos.")
