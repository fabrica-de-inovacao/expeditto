# Produto e experiência — nome, instalador, chat e CLI

> **Decisões de 2026-09-30 (prevalecem sobre o texto abaixo):**
> - Nome da ferramenta: **Expeditto** (dois "t", para diferenciar do nome próprio). Pacote, comando e servidor MCP: `expeditto`.
> - Mascote: **despertador laranja em pixel art** (caracteres de bloco `▀▄` com cor, como o mascote do Claude Code), **inspirado** na Senhorita Minutos (relógio mascote da AVT, série *Loki*), com desenho original. Sem nome próprio: é a "cara" do Expeditto. Protótipos em `docs/marca/` (v2 aprovada como direção).
> - Hospedagem: VPS com **Coolify 4.3.23**, projeto **Expeditto** com os recursos na rede do próprio Coolify; domínio **expeditto.fabitz.com.br** (DNS já resolve para a VPS). Primeiro recurso: site estático com `install.ps1`/`install.sh`; depois página de apresentação e tutoriais.
> - App OAuth do Gmail: **adiado**. E-mail pelo conector do host (Claude); backup próprio quando houver demanda.
> - TUI deve ocupar a janela inteira do terminal (Textual em tela cheia, layout responsivo).
>
> 2026-09-30. Proposta para debate. Nome **provisório**: Expedito (ver §1). Licença: **AGPL-3.0**.
> Premissas: distribuição **pública** e gerenciada por nós; CLI + MCP no mesmo pacote; e-mail pelo conector do Claude, com backup próprio para outros apps.

## 1. Nome e identidade (trocadilho com "segundo expediente")

Todos livres no PyPI em 2026-09-30:

| Nome | Trocadilho | Mascote | Assinatura |
|---|---|---|---|
| **Expedito** ⭐ | *expediente* → *expedito* ("despachado, ágil"); e São Expedito, "santo das causas urgentes", perfeito para o RIT de última hora | coruja que trabalha à noite | "Seu segundo expediente, resolvido." |
| **Serão** | "fazer serão" = trabalhar depois do horário | coruja / lamparina | "O serão fica comigo." |
| **Contraturno** | o turno extra da escola | relógio de ponto | "Seu contraturno automatizado." |
| **Hora Extra** (`horaextra`) | a hora extra que ninguém paga | relógio | "A hora extra é minha." |

**Recomendação: Expedito.** Soa como nome de pessoa (um colega que ajuda), o duplo sentido é imediato para servidores e cabe em qualquer automação futura (RIT, PIT, declarações, prestação de contas…). O mascote é **a coruja Expedito**: a coruja é o animal do trabalho noturno, o próprio "segundo expediente". Evitamos imagem religiosa: o santo fica só no trocadilho.

- Pacote PyPI: `expedito` · comando: `expedito` · servidor MCP: `expedito`.
- **Tom**: colega prestativo, em primeira pessoa, em português claro. Ex.: "Achei 18 publicações no seu Lattes sem comprovante. Vamos ver quais são deste semestre?"
- **Glossário fixo**: comprovante (nunca "evidência" na interface), pendência, relato, anexo, semestre (AAAA.P).
- **Paleta**: azul-noite (fundo) + âmbar de lamparina (destaque) + verde-folha (ok) + coral (atenção). Nenhum logotipo do IFMA/SUAP.
- **Aviso**: "Ferramenta independente, não oficial. Roda no seu computador, com a sua sessão. Nunca entrega o relatório por você."

## 2. Um produto, duas portas

```
                ┌──────────── pacote `expedito` (PyPI, AGPL) ────────────┐
 terminal ──▶   │  CLI/TUI (Textual)      servidor MCP (stdio)           │ ◀── Claude Desktop/Code,
                │         └──────── núcleo (coleta, anexos, relatos,     │     Codex, Gemini/Antigravity
                │                   formulário, pendências…) ────────────│
                └────────── mesmo acervo (~/expedito) e mesmo keyring ────┘
```
A CLI serve para instalar, configurar, diagnosticar, uso avançado e hosts sem chat. O MCP é a experiência principal no chat. Tudo o que é essencial (login, diagnóstico, pendências) existe nas duas portas.

## 3. Instalador ("ele cuida de tudo")

**Uma linha** (mesmo padrão do `uv`):
- Windows: `powershell -ExecutionPolicy ByPass -c "irm https://expedito.dev/install.ps1 | iex"`
- macOS/Linux: `curl -LsSf https://expedito.dev/install.sh | sh`

