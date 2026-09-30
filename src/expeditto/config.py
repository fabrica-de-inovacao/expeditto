"""Configuração global: URL do SUAP, diretório de dados e migração do nome antigo (suap-rit)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

NOME = "Expeditto"
BASE_URL = os.environ.get("EXPEDITTO_SUAP_URL", os.environ.get("SUAP_RIT_BASE_URL", "https://suap.ifma.edu.br"))
KEYRING_SERVICE = "expeditto"
KEYRING_SERVICE_ANTIGO = "suap-rit"  # protótipos anteriores


def _pasta_padrao() -> Path:
    return Path.home() / "expeditto"


def migrar_pasta_antiga() -> Path | None:
    """Move ~/suap-rit → ~/expeditto na primeira execução (se o novo ainda não existir)."""
    antiga, nova = Path.home() / "suap-rit", _pasta_padrao()
    if antiga.is_dir() and not nova.exists():
        shutil.move(str(antiga), str(nova))
        return nova
    return None


def home() -> Path:
    """Diretório de dados (`EXPEDITTO_HOME` ou `~/expeditto`)."""
    definido = os.environ.get("EXPEDITTO_HOME") or os.environ.get("SUAP_RIT_HOME")
    if definido:
        path = Path(definido)
    else:
        migrar_pasta_antiga()
        path = _pasta_padrao()
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    path = home() / "_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path
