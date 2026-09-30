"""Acervo local: cache de downloads e persistência de manifest/perfil (decisão D11)."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path

from expeditto import config
from expeditto.models import Manifest, Perfil


def _chave_arquivo(chave: str) -> str:
    legivel = re.sub(r"[^\w.-]+", "_", chave)[:60]
    return f"{legivel}-{hashlib.sha1(chave.encode()).hexdigest()[:10]}"


class Cache:
    """Cache em disco por chave estável (id da evidência/URL). Evita regerar PDFs
    no SUAP a cada execução — cada emissão cria registro no histórico do usuário."""

    def __init__(self, raiz: Path | None = None):
        self.raiz = raiz or config.cache_dir()
        self.raiz.mkdir(parents=True, exist_ok=True)

    def caminho(self, chave: str, extensao: str) -> Path:
        return self.raiz / f"{_chave_arquivo(chave)}.{extensao}"

    def bytes(self, chave: str, obter: Callable[[], bytes], extensao: str = "pdf") -> Path:
        destino = self.caminho(chave, extensao)
        if not destino.exists():
            destino.write_bytes(obter())
        return destino

    def texto(self, chave: str, obter: Callable[[], str]) -> str:
        destino = self.caminho(chave, "txt")
        if destino.exists():
            return destino.read_text(encoding="utf-8")
        valor = obter()
        destino.write_text(valor, encoding="utf-8")
        return valor

    def json(self, chave: str, obter: Callable[[], object]):
        destino = self.caminho(chave, "json")
        if destino.exists():
            return json.loads(destino.read_text(encoding="utf-8"))
        valor = obter()
        destino.write_text(json.dumps(valor, ensure_ascii=False, default=str), encoding="utf-8")
        return valor


def pasta_semestre(codigo: str) -> Path:
    pasta = config.home() / codigo
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def semestres_locais() -> list[str]:
    """Semestres (AAAA.P) com acervo coletado nesta máquina, do mais recente ao mais antigo."""
    raiz = config.home()
    if not raiz.exists():
        return []
    return sorted((p.name for p in raiz.iterdir() if re.fullmatch(r"\d{4}\.[12]", p.name)
                   and (p / "manifest.json").exists()), reverse=True)


def salvar_manifest(manifest: Manifest) -> Path:
    destino = pasta_semestre(manifest.semestre.codigo) / "manifest.json"
    destino.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return destino


def carregar_manifest(codigo: str) -> Manifest | None:
    origem = config.home() / codigo / "manifest.json"
    return Manifest.model_validate_json(origem.read_text(encoding="utf-8")) if origem.exists() else None


def salvar_perfil(perfil: Perfil) -> Path:
    destino = config.home() / "perfil.json"
    destino.write_text(perfil.model_dump_json(indent=2), encoding="utf-8")
    return destino


def carregar_perfil() -> Perfil | None:
    origem = config.home() / "perfil.json"
    return Perfil.model_validate_json(origem.read_text(encoding="utf-8")) if origem.exists() else None
