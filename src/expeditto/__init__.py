"""Expeditto — seu segundo expediente, resolvido. Assistente da burocracia docente (RIT do SUAP IFMA)."""


def main() -> None:
    import sys

    # Console do Windows usa cp1252 por padrão quando a saída é redirecionada.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    from expeditto.cli import app

    app()
