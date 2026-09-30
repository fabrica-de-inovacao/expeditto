"""Perfil do servidor (`/rh/servidor/{matricula}/`): pasta funcional, projetos,
funções, afastamentos e capacitações (CFS).

A resposta das abas traz todas as tabelas do perfil; cada parser localiza a
sua pelos cabeçalhos.
"""

from __future__ import annotations

import hashlib
import io
import re

from pypdf import PdfReader

from suap_rit import html as h
from suap_rit.acervo import Cache
from suap_rit.client import SuapClient
from suap_rit.models import Evidencia, Perfil, TipoEvidencia, normalizar_papel
from suap_rit.suap import portaria

_FONTE = "suap_servidor"

# Tipos de arquivo da pasta funcional que comprovam atividades do RIT (mapa §4).
TIPOS_RELEVANTES = (
    "Designação para compor comissões/conselhos/bancas",
    "Portaria de Designação em Programas Institucionais",
    "Designação de FCC",
    "Portaria de nomeação para exercício de CC",
    "Portaria de designação de substituto eventual",
)

_PROJETOS = {
    "/pesquisa/projeto/": (TipoEvidencia.PROJETO_PESQUISA,
                           ("/pesquisa/emitir_declaracao_participacao_pdf/", "/pesquisa/emitir_certificado_pdf/")),
    "/projetos/projeto/": (TipoEvidencia.PROJETO_EXTENSAO, ("/projetos/emitir_certificado_extensao_pdf/",)),
    "/projetos_ensino/projeto/": (TipoEvidencia.PROJETO_ENSINO,
                                  ("/projetos_ensino/emitir_certificado_participacao_pdf/",)),
}


def _hash(*partes: str) -> str:
    return hashlib.sha1("|".join(partes).encode()).hexdigest()[:12]


def _periodo_texto(valor: str):
    """'25 de Agosto de 2026 até 29 de Agosto de 2026' / '04/08/2021 a 16/08/2021' / 'Desde 05/04/2023'."""
    datas = re.findall(r"\d{1,2} de [A-Za-zç]+ de \d{4}|\d{2}/\d{2}/\d{4}", valor)
    inicio = h.parse_data(datas[0]) if datas else None
    fim = h.parse_data(datas[1]) if len(datas) > 1 else None
    return inicio, fim


# -- pasta funcional ------------------------------------------------------------
def linhas_pasta_funcional(pagina: str) -> list[dict[str, h.Celula]]:
    tabelas = h.tabelas_com(h.documento(pagina), "Tipo de Arquivo", "Nome")
    return [r for t in tabelas for r in t.registros()]


def _texto_pdf(conteudo: bytes) -> str:
    leitor = PdfReader(io.BytesIO(conteudo))
    return "\n".join(p.extract_text() or "" for p in leitor.pages)


def evidencia_portaria(linha: dict[str, h.Celula], texto: str, perfil: Perfil) -> Evidencia:
    links = [l for c in linha.values() for l in c.links]
    doc_id = next((h.id_da_url(l, "/documento_eletronico/visualizar_documento/") for l in links
                   if "/visualizar_documento/" in l), None)
    arquivo = next((l for l in links if "/arquivo/visualizar_arquivo_pdf/" in l), None)
    tipo_arquivo = linha["Tipo de Arquivo"].texto
    nome = linha["Nome"].texto
    descricao = linha.get("Descrição", h.Celula("")).texto
    if descricao.lower().startswith("adicionar descrição"):
        descricao = ""

    dados = portaria.parse(texto, nome=perfil.nome, matricula=perfil.matricula)
    extras = {"tipo_arquivo": tipo_arquivo, "assunto": dados.assunto}
    inicio, fim, evento = dados.inicio, dados.fim, dados.data_evento
    if not (inicio or evento):
        evento = dados.data or h.parse_data(linha.get("Inserido em", h.Celula("")).texto)
        extras["datas_inferidas"] = "data da portaria (vigência não identificada no texto)"

    return Evidencia(
        id=f"suap_pasta:portaria:{doc_id or _hash(arquivo or nome)}",
        fonte="suap_pasta_funcional",
        tipo=TipoEvidencia.PORTARIA,
        titulo=nome,
        descricao=descricao or dados.assunto[:200],
        papel=dados.papel,
        inicio=inicio,
        fim=fim,
        data_evento=evento,
        vigencia_indeterminada=dados.vigencia_indeterminada,
        url_pagina=f"/documento_eletronico/visualizar_documento/{doc_id}/" if doc_id else arquivo,
        url_comprovante=f"/documento_eletronico/imprimir_documento_pdf/{doc_id}/carta/" if doc_id else arquivo,
        comprovante_assincrono=bool(doc_id),
        extras=extras,
    )


