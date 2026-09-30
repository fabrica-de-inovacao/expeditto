"""Aviso de versão nova, atualização e permissões nos apps de IA."""

import asyncio
import json

from expeditto import atualizacao, hosts


def test_compara_versoes():
    assert atualizacao.mais_nova("0.10.0", "0.9.3")
    assert atualizacao.mais_nova("v1.0.0", "0.9")
    assert not atualizacao.mais_nova("0.3.0", "0.3.0")
    assert not atualizacao.mais_nova("0.2.9", "0.3.0")


def test_verificar_usa_cache_de_um_dia(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPEDITTO_HOME", str(tmp_path))
    monkeypatch.delenv("EXPEDITTO_SEM_ATUALIZACAO")
    monkeypatch.setattr(atualizacao, "versao_instalada", lambda: "0.3.0")
    chamadas = []

    def release(timeout):
        chamadas.append(1)
        return {"versao": "0.4.0", "url": "https://github.com/x/releases/v0.4.0", "notas": "novidades"}

    monkeypatch.setattr(atualizacao, "_buscar_release", release)
    nova = atualizacao.verificar()
    assert nova["disponivel"] == "0.4.0" and nova["instalada"] == "0.3.0" and "0.4.0" in nova["mensagem"]
    atualizacao.verificar()
    assert len(chamadas) == 1  # a segunda consulta veio do cache
    atualizacao.verificar(forcar=True)
    assert len(chamadas) == 2


def test_sem_internet_nao_ha_aviso(tmp_path, monkeypatch):
    import httpx

    monkeypatch.setenv("EXPEDITTO_HOME", str(tmp_path))
    monkeypatch.delenv("EXPEDITTO_SEM_ATUALIZACAO")

    def falha(timeout):
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(atualizacao, "_buscar_release", falha)
    assert atualizacao.verificar() is None


def test_desligado_por_variavel(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPEDITTO_HOME", str(tmp_path))
    monkeypatch.setattr(atualizacao, "_buscar_release", lambda t: {"versao": "9.9.9", "url": "", "notas": ""})
    assert atualizacao.verificar() is None  # EXPEDITTO_SEM_ATUALIZACAO=1 (conftest)


def test_comando_instala_a_tag_da_release(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda nome: "/bin/uv")
    cmd = atualizacao.comando("0.4.0")
    assert cmd[:4] == ["/bin/uv", "tool", "install", "--force"]
    assert cmd[-1].endswith("/archive/refs/tags/v0.4.0.zip")


def test_permissoes_do_claude_code_preservam_as_do_docente(tmp_path):
    arquivo = tmp_path / "settings.json"
    arquivo.write_text(json.dumps({"permissions": {"allow": ["Bash(git status)"]}, "tema": "escuro"}), encoding="utf-8")
    hosts.permitir_no_claude_code(arquivo)
    hosts.permitir_no_claude_code(arquivo)  # idempotente
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    assert dados["permissions"]["allow"] == ["Bash(git status)", "mcp__expeditto"]
    assert "mcp__expeditto__salvar_no_suap" in dados["permissions"]["ask"] and dados["tema"] == "escuro"
    hosts.permitir_no_claude_code(arquivo, remover=True)
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    assert dados["permissions"] == {"allow": ["Bash(git status)"]}


def test_gemini_confia_no_servidor():
    gemini = hosts.por_id("gemini")
    assert gemini.extras.get("trust") is True


def test_todas_as_ferramentas_tem_anotacao_e_so_duas_sao_sensiveis():
    from expeditto.mcp_server import servidor

    ferramentas = asyncio.run(servidor.list_tools())
    nomes = {f.name for f in ferramentas}
    assert {"verificar_atualizacao", "atualizar_expeditto", "preparar_rit"} <= nomes
    assert all(f.annotations is not None for f in ferramentas)
    sensiveis = {f.name for f in ferramentas if f.annotations.destructive_hint}
    assert sensiveis == {"salvar_no_suap", "atualizar_expeditto"}
