"""Fase 4 — instalador: modo de instalação, conexão com apps, desinstalação e o assistente."""

import json

import pytest

from expeditto import assistente, hosts, instalador


def test_modo_instalacao(tmp_path):
    assert instalador.modo_instalacao(r"C:\Users\x\AppData\Roaming\uv\tools\expeditto") == "uv-tool"
    assert instalador.modo_instalacao("/home/x/.local/share/uv/tools/expeditto") == "uv-tool"
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / ".venv").mkdir()
    assert instalador.modo_instalacao(str(tmp_path / ".venv")) == "desenvolvimento"
    assert instalador.modo_instalacao("/usr") == "outro"
    ferramenta = tmp_path / "ferramentas" / "expeditto"  # UV_TOOL_DIR personalizado: vale o recibo do uv
    ferramenta.mkdir(parents=True)
    (ferramenta / "uv-receipt.toml").write_text("[tool]", encoding="utf-8")
    assert instalador.modo_instalacao(str(ferramenta)) == "uv-tool"


@pytest.fixture
def app_falso(tmp_path, monkeypatch):
    """Um app de IA simulado (JSON com mcpServers) e a pasta de dados num diretório temporário."""
    monkeypatch.setenv("EXPEDITTO_HOME", str(tmp_path / "dados"))
    arquivo = tmp_path / "app" / "config.json"
    arquivo.parent.mkdir()
    arquivo.write_text(json.dumps({"mcpServers": {"outro": {"command": "x"}}}), encoding="utf-8")
    app = hosts.HostJson("claude-desktop", "Claude Desktop", arquivo, arquivo.parent)
    monkeypatch.setattr(hosts, "todos", lambda: [app])
    return app


def test_conectar_e_desconectar(app_falso):
    assert [a.id for a in instalador.apps_detectados()] == ["claude-desktop"]
    [r] = instalador.conectar([app_falso])
    assert r.ok and app_falso.configurado()
    [r] = instalador.desconectar_todos()
    assert r.ok and not app_falso.configurado()
    assert "outro" in json.loads(app_falso.arquivo.read_text(encoding="utf-8"))["mcpServers"]


def test_apagar_dados(app_falso, tmp_path, monkeypatch):
    apagadas = []
    monkeypatch.setattr("expeditto.auth.apagar_sessao", lambda *a, **k: apagadas.append("suap"))
    monkeypatch.setattr("keyring.delete_password", lambda servico, chave: apagadas.append(chave))
    pasta = tmp_path / "dados"
    pasta.mkdir()
    (pasta / "gmail_contas.json").write_text(json.dumps(["prof@ifma.edu.br"]), encoding="utf-8")
    resultados = instalador.apagar_dados()
    assert apagadas == ["suap", "gmail:prof@ifma.edu.br"]
    assert not pasta.exists() and all(r.ok for r in resultados)


def test_assistente_automatico_conecta_e_nao_apaga_nada(app_falso, monkeypatch):
    monkeypatch.setattr(instalador, "navegador_pronto", lambda: True)
    monkeypatch.setattr("expeditto.auth.carregar_sessao", lambda *a, **k: None)
    codigo = assistente.instalar(automatico=True, com_login=False)
    assert codigo == 0 and app_falso.configurado()
    assert assistente.desinstalar(automatico=True) == 0  # sem --apagar-dados: mantém os dados
    assert not app_falso.configurado()