def coletar_portarias(client: SuapClient, perfil: Perfil, cache: Cache, pagina: str) -> list[Evidencia]:
    evidencias = []
    for linha in linhas_pasta_funcional(pagina):
        if not linha.get("Tipo de Arquivo", h.Celula("")).texto.startswith(TIPOS_RELEVANTES):
            continue
        links = [l for c in linha.values() for l in c.links]
        doc = next((l for l in links if "/visualizar_documento/" in l), None)
        arquivo = next((l for l in links if "/arquivo/visualizar_arquivo_pdf/" in l), None)
        if doc:
            doc_id = h.id_da_url(doc, "/documento_eletronico/visualizar_documento/")
            caminho = f"/documento_eletronico/conteudo_documento/{doc_id}/"
            texto = cache.texto(f"portaria-{doc_id}",
                                lambda: h.texto(h.documento(client.html(caminho))))
        elif arquivo:
            pdf = cache.bytes(f"arquivo-{arquivo}", lambda: client.pdf(arquivo))
            texto = cache.texto(f"arquivo-{arquivo}", lambda: _texto_pdf(pdf.read_bytes()))
        else:
            continue
        evidencias.append(evidencia_portaria(linha, texto, perfil))
    return evidencias


# -- projetos ---------------------------------------------------------------------
def parse_projetos(pagina: str) -> list[Evidencia]:
    evidencias, vistos = [], set()
    for t in h.tabelas_com(h.documento(pagina), "Edital", "Projeto"):
        for reg in t.registros():
            links = [l for c in reg.values() for l in c.links]
            for prefixo, (tipo, comprovantes) in _PROJETOS.items():
                pagina_projeto = next((l for l in links if l.startswith(prefixo)), None)
                if not pagina_projeto:
                    continue
                projeto_id = h.id_da_url(pagina_projeto, prefixo)
                chave = f"{_FONTE}:{tipo.value}:{projeto_id}"
                if chave in vistos:  # a mesma participação aparece em mais de uma aba
                    break
                vistos.add(chave)
                comprovante = next((l for p in comprovantes for l in links if p in l), None)
                situacao = reg.get("Situação")
                evidencias.append(Evidencia(
                    id=chave,
                    fonte=_FONTE,
                    tipo=tipo,
                    titulo=reg["Projeto"].texto,
                    descricao=reg["Edital"].texto,
                    papel="Participante",
                    url_pagina=pagina_projeto,
                    url_comprovante=comprovante,
                    extras={"situacao": situacao.texto if situacao else "", "projeto_id": projeto_id},
                ))
                break
    return evidencias


def datas_projeto(pagina: str):
    doc = h.documento(pagina)
    rotulos = {}
    for el in doc.xpath("//td|//dt"):
        rotulo = h.texto(el)
        if rotulo in ("Início da Execução", "Término da Execução"):
            vizinho = el.getnext()
            rotulos[rotulo] = h.parse_data(h.texto(vizinho)) if vizinho is not None else None
    return rotulos.get("Início da Execução"), rotulos.get("Término da Execução")


