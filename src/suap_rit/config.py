"""Configuração global: URL do SUAP e diretório do acervo local."""

from __future__ import annotations

import os
from pathlib import Path

BASE_URL = os.environ.get("SUAP_RIT_BASE_URL", "https://suap.ifma.edu.br")
KEYRING_SERVICE = "suap-rit"


def home() -> Path:
    """Diretório raiz do acervo (`SUAP_RIT_HOME` ou `~/suap-rit`)."""
    path = Path(os.environ.get("SUAP_RIT_HOME", Path.home() / "suap-rit"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    path = home() / "_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path
