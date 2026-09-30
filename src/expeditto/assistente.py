"""Assistente de instalação no terminal (Rich): o que o docente vê ao rodar `expeditto instalar`."""

from __future__ import annotations


from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table
from rich.text import Text

from expeditto import config, diagnostico, instalador
from expeditto.tui import mascote
from expeditto.tui.tema import COR

console = Console(highlight=False)
AVISO = ("Ferramenta independente, não oficial. Roda no seu computador, com a sua sessão do SUAP, e nunca "
         "entrega o relatório por você. Licença AGPL-3.0.")


def _cabecalho(titulo: str, subtitulo: str, pose: str = "acenando") -> None:
    grade = Table.grid(padding=(0, 3))
    grade.add_column(), grade.add_column()
    texto = Text()
    texto.append("Expeditto\n", style=f"bold {COR['laranja']}")
    texto.append("seu segundo expediente, resolvido\n\n", style=f"italic {COR['ambar']}")
    texto.append(titulo + "\n", style="bold")
    texto.append(subtitulo, style=COR["apagado"])
    grade.add_row(mascote.render(pose, tamanho="pequeno"), texto)
    console.print()
    console.print(grade)
    console.print()


def _passo(n: int, total: int, titulo: str) -> None:
    console.print(Text.assemble((f" {n}/{total} ", f"bold #16110D on {COR['laranja']}"), " ", (titulo, "bold")))


def _linha(ok: bool | None, texto: str, detalhe: str = "") -> None:
    icone, cor = {True: ("✓", COR["verde"]), False: ("✗", COR["coral"]), None: ("!", COR["ambar"])}[ok]
    console.print(Text.assemble("   ", (icone, f"bold {cor}"), " ", texto,
                                (f"  {detalhe}" if detalhe else "", COR["apagado"])))


def _pergunta(texto: str, padrao: bool, automatico: bool) -> bool:
    if automatico:
        return padrao
    return Confirm.ask(f"   {texto}", default=padrao, console=console)


# -- instalar -------------------------------------------------------------------------------
def instalar(automatico: bool = False, apps_escolhidos: list[str] | None = None, com_login: bool = True) -> int:
    _cabecalho("Vamos deixar tudo pronto.", "Leva uns 3 minutos. Você pode rodar de novo quando quiser.")
    console.print(f"   {AVISO}\n", style=COR["apagado"])
    total = 5

    _passo(1, total, "Navegador para o login no SUAP")
    if instalador.navegador_pronto():
        _linha(True, diagnostico._navegador().detalhe)
    elif _pergunta("Não achei o Google Chrome. Baixo o Chromium (~150 MB)?", True, automatico):
        with console.status("   Baixando o Chromium…"):
            r = instalador.instalar_chromium()
        _linha(r.ok, r.mensagem)
    else:
        _linha(None, "sem navegador: instale o Google Chrome e rode `expeditto instalar` de novo")

    _passo(2, total, "Pasta dos seus dados")
    pasta = config.home()
    pasta.mkdir(parents=True, exist_ok=True)
    _linha(True, str(pasta), "acervo, anexos e relatos ficam aqui (mude com EXPEDITTO_HOME)")

    _passo(3, total, "Conectar aos seus assistentes de IA")
    detectados = instalador.apps_detectados()
    if not detectados:
        _linha(None, "nenhum app compatível encontrado",
               "instale o Claude Desktop (recomendado) e rode `expeditto instalar` de novo")
    escolhidos = []
    for app in detectados:
        if apps_escolhidos is not None:
            marcar = app.id in apps_escolhidos
        elif app.configurado():
            try:
                app.revisar()
                _linha(True, app.nome, "já conectado")
            except Exception as erro:  # noqa: BLE001
                _linha(None, app.nome, f"conectado, mas não consegui revisar: {erro}")
            continue
        else:
            marcar = _pergunta(f"Conectar ao {app.nome}?", True, automatico)
        if marcar:
            escolhidos.append(app)
    for r in instalador.conectar(escolhidos):
        _linha(r.ok, r.alvo, r.mensagem)
    if any(a.id == "claude-desktop" for a in escolhidos):
        _linha(None, "Feche e abra o Claude Desktop (inclusive o ícone perto do relógio) para ele carregar.")

    _passo(4, total, "Entrar no SUAP")
    from expeditto import auth

    if auth.carregar_sessao():
        _linha(True, "já existe uma sessão guardada")
    elif com_login and _pergunta("Abrir a janela do SUAP para você entrar agora?", True, automatico):
        try:
            from expeditto import coleta
            from expeditto.client import SuapClient

            with console.status("   Janela do SUAP aberta: faça o login nela (ela fecha sozinha)…"):
                cookies = auth.login_interativo()
                with SuapClient(cookies) as client:
                    perfil = coleta.setup(client)
            nome = (perfil.nome_usual or perfil.nome).split()[0].title()
            _linha(True, f"Olá, {nome}!", perfil.campus or "")
        except Exception as erro:  # noqa: BLE001 — dá para entrar depois
            _linha(False, "login não concluído", f"{erro} · tente depois com `expeditto login`")
    else:
        _linha(None, "depois, é só pedir ao seu assistente ou rodar `expeditto`")

    _passo(5, total, "Diagnóstico")
    verificacoes = diagnostico.executar(verificar_online=False)
    for v in verificacoes:
        _linha({"ok": True, "aviso": None, "erro": False}[v.estado], v.titulo, v.detalhe)

    geral = diagnostico.como_dict(verificacoes)["geral"]
    _cabecalho("Pronto!" if geral != "erro" else "Quase lá.",
               "No Claude (ou outro app conectado), escreva: “me ajuda com meu relatório do semestre”.\n"
               "No terminal, rode: expeditto", "comemorando" if geral != "erro" else "preocupado")
    return 1 if geral == "erro" else 0


