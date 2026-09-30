# suap-rit

Assistente do **Relatório Individual de Trabalho (RIT)** do SUAP IFMA. Faz o garimpo das evidências do docente no SUAP, organiza tudo por semestre e por tópico do RIT e baixa os comprovantes em PDF. A entrega do RIT continua sendo feita pelo docente.

- Descoberta e visão do produto: [`docs/discovery.md`](docs/discovery.md)
- Rotas e telas do SUAP mapeadas: [`docs/mapa-suap-ifma.md`](docs/mapa-suap-ifma.md)
- Decisões e regras de negócio: [`docs/decisoes.md`](docs/decisoes.md)

## Uso (protótipo 1 — CLI)

```bash
uv sync
uv run suap-rit login            # janela do SUAP para login (CAPTCHA/Gov.br); fecha sozinha
uv run suap-rit semestres        # estado do PIT/RIT por semestre + links
uv run suap-rit coletar 2025.1   # coleta, classifica e baixa comprovantes
uv run suap-rit status 2025.1    # resumo por tópico + pendências
uv run suap-rit logout           # apaga a sessão do keyring
```

O acervo fica em `~/suap-rit/` (ou em `SUAP_RIT_HOME`):

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
