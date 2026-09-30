# Expeditto: instalador para Windows.
# Uso (PowerShell):
#   powershell -ExecutionPolicy ByPass -c "irm https://expeditto.fabitz.com.br/install.ps1 | iex"
#
# O que faz: instala o uv (gerenciador de Python da Astral) se faltar, instala o Expeditto
# com `uv tool install` e abre o assistente `expeditto instalar` (navegador, apps de IA,
# login no SUAP e diagnóstico). Não pede senha de administrador.

# 'Continue': o uv escreve o progresso no stderr, e o PowerShell 5.1 trataria isso como erro fatal.
# Falhas são conferidas pelo código de saída ($LASTEXITCODE).
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

# Até a publicação no PyPI, a origem é o código do GitHub (branch main).
$Origem = if ($env:EXPEDITTO_ORIGEM) { $env:EXPEDITTO_ORIGEM } else {
    'expeditto @ https://github.com/vnschneider/expeditto/archive/refs/heads/main.zip'
}

function Diga([string]$texto) { Write-Host "  $texto" -ForegroundColor DarkYellow }

Write-Host ''
Write-Host '  Expeditto' -ForegroundColor Yellow -NoNewline
Write-Host ' · seu segundo expediente, resolvido'
Write-Host ''

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Diga 'Instalando o uv (gerenciador de Python)...'
    powershell -NoProfile -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'Nao consegui instalar o uv.' }
}

Diga 'Instalando o Expeditto (pode levar 1 ou 2 minutos)...'
uv tool install --force --reinstall-package expeditto --python 3.12 $Origem
if ($LASTEXITCODE -ne 0) { throw 'Nao consegui instalar o Expeditto.' }
uv tool update-shell *> $null

$bin = (uv tool dir --bin).Trim()
$env:Path = "$bin;$env:Path"
if ($env:EXPEDITTO_SO_INSTALAR) { Diga "Instalado em $bin"; return }  # testes: sem o assistente
& (Join-Path $bin 'expeditto.exe') instalar
