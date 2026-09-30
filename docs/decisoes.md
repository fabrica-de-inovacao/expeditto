# Decisões de produto e regras de negócio

> Respostas da cliente (2026-09-29) às perguntas de `discovery.md` §7, convertidas em regras implementáveis.
> Referências de rotas/campos: [`mapa-suap-ifma.md`](mapa-suap-ifma.md).

## 1. Escopo e fluxo

| # | Decisão | Regra |
|---|---|---|
| D1 | O usuário escolhe o semestre e o artefato (RIT ou PIT) a trabalhar. | Nenhuma fila automática. A ferramenta **lista** os semestres e seus estados (§1 do mapa) e o usuário escolhe. PIT entra no escopo (antes era só RIT). |
| D2 | A ferramenta pode **Salvar** o formulário como rascunho. | Preencher e clicar "Salvar". **Nunca** acionar `/entregar_relatorio/`. Ao final, devolver o link `…/preencher_relatorio_individual_trabalho/{id}/` (ou a visualização do plano) para a docente conferir e entregar. |
| D3 | A dor é o garimpo e a organização (1 dia ou mais por RIT). | A métrica de sucesso é o tempo até o rascunho salvo. O coração do produto é coleta + organização, não a redação. |
| D4 | RIT devolvido = anexos insuficientes ou texto pouco esclarecedor. | Todo item citado no texto tem comprovante no anexo do tópico. Atividade do PIT sem comprovante vira **pendência explícita** para o usuário, não é omitida em silêncio. |

## 2. Texto dos tópicos

| # | Decisão | Regra |
|---|---|---|
| D5 | Parágrafo narrativo **e** listagem. | Estrutura por tópico: 1 parágrafo-síntese e depois uma lista de itens (título, papel, período, documento de referência, por exemplo "Portaria nº X/AAAA"). Sem modelo prévio: criar um template e validar com a cliente. |
| D6 | "Alterações de Atividades" = atividades alteradas ou realizadas parcialmente em relação ao PIT. | Comparar as atividades marcadas no PIT com as evidências do acervo. Se houver divergência (planejado sem evidência, ou evidência não planejada), **perguntar ao usuário** se deve entrar em Alterações e pedir a justificativa. Nunca inventar justificativa. |
| D7 | O campo é rich text (CKEditor), sem limite, e aceita formatação. | Gerar HTML simples (`<p>`, `<ul>`, `<strong>`). Texto detalhado, porém enxuto: priorizar clareza sobre volume. |

## 3. Anexos

| # | Decisão | Regra |
|---|---|---|
| D8 | Anexo acima de 10 MB → comprimir. | Pipeline: juntar os PDFs → comprimir (downsample de imagens) → se ainda passar de 10 MB, avisar o usuário com a lista de itens por tamanho. |
| D9 | Documento assinado tem preferência. | Se houver o mesmo documento com e sem assinatura (por exemplo, ata do e-mail vs. documento do SUAP), usar o assinado. |
| D10 | Dados de alunos podem ir como estão no SUAP. | Sem anonimização. |
| D11 | A docente não guarda comprovantes, e isso é uma necessidade. | O workspace local da ferramenta **é o acervo dela**: persistente, organizado por `semestre/tópico`, reaproveitado entre execuções. Também deve aceitar comprovantes adicionados manualmente numa pasta de entrada. |

## 4. Classificação (fonte → tópico)

| # | Decisão | Regra |
|---|---|---|
| D12 | Orientações (de pesquisa, artigo, capítulo de livro, TCC, estágio e afins) → **Atendimento/Orientação de Alunos**. Não entram em Extensão. Orientação de bolsista de pesquisa vai para **os dois** tópicos (P1). | Orientação sempre vai para `orientacao_alunos`. Se for orientação ligada a projeto de pesquisa, o item também entra em `pesquisa`. |
| D13 | Gestão e Representação = portarias de coordenação (curso técnico, laboratórios como a Fábrica de Inovação, outros espaços do campus). | `historico_funcoes` + portarias de designação de FCC/coordenação → `gestao`. |
| D14 | Cursos de formação e encontros pedagógicos → Reuniões Pedagógicas **e** Preparação. | O mesmo item pode aparecer em mais de um tópico (duplicação entre tópicos permitida quando a regra disser). |
| D15 | Diárias/viagens (PCDP) **não** comprovam participação; é preciso ata. | PCDP serve só como **pista**: gera uma busca no Gmail pela ata daquela reunião/data. Sem ata → pendência. |
| D16 | Coordenação de curso → Gestão, com a portaria de designação anexada **em todo semestre** em que estiver vigente. | Evidência com vigência aberta ou longa é replicada em cada semestre que intersecta. |
| D25 | NDE/Colegiado → **Reuniões Pedagógicas** (confirmado, P2). | Portarias de NDE/Colegiado → `reunioes`, replicadas por vigência (D19). |

