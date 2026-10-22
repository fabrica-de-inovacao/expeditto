"""Expeditto — seu segundo expediente, resolvido. Assistente da burocracia docente (RIT do SUAP IFMA)."""


def main() -> None:
    import sys

    # Console do Windows usa cp1252 por padrão quando a saída é redirecionada.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    # Certificados do sistema em vez da lista embutida do Python: antivírus com varredura HTTPS e redes
    # com proxy instalam a própria raiz no Windows, e sem isso toda conexão dá CERTIFICATE_VERIFY_FAILED.
    import truststore

    truststore.inject_into_ssl()

    from expeditto.cli import app

    app()
