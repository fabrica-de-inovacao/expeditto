"""Orquestração: coleta no SUAP → alocação por semestre → classificação → acervo."""

from __future__ import annotations

import re
import shutil
import unicodedata
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path

from pypdf import PdfReader

from expeditto import acervo, semestres
from expeditto.acervo import Cache
from expeditto.classificar import classificar
from expeditto.html import parse_data
from expeditto.client import SuapClient
from expeditto.models import (
    EstadoPlano, Evidencia, ItemAcervo, Manifest, Pendencia, Perfil, PlanoSemestre, Semestre, TipoEvidencia, Topico,
)
from expeditto.suap import diarios, ensino, perfil as perfil_mod, planos, servidor

# Legenda/categoria das atividades do PIT → tópico do RIT (para detectar divergências, D6).
CATEGORIAS_PIT = [
    (r"prepara", Topico.APOIO_ENSINO),
    (r"programas ou projetos de ensino|programas e projetos", Topico.PROGRAMAS_PROJETOS_ENSINO),
    (r"atendimento", Topico.ORIENTACAO_ALUNOS),
    (r"reuni", Topico.REUNIOES),
    (r"pesquisa", Topico.PESQUISA),
    (r"extens", Topico.EXTENSAO),
    (r"gest", Topico.GESTAO),
]
_AFASTAMENTO_RELEVANTE_DIAS = 15

Progresso = Callable[[str], None]


def _nada(_: str) -> None:
    pass


def setup(client: SuapClient) -> Perfil:
    perfil = perfil_mod.carregar(client)
    anterior = acervo.carregar_perfil()
    if anterior:  # preserva calendário já confirmado
        perfil.semestres = anterior.semestres
    acervo.salvar_perfil(perfil)
    return perfil


def _vizinhos(codigo: str) -> list[str]:
    ano, p = map(int, codigo.split("."))
    anterior = f"{ano - 1}.2" if p == 1 else f"{ano}.1"
    proximo = f"{ano}.2" if p == 1 else f"{ano + 1}.1"
    return [anterior, codigo, proximo]


def calendario(client: SuapClient, perfil: Perfil, codigo: str) -> tuple[dict[str, Semestre], list[Evidencia]]:
    sems, diarios_semestre = {}, []
    for c in _vizinhos(codigo):
        lista, s = diarios.carregar(client, c)
        confirmado = perfil.semestres.get(c)
        if confirmado and confirmado.fonte_datas == "usuario":
            s = confirmado
        sems[c] = s if s.inicio else semestres.estimar(c)
        if c == codigo:
            diarios_semestre = lista
    perfil.semestres.update(sems)
    acervo.salvar_perfil(perfil)
    return sems, diarios_semestre


def _limitar_portarias_por_funcao(evidencias: list[Evidencia]) -> None:
    """Portaria de designação de FCC/CC tem vigência aberta; o fim real vem do
    histórico de funções (D16: anexar enquanto a função estiver vigente)."""
    funcoes = [e for e in evidencias if e.tipo == TipoEvidencia.FUNCAO and e.inicio]
    for ev in evidencias:
        if ev.tipo != TipoEvidencia.PORTARIA:
            continue
        if not ev.extras.get("tipo_arquivo", "").startswith(("Designação de FCC", "Portaria de nomeação")):
            continue
        ref = ev.inicio or ev.data_evento
        if not ref:
            continue
        casada = min(funcoes, key=lambda f: abs((f.inicio - ref).days), default=None)
        if casada and abs((casada.inicio - ref).days) <= 90:
            ev.inicio, ev.fim, ev.data_evento = ref, casada.fim, None
            ev.vigencia_indeterminada = casada.fim is None
            ev.extras["funcao_vinculada"] = casada.id


_ORGAOS = [
    (r"n[úu]cleo docente estruturante|\bnde\b", "nde"),
    (r"colegiado", "colegiado"),
    (r"comiss[ãa]o local de execu[çc][ãa]o de projetos|f[áa]brica de inova", "fabrica-inovacao"),
]