O script: (1) instala o `uv` se faltar; (2) `uv tool install expedito`; (3) abre **`expedito instalar`**, um assistente visual (TUI):

| Passo | O que faz | Visual |
|---|---|---|
| 1. Boas-vindas | mascote, aviso, termos (AGPL, não oficial) | coruja acena |
| 2. Navegador | detecta Chrome; se faltar, baixa o Chromium do Playwright | barra de download |
| 3. Onde guardar | pasta do acervo (padrão `~/expedito`) | seletor |
| 4. Assistentes de IA | detecta **Claude Desktop, Claude Code, Codex, Gemini CLI/Antigravity**; o docente marca onde instalar | checkboxes; ✓ detectado / – não encontrado |
| 5. Instalação do MCP | Claude Desktop: entrada em `claude_desktop_config.json` (com backup); Claude Code: `claude mcp add -s user`; Codex: `codex mcp add`; Gemini/Antigravity: `settings.json`/`mcp_config.json` | uma linha animada por app |
| 6. Login no SUAP | janela efêmera; confirma nome e campus | "Olá, Simone!" |
| 7. E-mail | Claude: lembra de ligar o conector Gmail; outros: oferece `expedito gmail entrar` (backup) | — |
| 8. Diagnóstico | roda o `doctor` e mostra o resumo | checklist verde |

Também: `expedito atualizar` (`uv tool upgrade`), `expedito desinstalar` (remove o MCP dos apps, restaura os backups e apaga os dados se o docente pedir) e `expedito doctor`.
**`.mcpb`**: continua como alternativa sem terminal, só para o Claude Desktop (arquivo em cada versão no GitHub).
**Executável próprio**: descartado por ora (alerta do SmartScreen sem certificado, falsos positivos de antivírus).

## 4. Experiência no chat (sem comandos `/`)

1. **Roteamento automático.** Instruções do servidor + descrições das ferramentas deixam claro: "use quando o docente falar de RIT, relatório individual de trabalho, relatório do semestre, comprovantes, SUAP". O docente escreve "me ajuda com meu relatório do semestre" e o Claude chama o Expedito.
2. **Porta de entrada única: `preparar_rit(semestre?)`.** Devolve o estado e **o próximo passo**, e o Claude segue um roteiro em vez de adivinhar entre 19 ferramentas.
3. **Progresso em etapas.** `aguardar_tarefa(id)` espera até ~50 s e devolve etapas + barra textual:
   ```
   Coleta 2025.2  ▓▓▓▓▓▓▓▓░░░░  62%   etapa 4/6 · Pasta funcional (portarias)
   ✓ Plano  ✓ Calendário  ✓ Estágios/TCCs/bancas  ◐ Pasta funcional  · Projetos  · Lattes
   ```
   As instruções pedem que o Claude mostre essa linha a cada atualização. É a forma que funciona em **todos** os apps (as notificações de progresso do protocolo não aparecem no Claude Code).
4. **Painel visual (MCP Apps) no Claude Desktop e na web.** As ferramentas `preparar_rit`/`aguardar_tarefa` declaram uma interface `ui://expedito/painel`: barra de progresso ao vivo, pendências como cartões com botões [Manter] [Ignorar] [Justificar], prévia dos tópicos e o botão "Salvar no SUAP" (com confirmação). Em apps sem MCP Apps (Claude Code, Codex, Gemini CLI), o mesmo conteúdo vem em texto.
5. **Pendências por grupo.** "18 itens do Lattes (5 anais, 4 resumos, 1 livro, 7 capítulos): quais são de 2025.2?", e não 18 perguntas.
6. **Cartão final padrão** com totais por tópico, pendências decididas e os links (prévia em PDF e formulário).
7. **`diagnostico`** (doctor) como ferramenta: o Claude consegue explicar "sua sessão expirou" ou "o Chrome não foi encontrado".

## 5. E-mail
- **Claude (Desktop/web)**: conector Gmail do Claude (D41). Ele vê anexos só por nome → registro pelo corpo + pendência (D43).
- **Codex, Gemini/Antigravity e outros**: **backup próprio** (D42/D51): o Expedito busca no Gmail e devolve as atas ao acervo (`buscar_atas_gmail`/`registrar_atas_gmail`). Pendente: criar o app OAuth no Google Cloud (§8).

## 6. CLI/TUI: rica, visual e completa (Textual)

Framework: **Textual** (widgets, botões clicáveis com mouse, animações, 16 milhões de cores, estilo tipo CSS). `expedito` sem argumentos abre a TUI; os subcomandos continuam existindo para scripts (`--sem-tui`, `--json`).

