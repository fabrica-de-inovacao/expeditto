"""Evidência → tópico(s) do RIT (decisões D12–D16, D25; mapa §6)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from suap_rit.models import Evidencia, TipoEvidencia, Topico

T = Topico


@dataclass
class Classificacao:
    topicos: list[Topico]
    motivo: str
    incerta: bool = False


_POR_TIPO: dict[TipoEvidencia, tuple[list[Topico], str]] = {
    TipoEvidencia.DIARIO: ([T.APOIO_ENSINO], "diário de classe: preparação e registro das aulas"),
    TipoEvidencia.ESTAGIO: ([T.ORIENTACAO_ALUNOS], "orientação de estágio (D12)"),
    TipoEvidencia.ORIENTACAO_TCC: ([T.ORIENTACAO_ALUNOS], "orientação de TCC (D12)"),
    TipoEvidencia.COORIENTACAO_TCC: ([T.ORIENTACAO_ALUNOS], "coorientação de TCC (D12)"),
    TipoEvidencia.BANCA: ([T.ORIENTACAO_ALUNOS], "participação em banca (catálogo do PIT)"),
    TipoEvidencia.PROJETO_PESQUISA: ([T.PESQUISA], "projeto de pesquisa"),
    TipoEvidencia.PROJETO_EXTENSAO: ([T.EXTENSAO], "projeto de extensão"),
    TipoEvidencia.PROJETO_ENSINO: ([T.PROGRAMAS_PROJETOS_ENSINO], "projeto de ensino"),
    TipoEvidencia.FUNCAO: ([T.GESTAO], "exercício de função/coordenação (D13, D16)"),
    TipoEvidencia.CAPACITACAO: ([T.REUNIOES, T.APOIO_ENSINO], "formação/encontro pedagógico (D14)"),
    TipoEvidencia.AFASTAMENTO: ([], "contexto: afastamento (não é comprovante)"),
    TipoEvidencia.MANUAL: ([], "tópico definido pelo docente (pasta de entrada)"),
}

# Tipos de arquivo da pasta funcional que já definem o tópico.
_POR_TIPO_ARQUIVO: list[tuple[str, list[Topico], str]] = [
    ("Portaria de Designação em Programas Institucionais", [T.PROGRAMAS_PROJETOS_ENSINO],
     "designação em programa institucional (PRONATEC/MEDIOTEC/ETEC)"),
    ("Designação de FCC", [T.GESTAO], "designação de função comissionada de coordenação (D13, D16)"),
    ("Portaria de nomeação para exercício de CC", [T.GESTAO], "nomeação para cargo de direção (D13)"),
    ("Portaria de designação de substituto eventual", [T.GESTAO], "substituição eventual de chefia"),
]

# Regras de portaria em ordem de prioridade: (padrão, tópicos, motivo).
_REGRAS_PORTARIA: list[tuple[str, list[Topico], str]] = [
    (r"banca|defesa|examinador|monografia|trabalho de conclus|\btcc\b",
     [T.ORIENTACAO_ALUNOS], "portaria de banca (D12)"),
    (r"n[úu]cleo docente estruturante|\bnde\b|colegiado|conselho de classe|reuni[ãa]o pedag",
     [T.REUNIOES], "NDE/Colegiado (D25)"),
    (r"\bppc\b|projeto pedag[óo]gico|plano de curso|matriz curricular|transi[çc][ãa]o curricular",
     [T.APOIO_ENSINO], "elaboração/reformulação de projeto ou plano de curso (catálogo do PIT)"),
    (r"programas institucionais|pronatec|mediotec|\betec\b|\bfic\b|bolsa[- ]forma[çc][ãa]o|nivelamento|monitoria|projeto de ensino",
     [T.PROGRAMAS_PROJETOS_ENSINO], "programa/projeto de ensino"),
    (r"pesquisa|pibic|pibiti|inicia[çc][ãa]o cient[íi]fica|comit[êe] de [ée]tica",
     [T.PESQUISA], "atividade de pesquisa"),
    (r"extens[ãa]o", [T.EXTENSAO], "atividade de extensão"),
    (r"designa[çc][ãa]o de fcc|\bfcc\b|nomea[çc][ãa]o.*\bcc\b|coordena[çc][ãa]o|coordenador|laborat[óo]rio|f[áa]brica de inova|substitut",
     [T.GESTAO], "coordenação/gestão de curso ou espaço (D13)"),
    (r"comiss[ãa]o|conselho|consup|consep|comit[êe]|organizador",
     [T.GESTAO], "comissão/conselho: representação institucional"),
]


def classificar(ev: Evidencia) -> Classificacao:
    if ev.tipo == TipoEvidencia.ORIENTACAO_PROJETO:
        # P1: orientação em projeto de pesquisa vai para os dois tópicos; em ensino/extensão só Orientação (D12)
        if ev.extras.get("tipo_projeto") == TipoEvidencia.PROJETO_PESQUISA.value:
            return Classificacao([T.ORIENTACAO_ALUNOS, T.PESQUISA], "orientação de bolsista em pesquisa (P1)")
        return Classificacao([T.ORIENTACAO_ALUNOS], "orientação de discente em projeto (D12)")
    if ev.tipo == TipoEvidencia.ATA:
        alvo = f"{ev.titulo} {ev.descricao}".lower()  # assunto + remetente/departamento; o corpo gera ruído
        for padrao, topicos, motivo in _REGRAS_PORTARIA:
            if re.search(padrao, alvo):
                return Classificacao(list(topicos), f"ata por e-mail: {motivo}")
        return Classificacao([T.REUNIOES], "ata de reunião por e-mail (D15)")
    if ev.tipo != TipoEvidencia.PORTARIA:
        topicos, motivo = _POR_TIPO[ev.tipo]
        return Classificacao(list(topicos), motivo)
    tipo_arquivo = ev.extras.get("tipo_arquivo", "")
    for prefixo, topicos, motivo in _POR_TIPO_ARQUIVO:
        if tipo_arquivo.startswith(prefixo):
            return Classificacao(list(topicos), motivo)
    # "Designação para compor comissões/conselhos/bancas" é genérico: decide o conteúdo.
    alvo = f"{ev.descricao} {ev.extras.get('assunto', '')}".lower()
    for padrao, topicos, motivo in _REGRAS_PORTARIA:
        if re.search(padrao, alvo):
            return Classificacao(list(topicos), motivo)
    return Classificacao([T.GESTAO], "portaria sem regra específica → Gestão (revisar)", incerta=True)
