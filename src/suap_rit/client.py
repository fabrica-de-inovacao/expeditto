"""Cliente HTTP do SUAP sobre a sessão web do usuário.

Todo acesso passa por uma allowlist de rotas (decisão D28): apenas páginas e
documentos do próprio usuário. Rotas administrativas e ações de envio são
bloqueadas mesmo que a conta tenha permissão para elas.
"""

from __future__ import annotations

import re
import time

import httpx

from suap_rit.config import BASE_URL

_ROTAS_PERMITIDAS = [
    r"/edu/professor/(\?.*)?$",
    r"/edu/professor/\d+/",
    r"/rh/servidor/{matricula}/(\?.*)?$",
    r"/cnpq/curriculo/\d+/$",
    r"/pit_rit_v2/(preencher_relatorio_individual_trabalho|plano_atividade_docente_pdf|relatorio_atividade_docente_pdf)/\d+/$",
    r"/api/edu/meus-diarios/\d{4}/\d/$",
    r"/api/rh/minhas-ocorrencias-afastamentos/$",
    r"/(pesquisa|projetos|projetos_ensino)/projeto/\d+/(\?tab=\w+)?$",
    r"/edu/declaracao_participacao_projeto_final_pdf/\d+/\w+/(\?.*)?$",
    r"/edu/emitir_declaracao_de_orientacao_pdf/\d+/(estagios|aprendizagens|atividadesprofissionaisefetivas)/\d+/$",
    r"/projetos/emitir_certificado_extensao_pdf/\d+/$",
    r"/edu/declaracaodocencia_pdf/\d+/(\d{4}/)?$",
    r"/pesquisa/emitir_(declaracao_participacao|certificado)_pdf/\d+/$",
    r"/projetos_ensino/emitir_certificado_participacao_pdf/\d+/$",
    r"/(pesquisa|projetos|projetos_ensino)/emitir_declaracao_(orientacao|participacao)_pdf/\d+/$",
    r"/arquivo/visualizar_arquivo_pdf/[0-9a-f]+/?$",
    r"/documento_eletronico/(conteudo_documento|imprimir_documento_pdf)/\d+/(carta/)?$",
    r"/djtools/process2/[0-9a-f-]+/$",
    r"/djtools/process_progress2/[01]/[0-9a-f-]+/$",
]
_ROTAS_BLOQUEADAS = [r"/admin/", r"breadcrumbs_reset", r"entregar_relatorio", r"enviar_plano"]


class SessaoExpirada(Exception):
    """A sessão do SUAP expirou (≈90 min sem uso) — é preciso logar de novo."""


class RotaNaoPermitida(Exception):
    pass


class SuapClient:
    def __init__(self, cookies: dict[str, str], matricula: str | None = None,
                 base_url: str = BASE_URL, transport: httpx.BaseTransport | None = None):
        self.matricula = matricula
        self._http = httpx.Client(
            base_url=base_url,
            cookies=cookies,
            follow_redirects=True,
            timeout=60,
            headers={"User-Agent": "suap-rit/0.1 (+uso pessoal do docente)"},
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> SuapClient:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- política de rotas ---------------------------------------------------
    def verificar_rota(self, caminho: str) -> None:
        if any(re.search(p, caminho) for p in _ROTAS_BLOQUEADAS):
            raise RotaNaoPermitida(caminho)
        matricula = re.escape(self.matricula) if self.matricula else r"\d+"
        padroes = [p.replace("{matricula}", matricula) for p in _ROTAS_PERMITIDAS]
        if not any(re.match(p, caminho) for p in padroes):
            raise RotaNaoPermitida(caminho)

    # -- requisições ---------------------------------------------------------
    def _get(self, caminho: str, aba: bool = False) -> httpx.Response:
        self.verificar_rota(caminho)
        headers = {"X-Requested-With": "XMLHttpRequest"} if aba else {}
        resp = self._http.get(caminho, headers=headers)
        if "/accounts/login" in str(resp.url):
            raise SessaoExpirada()
        resp.raise_for_status()
        return resp

    def html(self, caminho: str, aba: bool = False) -> str:
        return self._get(caminho, aba=aba).text

    def json(self, caminho: str):
        return self._get(caminho).json()

    def pdf(self, caminho: str) -> bytes:
        conteudo = self._get(caminho).content
        if not conteudo.startswith(b"%PDF"):
            raise ValueError(f"resposta não é PDF: {caminho}")
        return conteudo

    def pdf_assincrono(self, caminho: str, espera: float = 2.0, limite: float = 120.0) -> bytes:
        """Documentos eletrônicos: o SUAP cria uma tarefa (`djtools/process2`) e
        o PDF fica disponível em `process_progress2/1/{uuid}` quando termina."""
        resp = self._get(caminho)
        m = re.search(r"/djtools/process2/([0-9a-f-]+)/", str(resp.url))
        if not m:
            raise ValueError(f"tarefa de PDF não iniciada: {caminho}")
        uuid = m[1]
        prazo = time.monotonic() + limite
        while time.monotonic() < prazo:
            status = self._get(f"/djtools/process_progress2/0/{uuid}/").text
            _pct, mensagem, arquivo, _url, erro = (status.split("::") + [""] * 5)[:5]
            if erro:
                raise RuntimeError(f"SUAP falhou ao gerar PDF: {mensagem}")
            if mensagem and arquivo:
                return self.pdf(f"/djtools/process_progress2/1/{uuid}/")
            time.sleep(espera)
        raise TimeoutError(f"PDF não ficou pronto em {limite}s: {caminho}")
