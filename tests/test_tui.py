"""Fase 3 — interface do terminal (Textual), sem SUAP: tudo simulado."""

import asyncio
from datetime import datetime

import pytest
from textual.widgets import Button, SelectionList, TabbedContent

from expeditto import acervo, formulario, pendencias
from expeditto.models import (Evidencia, EstadoPlano, ItemAcervo, Manifest, Pendencia, PlanoSemestre, Semestre,
                              TipoEvidencia, Topico)
from expeditto.tui import mascote
from expeditto.tui.app import ExpedittoApp
from expeditto.tui.componentes import html_para_texto
from expeditto.tui.inicio import Inicio
from expeditto.tui.preparo import Preparo


def test_todas_as_poses_do_mascote():
    for pose in mascote.POSES:
        linhas = mascote.render(pose).plain.split("\n")
        assert len(linhas) == mascote.ALT // 2 and all(len(l) == mascote.LARG for l in linhas)
    for sequencia in mascote.ANIMACOES.values():
        assert all(pose in mascote.POSES and duracao > 0 for pose, duracao in sequencia)


def test_html_para_texto():
    assert html_para_texto("<p>Fiz <strong>3</strong> coisas:</p><ul><li>a</li><li>b</li></ul>") == \
        "Fiz **3** coisas:\n\n- a\n- b"


def _rodar(app, roteiro, tamanho=(150, 45)):
    async def principal():
        async with app.run_test(size=tamanho) as pilot:
            await pilot.pause(0.3)
            await roteiro(app, pilot)
    asyncio.run(principal())


def test_inicio_sem_sessao(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPEDITTO_HOME", str(tmp_path))
    monkeypatch.setattr("expeditto.auth.carregar_sessao", lambda *a, **k: None)

    async def roteiro(app, pilot):
        tela = app.screen
        assert isinstance(tela, Inicio)
        assert "Entre no SUAP" in str(tela.query_one("#resumo").render())
        assert "sem sessão" in str(tela.query_one("#sessao").render())

    _rodar(ExpedittoApp(), roteiro)


def test_login_conclui_e_fecha_a_janela_sem_derrubar_o_app(tmp_path, monkeypatch):
    """Regressão: dismiss() chamado por timer derrubava o app ("Can't await screen.dismiss()")."""
    from expeditto.models import Perfil
    from expeditto.tui.telas import Login

    monkeypatch.setenv("EXPEDITTO_HOME", str(tmp_path))
    monkeypatch.setattr("expeditto.auth.carregar_sessao", lambda *a, **k: None)
    monkeypatch.setattr("expeditto.auth.login_interativo", lambda *a, **k: {"__Host-sessionid": "x"})
    monkeypatch.setattr("expeditto.coleta.setup", lambda client: Perfil(matricula="1", nome="Fulana de Tal"))
    fechou = []

    async def roteiro(app, pilot):
        app.entrar(depois=lambda: fechou.append(True))
        await pilot.pause(0.5)
        assert isinstance(app.screen, Login)
        await pilot.pause(2.5)
        assert isinstance(app.screen, Inicio)

    _rodar(ExpedittoApp(), roteiro)
    assert fechou == [True]


@pytest.fixture
def semestre_coletado(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPEDITTO_HOME", str(tmp_path))
    monkeypatch.setattr("expeditto.auth.carregar_sessao", lambda *a, **k: {"__Host-sessionid": "x"})
    monkeypatch.setattr("expeditto.suap.planos.carregar_todos",
                        lambda client: [PlanoSemestre(semestre="2025.2", estado=EstadoPlano.RIT_A_PREENCHER)])
    ev = Evidencia(id="p", fonte="t", tipo=TipoEvidencia.PROJETO_PESQUISA, titulo="Projeto")
    m = Manifest(semestre=Semestre(ano=2025, periodo=2), gerado_em=datetime.now(), evidencias={"p": ev},
                 itens=[ItemAcervo(evidencia_id="p", topicos=[Topico.PESQUISA], motivo="")],
                 plano=PlanoSemestre(semestre="2025.2", plano_id=42, estado=EstadoPlano.RIT_A_PREENCHER),
                 pendencias=[Pendencia(tipo="lattes_sem_comprovante",
                                       mensagem=f"Lattes (capítulo de livro, 2025): Título {n} — sem comprovante")
                             for n in (1, 2, 3)])
    acervo.salvar_manifest(m)
    return tmp_path


def test_preparo_decide_pendencias_em_lote(semestre_coletado):
    async def roteiro(app, pilot):
        app.abrir_preparo("2025.2")
        await pilot.pause(0.5)
        tela = app.screen
        assert isinstance(tela, Preparo) and tela.passo.etapa == "pendencias"
        assert tela.query_one(TabbedContent).active == "pendencias"
        itens = tela.query_one("#itens-0", SelectionList)
        itens.deselect(3)  # o item 3 fica para depois
        await pilot.pause(0.1)
        tela.query_one("#decidir-ignorar-0", Button).press()
        await pilot.pause(0.5)

    _rodar(ExpedittoApp(), roteiro)
    decisoes = [p.resolucao for p in acervo.carregar_manifest("2025.2").pendencias]
    assert decisoes == ["ignorar", "ignorar", None]


def test_salvar_exige_dois_cliques(semestre_coletado, monkeypatch):
    chamadas = []
    monkeypatch.setattr(formulario, "salvar_semestre", lambda client, codigo: chamadas.append(codigo) or
                        formulario.ResultadoSalvar("https://suap/f", "https://suap/pdf", [], {"obs": True}, {}))
    pendencias.resolver(acervo.carregar_manifest("2025.2"), [1, 2, 3], "ignorar")

    async def roteiro(app, pilot):
        app.abrir_preparo("2025.2")
        await pilot.pause(0.5)
        tela = app.screen
        tela.query_one(TabbedContent).active = "salvar"
        botao = tela.query_one("#salvar-suap", Button)
        botao.press()
        await pilot.pause(0.3)
        assert chamadas == [] and "Tem certeza" in str(botao.label)
        botao.press()
        await pilot.pause(1.0)

    _rodar(ExpedittoApp(), roteiro)
    assert chamadas == ["2025.2"]
