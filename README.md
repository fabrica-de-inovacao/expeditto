# Expeditto

> **Seu segundo expediente, resolvido.** Assistente da burocracia docente. Hoje ele prepara o **Relatório Individual de Trabalho (RIT)** do SUAP IFMA: garimpa seus comprovantes, organiza por semestre e tópico, redige os relatos e deixa o rascunho salvo no SUAP para você conferir e entregar.

Ferramenta **independente e não oficial**. Roda no seu computador, com a sua sessão do SUAP, e **nunca entrega o relatório por você**. Licença [AGPL-3.0](LICENSE).

Funciona pelo terminal (`expeditto`) e dentro do seu assistente de IA (servidor MCP para Claude Desktop, Claude Code, Codex e Gemini/Antigravity CLI).

- Descoberta e visão do produto: [`docs/discovery.md`](docs/discovery.md)
- Rotas e telas do SUAP mapeadas: [`docs/mapa-suap-ifma.md`](docs/mapa-suap-ifma.md)
- Decisões e regras de negócio: [`docs/decisoes.md`](docs/decisoes.md)

## Instalação

Windows (PowerShell):

```powershell
irm https://expeditto.fabitz.com.br/install.ps1 | iex
```

macOS e Linux:

```bash
curl -LsSf https://expeditto.fabitz.com.br/install.sh | sh
```

O instalador coloca o [uv](https://docs.astral.sh/uv/) se faltar, instala o Expeditto e abre o assistente
`expeditto instalar`: navegador para o login, pasta de dados, conexão com os apps de IA (Claude Desktop, Claude Code,
Codex, Gemini CLI, Antigravity), login no SUAP e diagnóstico. Depois: `expeditto atualizar` e `expeditto desinstalar`
(tira o Expeditto dos apps; os dados só saem se você pedir).

## Interface visual (terminal)

```bash
uv sync
uv run expeditto                  # tela cheia: semestres, preparar RIT, pendências, anexos, relatos, salvar
uv run expeditto --semestre 2025.2 --alto-contraste
uv run expeditto doctor           # diagnóstico: navegador, sessão, apps de IA conectados
```

O despertador laranja é o mascote do Expeditto (pixel art em `docs/marca/`). Mouse e teclado funcionam em
todas as telas; em janelas pequenas o mascote dá lugar ao conteúdo.

## Uso (comandos)

```bash
uv run expeditto login            # janela do SUAP para login (CAPTCHA/Gov.br); fecha sozinha
uv run expeditto semestres        # estado do PIT/RIT por semestre + links
uv run expeditto coletar 2025.1   # coleta, classifica e baixa comprovantes
uv run expeditto status 2025.1    # resumo por tópico + pendências
uv run expeditto montar 2025.1    # 1 PDF por tópico (capa + índice), ≤ 10 MB
uv run expeditto textos 2025.1    # rascunhos dos Relatos (HTML)
uv run expeditto entrada 2025.1   # onde colocar comprovantes próprios
uv run expeditto preencher 2025.1 [--salvar]   # prévia; com --salvar grava rascunho (nunca entrega)
uv run expeditto gmail-login / gmail-atas 2025.1   # backup de atas por e-mail
uv run expeditto mcp              # servidor MCP (ver docs/integracao-hosts.md)
uv run expeditto logout           # apaga a sessão do keyring e o perfil do navegador
```

O acervo fica em `~/expeditto/` (ou em `EXPEDITTO_HOME`):

```
perfil.json                      # contexto do docente (allowlist, sem dados sensíveis)
_cache/                          # downloads e textos de portarias, por chave estável
2025.1/manifest.json             # evidências, tópicos, motivos e pendências
2025.1/01-apoio-ensino/*.pdf     # uma pasta por tópico do RIT (cópia física)
...
```

## Estado

O protótipo 1 foi validado com dados reais (2025.1): 72 evidências nos 7 tópicos, 65 delas comprovadas por 54 PDFs distintos, e 1 pendência legítima. Os números estão em [`docs/decisoes.md` §10](docs/decisoes.md). Próximo passo: servidor MCP, Gmail, junção dos PDFs, textos e "Salvar" (protótipo 2).

## Garantias

- **Somente leitura no protótipo 1.** Nada é salvo nem enviado no SUAP.
- **Allowlist de rotas** (`client.py`): só páginas e documentos do próprio usuário. `/admin/`, `entregar_relatorio` e `enviar_plano` ficam bloqueados.
- **Minimização de dados**: o perfil lê só os campos da allowlist (D26). CPF, dados bancários, endereço etc. nem são extraídos.
- **Sessão no keyring do SO**, válida por cerca de 90 min. A senha nunca passa pela ferramenta.

## Testes

```bash
uv run pytest
```
