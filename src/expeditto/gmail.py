"""D42 — backup de e-mail para hosts sem conector: app OAuth próprio, somente leitura.

Login: fluxo "loopback" (abre o navegador, o docente entra no Google e a CLI recebe
o token em http://localhost). Escopo `gmail.readonly` (restrito): enquanto o app do
Google Cloud estiver em modo "Testing", cada conta precisa estar na lista de testers
e o consentimento expira em 7 dias. As credenciais do app ficam em
`~/expeditto/google_client.json` (ou `EXPEDITTO_GOOGLE_CLIENT`); tokens no keyring.
"""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import timedelta
from pathlib import Path

import httpx
import keyring

from expeditto import acervo, atas, config
from expeditto.models import Semestre

ESCOPOS = ["https://www.googleapis.com/auth/gmail.readonly", "openid",
           "https://www.googleapis.com/auth/userinfo.email"]
API = "https://gmail.googleapis.com/gmail/v1/users/me"
PALAVRAS = ["ata", "atas", "convocação", "convocacao", "reunião", "reuniao", "NDE", "colegiado", "conselho",
            "comissão", "comissao", "banca", "portaria"]


def _arquivo_cliente() -> Path:
    return Path(os.environ.get("EXPEDITTO_GOOGLE_CLIENT", config.home() / "google_client.json"))


def _contas_arquivo() -> Path:
    return config.home() / "gmail_contas.json"


def contas() -> list[str]:
    origem = _contas_arquivo()
    return json.loads(origem.read_text(encoding="utf-8")) if origem.exists() else []


def login(conta_sugerida: str | None = None) -> str:
    """Abre o navegador para autorizar leitura do Gmail; devolve o e-mail autorizado."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    cliente = _arquivo_cliente()
    if not cliente.exists():
        raise FileNotFoundError(
            f"Credenciais do app Google não encontradas em {cliente}. Baixe o JSON do cliente OAuth "
            f"'Desktop app' do projeto Google Cloud da ferramenta e salve nesse caminho.")
    fluxo = InstalledAppFlow.from_client_secrets_file(str(cliente), scopes=ESCOPOS)
    extra = {"login_hint": conta_sugerida} if conta_sugerida else {}
    cred = fluxo.run_local_server(port=0, open_browser=True, prompt="consent", **extra)
    email = httpx.get(f"{API}/profile", headers={"Authorization": f"Bearer {cred.token}"}).json()["emailAddress"]
    keyring.set_password(config.KEYRING_SERVICE, f"gmail:{email}", cred.to_json())
    _contas_arquivo().write_text(json.dumps(sorted(set(contas()) | {email})), encoding="utf-8")
    return email


def _token(email: str) -> str:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    bruto = keyring.get_password(config.KEYRING_SERVICE, f"gmail:{email}")
    if not bruto:
        raise PermissionError(f"Conta {email} não autorizada: rode `expeditto gmail-login`.")
    cred = Credentials.from_authorized_user_info(json.loads(bruto), ESCOPOS)
    if not cred.valid:
        cred.refresh(Request())  # expira em 7 dias no modo "Testing" → novo login
        keyring.set_password(config.KEYRING_SERVICE, f"gmail:{email}", cred.to_json())
    return cred.token


def consulta(semestre: Semestre) -> str:
    """Busca "burra" (D20): palavras-chave + período do semestre (com folga de 30 dias)."""
    inicio = semestre.inicio - timedelta(days=15)
    fim = semestre.fim + timedelta(days=30)
    termos = " OR ".join(PALAVRAS)
    return f"({termos}) after:{inicio:%Y/%m/%d} before:{fim:%Y/%m/%d}"


@dataclass
class Candidata:
    conta: str
    id_mensagem: str
    assunto: str
    data: str
    remetente: str
    trecho: str
    anexos_pdf: list[str]


def _cabecalho(msg: dict, nome: str) -> str:
    return next((h["value"] for h in msg.get("payload", {}).get("headers", []) if h["name"].lower() == nome), "")


def _partes(parte: dict):
    yield parte
    for p in parte.get("parts", []) or []:
        yield from _partes(p)


def _b64(dado: str) -> bytes:
    return base64.urlsafe_b64decode(dado + "=" * (-len(dado) % 4))


def buscar(semestre: Semestre, cliente: httpx.Client | None = None, limite: int = 50) -> list[Candidata]:
    candidatas = []
    http = cliente or httpx.Client(timeout=60)
    for conta in contas():
        headers = {"Authorization": f"Bearer {_token(conta)}"}
        lista = http.get(f"{API}/messages", params={"q": consulta(semestre), "maxResults": limite},
                         headers=headers).json()
        for ref in lista.get("messages", []):
            msg = http.get(f"{API}/messages/{ref['id']}", params={"format": "full"}, headers=headers).json()
            pdfs = [p.get("filename") for p in _partes(msg.get("payload", {}))
                    if (p.get("filename") or "").lower().endswith(".pdf")]
            candidatas.append(Candidata(conta, ref["id"], _cabecalho(msg, "subject"), _cabecalho(msg, "date"),
                                        _cabecalho(msg, "from"), msg.get("snippet", ""), pdfs))
    _salvar_candidatas(semestre.codigo, candidatas)
    return candidatas


def _salvar_candidatas(codigo: str, candidatas: list[Candidata]) -> None:
    destino = acervo.pasta_semestre(codigo) / "gmail_candidatas.json"
    destino.write_text(json.dumps([asdict(c) for c in candidatas], ensure_ascii=False, indent=2), encoding="utf-8")


def candidatas_salvas(codigo: str) -> list[Candidata]:
    origem = acervo.pasta_semestre(codigo) / "gmail_candidatas.json"
    return [Candidata(**c) for c in json.loads(origem.read_text(encoding="utf-8"))] if origem.exists() else []


def _texto_corpo(msg: dict) -> str:
    for parte in _partes(msg.get("payload", {})):
        if parte.get("mimeType") == "text/plain" and parte.get("body", {}).get("data"):
            return _b64(parte["body"]["data"]).decode("utf-8", "replace")
    return msg.get("snippet", "")


def registrar(codigo: str, numeros: list[int], cliente: httpx.Client | None = None) -> list[dict]:
    """Registra como atas as candidatas escolhidas (1..N) — baixa o PDF anexo quando houver."""
    candidatas = candidatas_salvas(codigo)
    registradas = []
    http = cliente or httpx.Client(timeout=60)
    for n in numeros:
        c = candidatas[n - 1]
        headers = {"Authorization": f"Bearer {_token(c.conta)}"}
        msg = http.get(f"{API}/messages/{c.id_mensagem}", params={"format": "full"}, headers=headers).json()
        anexo_b64, nome = None, None
        for parte in _partes(msg.get("payload", {})):
            if (parte.get("filename") or "").lower().endswith(".pdf") and parte.get("body", {}).get("attachmentId"):
                dado = http.get(f"{API}/messages/{c.id_mensagem}/attachments/{parte['body']['attachmentId']}",
                                headers=headers).json()["data"]
                anexo_b64, nome = base64.b64encode(_b64(dado)).decode(), parte["filename"]
                break
        data = re.sub(r"\s*\(.*\)$", "", c.data)
        registradas.append(atas.registrar(codigo, c.assunto, _data_iso(data), c.remetente, c.id_mensagem,
                                          _texto_corpo(msg), anexo_b64, nome))
    return registradas


def _data_iso(cabecalho_data: str) -> str:
    from email.utils import parsedate_to_datetime

    try:
        return parsedate_to_datetime(cabecalho_data).date().isoformat()
    except (TypeError, ValueError):
        return cabecalho_data
