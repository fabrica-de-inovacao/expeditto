# Versões, avisos e atualização

## Publicar uma versão nova

1. Suba o número em `pyproject.toml` (`version = "0.4.0"`) e faça o merge na `main`.
2. Crie e envie a tag:
   ```bash
   git tag v0.4.0 && git push origin v0.4.0
   ```
3. O workflow `.github/workflows/release.yml` confere se a tag bate com o `pyproject.toml`, roda os testes e
   publica a release com as notas geradas pelos PRs.

## O que o docente vê

- **Terminal:** qualquer comando (menos `mcp`, `doctor` e `atualizar`) mostra uma linha amarela
  "Há uma versão nova do Expeditto: 0.4.0 (você tem a 0.3.0). Para atualizar: expeditto atualizar".
- **Interface (`expeditto`):** um aviso na tela inicial pedindo para sair e rodar `expeditto atualizar`.
- **Chat (MCP):** `preparar_rit` traz o campo `atualizacao`; o assistente avisa uma vez e, se o docente pedir,
  chama `atualizar_expeditto(confirmado=true)`. Também há `verificar_atualizacao`.

A consulta à última release fica em cache por um dia (`~/expeditto/.atualizacao.json`), leva no máximo 2,5 s e,
sem internet, simplesmente não gera aviso. Para desligar: `EXPEDITTO_SEM_ATUALIZACAO=1`.

## Como a atualização roda

`uv tool install --force` apontando para o `.zip` da tag da release (até a publicação no PyPI).

- **macOS e Linux:** instala na hora. Depois, basta reiniciar o app de IA.
- **Windows:** enquanto o Expeditto roda, os arquivos dele ficam travados (o próprio comando `atualizar`, a
  interface ou o servidor MCP). Por isso a reinstalação roda num processo separado que espera o Expeditto fechar:
  - pelo terminal, abre uma janela do PowerShell mostrando o andamento;
  - pelo chat, roda em segundo plano (log em `~/expeditto/atualizacao.log`) assim que o app de IA for fechado.

## Permissões nos apps de IA

Todas as ferramentas declaram anotações MCP (`readOnlyHint`, `destructiveHint`, `idempotentHint`,
`openWorldHint`). Só `salvar_no_suap` e `atualizar_expeditto` são marcadas como sensíveis.

- **Claude Code:** o instalador adiciona `mcp__expeditto` em `permissions.allow` do `~/.claude/settings.json` e
  deixa `salvar_no_suap` e `atualizar_expeditto` em `permissions.ask`. A desinstalação remove essas regras.
- **Gemini CLI:** o servidor é registrado com `"trust": true`.
- **Claude Desktop:** não há configuração em arquivo. Na primeira vez, escolha "Permitir sempre" nas
  ferramentas do Expeditto (as anotações ajudam o app a agrupar as de leitura).