## 5. Semestres

| # | Decisão | Regra |
|---|---|---|
| D17 | O semestre segue o **calendário do campus**, obtido no setup. | No setup: extrair o campus do perfil; datas do semestre = menor `data_inicio` / maior `data_fim` dos **diários semestrais** do docente no período (`/api/edu/meus-diarios/{ano}/{p}/`; ex.: 2025.1 → 03/02/2025–26/06/2025). Descartar diários anuais (técnico integrado: jan–dez). Confirmar com o usuário e permitir editar. |
| D18 | Banca sem vigência → vale a **data da defesa**. | Usar "Data da Apresentação" da aba `banca`/`projetofinal`. |
| D19 | Vigência longa (ex.: NDE 2025–2027) → entra em **todos** os semestres do intervalo. | Interseção `[início, fim]` × semestre. |

## 6. Fontes externas

| # | Decisão | Regra |
|---|---|---|
| D20 | Gmail institucional (@ifma.edu.br), sem marcadores → busca "burra". | Consultas por palavras-chave (`ata`, `portaria`, `banca`, `reunião`, `convocação`, `NDE`, `colegiado`…) + período do semestre + anexos PDF. Resultado sempre passa por revisão do usuário. |
| D21 | Lattes atualizado e usado como fonte. | O link está no perfil do SUAP (`/cnpq/curriculo/{id}/`); extrair no setup. Usar para publicações, capítulos e bancas externas. |

## 7. Interface e usuários

| # | Decisão | Regra |
|---|---|---|
| D22 | Cliente principal: **Claude Desktop (MCP)**. CLI para usuários técnicos. | O MCP é a interface prioritária. A CLI fica como casca secundária e ferramenta de desenvolvimento. |
| D23 | Conferência pelo link do SUAP antes de entregar. | Saída final obrigatória: link do rascunho salvo + resumo (itens por tópico, pendências, tamanho dos anexos). |
| D24 | A coordenação quer para vários docentes. | A arquitetura continua local e por usuário. Multi-docente fica como visão futura (não bloquear no design: nada de caminhos fixos para um único usuário). |

## 8. Login (resposta técnica à pergunta 22)

Observado na sessão:
- Cookies: `__Host-sessionid` (HttpOnly) e `__Host-csrftoken`. A sessão expira **cerca de 90 min após a última atividade** (renovação a cada uso). Não existe token de longa duração.
- A janela do navegador só é necessária **no momento do login** (CAPTCHA, código de verificação e Gov.br). Depois, basta o cookie de sessão: toda a coleta e o POST do formulário funcionam por HTTP sem navegador.
- `POST /api/token/pair` (usuário/senha, sem CAPTCHA) gera JWT, mas **só serve para a API REST**. Não cobre as páginas HTML, a pasta funcional nem o formulário do RIT.

Opções, da mais recomendada para a menos:
1. **Janela de login compacta e efêmera** (recomendado): a ferramenta abre uma janela pequena só com o login do SUAP, detecta o sucesso, captura os cookies e fecha sozinha. Os cookies ficam em memória ou no keyring do sistema. Um login por sessão de trabalho.
2. **Reaproveitar o Chrome em que ela já está logada** (Playwright via extensão/CDP): zero login extra, mas exige mais permissão no navegador pessoal dela e é mais frágil.
3. JWT por usuário e senha: só complementar (API). ❌ Não substitui a sessão.
4. POST direto no formulário de login com senha salva: ❌ quebra com CAPTCHA e exige guardar a senha.

A investigar: o cookie `__Host-suap-control` (validade de 90 dias) pode ser uma marca de "dispositivo confiável" que reduz CAPTCHA ou 2FA nos próximos logins.

## Pendências resolvidas (2026-09-29)

- **P1.** Orientação de bolsista de pesquisa → vai para os **dois** tópicos (Orientação e Pesquisa). Incorporado em D12.
- **P2.** NDE/Colegiado → Reuniões Pedagógicas. Confirmado em D25.
- **P3.** Fluxo do PIT → **adiado** para depois do primeiro protótipo (que é só RIT).

## 9. Decisões técnicas (2026-09-29)