def _curso(texto: str) -> str:
    """'...do Curso Bacharelado em Sistemas de Informação do IFMA Campus...' → 'sistemas-de-informacao'."""
    m = re.search(
        r"curso\s+(?:de\s+|do\s+|da\s+)?"
        r"(?:(?:bacharel(?:ado)?|licenciatura|t[ée]cnico|superior de tecnologia)\s+(?:em|de)\s+)?"
        r"([a-zà-ú ]+?)(?=\s+d[oa] ifma|\s+d[oa] campus|\s+no [âa]mbito|\s+campus|\s+modalidade|\s*[/,.;(\-]|$)",
        texto)
    return _slug(m[1]) if m else ""


def _grupo_portaria(ev: Evidencia) -> str | None:
    """Órgão/cargo que a portaria compõe — portarias do mesmo grupo se substituem."""
    if ev.extras.get("tipo_arquivo", "").startswith(("Designação de FCC", "Portaria de nomeação")):
        return "funcao-comissionada"
    alvo = f"{ev.descricao} {ev.extras.get('assunto', '')}".lower()
    for padrao, orgao in _ORGAOS:
        if re.search(padrao, alvo):
            return f"{orgao}:{_curso(alvo)}"
    return None


def _encerrar_substituidas(evidencias: list[Evidencia]) -> None:
    """Uma nova composição de NDE/Colegiado/comissão encerra a anterior do mesmo
    órgão. Sem isso, portarias "a partir desta data" valeriam para sempre."""
    grupos: dict[str, list[Evidencia]] = {}
    for ev in evidencias:
        if ev.tipo == TipoEvidencia.PORTARIA and ev.inicio and (grupo := _grupo_portaria(ev)):
            grupos.setdefault(grupo, []).append(ev)
    for lista in grupos.values():
        lista.sort(key=lambda e: e.inicio)
        for atual, seguinte in zip(lista, lista[1:]):
            if atual.fim is None or atual.fim >= seguinte.inicio:
                atual.fim = seguinte.inicio - timedelta(days=1)
                atual.vigencia_indeterminada = False
                atual.extras["substituida_por"] = seguinte.id


def _comprovar_funcoes(evidencias: list[Evidencia]) -> None:
    """A função (histórico) é comprovada pela portaria de designação vinculada."""
    for ev in evidencias:
        if (vinculo := ev.extras.get("funcao_vinculada")):
            funcao = next((f for f in evidencias if f.id == vinculo), None)
            if funcao:
                funcao.extras["comprovada_por"] = ev.id


def _comprovante_por_banca(evidencias: list[Evidencia]) -> None:
    """Orientação de TCC não tem declaração própria: usa a de presidente da banca."""
    presidentes = {e.extras.get("tcc_id"): e.url_comprovante for e in evidencias
                   if e.tipo == TipoEvidencia.BANCA and e.extras.get("papel") == "presidente"}
    for ev in evidencias:
        if ev.tipo == TipoEvidencia.ORIENTACAO_TCC and not ev.url_comprovante:
            ev.url_comprovante = presidentes.get(ev.extras.get("tcc_id"))


def _slug(texto: str, limite: int = 60) -> str:
    base = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower()[:limite] or "documento"


def _validade(pdf: Path) -> date | None:
    """Documentos emitidos pelo SUAP trazem "Válido até: dd/mm/aaaa" (ex.: banca 30 dias,
    projeto de ensino 1 ano); portarias e certificados de pesquisa/extensão não expiram."""
    try:
        texto = " ".join((p.extract_text() or "") for p in PdfReader(pdf).pages[-1:])
    except Exception:  # noqa: BLE001 — PDF ilegível não impede o uso
        return None
    m = re.search(r"V[áa]lid[oa] at[ée]:?\s*(\d{2}/\d{2}/\d{4})", texto)
    return parse_data(m[1]) if m else None


def _baixar(client: SuapClient, cache: Cache, ev: Evidencia) -> tuple[Path, date | None]:
    obter = (lambda: client.pdf_assincrono(ev.url_comprovante)) if ev.comprovante_assincrono \
        else (lambda: client.pdf(ev.url_comprovante))
    # chave pela URL: o mesmo PDF pode comprovar mais de uma evidência (TCC e banca)
    chave = f"comprovante-{ev.url_comprovante}"
    caminho = cache.caminho(chave, "pdf")
    if caminho.exists() and (v := _validade(caminho)) and v < date.today():
        caminho.unlink()  # vencido: emite de novo
    caminho = cache.bytes(chave, obter)
    return caminho, _validade(caminho)


