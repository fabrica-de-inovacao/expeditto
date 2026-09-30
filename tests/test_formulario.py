"""E5 — formulário do RIT: somente "Salvar", com conferência após gravar."""

from pathlib import Path

import httpx
import pytest

from suap_rit import formulario
from suap_rit.client import RotaNaoPermitida, SuapClient
from suap_rit.models import Topico

CAMINHO = "/pit_rit_v2/preencher_relatorio_individual_trabalho/42/"


def _pagina(valores: dict[str, str], extra: str = "") -> str:
    areas = "".join(f'<textarea name="{t.campo_texto}">{valores.get(t.campo_texto, "")}</textarea>'
                    f'<input type="file" name="{t.campo_arquivo}">' for t in Topico)
    return (f'<html><body><form method="post" enctype="multipart/form-data">'
            f'<input type="hidden" name="csrfmiddlewaretoken" value="tok">{areas}'
            f'<textarea name="alteracoes">{valores.get("alteracoes", "")}</textarea>{extra}'
            f'<input type="submit" name="relatorioindividualtrabalhoprofessor_form" value="Salvar"></form></body></html>')


def test_salvar_envia_campos_e_confere(tmp_path: Path):
    gravado: dict[str, str] = {}
    recebidos = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            assert request.headers["Referer"].endswith(CAMINHO)
            corpo = request.content.decode("latin-1")
            recebidos["corpo"] = corpo
            for t in Topico:
                marca = f'name="{t.campo_texto}"\r\n\r\n'
                if marca in corpo:
                    gravado[t.campo_texto] = corpo.split(marca, 1)[1].split("\r\n--", 1)[0]
            return httpx.Response(302, headers={"Location": CAMINHO})
        return httpx.Response(200, text=_pagina({k: v.replace("<", "&lt;") for k, v in gravado.items()}))

    pdf = tmp_path / "03-orientacao-alunos.pdf"
    pdf.write_bytes(b"%PDF-1.4 teste")
    envio = formulario.Envio(textos={t.campo_texto: "" for t in Topico} | {"alteracoes": "",
                                     "obs_orientacao_alunos": "<p>Relato</p>"},
                             arquivos={"arquivo_orientacao_alunos": pdf})
    c = SuapClient({}, transport=httpx.MockTransport(handler), base_url="https://suap.test")
    r = formulario.salvar(c, 42, envio)
    assert 'name="relatorioindividualtrabalhoprofessor_form"' in recebidos["corpo"]
    assert 'filename="03-orientacao-alunos.pdf"' in recebidos["corpo"]
    assert r.textos_conferem["obs_orientacao_alunos"]
    assert r.url.endswith(CAMINHO)


def test_formulario_com_campo_novo_aborta():
    def handler(request):
        assert request.method == "GET", "não pode postar com formulário desconhecido"
        return httpx.Response(200, text=_pagina({}, extra='<input name="enviar_para_avaliacao" value="1">'))
    c = SuapClient({}, transport=httpx.MockTransport(handler), base_url="https://suap.test")
    with pytest.raises(RuntimeError, match="campos inesperados"):
        formulario.salvar(c, 42, formulario.Envio(textos={}, arquivos={}))


def test_escrita_so_no_formulario_do_rit():
    c = SuapClient({}, base_url="https://suap.test")
    for rota in ("/pit_rit_v2/entregar_relatorio/42/", "/edu/professor/", "/rh/servidor/1/"):
        with pytest.raises(RotaNaoPermitida):
            c.post_formulario(rota, {})


def test_campos_clear_do_django_sao_aceitos_e_anexo_atual_lido():
    extra = ('<p>Atualmente: <a href="https://s3/x.pdf">pit_rit_v2/01-apoio.pdf</a>'
             '<input type="checkbox" name="arquivo_apoio_ensino-clear"> Limpar Modificar:</p>')
    pagina = _pagina({}).replace('<input type="file" name="arquivo_apoio_ensino">',
                                 extra.replace("Modificar:", 'Modificar: <input type="file" name="arquivo_apoio_ensino">'))
    estado = formulario.ler_estado(pagina)
    assert estado.campos_desconhecidos == []
    assert estado.arquivos_atuais == {"arquivo_apoio_ensino": "pit_rit_v2/01-apoio.pdf"}
