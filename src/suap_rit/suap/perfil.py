"""Perfil do usuário — apenas campos da allowlist (decisão D26, mapa §7)."""

from __future__ import annotations

import re

from suap_rit import html as h
from suap_rit.client import SuapClient
from suap_rit.models import Perfil

# Rótulo no SUAP → campo do Perfil. Qualquer outro rótulo é ignorado na leitura.
_ALLOWLIST = {
    "Nome usual": "nome_usual",
    "Nome do Registro": "nome",
    "E-mail institucional": "email_institucional",
    "E-mail acadêmico": "email_academico",
    "Setor SUAP": "setor",
    "Cargo": "cargo",
    "Jornada Trabalho": "jornada",
    "Titulação": "titulacao",
    "Participa do PGD": "participa_pgd",
}


def identificar(pagina_professor: str) -> tuple[str, str, int | None]:
    """(nome, matrícula, id do professor) a partir de `/edu/professor/`."""
    doc = h.documento(pagina_professor)
    titulo = next((h.texto(e) for e in doc.iter("h2") if "Professor(a):" in h.texto(e)), "")
    m = re.search(r"Professor\(a\):\s*(.+?)\s*\((\d+)\)", titulo)
    if not m:
        raise ValueError("página do professor sem identificação (sessão inválida?)")
    professor_id = None
    for a in doc.iter("a"):
        href = a.get("href") or ""
        if mm := re.search(r"/pit_rit_v2/criar_plano/(\d+)/|/edu/professor/(\d+)/", href):
            professor_id = int(mm[1] or mm[2])
            break
    return m[1], m[2], professor_id


def parse_dados_gerais(pagina_servidor: str, nome: str, matricula: str,
                       professor_id: int | None) -> Perfil:
    doc = h.documento(pagina_servidor)
    dados = h.definicoes(doc, somente=set(_ALLOWLIST))
    campos: dict = {"matricula": matricula, "nome": nome, "professor_id": professor_id}
    for rotulo, campo in _ALLOWLIST.items():
        valor = dados.get(rotulo)
        if valor and valor != "-":
            campos[campo] = valor
    if "setor" in campos and (m := re.search(r"campus:\s*([\w-]+)", campos["setor"])):
        campos["campus"] = m[1]
    if "participa_pgd" in campos:
        campos["participa_pgd"] = campos["participa_pgd"].lower().startswith("sim")
    lattes = next((a.get("href") for a in doc.iter("a")
                   if (a.get("href") or "").startswith("/cnpq/curriculo/")), None)
    campos["lattes_suap"] = lattes
    return Perfil(**campos)


def carregar(client: SuapClient) -> Perfil:
    nome, matricula, professor_id = identificar(client.html("/edu/professor/?tab=planoatividades", aba=True))
    client.matricula = matricula
    perfil = parse_dados_gerais(client.html(f"/rh/servidor/{matricula}/"), nome, matricula,
                                professor_id)
    if perfil.lattes_suap:
        pagina = client.html(perfil.lattes_suap)
        if m := re.search(r"Atualizado em\s*(\d{2}/\d{2}/\d{4})", h.texto(h.documento(pagina))):
            perfil.lattes_atualizado = m[1]
    return perfil