def _ministrado_incompleto(ev: Evidencia, pdf: Path, semestre: Semestre) -> list[Pendencia]:
    """A declaração de docência mostra o % de carga horária ministrada registrada no diário.
    Semestre encerrado com menos de 100% chama atenção da chefia → avisar o docente."""
    if not semestre.fim or semestre.fim >= date.today():
        return []
    texto = " ".join((p.extract_text() or "") for p in PdfReader(pdf).pages)
    atribuido, ministrado = ensino.percentuais_docencia(texto).get(ev.extras.get("diario_id", ""), (0, 100))
    if ministrado >= 100:
        return []
    return [Pendencia(tipo="diario_incompleto", evidencia_id=ev.id,
                      mensagem=f"{ev.titulo}: {ministrado}% da carga horária ministrada registrada no SUAP "
                               f"(atribuído {atribuido}%). Completar o registro de aulas antes de enviar o RIT, "
                               f"ou justificar em 'Alterações de Atividades'.")]


def _declaracao_de_estagio(ev: Evidencia, semestre: Semestre) -> None:
    """Estágios não têm declaração individual: usa a declaração anual da modalidade."""
    if ev.tipo == TipoEvidencia.ESTAGIO and not ev.url_comprovante:
        ev.url_comprovante = ev.extras.get(f"declaracao_{semestre.ano}")


def _pendencias_pit(plano: PlanoSemestre | None, itens: list[ItemAcervo]) -> list[Pendencia]:
    if not plano:
        return []
    cobertos = {t for i in itens for t in i.topicos}
    pendencias = []
    for categoria, atividades in plano.atividades_pit.items():
        if not atividades:
            continue
        topico = next((t for padrao, t in CATEGORIAS_PIT if re.search(padrao, categoria, re.I)), None)
        if topico and topico not in cobertos:
            pendencias.append(Pendencia(
                tipo="divergencia_pit",
                mensagem=f"O PIT prevê atividades em '{categoria}' ({len(atividades)} itens), mas nenhuma "
                         f"evidência foi encontrada para '{topico.rotulo}'. Declarar em 'Alterações de "
                         f"Atividades' ou adicionar comprovantes?",
            ))
    return pendencias