def parse_equipe(pagina: str, matricula: str) -> dict[str, str]:
    """Papel do usuário na equipe do projeto. Pesquisa/ensino usam tabela
    (Membro | Coordenador Sim/Sub/Não | Carga Horária); extensão usa cartões
    `div.general-box` com etiquetas de status (Coordenador, Voluntário...)."""
    doc = h.documento(pagina)
    alvo = f"/rh/servidor/{matricula}/"
    links_meus = [a for a in doc.iter("a") if (a.get("href") or "").startswith(alvo)]
    for a in links_meus:
        linha = next((e for e in a.iterancestors("tr")), None)
        tabela = linha.getparent().getparent() if linha is not None else None
        if linha is not None and tabela is not None and tabela.tag == "table":
            cabecalhos = [h.texto(th) for th in tabela.xpath("./thead//th")]
            if "Coordenador" not in cabecalhos:
                continue
            celulas = linha.xpath("./td")
            reg = dict(zip(cabecalhos, celulas))
            coord = h.texto(reg.get("Coordenador")).lower()
            papel = {"sim": "Coordenador(a)", "sub": "Subcoordenador(a)"}.get(coord, "Membro da equipe")
            return _equipe(papel, h.texto(reg.get("Carga Horária")), linha)
        cartao = next((e for e in a.iterancestors("div") if "general-box" in (e.get("class") or "")), None)
        if cartao is not None:
            status = [h.texto(s) for s in cartao.xpath('.//span[contains(@class, "status")]')]
            dados = h.definicoes(cartao)
            papel = next((s for s in status if s in ("Coordenador", "Subcoordenador")), None)
            funcao = dados.get("Função:", "")
            papel = f"{papel}(a)" if papel else (funcao if funcao not in ("", "-") else "Membro da equipe")
            return _equipe(papel, dados.get("Carga Horária Semanal:", ""), cartao)
    return {}


def _equipe(papel: str, carga: str, bloco) -> dict[str, str]:
    info = {"papel": papel, "carga_horaria": carga}
    for a in bloco.iter("a"):
        href = a.get("href") or ""
        if "emitir_declaracao_orientacao_pdf" in href:
            info["declaracao_orientacao"] = href
        elif "emitir_declaracao_participacao_pdf" in href:
            info["declaracao_participacao"] = href
    return info


def completar_projetos(client: SuapClient, cache: Cache, evidencias: list[Evidencia],
                       matricula: str) -> list[Evidencia]:
    """Datas de execução e papel na equipe de cada projeto; devolve as evidências
    de orientação de discentes encontradas nas equipes (regra P1)."""
    orientacoes = []
    for ev in evidencias:
        def ler() -> dict:
            pagina = client.html(f"{ev.url_pagina}?tab=equipe", aba=True)
            inicio, fim = datas_projeto(pagina)
            return {"inicio": str(inicio) if inicio else None, "fim": str(fim) if fim else None,
                    **parse_equipe(pagina, matricula)}
        # projetos concluídos não mudam; os em andamento são relidos a cada coleta
        dados = cache.json(f"projeto-{ev.url_pagina}", ler) if "Conclu" in ev.extras.get("situacao", "") \
            else ler()
        ev.inicio, ev.fim = h.parse_data(dados.get("inicio")), h.parse_data(dados.get("fim"))
        if dados.get("papel"):
            ev.papel = dados["papel"]
        if dados.get("carga_horaria"):
            ev.extras["carga_horaria"] = dados["carga_horaria"]
        if not ev.url_comprovante and dados.get("declaracao_participacao"):
            ev.url_comprovante = dados["declaracao_participacao"]  # projeto em andamento: ainda sem certificado
        if dados.get("declaracao_orientacao"):
            orientacoes.append(Evidencia(
                id=f"{ev.id}:orientacao",
                fonte=ev.fonte,
                tipo=TipoEvidencia.ORIENTACAO_PROJETO,
                titulo=f"Orientação de discente(s) no projeto: {ev.titulo}",
                descricao=ev.descricao,
                papel="Orientador(a)",
                inicio=ev.inicio,
                fim=ev.fim,
                url_pagina=ev.url_pagina,
                url_comprovante=dados["declaracao_orientacao"],
                extras={"projeto": ev.id, "tipo_projeto": ev.tipo.value},
            ))
    return orientacoes


