"""Modelos de domínio: semestres, planos, evidências e o manifest do acervo."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Topico(StrEnum):
    """Os 7 tópicos do formulário do RIT (pit_rit_v2)."""

    APOIO_ENSINO = "apoio_ensino"
    PROGRAMAS_PROJETOS_ENSINO = "programas_projetos_ensino"
    ORIENTACAO_ALUNOS = "orientacao_alunos"
    REUNIOES = "reunioes"
    PESQUISA = "pesquisa"
    EXTENSAO = "extensao"
    GESTAO = "gestao"

    @property
    def rotulo(self) -> str:
        return _ROTULOS[self]

    @property
    def campo_texto(self) -> str:
        return f"obs_{self.value}"

    @property
    def campo_arquivo(self) -> str:
        return f"arquivo_{self.value}"

    @property
    def pasta(self) -> str:
        return f"{list(Topico).index(self) + 1:02d}-{self.value.replace('_', '-')}"


_ROTULOS = {
    Topico.APOIO_ENSINO: "Ensino: Preparação, Manutenção e Apoio ao Ensino",
    Topico.PROGRAMAS_PROJETOS_ENSINO: "Ensino: Programas e Projetos de Ensino",
    Topico.ORIENTACAO_ALUNOS: "Ensino: Atendimento, Acompanhamento, Avaliação e Orientação de Alunos",
    Topico.REUNIOES: "Ensino: Reuniões Pedagógicas, de Grupo e Afins",
    Topico.PESQUISA: "Pesquisa",
    Topico.EXTENSAO: "Extensão",
    Topico.GESTAO: "Gestão e Representação Institucional",
}


class Semestre(BaseModel):
    ano: int
    periodo: int
    inicio: date | None = None
    fim: date | None = None
    fonte_datas: str = "desconhecida"  # "diarios" | "estimativa" | "usuario"

    @property
    def codigo(self) -> str:
        return f"{self.ano}.{self.periodo}"

    @classmethod
    def de_codigo(cls, codigo: str) -> Semestre:
        ano, periodo = codigo.split(".")
        return cls(ano=int(ano), periodo=int(periodo))


class EstadoPlano(StrEnum):
    SEM_PLANO = "sem_plano"
    PLANO_NAO_ENVIADO = "plano_nao_enviado"
    PLANO_EM_AVALIACAO = "plano_em_avaliacao"
    RIT_A_PREENCHER = "rit_a_preencher"
    RIT_EM_AVALIACAO = "rit_em_avaliacao"
    RIT_APROVADO = "rit_aprovado"
    RIT_PUBLICADO = "rit_publicado"


class PlanoSemestre(BaseModel):
    semestre: str
    plano_id: int | None = None
    estado: EstadoPlano
    plano_enviado: bool = False
    plano_aprovado: bool = False
    relatorio_enviado: bool = False
    relatorio_aprovado: bool = False
    relatorio_publicado: bool = False
    avaliador_plano: str | None = None
    historico: list[str] = Field(default_factory=list)
    ch_total: str | None = None
    quadro_resumo: dict[str, str] = Field(default_factory=dict)
    # Atividades do catálogo marcadas no PIT, por categoria (legenda da tabela).
    atividades_pit: dict[str, list[str]] = Field(default_factory=dict)
    links: dict[str, str] = Field(default_factory=dict)


class TipoEvidencia(StrEnum):
    DIARIO = "diario"
    ESTAGIO = "estagio"
    ORIENTACAO_TCC = "orientacao_tcc"
    COORIENTACAO_TCC = "coorientacao_tcc"
    ORIENTACAO_PROJETO = "orientacao_projeto"  # orientação de discente em projeto (declaração própria)
    BANCA = "banca"
    PROJETO_PESQUISA = "projeto_pesquisa"
    PROJETO_EXTENSAO = "projeto_extensao"
    PROJETO_ENSINO = "projeto_ensino"
    PORTARIA = "portaria"
    FUNCAO = "funcao"
    AFASTAMENTO = "afastamento"
    CAPACITACAO = "capacitacao"
    ATA = "ata"  # ata/convocação recebida por e-mail (registrar_ata, D41)


class Evidencia(BaseModel):
    id: str  # estável entre execuções: "<fonte>:<tipo>:<id na origem>"
    fonte: str
    tipo: TipoEvidencia
    titulo: str
    descricao: str = ""
    papel: str | None = None
    inicio: date | None = None
    fim: date | None = None
    data_evento: date | None = None  # atividade pontual (ex.: data da defesa)
    semestre_letivo: str | None = None  # quando a origem já informa "AAAA.P"
    vigencia_indeterminada: bool = False
    url_pagina: str | None = None
    url_comprovante: str | None = None
    comprovante_assincrono: bool = False
    extras: dict[str, str] = Field(default_factory=dict)


class Pendencia(BaseModel):
    tipo: str
    mensagem: str
    evidencia_id: str | None = None
    # decisão do docente: "manter" | "remover_item" | "justificar" | "ignorar"
    resolucao: str | None = None
    justificativa: str | None = None

    @property
    def chave(self) -> str:
        """Identidade estável entre coletas (para reaplicar a decisão do docente)."""
        return f"{self.tipo}:{self.evidencia_id or self.mensagem}"


class ItemAcervo(BaseModel):
    evidencia_id: str
    topicos: list[Topico]
    motivo: str
    arquivo: str | None = None  # caminho relativo ao acervo
    validade: date | None = None  # "Válido até" impresso no comprovante emitido pelo SUAP


class AnexoTopico(BaseModel):
    """PDF único enviado no campo `arquivo_<topico>` do RIT (capa + índice + comprovantes)."""

    topico: Topico
    arquivo: str  # caminho relativo ao acervo
    bytes: int
    paginas: int
    documentos: int
    comprimido: bool = False


class Manifest(BaseModel):
    semestre: Semestre
    plano: PlanoSemestre | None = None
    gerado_em: datetime
    evidencias: dict[str, Evidencia] = Field(default_factory=dict)
    itens: list[ItemAcervo] = Field(default_factory=list)
    pendencias: list[Pendencia] = Field(default_factory=list)
    anexos: dict[str, AnexoTopico] = Field(default_factory=dict)


class Perfil(BaseModel):
    """Contexto do usuário — somente campos da allowlist (decisão D26)."""

    matricula: str
    nome: str
    nome_usual: str | None = None
    professor_id: int | None = None
    email_institucional: str | None = None
    email_academico: str | None = None
    campus: str | None = None
    setor: str | None = None
    cargo: str | None = None
    jornada: str | None = None
    titulacao: str | None = None
    participa_pgd: bool | None = None
    lattes_suap: str | None = None
    lattes_atualizado: str | None = None
    semestres: dict[str, Semestre] = Field(default_factory=dict)
