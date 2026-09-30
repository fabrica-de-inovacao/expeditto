# Protótipo 2 — do acervo ao rascunho salvo no SUAP

> Branch `feat/prototipo-2`. Parte do protótipo 1 (`feat/prototipo-1`, commit `f29796f`): acervo organizado por semestre/tópico com comprovantes em PDF.
> Objetivo: a docente pede "prepara meu RIT de 2025.1" no Claude Desktop e recebe um **rascunho salvo no SUAP** + link para conferir e entregar (D2, D23).

## 1. Consolidação do protótipo 1 (ponto de partida)

| Já temos | Onde |
|---|---|
| Login humano efêmero + sessão no keyring (~90 min) | `auth.py` |
| Allowlist de rotas / minimização de dados | `client.py`, `suap/perfil.py` |
| Estado PIT/RIT por semestre, calendário pelos diários | `suap/planos.py`, `suap/diarios.py` |
| Coleta: diários, estágios, TCC, bancas, projetos (papel/orientação), portarias, funções, afastamentos, capacitações | `suap/*.py` |
| Comprovantes: declarações anuais (docência, estágio), banca, orientação, participação, certificados, portarias (PDF assíncrono), validade | `coleta.py` |
| Classificação em 7 tópicos + pendências (sem comprovante, diário incompleto, divergência PIT, afastamento) | `classificar.py`, `coleta.py` |
| Regras D1–D40 | `docs/decisoes.md` |

Resultado real 2025.1: 72 evidências, 54 PDFs distintos, 3 pendências de decisão da docente.

## 2. Escopo do protótipo 2

| # | Entrega | Descrição | Decisões |
|---|---|---|---|
| E1 | **Servidor MCP** (FastMCP) | Ferramentas de alto nível sobre o núcleo; transportes `stdio` e `streamable-http` em 127.0.0.1 (D44); configuração para Claude Desktop | D22, D29, D44 |
| E2 | **Montagem dos anexos** | 1 PDF por tópico: capa + índice + comprovantes em ordem; compressão se > 10 MB | D8, D9 |
| E3 | **Textos dos tópicos** | Parágrafo-síntese + lista de itens (HTML simples p/ CKEditor), ancorados em evidências; no MCP o LLM do host redige, na CLI um rascunho por template | D4, D5, D7 |
| E4 | **Alterações de Atividades** | Diff PIT × acervo → perguntas ao docente → texto de `alteracoes` | D6, D40 |
| E5 | **Preencher e Salvar** | POST do formulário `pit_rit_v2` (textos + 7 anexos), **nunca** entregar; devolve link | D2, D23 |
| E6 | **Atas por e-mail** | Fluxo principal: o LLM do host busca com o conector de e-mail do ecossistema e chama `registrar_ata` (D41, D43). Backup na CLI: app OAuth próprio, loopback, `gmail.readonly` (D42). PCDP como pista | D15, D18, D20, D41–D43 |
| E7 | **Lattes como detector de lacunas** | Itens do Lattes no ano sem evidência no SUAP → pendência | D27 |
| E8 | **Pasta de entrada manual** | Comprovantes que a docente adiciona (`acervo/AAAA.P/_entrada/`) entram no manifest | D11 |

Fora do escopo: fluxo do PIT (P3), multi-docente (D24), entrega automática (proibida).

## 3. Arquitetura (acréscimos)

```
núcleo (protótipo 1)
 ├─ anexos.py      E2  merge + capa/índice + compressão + checagem 10 MB
 ├─ textos.py      E3  contexto por tópico (itens, papéis, CH, datas) + template HTML
 ├─ alteracoes.py  E4  diff PIT × acervo, perguntas, texto
 ├─ formulario.py  E5  GET do form → estado atual; POST multipart "Salvar"; verificação
 ├─ gmail/         E6  cliente OAuth (gmail.readonly) + busca + extração de atas
 └─ lattes.py      E7  parser do Lattes importado no SUAP
interfaces
 ├─ cli.py         + montar, textos, preencher --dry-run
 └─ mcp_server.py  E1
```

### Ferramentas MCP (rascunho)

