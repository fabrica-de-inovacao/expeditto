"""E5 — preencher e SALVAR o formulário do RIT (pit_rit_v2), nunca entregar (D2, D23).

Fluxo: GET (CSRF + estado atual) → POST multipart com os 15 campos → GET de
verificação. Sempre enviamos todos os textos (o POST do Django substitui o
valor de cada textarea); anexos só são enviados para os tópicos que têm PDF.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from expeditto import acervo, config, html as h, textos
from expeditto.client import SuapClient
from expeditto.models import Manifest, Topico

_SUBMIT = "relatorioindividualtrabalhoprofessor_form"


def caminho_formulario(plano_id: int) -> str:
    return f"/pit_rit_v2/preencher_relatorio_individual_trabalho/{plano_id}/"


@dataclass
class EstadoFormulario:
    csrf: str
    textos: dict[str, str]  # campo → HTML atual
    arquivos_atuais: dict[str, str]  # campo → link do anexo já enviado (se o SUAP mostrar)
    campos_desconhecidos: list[str] = field(default_factory=list)


@dataclass
class Envio:
    textos: dict[str, str]  # obs_<topico> / alteracoes → HTML
    arquivos: dict[str, Path]  # arquivo_<topico> → PDF

    def resumo(self) -> list[str]:
        linhas = []
        for topico in Topico:
            texto = self.textos.get(topico.campo_texto, "")
            anexo = self.arquivos.get(topico.campo_arquivo)
            linhas.append(f"{topico.rotulo}: texto {len(texto)} caracteres; "
                          + (f"anexo {anexo.name} ({anexo.stat().st_size / 1048576:.2f} MB)" if anexo else "sem anexo"))
        linhas.append(f"Alterações de Atividades: {len(self.textos.get('alteracoes', ''))} caracteres")
        return linhas


# Após o 1º upload, o Django mostra "Atualmente: <link> [ ] Limpar" → campo `<arquivo>-clear`.
# Nunca o enviamos: reenviar o arquivo substitui; omitir mantém o atual.
_CAMPOS_ESPERADOS = {"csrfmiddlewaretoken", _SUBMIT, "alteracoes"} | {t.campo_texto for t in Topico} \
    | {t.campo_arquivo for t in Topico} | {f"{t.campo_arquivo}-clear" for t in Topico}


def ler_estado(pagina: str) -> EstadoFormulario:
    doc = h.documento(pagina)
    form = next((f for f in doc.iter("form") if f.xpath('.//textarea[@name="obs_apoio_ensino"]')), None)
    if form is None:
        raise ValueError("formulário do RIT não encontrado (plano sem RIT a preencher?)")
    csrf = form.xpath('.//input[@name="csrfmiddlewaretoken"]/@value')
    textos_atuais = {t.get("name"): (t.text or "") for t in form.iter("textarea")}
    arquivos = {}
    for inp in form.xpath('.//input[@type="file"]'):
        # "Atualmente: <a>…</a> Limpar Modificar: <input type=file>" — o link fica num ancestral próximo
        for bloco in list(inp.iterancestors())[:3]:
            if len(bloco.xpath('.//input[@type="file"]')) > 1:  # subiu demais: bloco de outro campo
                break
            link = next((a for a in bloco.iter("a") if a.get("href")), None)
            if link is not None:
                arquivos[inp.get("name")] = h.texto(link)
                break
    nomes = {e.get("name") for e in form.xpath(".//input|.//textarea|.//select") if e.get("name")}
    return EstadoFormulario(csrf=csrf[0] if csrf else "", textos=textos_atuais, arquivos_atuais=arquivos,
                            campos_desconhecidos=sorted(nomes - _CAMPOS_ESPERADOS))


def preparar(manifest: Manifest) -> Envio:
    codigo = manifest.semestre.codigo
    dados = {t.campo_texto: textos.carregar(codigo, t.value) or "" for t in Topico}
    alteracoes = textos.carregar(codigo, "alteracoes")
    dados["alteracoes"] = alteracoes or ""
    arquivos = {Topico(k).campo_arquivo: config.home() / a.arquivo for k, a in manifest.anexos.items()}
    return Envio(textos=dados, arquivos=arquivos)


def _normalizar(html_texto: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r">\s+<", "><", html_texto or "")).strip()


@dataclass
class ResultadoSalvar:
    url: str
    url_relatorio_pdf: str
    mensagens: list[str]
    textos_conferem: dict[str, bool]
    anexos_depois: dict[str, str]


def salvar(client: SuapClient, plano_id: int, envio: Envio) -> ResultadoSalvar:
    caminho = caminho_formulario(plano_id)
    estado = ler_estado(client.html(caminho))
    if estado.campos_desconhecidos:  # o SUAP mudou o formulário: não arriscar apagar algo
        raise RuntimeError(f"formulário tem campos inesperados: {estado.campos_desconhecidos}")
    dados = {"csrfmiddlewaretoken": estado.csrf, _SUBMIT: "Salvar", **envio.textos}
    arquivos = {campo: (p.name, p.read_bytes(), "application/pdf") for campo, p in envio.arquivos.items()}
    resposta = client.post_formulario(caminho, dados, arquivos)
    doc = h.documento(resposta.text)
    mensagens = [h.texto(e) for e in doc.xpath('//*[contains(@class,"msg") or contains(@class,"errorlist") '
                                              'or contains(@class,"errornote")]') if h.texto(e)]
    depois = ler_estado(client.html(caminho))
    conferem = {campo: _normalizar(depois.textos.get(campo, "")) == _normalizar(valor)
                for campo, valor in envio.textos.items()}
    base = client._http.base_url
    return ResultadoSalvar(url=str(base.join(caminho)),
                           url_relatorio_pdf=str(base.join(f"/pit_rit_v2/relatorio_atividade_docente_pdf/{plano_id}/")),
                           mensagens=mensagens,
                           textos_conferem=conferem, anexos_depois=depois.arquivos_atuais)


def salvar_semestre(client: SuapClient, codigo: str) -> ResultadoSalvar:
    manifest = acervo.carregar_manifest(codigo)
    if not manifest or not manifest.plano or not manifest.plano.plano_id:
        raise ValueError(f"semestre {codigo} sem acervo/plano coletado")
    return salvar(client, manifest.plano.plano_id, preparar(manifest))