def coletar_semestre(client: SuapClient, perfil: Perfil, codigo: str, baixar: bool = True,
                     progresso: Progresso = _nada) -> Manifest:
    cache = Cache()
    progresso(f"Plano {codigo}")
    plano = planos.carregar(client, codigo)
    progresso("Calendário do semestre (diários)")
    sems, diarios_semestre = calendario(client, perfil, codigo)
    janela = semestres.janelas(sems)[codigo]

    progresso("Estágios, TCCs e bancas")
    docencia = ensino.declaracoes_docencia(client.html("/edu/professor/?tab=disciplinas", aba=True))
    for diario in diarios_semestre:  # D39: diários comprovados pela declaração anual de docência
        diario.url_comprovante = docencia.get(str(sems[codigo].ano))
    evidencias = diarios_semestre + ensino.coletar(client)
    progresso("Pasta funcional, projetos e funções")
    evidencias += servidor.coletar(client, perfil, cache)
    itens_lattes = []
    if perfil.lattes_suap:
        progresso("Lattes importado no SUAP (detector de lacunas)")
        from expeditto import lattes
        itens_lattes = lattes.parse(client.html(perfil.lattes_suap))
    _limitar_portarias_por_funcao(evidencias)
    _encerrar_substituidas(evidencias)
    _comprovar_funcoes(evidencias)
    _comprovante_por_banca(evidencias)

    letivo = (sems[codigo].inicio, sems[codigo].fim)
    do_semestre = [e for e in evidencias if semestres.pertence(e, codigo, janela, letivo=letivo)]
    pasta = acervo.pasta_semestre(codigo)
    itens: list[ItemAcervo] = []
    pendencias: list[Pendencia] = []
    copiados: set[tuple[Topico, str]] = set()
    if plano.estado != EstadoPlano.RIT_A_PREENCHER:
        pendencias.append(Pendencia(tipo="estado_plano",
                                    mensagem=f"Estado do plano {codigo}: {plano.estado.value}."))

    for ev in do_semestre:
        cls = classificar(ev)
        if ev.tipo == TipoEvidencia.AFASTAMENTO:
            dias = (ev.fim - ev.inicio).days + 1 if ev.inicio and ev.fim else 0
            if dias >= _AFASTAMENTO_RELEVANTE_DIAS:
                pendencias.append(Pendencia(tipo="afastamento", evidencia_id=ev.id,
                                            mensagem=f"Afastamento de {dias} dias ({ev.titulo}). "
                                                     f"Mencionar em 'Alterações de Atividades'?"))
            continue
        _declaracao_de_estagio(ev, sems[codigo])
        arquivo = validade = None
        if ev.url_comprovante and baixar:
            progresso(f"Baixando: {ev.titulo[:60]}")
            try:
                origem, validade = _baixar(client, cache, ev)
                arquivo = str(origem.relative_to(acervo.config.home()))
                for topico in cls.topicos:  # cópia física por tópico (pedido da cliente)
                    if (topico, origem.name) in copiados:
                        continue
                    copiados.add((topico, origem.name))
                    destino = pasta / topico.pasta / f"{_slug(ev.titulo)}-{origem.stem[-10:]}.pdf"
                    destino.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(origem, destino)
            except Exception as erro:  # noqa: BLE001 — registra e segue com os demais
                pendencias.append(Pendencia(tipo="download", evidencia_id=ev.id,
                                            mensagem=f"Falha ao baixar comprovante: {erro}"))
        elif not ev.url_comprovante and ev.tipo != TipoEvidencia.DIARIO \
                and not ev.extras.get("comprovada_por"):
            situacao = ev.extras.get("situacao", "")
            detalhe = f" (situação no SUAP: {situacao} — confirmar se entra no RIT)" \
                if situacao and "Conclu" not in situacao else ""
            pendencias.append(Pendencia(tipo="sem_comprovante", evidencia_id=ev.id,
                                        mensagem=f"Sem comprovante no SUAP: {ev.titulo}{detalhe}"))
        if ev.tipo == TipoEvidencia.DIARIO and arquivo:
            pendencias += _ministrado_incompleto(ev, acervo.config.home() / arquivo, sems[codigo])
        if cls.incerta:
            pendencias.append(Pendencia(tipo="classificacao", evidencia_id=ev.id,
                                        mensagem=f"Tópico incerto para '{ev.titulo}': {cls.motivo}"))
        if ev.extras.get("datas_inferidas"):
            pendencias.append(Pendencia(tipo="datas", evidencia_id=ev.id,
                                        mensagem=f"'{ev.titulo}': {ev.extras['datas_inferidas']}"))
        itens.append(ItemAcervo(evidencia_id=ev.id, topicos=cls.topicos, motivo=cls.motivo, arquivo=arquivo,
                                validade=validade))

    pendencias += _pendencias_pit(plano, itens)
    manifest = Manifest(
        semestre=sems[codigo],
        plano=plano,
        gerado_em=datetime.now(),
        evidencias={e.id: e for e in do_semestre},
        itens=itens,
        pendencias=pendencias,
    )
    from expeditto import atas, entrada, lattes, pendencias as decisoes  # import tardio: evita ciclo com textos

    atas.aplicar(manifest)  # atas registradas pelo host (e-mail) sobrevivem a novas coletas
    entrada.aplicar(manifest)  # comprovantes colocados pelo docente na pasta de entrada (E8)
    manifest.pendencias += lattes.lacunas(manifest, itens_lattes, evidencias)  # E7 (compara com tudo)
    decisoes.aplicar(manifest)  # decisões já tomadas pelo docente não são perguntadas de novo
    acervo.salvar_manifest(manifest)
    return manifest