| Tool | Faz | Confirmação humana |
|---|---|---|
| `status_sessao` / `login` | verifica sessão; abre janela de login | — |
| `listar_semestres` | estados PIT/RIT + links | — |
| `coletar_semestre(semestre)` | protótipo 1 + Gmail + entrada manual | — |
| `registrar_ata(semestre, assunto, data, remetente, id_mensagem, texto, anexo_base64?)` | recebe ata encontrada pelo conector de e-mail do host (D41, D43) | — |
| `listar_pendencias(semestre)` / `resolver_pendencia(id, decisao, justificativa?)` | revisão conversacional | sim (decisão é do docente) |
| `contexto_topico(semestre, topico)` | evidências do tópico para o LLM redigir | — |
| `salvar_texto(semestre, topico, html)` | guarda texto (valida HTML e citações) | — |
| `montar_anexos(semestre)` | gera os 7 PDFs, informa tamanhos | — |
| `previa_preenchimento(semestre)` | mostra o que será enviado ao formulário (dry-run) | — |
| `salvar_no_suap(semestre)` | POST "Salvar" + verificação + link | **sim, explícita** |

Resources: `rit://{semestre}/manifest`, `rit://{semestre}/{topico}/texto`, `rit://perfil`.

## 4. Investigações abertas (antes de codar cada entrega)

| # | Pergunta | Bloqueia |
|---|---|---|
| I1 | Estrutura completa do form `preencher_relatorio_individual_trabalho`: campos ocultos, valores atuais, anexos já enviados (substituir/limpar?), CSRF, `enctype`, resposta do Salvar | E5 |
| I2 | O que muda no estado após "Salvar" (link de visualização, "entregar" aparece?) — testar **somente com autorização** num semestre combinado | E5 |
| I3 | CKEditor: quais tags/estilos o campo aceita e como o SUAP renderiza no PDF do RIT | E3 |
| I4 | Gmail: OAuth próprio (Google Cloud project, escopo `gmail.readonly`) × Gmail MCP oficial no Claude Desktop × política do Workspace do IFMA para apps de terceiros | E6 |
| I5 | Ferramentas de PDF no Windows: `pypdf` (merge) basta? compressão via `pikepdf` ou Ghostscript? | E2 |
| I6 | Lattes importado: estrutura HTML das seções e granularidade das datas | E7 |
| I7 | FastMCP + Playwright no Claude Desktop (stdio, Windows): login abre janela a partir do processo MCP? | E1 |

## 5. Ordem proposta

1. I1/I3 (leitura) → E2 anexos → E3 textos → E4 alterações (tudo local, sem escrita no SUAP).
2. E1 servidor MCP com o fluxo até `previa_preenchimento`.
3. I2 com autorização → E5 `salvar_no_suap`.
4. I4 → E6 Gmail; I6 → E7 Lattes; E8 entrada manual.

## 6. Critérios de pronto

- No Claude Desktop, "prepara meu RIT de 2025.1" termina com rascunho **salvo** e link, sem entrega.
- Cada item citado nos textos tem comprovante no anexo do tópico; anexos ≤ 10 MB.
- Pendências apresentadas e resolvidas em conversa; "Alterações de Atividades" preenchido quando houver divergência.
- Nenhuma rota fora da allowlist; `entregar_relatorio` continua bloqueado; testes automatizados cobrindo form/anexos/textos.

## 7. Resultados das investigações (2026-09-29)

