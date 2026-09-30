# Integração com os hosts (MCP local, stdio) — D47

O mesmo servidor atende todos os hosts: `uv --directory <REPO> run suap-rit mcp`.
Troque `<REPO>` pelo caminho do repositório (ex.: `C:\Users\<voce>\Documents\GitHub\suap-cli-mcp`).

Pré-requisitos (uma vez): [uv](https://docs.astral.sh/uv/) instalado, `uv sync` no repositório e Google Chrome instalado. Sem Chrome, rode `uv run playwright install chromium`.

## Claude Desktop
Arquivo `%APPDATA%\Claude\claude_desktop_config.json` (Windows) ou `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "suap-rit": {
      "command": "uv",
      "args": ["--directory", "<REPO>", "run", "suap-rit", "mcp"]
    }
  }
}
```
Reinicie o Claude Desktop. O conector **Gmail** do Claude (Configurações › Conectores) permite ao Claude achar atas e chamar `registrar_ata` (D41).

## Claude Code
```bash
claude mcp add suap-rit -s user -- uv --directory "<REPO>" run suap-rit mcp
```

## OpenAI Codex (CLI, extensão de IDE e app desktop)
```bash
codex mcp add suap-rit -- uv --directory "<REPO>" run suap-rit mcp
```
ou em `~/.codex/config.toml`:
```toml
[mcp_servers.suap-rit]
command = "uv"
args = ["--directory", "<REPO>", "run", "suap-rit", "mcp"]
```

## Gemini CLI / Antigravity CLI
`~/.gemini/settings.json` (Gemini CLI) ou `~/.gemini/config/mcp_config.json` (Antigravity CLI):
```json
{
  "mcpServers": {
    "suap-rit": {
      "command": "uv",
      "args": ["--directory", "<REPO>", "run", "suap-rit", "mcp"],
      "timeout": 600000
    }
  }
}
```

## Uso
Peça ao assistente, por exemplo: *"Prepare meu RIT de 2025.1."* As instruções do servidor conduzem o fluxo:
login → coleta → atas do e-mail → pendências → anexos → relatos → prévia → **Salvar** (com a sua confirmação) → links para conferir e entregar.

Hosts sem integração de e-mail (CLIs) seguem sem atas por e-mail. Alternativas: backup OAuth da CLI (D42, a implementar) ou colocar os PDFs na pasta de entrada (E8).

## Ferramentas expostas
`status_sessao`, `login`, `status_tarefa`, `listar_semestres`, `coletar_semestre`, `resumo_semestre`, `registrar_ata`,
`resolver_pendencia`, `montar_anexos`, `contexto_topico`, `salvar_texto`, `gerar_rascunhos`, `gerar_alteracoes`,
`previa_preenchimento`, `salvar_no_suap` (exige `confirmado=true`; só grava rascunho, nunca entrega).
