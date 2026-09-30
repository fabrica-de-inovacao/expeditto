"""Explicações das pendências, em linguagem do docente: o que é, por que importa, o que cada opção faz
e, quando dá para saber, o que o Expeditto sugere. Usado pelo chat (MCP) e pela interface do terminal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from expeditto.models import Pendencia

# decisão → (rótulo do botão, o que acontece)
OPCOES = {
    "manter": ("Manter no relato", "O item continua no relato e no anexo como está."),
    "ignorar": ("Deixar de fora", "O item não entra no RIT deste semestre. Nada muda no SUAP."),
    "remover_item": ("Tirar do relato", "O item sai do relato e do PDF de comprovantes deste tópico."),
    "justificar": ("Justificar", "Sua justificativa entra em “Alterações de Atividades”, com as suas palavras."),
}


@dataclass
class Explicacao:
    titulo: str
    o_que_e: str
    por_que_importa: str
    opcoes: list[str]
    dica: str = ""
    extra_opcoes: dict[str, str] = field(default_factory=dict)  # efeito específico deste tipo


CATALOGO: dict[str, Explicacao] = {
    "diario_incompleto": Explicacao(
        "Diário com aulas faltando no SUAP",
        "O SUAP registra só parte das aulas deste diário (o percentual está em cada item).",
        "O RIT declara a carga horária do PIT. Se o registro de aulas estiver incompleto, a avaliação pode "
        "questionar a diferença.",
        ["manter", "justificar"],
        "O mais comum é o registro de aulas estar atrasado: complete no SUAP (link “Ver no SUAP”) e mantenha. "
        "Se as aulas de fato não aconteceram, justifique.",
        {"manter": "Mantém o diário no relato. Complete o registro de aulas no SUAP antes de entregar o RIT."}),
    "sem_comprovante": Explicacao(
        "Atividade sem comprovante no SUAP",
        "A atividade aparece no SUAP, mas o SUAP não oferece declaração ou documento para ela.",
        "Sem comprovante, o item entra no relato, mas o PDF de anexos não tem como prová-lo.",
        ["manter", "remover_item", "justificar"],
        "Se você tem um comprovante (declaração, certificado, e-mail), coloque na pasta de entrada, no tópico "
        "certo, e mantenha. Se a atividade não aconteceu neste semestre, tire do relato."),
    "lattes_sem_comprovante": Explicacao(
        "Publicação ou atividade do Lattes sem comprovante",
        "Está no seu Lattes, com o ano do semestre, mas não achei nada correspondente no SUAP.",
        "O Lattes só informa o ano. Só entra no RIT o que é deste semestre, e com comprovante.",
        ["manter", "ignorar"],
        "Use a data da publicação (quando encontrada) para saber o semestre. Se for deste semestre, coloque o "
        "comprovante na pasta de entrada e mantenha; se não for, deixe de fora.",
        {"manter": "Entra no relato. Coloque o comprovante na pasta de entrada, no tópico certo."}),
    "ata_sem_anexo": Explicacao(
        "Ata registrada sem o PDF original",
        "Registrei a reunião pelo texto do e-mail, mas o PDF da ata não veio junto.",
        "O texto do e-mail serve de registro, mas a ata assinada é um comprovante mais forte.",
        ["manter", "ignorar"],
        "Se tiver a ata assinada, coloque na pasta de entrada (tópico Reuniões) e mantenha."),
    "datas": Explicacao(
        "Data deduzida da portaria",
        "A portaria não traz o período da atividade; usei a data da própria portaria.",
        "A data decide em quais semestres a atividade aparece.",
        ["manter", "ignorar"],
        "Se a data da portaria é uma boa referência, mantenha."),
    "afastamento": Explicacao(
        "Afastamento longo no semestre",
        "Você teve um afastamento de vários dias neste semestre.",
        "Afastamentos explicam atividades do PIT que não aconteceram.",
        ["justificar", "ignorar"],
        "Se o afastamento afetou atividades previstas no PIT, justifique em Alterações de Atividades."),
    "divergencia_pit": Explicacao(
        "Atividade prevista no PIT sem nada no semestre",
        "O PIT prevê atividades nesta categoria, mas não encontrei nenhuma no SUAP.",
        "A avaliação compara o RIT com o PIT. Atividades previstas que não aconteceram devem ser justificadas.",
        ["justificar", "ignorar"],
        "Se a atividade aconteceu, coloque o comprovante na pasta de entrada. Se não, justifique."),
    "entrada_sem_topico": Explicacao(
        "Arquivo na pasta de entrada sem tópico",
        "Há um arquivo solto na pasta de entrada, fora das subpastas de tópico.",
        "Sem tópico, o arquivo não entra em nenhum anexo.",
        ["ignorar"],
        "Mova o arquivo para a subpasta do tópico certo (ou me diga qual é)."),
    "anexo_grande": Explicacao(
        "Anexo acima de 10 MB",
        "O PDF de comprovantes deste tópico passou do limite do SUAP, mesmo comprimido.",
        "O SUAP recusa arquivos acima de 10 MB.",
        ["remover_item", "ignorar"],
        "Tire do relato os comprovantes menos importantes ou troque por versões menores."),
    "classificacao": Explicacao(
        "Tópico do RIT incerto",
        "Não tenho certeza em qual tópico do RIT esta atividade entra.",
        "Cada tópico tem seu relato e seu anexo.",
        ["manter", "remover_item"]),
    "download": Explicacao(
        "Não consegui baixar o comprovante",
        "O SUAP não entregou o PDF deste comprovante.",
        "Sem o PDF, o anexo fica sem essa prova.",
        ["manter", "remover_item"],
        "Tente coletar de novo mais tarde. Se persistir, baixe pelo link e coloque na pasta de entrada."),
    "estado_plano": Explicacao(
        "Situação do plano no SUAP",
        "O plano deste semestre não está em “RIT a preencher”.",
        "Só dá para salvar o RIT quando o SUAP abre o preenchimento.",
        ["ignorar"]),
}

_GENERICA = Explicacao("Pendência", "", "", ["manter", "ignorar", "justificar"])


def explicar(tipo: str) -> Explicacao:
    return CATALOGO.get(tipo, _GENERICA)


def opcoes(tipo: str) -> list[dict]:
    exp = explicar(tipo)
    return [{"decisao": d, "rotulo": OPCOES[d][0], "efeito": exp.extra_opcoes.get(d, OPCOES[d][1])}
            for d in exp.opcoes]


_LATTES_ANTIGO = re.compile(r"Lattes \((?P<categoria>[^,]+), (?P<ano>\d{4})\): (?P<titulo>.+?) — sem comprovante")
_DIARIO_ANTIGO = re.compile(r"^(?P<diario>.+?): (?P<ministrado>\d+)% da carga horária ministrada.*?atribuído (?P<atribuido>\d+)%")


def completar_detalhes(p: Pendencia) -> Pendencia:
    """Pendências de coletas antigas não têm `detalhes`: extrai o que der da mensagem (sem gravar)."""
    if p.detalhes:
        return p
    padrao = {"lattes_sem_comprovante": _LATTES_ANTIGO, "diario_incompleto": _DIARIO_ANTIGO}.get(p.tipo)
    if padrao and (m := padrao.search(p.mensagem)):
        p.detalhes = {k: v.strip() for k, v in m.groupdict().items()}
    return p


def resumo_item(p: Pendencia) -> str:
    """Uma linha que identifica o item, sem cortar no meio: título, dados principais e data."""
    d = p.detalhes
    if p.tipo == "lattes_sem_comprovante" and d.get("titulo"):
        partes = [d["titulo"]]
        extras = [d.get("tipo_publicacao") or d.get("categoria"), d.get("veiculo"), d.get("data") or d.get("ano")]
        partes += [e for e in extras if e]
        return " · ".join(partes)
    if p.tipo == "diario_incompleto" and d.get("diario"):
        return f"{d['diario']}: {d.get('ministrado', '?')}% das aulas registradas"
    if d.get("titulo"):
        return d["titulo"] + (f" · {d['papel']}" if d.get("papel") else "") + (
            f" · {d['periodo']}" if d.get("periodo") else "")
    return p.mensagem.split(". ")[0]


def sugestao_item(p: Pendencia) -> str:
    """Sugestão específica do item, quando os dados permitem (ex.: data da publicação fora do semestre)."""
    d = p.detalhes
    if p.tipo == "lattes_sem_comprovante" and d.get("semestre_provavel"):
        if d.get("semestre_provavel") == d.get("semestre_atual"):
            return f"Pela data ({d['data']}), parece ser deste semestre."
        return f"Pela data ({d['data']}), parece ser de {d['semestre_provavel']}: provavelmente fica de fora."
    if p.tipo == "diario_incompleto" and d.get("ministrado", "").isdigit() and int(d["ministrado"]) < 50:
        return "Menos da metade registrada: vale conferir o diário no SUAP."
    return ""