| # | Resultado | Consequência |
|---|---|---|
| I1 ✅ | Form Django `POST multipart/form-data` na própria URL; campos: `csrfmiddlewaretoken`, 7× `obs_<topico>` (textarea CKEditor), 7× `arquivo_<topico>` (file, sem `accept`), `alteracoes`, submit `relatorioindividualtrabalhoprofessor_form` ("Salvar"). Nenhum outro campo oculto. Em 2025.1 está vazio. | E5 = GET (CSRF + estado atual) → POST com os 15 campos → GET de verificação. Sem Playwright para preencher. |
| I2 ✅ | **Testado em 2025.1 (autorizado)** — ver mapa §10.1. Antes: não testado; exigia **Salvar** de verdade. Falta saber como o form mostra anexo já enviado (substituir/limpar?) e se o POST parcial apaga campos não enviados. | Pedir autorização para um teste controlado num semestre combinado. |
| I3 ✅ | CKEditor 4 com `allowedContent: true`: aceita HTML livre (`p`, `ul/ol`, `strong`, `table`, alinhamento). | E3 gera HTML simples (parágrafo + lista); tabelas possíveis se ajudarem. |
| I3+ ✅ | O RIT publicado (PDF) já inclui, por tópico: CH do PIT, lista de atividades do catálogo e, em Gestão, o histórico de funções. Os textos entram como **"Relatos"**. Os **anexos não aparecem no PDF publicado**. Em RITs publicados que consultamos, os relatos costumam ser "As comprovações estão no SUAP.". | O texto não precisa repetir o catálogo do PIT: deve **relatar o que foi feito** (itens concretos, papéis, períodos, documentos). É o maior ganho de qualidade em relação ao que é entregue hoje. |
| I4 ⚠️ | `gmail.readonly` é escopo **restrito** do Google; admins do Workspace podem bloquear apps não verificados/não confiáveis (Admin console › Segurança › Controles de API). Não há confirmação de Gmail MCP oficial do Google; existem servidores comunitários com download de anexos. | Experimento necessário com a conta @ifma.edu.br: cliente OAuth "desktop" num projeto Google Cloud próprio. Se o IFMA bloquear: fallback = pasta de entrada manual (E8) + busca guiada (a ferramenta monta a query e a docente baixa as atas). |
| I5 ✅ | `pypdf` (merge) já é dependência; `pikepdf 10.16` instala no Windows/Py3.12; sem Ghostscript. | Compressão via pikepdf (recompressão de streams/imagens); maior tópico atual (2,8 MB) nem precisa. |
| I6 ✅ | Lattes importado: seções em `h3/h4` + `div`; itens em texto corrido com ano (ex.: "Início: 2025"); granularidade anual. Orientações (andamento/concluídas) e bancas (TCC e comissões) parseáveis. | E7 compara itens do Lattes do ano com as evidências do SUAP e gera pendência "sem comprovante" para o que faltar. |
| I7 ⏳ | `mcp 2.2.0` (FastMCP) instala. Falta testar o login com janela aberta a partir do processo stdio do Claude Desktop. | Teste no início de E1. |

### Ações que dependem de pessoas
1. **I2**: autorizar um "Salvar" de teste. Sugestão: 2025.1, com textos e anexos reais gerados pela ferramenta e conferidos antes. É reversível, porque o RIT continua editável até a entrega.
2. **I4**: criar/usar um projeto Google Cloud e testar o consentimento OAuth com a conta institucional da docente. Se bloquear, perguntar à TI do IFMA sobre liberação (ou seguir com o fallback manual).

### Atualização I4 (e-mail) e I7 — 2026-09-29, noite
- I4 resolvido por decisão: conector do ecossistema (D41) + backup OAuth próprio na CLI (D42). Limitação de anexos tratada em D43.
- Portabilidade entre hosts: D44 (stdio + HTTP local; remoto/túnel fora do escopo).
- Login SUAP: D45.

## 8. Andamento (2026-09-29, noite)

| Entrega | Estado | Onde |
|---|---|---|
| E2 anexos | ✅ capa + índice + marcadores + compressão; 7 anexos de 2025.1 (0,09–2,76 MB) | `anexos.py`, `suap-rit montar` |
| E3 textos | ✅ rascunho determinístico + `contexto_topico` para o LLM do host | `textos.py`, `suap-rit textos` |
| E5 salvar | ✅ prévia + Salvar com conferência; testado no SUAP real (2025.1) | `formulario.py`, `suap-rit preencher [--salvar]` |
| E4 alterações | ⏳ próximo | — |
| E1 servidor MCP | ⏳ próximo | — |
| E6 atas (registrar_ata + backup OAuth) | ⏳ | — |
| E7 Lattes / E8 entrada manual | ⏳ | — |

Observação: o RIT 2025.1 de teste ficou **salvo como rascunho** com os textos gerados por template. A docente deve revisar (ou pedir nova versão pelo MCP) antes de entregar.
