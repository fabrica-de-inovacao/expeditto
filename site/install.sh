#!/bin/sh
# Expeditto: instalador para macOS e Linux.
# Uso:
#   curl -LsSf https://expeditto.fabitz.com.br/install.sh | sh
#
# O que faz: instala o uv (gerenciador de Python da Astral) se faltar, instala o Expeditto
# com `uv tool install` e abre o assistente `expeditto instalar` (navegador, apps de IA,
# login no SUAP e diagnóstico). Não usa sudo.
set -eu

# Até a publicação no PyPI, a origem é o código do GitHub (branch main).
ORIGEM="${EXPEDITTO_ORIGEM:-expeditto @ https://github.com/vnschneider/expeditto/archive/refs/heads/main.zip}"

diga() { printf '  \033[33m%s\033[0m\n' "$1"; }

printf '\n  \033[1;33mExpeditto\033[0m · seu segundo expediente, resolvido\n\n'

if ! command -v uv >/dev/null 2>&1; then
    diga "Instalando o uv (gerenciador de Python)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    PATH="$HOME/.local/bin:$PATH"
    export PATH
fi

diga "Instalando o Expeditto (pode levar 1 ou 2 minutos)..."
uv tool install --force --reinstall-package expeditto --python 3.12 "$ORIGEM"
uv tool update-shell >/dev/null 2>&1 || true

BIN="$(uv tool dir --bin)"
PATH="$BIN:$PATH"
export PATH
if [ -n "${EXPEDITTO_SO_INSTALAR:-}" ]; then diga "Instalado em $BIN"; exit 0; fi  # testes: sem o assistente
# stdin veio do curl: as perguntas do assistente leem do terminal
if [ -t 1 ] && [ -r /dev/tty ]; then
    "$BIN/expeditto" instalar </dev/tty
else
    "$BIN/expeditto" instalar --sim --sem-login
fi
