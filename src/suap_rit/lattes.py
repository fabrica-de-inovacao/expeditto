"""E7 — Lattes importado no SUAP como detector de lacunas (D27).

O Lattes é autodeclaração (não é comprovante): cada item do ano do semestre
sem evidência correspondente no acervo vira pendência — o docente decide se
adiciona o comprovante (pasta de entrada) ou ignora.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from suap_rit import html as h
from suap_rit.models import Manifest, Pendencia, Topico

# (seção h4 contém, subseção h2 começa com) → (categoria, tópico). Seção vazia = qualquer.
_MAPA = [
    ("", "Artigos completos publicados", "artigo em periódico", Topico.PESQUISA),
    ("", "Trabalhos completos publicados em anais", "trabalho completo em anais", Topico.PESQUISA),
    ("", "Resumos expandidos publicados", "resumo expandido em anais", Topico.PESQUISA),
    ("", "Resumos publicados em anais", "resumo em anais", Topico.PESQUISA),
    ("", "Livros publicados", "livro publicado/organizado", Topico.PESQUISA),
    ("", "Capítulos de livros", "capítulo de livro", Topico.PESQUISA),
    ("", "Apresentações de Trabalhos", "apresentação de trabalho", Topico.PESQUISA),
    ("", "Organização de Eventos", "organização de evento", Topico.EXTENSAO),
    ("Orientações e Supervisões em Andamento", "", "orientação em andamento", Topico.ORIENTACAO_ALUNOS),
    ("Orientações e Supervisões Concluídas", "Graduação", "orientação concluída (graduação)", Topico.ORIENTACAO_ALUNOS),
    ("Orientações e Supervisões Concluídas", "Iniciação Científica", "orientação concluída (IC)", Topico.ORIENTACAO_ALUNOS),
    ("Orientações e Supervisões Concluídas", "Outras Orientações", "orientação concluída", Topico.ORIENTACAO_ALUNOS),
    ("Participação em Bancas de Trabalhos", "", "participação em banca", Topico.ORIENTACAO_ALUNOS),
]


@dataclass
class ItemLattes:
    categoria: str
    topico: Topico
    texto: str
    ano: int | None
    andamento: bool


def _categoria(secao: str, subsecao: str):
    for sec, sub, categoria, topico in _MAPA:
        if (not sec or sec in secao) and (not sub or subsecao.startswith(sub)):
            return categoria, topico
    return None


def parse(pagina: str) -> list[ItemLattes]:
    doc = h.documento(pagina)
    itens = []
    for bloco in doc.xpath('//div[contains(@class,"accordion-item")]'):
        subsecao = h.texto(bloco.find(".//h2"))
        anterior = bloco.xpath("preceding::h4[1]")
        mapeado = _categoria(h.texto(anterior[0]) if anterior else "", subsecao)
        if not mapeado:
            continue
        categoria, topico = mapeado
        andamento = "Andamento" in (h.texto(anterior[0]) if anterior else "")
        for linha in bloco.xpath('.//div[contains(@class,"accordion-body")]//tr'):
            texto = re.sub(r"^\d+\s*", "", h.texto(linha))
            if len(texto) < 20:
                continue
            inicio = re.search(r"In[íi]cio:\s*((?:19|20)\d\d)", texto)
            anos = re.findall(r"\b((?:19|20)\d\d)\b", texto)
            ano = int(inicio[1]) if inicio else (int(anos[-1]) if anos else None)
            itens.append(ItemLattes(categoria, topico, texto, ano, andamento))
    return itens


def titulo_do_item(texto: str) -> str:
    """Remove a lista de autores das citações ("SOBRENOME, Nome ; ... . Título. Local, ano").
    Orientações vêm como "Aluno. Título. Início: ..." → fica o título."""
    if " . " in texto:  # separador ABNT entre autores e título
        resto = texto.split(" . ", 1)[1]
    elif re.search(r"In[íi]cio:|Orienta", texto) and ". " in texto:
        resto = texto.split(". ", 1)[1]
    else:
        return texto  # formato desconhecido: mantém a citação inteira
    return resto.split(". ")[0].strip() or texto


def _tokens(texto: str) -> set[str]:
    base = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return {t for t in re.findall(r"[a-z0-9]{4,}", base)}


def _coberto(item: ItemLattes, titulos_suap: list[set[str]]) -> bool:
    """Algum título do acervo está (quase) contido no texto do item do Lattes."""
    alvo = _tokens(item.texto)
    return any(t and len(t & alvo) / len(t) >= 0.7 for t in titulos_suap)


def lacunas(manifest: Manifest, itens: list[ItemLattes]) -> list[Pendencia]:
    ano = manifest.semestre.ano
    titulos = [_tokens(e.titulo) for e in manifest.evidencias.values() if len(_tokens(e.titulo)) >= 3]
    pendencias = []
    for item in itens:
        do_ano = item.ano == ano or (item.andamento and item.ano is not None and item.ano <= ano)
        if not do_ano or _coberto(item, titulos):
            continue
        titulo = titulo_do_item(item.texto)
        resumo = titulo if len(titulo) <= 160 else titulo[:157].rsplit(" ", 1)[0] + "..."
        pendencias.append(Pendencia(
            tipo="lattes_sem_comprovante",
            mensagem=f"Lattes ({item.categoria}, {item.ano}): {resumo} — sem comprovante no acervo. Se for do "
                     f"semestre {manifest.semestre.codigo}, adicione o comprovante na pasta de entrada "
                     f"({item.topico.value}); caso contrário, ignore.",
        ))
    return pendencias