# -- desinstalar ----------------------------------------------------------------------------
def desinstalar(apagar: bool | None = None, automatico: bool = False) -> int:
    _cabecalho("Desinstalar", "Tiro o Expeditto dos seus apps de IA. Seus dados só saem se você pedir.",
               "preocupado")
    resultados = instalador.desconectar_todos()
    for r in resultados:
        _linha(r.ok, r.alvo, r.mensagem)
    if not resultados:
        _linha(True, "nenhum app estava conectado")
    if apagar is None:
        apagar = _pergunta(f"Apagar também seus dados ({config.home()}) e a sessão do SUAP?", False, automatico)
    if apagar:
        for r in instalador.apagar_dados():
            _linha(r.ok, r.alvo, r.mensagem)
    console.print(f"\n   Para remover o programa: [bold]{instalador.comando_remover_programa()}[/]\n")
    return 0


# -- atualizar ------------------------------------------------------------------------------
def atualizar() -> int:
    import os

    from expeditto import atualizacao

    with console.status("   Procurando a versão mais nova…"):
        nova = atualizacao.verificar(forcar=True)
    if not nova:
        _linha(True, f"Você já tem a versão mais nova ({atualizacao.versao_instalada()}).")
        return 0
    _cabecalho(f"Atualizar para a versão {nova['disponivel']}", f"Você tem a {nova['instalada']}.", "trabalhando")
    if instalador.modo_instalacao() == "desenvolvimento":
        _linha(None, "Esta é uma cópia de desenvolvimento: use git pull && uv sync.")
        return 1
    # No Windows, este próprio comando trava os arquivos: a reinstalação abre numa janela nova e espera ele fechar.
    r = atualizacao.atualizar(nova["disponivel"], aguardar_pid=os.getpid(), visivel=True)
    _linha(r["ok"], r["mensagem"])
    if r.get("agendada"):
        _linha(None, "Uma janela nova vai mostrar o andamento. Feche os apps de IA antes, se estiverem abertos.")
    else:
        _linha(None, "Reinicie os apps de IA para eles usarem a versão nova.")
    return 0 if r["ok"] else 1