| # | Decisão | Regra |
|---|---|---|
| D26 | **Minimização de dados.** | Allowlist de campos do perfil (mapa §7.1). Dados sensíveis (mapa §7.3) nunca são lidos para disco nem enviados ao LLM. |
| D27 | Lattes via cópia importada no SUAP. | Fonte secundária: detector de lacunas e enriquecimento de texto. Nunca vale como comprovante sozinho. |
| D28 | Allowlist de rotas. | O cliente HTTP só aceita rotas do próprio usuário; bloqueia `/admin/` e rotas de terceiros, mesmo que a conta tenha permissão. |
| D29 | Sem FastAPI no protótipo. | Interfaces: MCP local (FastMCP, stdio) + CLI (Typer) sobre o mesmo núcleo. FastAPI só quando houver serviço multi-docente para a coordenação (D24), que exige outro desenho de segurança (guarda de sessões de terceiros). |
| D30 | Stack. | Python 3.11+, `uv`, Playwright (só login), `httpx`, `selectolax`/`lxml` (HTML), `pydantic` (modelos), `pypdf`/`pikepdf` (PDF), `keyring` (sessão). |

## 10. Fechamento do protótipo 1 (2026-09-29)

| # | Decisão | Regra |
|---|---|---|
| D31 | Estágio é comprovado pela **declaração anual** da modalidade (mapa §9.1). | Para o semestre AAAA.P usa-se a declaração do ano AAAA. Um único PDF comprova todos os estágios do ano, sem duplicar no anexo. |
| D32 | Papel em projetos vem da **aba equipe** (mapa §9.2). | Coordenador(a) / Subcoordenador(a) / função informada / "Membro da equipe". A carga horária semanal é guardada para os textos. |
| D33 | Orientação em projeto = evidência própria, com a "Declaração de Orientação". | Projeto de pesquisa → Orientação **e** Pesquisa (P1); ensino/extensão → só Orientação (D12). |
| D34 | Projeto em andamento usa a **Declaração de Participação**. | Fallback quando não há certificado. Participação "Inativado" vira pendência para o docente decidir. |
| D35 | Portaria de banca pode usar a **data da portaria** quando o texto não traz a data da defesa. | Emenda a D18 (aceito pela cliente). |
| D36 | Validade dos comprovantes emitidos. | Ler "Válido até" no PDF, registrar no manifest e emitir de novo se vencido (mapa §9.3). |
| D37 | Nova composição do mesmo órgão encerra a portaria anterior. | NDE/Colegiado/comissão do mesmo curso: a portaria antiga termina na véspera da nova. FCC/CC: vigência limitada pelo histórico de funções. |
| D38 | Login validado pela cliente. | `suap-rit login`: janela abre, login humano, fecha sozinha, sessão no keyring (teste em 2026-09-29). |

### Resultado da validação com dados reais (2025.1)

| Tópico | Itens | PDFs | Tamanho |
|---|---|---|---|
| Preparação/Apoio ao Ensino | 6 | 1 | 52 KB |
| Programas e Projetos de Ensino | 3 | 3 | 140 KB |
| Atendimento/Orientação de Alunos | 36 | 17 | 744 KB |
| Reuniões Pedagógicas | 4 | 4 | 208 KB |
| Pesquisa | 21 | 20 | 896 KB |
| Extensão | 7 | 7 | 2,8 MB |
| Gestão e Representação | 3 | 2 | 132 KB |

Pendências: 19 → **1** (participação "Inativado" num projeto de pesquisa, que é uma decisão legítima do docente). Nenhuma divergência PIT × evidências. Todos os tópicos bem abaixo de 10 MB.

Observação: os diários (Apoio ao Ensino) não têm comprovante em PDF. Avaliar no protótipo 2 se vale gerar o relatório do diário (há opção de impressão no diário) ou se basta citá-los no texto.

## 11. Diários (2026-09-29)

| # | Decisão | Regra |
|---|---|---|
| D39 | Diários são comprovados pela **Declaração de Docência** anual (mapa §9.4), não pela impressão do diário. | O semestre AAAA.P usa a declaração do ano AAAA, anexada a "Preparação, Manutenção e Apoio ao Ensino". O texto do tópico cita os diários (disciplina, CH, turma). |
| D40 | Aviso de registro incompleto. | Semestre já encerrado com diário abaixo de 100% ministrado vira pendência `diario_incompleto`: completar o registro no SUAP ou justificar em "Alterações de Atividades". |

Validação (2025.1): Preparação passou a ter 6/6 itens comprovados. Dois diários apareceram com registro incompleto: 38% e 0%. O de 0% está como "Diário Dividido — 100% em 2025/2" no PIT, então pode ser esperado. A ferramenta avisa, e o docente decide.

