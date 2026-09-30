"""Abas de "Meus planos" em `/edu/professor/`: estágios, projetos finais e bancas."""

from __future__ import annotations

import re

from suap_rit import html as h
from suap_rit.client import SuapClient
from suap_rit.models import Evidencia, TipoEvidencia

_FONTE = "suap_professor"


def _coluna(registro: dict[str, h.Celula], *termos: str) -> h.Celula | None:
    return next((c for k, c in registro.items() if all(t in k for t in termos)), None)


def _datas_no_texto(registro: dict[str, h.Celula]) -> list:
    achadas = []
    for cel in registro.values():
        for trecho in re.findall(r"\d{1,2} de [A-Za-zç]+ de \d{4}|\d{2}/\d{2}/\d{4}", cel.texto):
            if d := h.parse_data(trecho):
                achadas.append(d)
    return sorted(achadas)


def parse_estagios(pagina: str) -> list[Evidencia]:
    evidencias = []
    for t in h.tabelas_com(h.documento(pagina), "Aluno"):
        for reg in t.registros():
            link = next((l for c in reg.values() for l in c.links if l.startswith("/estagios/")), None)
            if not link:
                continue
            tipo_origem, id_origem = link.strip("/").split("/")[1:3]
            ini = _coluna(reg, "Início")
            fim = _coluna(reg, "Encerramento")
            inicio, termino = h.parse_data(ini.texto if ini else None), h.parse_data(fim.texto if fim else None)
            if not (inicio or termino):
                datas = _datas_no_texto(reg)
                inicio, termino = (datas[0], datas[-1]) if datas else (None, None)
            tipo = _coluna(reg, "Tipo")
            aluno = _coluna(reg, "Aluno")
            local = _coluna(reg, "Concedente") or _coluna(reg, "Instituição")
            titulo = f"Orientação de {tipo.texto if tipo else 'estágio'}"
            evidencias.append(Evidencia(
                id=f"{_FONTE}:estagio:{tipo_origem}:{id_origem}",
                fonte=_FONTE,
                tipo=TipoEvidencia.ESTAGIO,
                titulo=titulo,
                descricao=" — ".join(x.texto for x in (aluno, local) if x),
                papel="Orientador(a)",
                inicio=inicio,
                fim=termino,
                url_pagina=link,
                extras={"modalidade": tipo_origem},
            ))
    return evidencias


# Tipo de estágio (URL da linha) → modalidade do botão "Emitir Declaração de Orientação".
_MODALIDADE_DECLARACAO = {
    "pratica_profissional": "estagios",
    "aprendizagem": "aprendizagens",
    "atividade_profissional_efetiva": "atividadesprofissionaisefetivas",
}


def declaracoes_orientacao(pagina: str) -> dict[str, dict[str, str]]:
    """Menus "Emitir Declaração de Orientação…": {modalidade: {ano: url}}.
    A declaração é anual e lista todos os estágios da modalidade naquele ano."""
    declaracoes: dict[str, dict[str, str]] = {}
    for a in h.documento(pagina).iter("a"):
        href = a.get("href") or ""
        if m := re.search(r"/edu/emitir_declaracao_de_orientacao_pdf/\d+/(\w+)/(\d{4})/$", href):
            declaracoes.setdefault(m[1], {})[m[2]] = href
    return declaracoes


def declaracoes_docencia(pagina: str) -> dict[str, str]:
    """Menu "Emitir Declaração de Docência" (aba disciplinas): {ano: url}. A declaração
    é anual e lista disciplina, período, CH, diário e % atribuído/ministrado."""
    declaracoes = {}
    for a in h.documento(pagina).iter("a"):
        href = a.get("href") or ""
        if m := re.search(r"/edu/declaracaodocencia_pdf/\d+/(\d{4})/$", href):
            declaracoes[m[1]] = href
    return declaracoes


