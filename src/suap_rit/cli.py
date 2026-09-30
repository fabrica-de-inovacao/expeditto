"""CLI `suap-rit` — casca fina sobre o núcleo (o MCP usará as mesmas funções)."""

from __future__ import annotations

from collections import Counter

import typer

from suap_rit import acervo, auth, coleta, config
from suap_rit.client import SessaoExpirada, SuapClient
from suap_rit.models import Perfil, Topico
from suap_rit.suap import planos

app = typer.Typer(help="Organiza evidências do SUAP IFMA para o Relatório Individual de Trabalho (RIT).",
                  no_args_is_help=True)


def _cliente() -> tuple[SuapClient, Perfil | None]:
    cookies = auth.carregar_sessao()
    if not cookies:
        typer.secho("Sem sessão. Rode `suap-rit login`.", fg="red")
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
            typer.secho("Sessão expirada. Rode `suap-rit login`.", fg="red")
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
                                               progresso=lambda m: typer.echo(f"  · {m}"))
        except SessaoExpirada:
            typer.secho("Sessão expirada. Rode `suap-rit login`.", fg="red")
            raise typer.Exit(1)
    _resumo(manifest)


@app.command()
def status(semestre: str) -> None:
    """Mostra o resumo do acervo já coletado de um semestre."""
    manifest = acervo.carregar_manifest(semestre)
    if not manifest:
        typer.secho(f"Nada coletado para {semestre}. Rode `suap-rit coletar {semestre}`.", fg="red")
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
    from suap_rit import anexos

    manifest = acervo.carregar_manifest(semestre)
    if not manifest:
        typer.secho(f"Nada coletado para {semestre}. Rode `suap-rit coletar {semestre}`.", fg="red")
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
def logout() -> None:
    """Apaga a sessão guardada no keyring."""
    auth.apagar_sessao()
    typer.echo("Sessão removida.")
