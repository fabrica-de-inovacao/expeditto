"""Fase 2 — experiência: tarefas com etapas, roteiro (porta de entrada), apps e diagnóstico."""

import json
import time
from datetime import datetime

import pytest

from expeditto import acervo, diagnostico, hosts, roteiro, tarefas, textos
from expeditto.models import AnexoTopico, ItemAcervo, Manifest, Pendencia, Semestre, Topico, Evidencia, TipoEvidencia


# -- tarefas --------------------------------------------------------------------------------
def test_barra():
    assert tarefas.barra(0) == "░" * 20
    assert tarefas.barra(50, 10) == "▓" * 5 + "░" * 5
    assert tarefas.barra(100, 4) == "▓" * 4


def test_tarefa_avanca_por_etapas_e_conclui():
    g = tarefas.Gerenciador()

    def alvo(progresso):
        progresso("plano", etapa="plano")
        progresso("baixando", etapa="comprovantes", fracao=0.5)
        time.sleep(0.2)
        return {"ok": True}

    t = g.iniciar("coleta", "Coleta 2025.2", alvo)
    time.sleep(0.05)
    v = t.visao()
    assert v["estado"] == "executando"
    assert "etapa 6/7 · Baixando comprovantes" in v["progresso"]
    assert v["etapas"].startswith("✓ Plano do semestre")  # etapas anteriores marcadas como concluídas
    assert 40 < v["percentual"] < 90
    time.sleep(0.4)
    v = t.visao()
    assert v["estado"] == "concluida" and v["percentual"] == 100 and v["resultado"] == {"ok": True}


def test_tarefa_com_erro_amigavel():
    g = tarefas.Gerenciador()

    def alvo(progresso):
        progresso("x", etapa="janela")
        raise RuntimeError("falhou")

    t = g.iniciar("login", "Login", alvo, ao_erro=lambda e: "mensagem amigável")
    time.sleep(0.1)
    assert t.visao()["estado"] == "erro" and t.visao()["erro"] == "mensagem amigável"


# -- roteiro --------------------------------------------------------------------------------
@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPEDITTO_HOME", str(tmp_path))
    monkeypatch.setattr("expeditto.auth.carregar_sessao", lambda *a, **k: {"__Host-sessionid": "x"})
    return tmp_path


def _manifest(pendencias=(), anexos=True):
    ev = Evidencia(id="p", fonte="t", tipo=TipoEvidencia.PROJETO_PESQUISA, titulo="Projeto")
    m = Manifest(semestre=Semestre(ano=2025, periodo=2), gerado_em=datetime.now(), evidencias={"p": ev},
                 itens=[ItemAcervo(evidencia_id="p", topicos=[Topico.PESQUISA], motivo="")],
                 pendencias=list(pendencias))
    if anexos:
        m.anexos = {"pesquisa": AnexoTopico(topico=Topico.PESQUISA, arquivo="a.pdf", bytes=1000, paginas=2,
                                            documentos=1)}
    acervo.salvar_manifest(m)
    return m


def test_roteiro_sem_sessao_pede_login(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPEDITTO_HOME", str(tmp_path))
    monkeypatch.setattr("expeditto.auth.carregar_sessao", lambda *a, **k: None)
    assert roteiro.situacao("2025.2").etapa == "login"


def test_roteiro_percorre_as_etapas(ambiente):
    assert roteiro.situacao(None, semestres_a_preencher=["2025.2"]).etapa == "escolher_semestre"
    assert roteiro.situacao("2025.2").proximo["ferramenta"] == "coletar_semestre"

    lattes = Pendencia(tipo="lattes_sem_comprovante",
                       mensagem="Lattes (capítulo de livro, 2025): Um título — sem comprovante no acervo.")
    _manifest([lattes], anexos=False)
    passo = roteiro.situacao("2025.2")
    assert passo.etapa == "pendencias"
    grupo = passo.dados["grupos"][0]
    assert grupo["quantidade"] == 1 and "1 capítulo de livro" in grupo["pergunta_sugerida"]

    assert roteiro.situacao("2025.2", seguir_sem_decidir=True).etapa == "anexos"
    _manifest([lattes], anexos=True)
    passo = roteiro.situacao("2025.2", seguir_sem_decidir=True)
    assert passo.etapa == "relatos" and passo.dados["topicos_faltando"] == ["pesquisa"]

    textos.salvar("2025.2", "pesquisa", "<p>Relato</p>")
    assert roteiro.situacao("2025.2").etapa == "previa"  # com texto, pendências abertas não bloqueiam

    time.sleep(1.1)
    roteiro.registrar_salvamento("2025.2", "https://suap/f", "https://suap/pdf")
    passo = roteiro.situacao("2025.2")
    assert passo.etapa == "concluido" and "https://suap/pdf" in passo.dados["cartao"]
    assert passo.como_dict()["passo"] == "8/8"

    time.sleep(1.1)
    textos.salvar("2025.2", "pesquisa", "<p>Relato revisado</p>")  # mudou depois de salvar
    assert roteiro.situacao("2025.2").etapa == "previa"


# -- apps (hosts) ---------------------------------------------------------------------------
def test_host_json_configura_com_backup_e_remove(tmp_path):
    arquivo = tmp_path / "claude_desktop_config.json"
    arquivo.write_text(json.dumps({"mcpServers": {"outro": {"command": "x"}}, "tema": "escuro"}), encoding="utf-8")
    host = hosts.HostJson("claude-desktop", "Claude Desktop", arquivo, tmp_path)
    assert host.instalado() and not host.configurado()
    host.configurar()
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    assert dados["mcpServers"]["expeditto"]["args"][-2:] == ["expeditto", "mcp"]
    assert dados["mcpServers"]["outro"] == {"command": "x"} and dados["tema"] == "escuro"  # preserva o resto
    assert (tmp_path / "claude_desktop_config.json.expeditto-bak").exists()
    assert host.configurado()
    host.remover()
    assert not host.configurado() and "outro" in json.loads(arquivo.read_text(encoding="utf-8"))["mcpServers"]


def test_lista_de_apps():
    assert [h.id for h in hosts.todos()] == ["claude-desktop", "claude-code", "codex", "gemini", "antigravity"]


# -- diagnóstico ----------------------------------------------------------------------------
def test_diagnostico_offline(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPEDITTO_HOME", str(tmp_path))
    monkeypatch.setattr("expeditto.auth.carregar_sessao", lambda *a, **k: None)
    resultado = diagnostico.como_dict(diagnostico.executar(verificar_online=False))
    ids = [v["id"] for v in resultado["verificacoes"]]
    assert {"versao", "pasta", "navegador", "sessao", "perfil"} <= set(ids)
    sessao = next(v for v in resultado["verificacoes"] if v["id"] == "sessao")
    assert sessao["estado"] == "aviso" and "login" in sessao["como_resolver"]