def percentuais_docencia(texto: str) -> dict[str, tuple[int, int]]:
    """{diário: (% atribuído, % ministrado)} a partir do texto da declaração de docência."""
    return {m[1]: (int(m[2]), int(m[3]))
            for m in re.finditer(r"\b(\d{5,})\s*\((?:Semestral|Anual)\)\s*(\d+)%\s*(\d+)%", texto)}


def anexar_declaracoes(estagios: list[Evidencia], declaracoes: dict[str, dict[str, str]]) -> None:
    for ev in estagios:
        modalidade = _MODALIDADE_DECLARACAO.get(ev.extras.get("modalidade", ""), "")
        for ano, url in declaracoes.get(modalidade, {}).items():
            ev.extras[f"declaracao_{ano}"] = url


def _tcc(reg: dict[str, h.Celula]) -> tuple[str | None, str | None]:
    link = next((l for c in reg.values() for l in c.links if "/visualizar_projeto_final/" in l), None)
    return h.id_da_url(link, "/visualizar_projeto_final/"), link


def _base_tcc(reg: dict[str, h.Celula]) -> dict:
    titulo = _coluna(reg, "Título")
    aluno = _coluna(reg, "Aluno")
    tipo = _coluna(reg, "Tipo")
    periodo = _coluna(reg, "Ano Período Letivo")
    data = _coluna(reg, "Data da Apresentação")
    return {
        "titulo": titulo.texto if titulo else "Trabalho de conclusão",
        "descricao": " — ".join(x.texto for x in (tipo, aluno) if x and x.texto),
        "data_evento": h.parse_data(data.texto) if data else None,
        "semestre_letivo": periodo.texto if periodo and re.fullmatch(r"\d{4}\.\d", periodo.texto) else None,
    }


def parse_projetos_finais(pagina: str) -> list[Evidencia]:
    evidencias = []
    for t in h.tabelas_com(h.documento(pagina), "Título", "Aluno"):
        for reg in t.registros():
            tcc_id, link = _tcc(reg)
            if not tcc_id:
                continue
            declaracao = next((l for c in reg.values() for l in c.links if "/coorientador/" in l), None)
            tipo = TipoEvidencia.COORIENTACAO_TCC if declaracao else TipoEvidencia.ORIENTACAO_TCC
            evidencias.append(Evidencia(
                id=f"{_FONTE}:{tipo.value}:{tcc_id}",
                fonte=_FONTE,
                tipo=tipo,
                papel="Coorientador(a)" if declaracao else "Orientador(a)",
                url_pagina=link,
                url_comprovante=declaracao,
                extras={"tcc_id": tcc_id},
                **_base_tcc(reg),
            ))
    return evidencias


def parse_bancas(pagina: str) -> list[Evidencia]:
    evidencias = []
    for t in h.tabelas_com(h.documento(pagina), "Título", "Aluno"):
        for reg in t.registros():
            tcc_id, link = _tcc(reg)
            declaracao = next((l for c in reg.values() for l in c.links
                               if "/declaracao_participacao_projeto_final_pdf/" in l), None)
            if not tcc_id or not declaracao:
                continue
            papel = declaracao.rstrip("/").split("/")[-1]
            evidencias.append(Evidencia(
                id=f"{_FONTE}:banca:{tcc_id}:{papel}",
                fonte=_FONTE,
                tipo=TipoEvidencia.BANCA,
                papel=papel.replace("_", " ").capitalize(),
                url_pagina=link,
                url_comprovante=declaracao,
                extras={"tcc_id": tcc_id, "papel": papel},
                **_base_tcc(reg),
            ))
    return evidencias


def coletar(client: SuapClient) -> list[Evidencia]:
    aba = lambda nome: client.html(f"/edu/professor/?tab={nome}", aba=True)  # noqa: E731
    pagina_estagios = aba("estagios")
    estagios = parse_estagios(pagina_estagios)
    anexar_declaracoes(estagios, declaracoes_orientacao(pagina_estagios))
    return estagios + parse_projetos_finais(aba("projetofinal")) + parse_bancas(aba("banca"))
