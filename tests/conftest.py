import pytest


@pytest.fixture(autouse=True)
def _sem_consulta_de_versao(monkeypatch):
    """Nenhum teste consulta o GitHub (aviso de atualização desligado, salvo onde o teste religar)."""
    monkeypatch.setenv("EXPEDITTO_SEM_ATUALIZACAO", "1")