## 12. E-mail e login — decisões de 2026-09-29 (noite)

| # | Decisão | Regra |
|---|---|---|
| D41 | **E-mail pelo conector do ecossistema** do host (Claude: conector Gmail; ChatGPT: app Gmail; Gemini: integração Workspace). Testado pelo usuário: o conector Gmail do Claude funciona com conta @ifma.edu.br. | A ferramenta **não** acessa o e-mail no fluxo principal. O LLM do host busca as atas com o conector dele e entrega o resultado à nossa ferramenta MCP (`registrar_ata`), num contrato neutro de host. |
| D42 | **Backup na CLI: app OAuth próprio** (Google, "Desktop app", escopo `gmail.readonly`, fluxo loopback: abre o navegador, a pessoa loga no Google e a CLI recebe o token). | Protótipo em modo "Testing": até 100 usuários cadastrados como testers, e o consentimento expira em **7 dias**. Produção exige verificação + CASA anual (escopo restrito) **ou** app "Interno" criado no Workspace do IFMA (isento). Um projeto para todos; o usuário não configura Google Cloud. Token no keyring. |
| D43 | Anexos das atas: o conector do Claude **vê nome/metadados dos anexos mas não o conteúdo** (segundo fontes públicas; confirmar no uso). | `registrar_ata` aceita: metadados (assunto, data, remetente, id da mensagem) + texto do corpo + anexo em base64 **opcional**. Sem o PDF, a ferramenta (a) baixa pelo backup D42 se autorizado, ou (b) gera um PDF "registro do e-mail" com o corpo e cria pendência pedindo o anexo original (preferir documento assinado, D9). |
| D44 | **Portabilidade do servidor MCP**: mesmo núcleo, dois transportes. | `stdio` (Claude Desktop, Claude Code, Gemini CLI, Cursor) e `streamable-http` escutando **apenas em 127.0.0.1**. ChatGPT e Gemini Spark só falam com MCP **remoto**, o que exige túnel (ex.: Secure MCP Tunnel da OpenAI) e expõe uma ferramenta que guarda a sessão SUAP. Fica **fora do protótipo 2**; se adotado, só com autenticação no túnel e sem tools de escrita. |
| D45 | **Login do SUAP continua via web** (janela efêmera, D38). OAuth do SUAP ("Minhas Aplicações") não serve: o token só vale para a API REST, não para as páginas web e o formulário do RIT. | Melhoria: perfil persistente do navegador (menos CAPTCHA/Gov.br). Futuro multi-docente: extensão de navegador. |

Fontes: [conector Gmail do Claude](https://claude.com/connectors/gmail), [Workspace connectors](https://support.claude.com/en/articles/10166901-use-google-workspace-connectors), [limites de anexos](https://www.fyxer.com/blog/claude-gmail-integration); [ChatGPT developer mode/MCP](https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt), [sem stdio no ChatGPT](https://peliqan.io/blog/chatgpt-mcp/); [Gemini Spark](https://techcrunch.com/2026/05/19/google-introduces-gemini-spark-a-24-7-agentic-assistant-with-gmail-integration/); [modo Testing do OAuth Google](https://www.unipile.com/google-oauth-refresh-token/); [device flow sem Gmail](https://developers.google.com/identity/protocols/oauth2/limited-input-device?authuser=6); [escopos restritos/CASA](https://developer.nylas.com/docs/cookbook/use-cases/build/fix-google-access-denied/).

## 13. Execução local e hosts suportados (2026-09-29)

| # | Decisão | Regra |
|---|---|---|
| D46 | **Uso local por ora.** A arquitetura remota (VPS, multiusuário) foi só investigação e está arquivada em `arquitetura-remota.md`. | Servidor MCP roda na máquina do docente (stdio). Sessão SUAP, acervo e tokens ficam só nela (D26, D45). |
| D47 | **Hosts desktop suportados** (todos via MCP stdio, mesmo comando `suap-rit mcp`): **Claude Desktop**, **Claude Code**, **OpenAI Codex** (CLI, IDE e app desktop, `~/.codex/config.toml`), **Gemini CLI / Antigravity CLI** (`~/.gemini/settings.json` ou `mcp_config.json`). | O chat web do ChatGPT e o Gemini Spark só aceitam MCP remoto → fora do escopo (D44). Guia de configuração: `docs/integracao-hosts.md`. |
| D48 | E-mail no host que tiver conector; se o host não tiver (ex.: CLIs), usa o backup OAuth da CLI (D42) ou a pasta de entrada (D11). | `registrar_ata` é igual para todos os hosts. |