```
╭──────────────────────────────── Expedito · seu segundo expediente ───────────────────────────────╮
│    ,_,     Boa noite, Simone!                                    sessão SUAP ● ativa (72 min)     │
│   (O,O)    3 RITs esperando por você.                            IFMA · Campus Exemplo         │
│   (   )                                                                                           │
│  --"-"--   [ Preparar RIT 2025.2 ]  [ Pendências ]  [ Diagnóstico ]  [ Configurar ]               │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│  Semestre   Situação           Comprovantes   Pendências   Rascunho no SUAP                       │
│  2026.2     a preencher        —              —            —                                       │
│  2025.2     a preencher        66             ⚠ 23         —                  [ Continuar ▸ ]      │
│  2025.1     rascunho salvo     72             ✓            ✓ 30/09 10:52      [ Conferir ▸ ]       │
│  2024.2     publicado          —              —            —                                       │
╰───────────────────────────────────────────────────────────────── q sair · ? ajuda · ↑↓ navegar ──╯
```

Telas:
1. **Início**: mascote animado (pisca e acompanha a seleção), semestres, atalhos.
2. **Preparar RIT** (assistente em etapas): coleta com **etapas animadas** e barra por etapa; o mascote "trabalha" (animação de carimbo) durante os downloads.
3. **Pendências**: cartões agrupados, botões `[Manter] [Ignorar] [Justificar…]`, seleção múltipla para lotes, justificativa digitada no próprio cartão.
4. **Relatos**: lista de tópicos à esquerda, prévia formatada à direita, `[Gerar rascunho]` `[Editar no editor]` `[Aprovar]`.
5. **Anexos**: tamanho por tópico com medidor até 10 MB, índice de documentos, `[Abrir PDF]`.
6. **Salvar no SUAP**: resumo + confirmação com botão duplo ("Tem certeza?") → resultado com links clicáveis.
7. **Diagnóstico**: checklist ao vivo (Chrome, sessão, pasta, versão, apps com MCP, Gmail).

Acessibilidade: modo alto contraste, `--sem-cor`, tudo acessível pelo teclado, textos curtos.

## 7. Plano de implementação
1. Renomear para o nome escolhido (pacote, comando, servidor, pasta de dados com migração de `~/suap-rit`), licença AGPL, avisos.
2. MCP: `preparar_rit`, `aguardar_tarefa` com etapas, `diagnostico`, pendências agrupadas, cartão final; instruções de roteamento.
3. TUI Textual: Início → Preparar RIT → Pendências → Relatos → Anexos → Salvar → Diagnóstico.
4. Instalador: `expedito instalar`/`desinstalar`/`atualizar` + scripts de uma linha + registro nos 4 apps.
5. Painel MCP Apps no Claude Desktop.
6. Publicação: GitHub público (AGPL), GitHub Actions → PyPI, `.mcpb` na release, registro oficial de MCPs.
7. App OAuth do Gmail (backup) — §8.

## 8. App do Gmail (backup) — a criar
Precisamos de: conta Google dona do projeto (recomendado: conta do projeto, que aparece na tela de consentimento) e da lista de testadores. Passos no Console do Google Cloud: projeto → ativar Gmail API → tela de consentimento "Externo", modo Testing, escopos `gmail.readonly` + `openid email` → cadastrar testadores → cliente OAuth "App para computador" → baixar o JSON. Limites: 100 testadores e consentimento de 7 dias (produção exige verificação + CASA). A ferramenta sempre prioriza o conector do Claude.

Fontes: [MCP Apps oficial](https://modelcontextprotocol.info/blog/mcp-apps-ui-capabilities/), [WorkOS sobre MCP Apps](https://workos.com/blog/2026-01-27-mcp-apps); [progresso no protocolo](https://modelcontextprotocol.io/specification/2025-06-18/basic/utilities/progress.md) e [limitação no Claude Code](https://glama.ai/mcp/servers/@hanlulong/stata-mcp/blob/e1a980b3f64be90ed31a33200251b5a28f5a82d4/docs/incidents/CLAUDE_CODE_NOTIFICATION_DIAGNOSIS.md); [Textual](https://realpython.com/python-textual/); [Gmail em Codex/Gemini via terceiros](https://www.zonca.dev/posts/2026-02-06-smithery-gmail-mcp-terminal-ai.html); [instalador do uv](https://docs.astral.sh/uv//getting-started/installation/); [MCPB](https://www.anthropic.com/engineering/desktop-extensions).