# -- funções, afastamentos, capacitações ------------------------------------------
def parse_funcoes(pagina: str) -> list[Evidencia]:
    doc = h.documento(pagina)
    evidencias = []
    for t in h.tabelas_com(doc, "Função", "Atividade"):
        for reg in t.registros():
            if "Data Início" in reg:
                inicio, fim = h.parse_data(reg["Data Início"].texto), h.parse_data(reg["Data Fim"].texto)
            elif "Período" in reg:
                inicio, fim = _periodo_texto(reg["Período"].texto)
            else:
                continue
            atividade = reg["Atividade"].texto
            setor = (reg.get("Setor SUAP") or reg.get("Setor/Campus") or h.Celula("")).texto
            evidencias.append(Evidencia(
                id=f"{_FONTE}:funcao:{_hash(atividade, str(inicio))}",
                fonte=_FONTE,
                tipo=TipoEvidencia.FUNCAO,
                titulo=normalizar_papel(re.sub(r"^\d+\s*-\s*", "", atividade)) or atividade,
                descricao=f"{reg['Função'].texto} — {setor}".strip(" —"),
                papel=re.sub(r"^\d+\s*-\s*", "", atividade),
                inicio=inicio,
                fim=fim,
            ))
    # a função atual aparece nas duas tabelas: fica a primeira ocorrência
    unicas = {}
    for ev in evidencias:
        unicas.setdefault((ev.titulo, ev.inicio), ev)
    return list(unicas.values())


def parse_afastamentos(pagina: str) -> list[Evidencia]:
    evidencias = []
    for t in h.tabelas_com(h.documento(pagina), "Tipo de Afastamento", "Período"):
        for reg in t.registros():
            inicio, fim = _periodo_texto(reg["Período"].texto)
            descricao = reg["Descrição"].texto
            evidencias.append(Evidencia(
                id=f"{_FONTE}:afastamento:{_hash(descricao, str(inicio))}",
                fonte=_FONTE,
                tipo=TipoEvidencia.AFASTAMENTO,
                titulo=descricao,
                inicio=inicio,
                fim=fim or inicio,
                extras={"dias": reg.get("Total de Dias", h.Celula("")).texto},
            ))
    return evidencias


def parse_capacitacoes(pagina: str) -> list[Evidencia]:
    evidencias = []
    for t in h.tabelas_com(h.documento(pagina), "Curso/Evento", "Aulas"):
        for reg in t.registros():
            curso = reg["Curso/Evento"].texto
            inicio, fim = _periodo_texto(reg["Aulas"].texto)
            link = next((l for l in reg["Ações"].links if "/cfs/" in l), None) if "Ações" in reg else None
            evidencias.append(Evidencia(
                id=f"{_FONTE}:capacitacao:{_hash(curso, str(inicio))}",
                fonte=_FONTE,
                tipo=TipoEvidencia.CAPACITACAO,
                titulo=curso,
                descricao=reg.get("Local das aulas", h.Celula("")).texto[:200],
                papel="Participante",
                inicio=inicio,
                fim=fim or inicio,
                url_pagina=link,
            ))
    return evidencias


def coletar(client: SuapClient, perfil: Perfil, cache: Cache) -> list[Evidencia]:
    base = f"/rh/servidor/{perfil.matricula}/"
    pagina_pasta = client.html(f"{base}?tab=pasta_funcional", aba=True)
    projetos = []
    for aba in ("participacoes_ensino", "participacoes_pesquisas", "participacoes_extensoes"):
        projetos += parse_projetos(client.html(f"{base}?tab={aba}", aba=True))
    unicos = {p.id: p for p in projetos}
    projetos = list(unicos.values())
    orientacoes = completar_projetos(client, cache, projetos, perfil.matricula)
    return (
        coletar_portarias(client, perfil, cache, pagina_pasta)
        + projetos
        + orientacoes
        + parse_funcoes(pagina_pasta)
        + parse_afastamentos(pagina_pasta)
        + parse_capacitacoes(pagina_pasta)
    )
