# SUAP RIT Assistant — Descoberta, Modelagem e Validação

> Status: rascunho de descoberta (2026-09-29). Base: entrevista rápida com a usuária + investigação técnica do SUAP IFMA.
> Objetivo deste documento: entender a dor, registrar o que já foi verificado, propor uma arquitetura e listar o que **ainda precisa ser validado com a cliente e com a TI do IFMA** antes de construir.

> **Estado em 2026-09-29 (fim do dia):** as perguntas das seções 6 e 7 foram respondidas pela cliente → [`decisoes.md`](decisoes.md) (D1–D38). O **protótipo 1** (login, semestres, coleta e organização do acervo, somente leitura) foi validado com dados reais → [`decisoes.md` §10](decisoes.md). As rotas do SUAP estão em [`mapa-suap-ifma.md`](mapa-suap-ifma.md). Este documento fica como registro da descoberta; onde houver divergência, valem os dois documentos citados.
>
> **Protótipo 2 (próximo):** servidor MCP (FastMCP) para o Claude Desktop · busca de atas no Gmail (duas caixas: institucional e acadêmica) · junção e compressão dos PDFs por tópico · textos por tópico (parágrafo + lista, D5) · "Alterações de Atividades" guiada (D6) · preencher e **Salvar** o formulário, devolvendo o link (D2, D23) · fluxo do PIT adiado (P3).

---

## 1. A dor, reescrita

Todo semestre o docente do IFMA precisa entregar o **RIT (Relatório Individual de Trabalho)**, que comprova a execução do **PIT (Plano Individual de Trabalho)** aprovado. O trabalho penoso não é escrever — é **garimpar e organizar evidências** espalhadas em vários lugares:

| Fonte | O que tem | Hoje |
|---|---|---|
| SUAP › Ensino › Planos Individuais de Trabalho › Meus planos | diários, orientações de estágio, orientações de TCC/projeto final, participação em projetos, participação em bancas | clicar aba por aba |
| SUAP › Perfil › Pasta funcional | portarias (bancas, comissões, reuniões, programas de ensino), histórico | abrir PDF por PDF |
| SUAP › acervo geral de projetos/orientações | sobrepõe o que já veio em "Meus planos" | risco de duplicar |
| Gmail | atas de reunião, convocações, portarias enviadas por e-mail | busca manual |
| Arquivos locais do docente | certificados, declarações, artigos | pastas desorganizadas |

Depois de garimpar, o docente precisa: separar por **semestre** (atividades que atravessam semestres aparecem nos dois), agrupar por **tópico do relatório**, **unificar PDFs** (1 anexo por tópico), escrever um **texto por tópico**, preencher no SUAP e enviar.

**Proposta de valor:** o docente sai de "horas de garimpo e colagem" para "10–20 min revisando um rascunho pronto e clicando Enviar".

**Decisão de produto já tomada pela cliente (importante e correta):** a ferramenta **não envia**. Ela preenche, gera link de visualização e pede o envio manual. Isso mantém a responsabilidade legal do docente sobre o que declara.

---

## 2. O que foi verificado tecnicamente (fatos, não suposições)

> **Atualização (sessão autenticada, 2026-09-29):** o mapeamento completo das rotas está em [`mapa-suap-ifma.md`](mapa-suap-ifma.md). Conclusões que mudam o desenho:
> 1. **Um único login humano basta.** Depois dele, toda a coleta é feita por `GET` HTTP na sessão (HTML das abas + API REST aceita o cookie de sessão). Playwright só é necessário para o login; a coleta pode usar `httpx` com os cookies exportados. Isso deixa a coleta muito mais robusta que um scraping de cliques.
> 2. **O formulário é um form Django com `Salvar` separado de `Entregar`.** O preenchimento pode ser um POST multipart (ou Playwright preenchendo e clicando Salvar); a entrega fica com a docente — atende o requisito.
> 3. **Comprovantes em PDF já existem no SUAP** (declarações de banca por papel, coorientação, certificados de pesquisa/extensão/ensino, portarias em PDF/A) → o bundler baixa em vez de pedir arquivos à docente.
> 4. **Dedup "Meus planos" × perfil é exata** (mesmos ids de projeto). Projetos de **ensino só aparecem no perfil**.
> 5. **Portarias trazem vigência e papel no texto** → alocação por semestre via parsing, não pela data de inserção.
> 6. **A dor real inclui backlog:** a conta tem 5 semestres com RIT pendente e entregou ~10 no mesmo dia. O produto deve processar **vários semestres em lote**.

### 2.1 API oficial do SUAP IFMA
- Swagger em `https://suap.ifma.edu.br/api/docs/`, schema em **`https://suap.ifma.edu.br/openapi.json`** (IFRN: `/api/openapi.json`). Django Ninja. 176 operações no IFMA, 93 no IFRN.
- Autenticação: `POST /api/token/pair` com `username`/`password` → JWT (testado: responde 401 com credencial inválida, **sem captcha**). Também existem esquemas OAuth2, DRF Token e Session cookie.
- **Não existe nenhum endpoint de PIT/RIT, bancas, orientações, portarias ou pasta funcional.** A API cobre o problema só parcialmente.

Endpoints úteis para o RIT (IFMA):

| Endpoint | Utilidade | Observação |
|---|---|---|
| `GET /api/edu/meus-diarios/{ano}/{periodo}/` | diários do professor (componente, datas, participantes, aulas) | fonte principal de "Ensino/aulas" |
| `GET /api/edu/meus-periodos-letivos/` | períodos letivos disponíveis | define semestres válidos |
| `GET /api/rh/meu-historico-funcional/` | eventos funcionais | **investigar** se inclui portarias |
| `GET /api/rh/minhas-ocorrencias-afastamentos/` | afastamentos/licenças | afetam o RIT (justificativa de carga) |
| `GET /api/protocolo/meus-processos/` | processos do docente | possível evidência de gestão |
| `GET /api/v2/minhas-informacoes/participacoes-projetos/` | projetos de pesquisa/extensão (só `edital` e `projeto`) | **marcado "será removido"** |
| `GET /api/projetos/` | projetos com datas `dt_inicio`/`dt_final`, situação, coordenador | **marcado "será removido"** — útil para regra de semestre |
| `GET /api/rh/eu/`, `/api/rh/meus-dados/` | identidade, matrícula, campus | contexto |

> O IFRN já tem `/api/pesquisa/projetos/` e `/api/extensao/projetos/`; é provável que o IFMA migre para isso. A API está em transição (muitos "será movido/removido") → **camada de adaptação obrigatória**.

### 2.2 Interface web (onde está o RIT de fato)
- Módulo do RIT no IFMA: **`pit_rit_v2`**. A consulta pública fica em `/pit_rit/planos_individuais_trabalho/` (4.265 relatórios publicados, desde 2019.1), com PDF em `/pit_rit_v2/relatorio_atividade_docente_pdf/{id}/`.
  → **RITs aprovados são públicos.** Isso é ótimo para entender a estrutura do documento final (usar o RIT da própria cliente como referência).
- `/edu/professor/?tab=planoatividades` exige login (redireciona para `/accounts/login/`).
- **Login web tem CAPTCHA, campo `auth_code` (código de verificação) e "Entrar com Gov.BR".** Consequência: automação web **não** consegue logar sozinha de forma confiável → o login precisa ser humano (navegador visível), e a sessão reaproveitada.
- Rodapé mostra builds diferentes (`suap-113`, `suap-165`) → deploys frequentes → **seletores de tela vão quebrar**; precisamos de testes de contrato e "modo diagnóstico".

### 2.3 Estrutura real no IFMA (telas enviadas pela cliente, 2026-09-29)

**Tela do plano** — `GET /edu/professor/?tab=planoatividades&ano-periodo=2025.1`
- Cabeçalho: dados do docente, período, C.H. total semanal (ex.: 40 h). A carga horária segue a "Portaria Normativa vigente" no período.
- **Dados da Avaliação** (é daqui que sai o status): Avaliador do Plano, Plano Enviado/Aprovado (com data e hora), Avaliador do Relatório, Relatório Enviado/Aprovado, Responsável pela Publicação, Relatório Publicado, Histórico (pareceres).
  → Regra "apto a preencher RIT" = `Plano Aprovado = Sim` e `Relatório Enviado = Não`.
- **Quadro Resumo** com C.H. por categoria: Aulas SUAP, Outras aulas (Q-Acadêmico, EAD…), Preparação/Manutenção/Apoio, Programas e Projetos de Ensino, Atendimento/Orientação de Alunos, Reuniões Pedagógicas, Pesquisa, Extensão, Gestão e Representação.
- **1. Ensino › Aulas SUAP**: tabela de diários (nº do diário, disciplina, diário dividido, local, modalidade, turma/horário, nº de alunos, CH semanal).
- Cada categoria lista as **atividades marcadas no PIT** (itens do catálogo da Portaria Normativa, ex.: "Orientação ou coorientação de TCC", "Participação em banca…", "Reuniões do Colegiado/NDE") e tem um campo **Arquivo** (anexo do PIT).

**Tela de preencher relatório** — `/pit_rit_v2/preencher_relatorio_individual_trabalho/{id}/`
São 7 tópicos fixos, e cada um tem **um editor rich text (CKEditor) e um único arquivo de até 10,0 MB**:
1. Ensino: Preparação, Manutenção e Apoio ao Ensino
2. Ensino: Programas e Projetos de Ensino
3. Ensino: Atendimento, Acompanhamento, Avaliação e Orientação de Alunos
4. Ensino: Reuniões Pedagógicas, de Grupo e Afins
5. Pesquisa
6. Extensão
7. Gestão e Representação Institucional

Mais um campo rich text **"Alterações de Atividades"** (sem anexo), para declarar o que mudou em relação ao PIT.
- **Aulas não têm tópico no RIT.** Os diários provavelmente vêm do sistema e servem de evidência para "Preparação" e "Atendimento".
- Confirmado: **1 anexo por tópico, ≤ 10 MB** → a ideia da cliente de "PDF unificado por tópico" é exatamente o que o formulário pede; o bundler **precisa comprimir e dividir por prioridade** para caber em 10 MB.
- Os textos vão para o CKEditor: gerar HTML simples (parágrafos e listas) e injetar pela API do editor, sem digitar tecla a tecla.

### 2.4 Como o RIT funciona em outros IFs (referência)
- O relatório é gerado a partir do plano; tem as mesmas categorias (ensino, pesquisa, extensão, gestão/representação…); cada atividade recebe **quantidade/execução, descrição e comprovante**.
- **Restrição relevante vista em outro sistema: "apenas UM anexo por atividade"** → daí a ideia da cliente de "um PDF unificado por tópico". Precisamos confirmar no IFMA: é 1 anexo por **tópico** ou por **atividade**? Qual o limite de tamanho? Aceita só PDF?
- Fluxo: preencher → "Submeter relatório para avaliação" → avaliador/chefia → pode voltar para correção → publicado.

---

## 3. Mercado e soluções semelhantes

| Solução | O que faz | Lição para nós |
|---|---|---|
| **Pgd2 Pitrit Autofill Pro** (extensão Chrome, v1.0.18, fev/2026, ~10 usuários, modelo de licença/trial) | autopreenche entregas de PIT/RIT **do PGD2** (Programa de Gestão, técnico-administrativos), em lote | Prova que existe demanda paga; **mas é o PGD, não o PIT/RIT docente**, e só preenche — não garimpa evidências. Nosso diferencial é o garimpo + organização + texto. |
| **SUAP++** (extensão Chrome, 2023) | importa aulas e faltas nos diários | Extensão roda dentro da sessão já logada → contorna CAPTCHA naturalmente. Alternativa de arquitetura a considerar. |
| **Scripts IFMS** (extensão) | preenche diários, planos, frequência em massa | Idem. |
| **Normativa Docente IFSULDEMINAS** (sistema próprio) | plano → relatório clonado → comprovantes → comissão | Modelo mental do "relatório como cópia editável do plano". |
| **scriptLattes / Rank Lattes / SAAD (UFRB)** | geram relatórios a partir do Lattes/sistemas institucionais | O **Lattes** é uma fonte de evidência que a entrevista não citou (publicações, bancas, orientações). |
| Wrappers da API SUAP (`ivmelo/suap-api-php` etc.) | cliente da API (foco aluno) | Não cobrem PIT/RIT; nada pronto para docente. |
| **Gmail MCP oficial do Google** (preview, ago/2026) | busca/leitura/rascunho, **sem envio**, escopos `gmail.readonly`/`gmail.compose` | Não precisamos construir integração Gmail do zero no modo MCP; no modo CLI usamos a Gmail API com `gmail.readonly`. |

**Conclusão de mercado:** não encontrei nada que faça **garimpo multi-fonte + organização por semestre + preenchimento do RIT docente**. Existem ferramentas de *preenchimento* (extensões), e o nicho é pequeno (docentes de IFs que usam SUAP), mas a dor é recorrente (2×/ano) e universal na rede federal que usa SUAP.

---

## 4. Validação do modelo CLI + MCP

### O que o modelo acerta
- **Um núcleo, duas interfaces.** A lógica (coleta, dedup, semestres, PDFs, preenchimento) vive numa biblioteca; CLI e MCP são cascas finas.
- **CLI** = pipeline determinístico, reexecutável, testável, bom para dev/power user e para rodar em lote.
- **MCP** = o docente conversa com o Claude: "monta meu RIT de 2026.1", revisa classificações ambíguas, pede para reescrever um texto. O **LLM do host escreve os textos** — não precisamos embutir um LLM no MCP.

### Onde o modelo tem risco
1. **Perfil do usuário.** Docente típico não usa terminal. CLI é para *nós*; o produto para a cliente é o MCP (Claude Desktop) — **ela usa/aceita usar Claude Desktop com plano pago?** Se não, o caminho natural é extensão de navegador ou app desktop simples.
2. **Login com CAPTCHA/Gov.br.** Tanto CLI quanto MCP precisam abrir um navegador visível para o docente logar, e guardar a sessão. Funciona, mas o MCP tem que lidar com "sessão expirou, faça login de novo".
3. **O preenchimento precisa de navegador local** (Playwright). MCP local (stdio) resolve; MCP remoto não (credenciais e sessão do docente não devem sair da máquina dela).
4. **MCP com ferramentas granulares demais** faz o LLM se perder. Preferir ferramentas de alto nível com checkpoints.

### Recomendação
- Núcleo + CLI primeiro (MVP testável), MCP local como segunda casca logo em seguida.
- Manter a porta aberta para **extensão de navegador** como terceira casca do preenchimento (resolve login/CAPTCHA e é o formato que o mercado já adota).

---

## 5. Arquitetura proposta

```
┌──────────── Interfaces ────────────┐
│  CLI (typer)      MCP server (stdio)│
└───────────────┬────────────────────┘
                │
┌───────────────▼──────────────── Núcleo ──────────────────────────────┐
│ auth        sessão web (Playwright storage_state, login humano)       │
│             + JWT da API (/api/token/pair)                            │
│ collectors  api_suap │ web_suap (meus planos, pasta funcional) │      │
│             gmail │ pasta local │ (lattes, futuro)                    │
│ model       Evidence(id, tipo, título, período[início,fim], fonte,    │
│             arquivos, hash, chaves de dedup, confiança)               │
│ dedup       chave natural (tipo+título normalizado+datas+nº portaria) │
│             + hash de arquivo; conflitos → revisão humana             │
│ allocator   evidência → semestres (regra de sobreposição com calendário)│
│ classifier  evidência → tópico do RIT (regras + LLM p/ ambíguos)      │
│ bundler     PDFs por tópico: merge, índice/capa, compressão, limites  │
│ writer      texto por tópico (template + LLM; nunca inventa)          │
│ filler      Playwright preenche o RIT, faz upload, NÃO clica enviar,  │
│             devolve link de visualização                              │
│ workspace   disco local (ver 5.1) + manifest.json                     │
└──────────────────────────────────────────────────────────────────────┘
```

**Stack sugerida:** Python (Playwright, `pypdf`/`pikepdf` para merge e compressão, `pdfminer` para extrair texto de portarias, SDK oficial de MCP, Gmail API). Python concentra o melhor ferramental de PDF.

### 5.1 Workspace em disco (a "pasta do semestre")

```
~/suap-rit/
  2026.1/
    manifest.json            # evidências, origem, hash, tópico, status de revisão
    01-ensino/
      evidencias/*.pdf
      ENSINO_2026.1.pdf      # unificado (capa + índice + anexos)
      texto.md
    02-orientacoes/ ...
    03-projetos/ ...
    04-bancas/ ...
    05-gestao-representacao/ ...
  2026.2/ ...
  _cache/                    # downloads brutos, deduplicados por hash
```

- Evidência que atravessa semestres é **referenciada nos dois** pelo manifest (cópia física feita no momento do bundle, como pediu a cliente), sem duplicar o download.
- O `manifest.json` é a fonte da verdade; as pastas são projeção dele. Isso permite reprocessar sem perder revisões manuais.

### 5.2 Pipeline

1. `suap-rit login` — abre navegador, docente loga (CAPTCHA/Gov.br), sessão salva localmente.
2. `suap-rit planos` — lista PITs por ano/semestre e status; só os **aprovados** seguem.
3. `suap-rit coletar 2026.1` — roda coletores, baixa PDFs, normaliza em `Evidence`, deduplica.
4. `suap-rit organizar 2026.1` — aloca por semestre, classifica por tópico, marca pendências.
5. `suap-rit revisar 2026.1` — lista ambiguidades (duplicata provável? tópico incerto? data ausente?) para decisão humana.
6. `suap-rit montar 2026.1` — gera PDFs unificados e rascunhos de texto.
7. `suap-rit preencher 2026.1 [--dry-run]` — preenche o RIT no SUAP, faz uploads, **não envia**, imprime link.

### 5.3 Ferramentas MCP (alto nível)

| Tool | Efeito |
|---|---|
| `listar_planos(ano?)` | PITs + status |
| `coletar_evidencias(semestre)` | roda 3; devolve resumo + pendências |
| `listar_pendencias(semestre)` / `resolver_pendencia(id, decisao)` | revisão conversacional |
| `obter_topico(semestre, topico)` | evidências + texto atual (para o LLM redigir) |
| `salvar_texto(semestre, topico, texto)` | grava o texto escrito pelo LLM |
| `montar_anexos(semestre)` | gera PDFs |
| `preencher_rit(semestre, dry_run)` | preenche, retorna link; exige confirmação |

Resources MCP: `rit://2026.1/manifest`, `rit://2026.1/{topico}/texto`.

### 5.4 Regras de negócio que precisam estar explícitas no código
- **Alocação por semestre:** evidência entra no semestre se `[início, fim]` intersecta o período letivo. Evidência sem data de fim (ex.: portaria de comissão "por prazo indeterminado") → pendência de revisão.
- **Dedup entre "Meus planos" e acervo/pasta funcional:** chave natural + similaridade de título + mesmo nº de portaria/processo. Em dúvida, **não descartar — perguntar**.
- **Texto nunca afirma o que não tem evidência.** Todo parágrafo gerado deve apontar para evidências do manifest.

---

## 6. Lacunas que a entrevista não cobriu

1. ~~Estrutura exata do formulário do RIT~~ → **resolvido em 2.3** (7 tópicos com texto e 1 anexo de até 10 MB, mais "Alterações de Atividades"). Ainda em aberto: limite de caracteres do texto, formatos aceitos no anexo e se o formulário salva rascunho parcial.
2. **Relação PIT ↔ RIT:** o RIT nasce clonado do PIT? Dá para adicionar atividades não previstas no PIT? Atividade planejada e não executada — remove ou justifica?
3. **Carga horária:** o RIT pede horas por atividade? Existe mínimo/máximo por categoria (regulamento docente do IFMA — Res. CONSUP 67/2019 e sucessoras)? A ferramenta deveria validar isso.
4. **Afastamentos, licenças, férias** no semestre alteram o que é exigido.
5. **Definição de semestre:** calendário acadêmico do campus (datas letivas) ou semestre civil (jan–jun/jul–dez)? Cursos anuais/integrados?
6. **Lattes** como fonte (publicações, bancas externas, orientações) — não citado.
7. **Assinatura/validade dos documentos:** portaria baixada do SUAP já tem autenticação; ata do Gmail pode ser rascunho sem assinatura — vale como comprovante?
8. **Privacidade (LGPD):** diários e atas contêm nomes/matrículas de alunos; RIT aprovado **fica público**. O anexo também fica público ou só o relatório? Talvez seja preciso **não anexar** listas de alunos.
9. **Segurança de credenciais:** senha do SUAP e token Gmail ficam onde? (keyring do SO, nunca em texto puro; nada sai da máquina.)
10. **Termos de uso / posição da TI do IFMA** sobre automação da interface web e uso da API por aplicação de terceiro (existe cadastro de aplicação OAuth2 no SUAP?).
11. **Modo multi-docente:** a ferramenta é para uma pessoa ou para vários docentes/coordenação?
12. **Correções pós-avaliação:** quando a chefia devolve o RIT, a ferramenta ajuda a corrigir?

---

## 7. Perguntas para validar com a cliente

**Processo e dor**
1. Quanto tempo leva hoje para fazer um RIT? Qual etapa dói mais: achar, organizar, escrever ou subir?
2. Você já teve RIT devolvido? Por quê (falta de comprovante, texto, carga horária)?
3. Qual o prazo do RIT no seu campus e quando você costuma fazer (na véspera?)?
4. Você faz o RIT de um semestre de cada vez ou acumula?

**Formulário do RIT**
5. Pode compartilhar a tela de preenchimento do RIT (print ou gravação) e o PDF de um RIT seu já aprovado?
6. ~~Anexo por tópico ou por atividade?~~ Resolvido: por tópico, até 10 MB. O que fazer quando os comprovantes passam de 10 MB: comprimir, priorizar ou anexar um índice com link?
7. O que costuma ir em "Alterações de Atividades"? Atividade do PIT que não aconteceu precisa ser justificada ali?
8. O campo de texto tem limite de caracteres? Há um padrão de redação esperado pela chefia?

**Evidências**
9. Quais tipos de comprovante a chefia aceita? Ata não assinada vale? Print de e-mail vale?
10. Na pasta funcional, as portarias estão todas lá ou algumas só chegam por e-mail?
11. O Gmail é institucional (Google Workspace do IFMA) ou pessoal? Há uma pasta/marcador onde as atas chegam? Remetentes típicos?
12. Você guarda certificados/declarações em alguma pasta ou Drive?
13. Usa o Lattes atualizado? Vale como fonte?
14. Um exemplo concreto de "atividade que atravessa semestre" e como você declara hoje nos dois.
15. Exemplo concreto de duplicidade entre "Meus planos" e a pasta funcional — o que se repete?

**Uso da ferramenta**
16. Você usa (ou toparia usar) o Claude Desktop? Terminal está fora de questão?
17. Você se sente confortável em logar no SUAP numa janela aberta pela ferramenta (sua senha não sai do seu computador)?
18. O que você precisa **ver** antes de clicar Enviar para confiar no resultado?
19. Outros colegas teriam a mesma dor? Coordenação usaria para vários docentes?
20. Quanto pagaria / a instituição pagaria? (O concorrente mais próximo cobra licença.)

**Novas, após a navegação autenticada**
21. Há 5 semestres com RIT pendente (2020.2, 2025.1, 2025.2, 2026.1, 2026.2). Qual a prioridade? Tem prazo de regularização?
22. Posso usar **"Salvar"** no formulário (fica como rascunho, sem entregar)? Ou você prefere que a ferramenta só gere textos e PDFs e você cole?
23. Diárias/viagens (PCDP, ex.: reuniões do CONSUP) contam como comprovante de representação?
24. Cursos de formação (CFS, encontros pedagógicos) entram em "Reuniões pedagógicas" ou em "Preparação"?
25. Portarias sem vigência explícita (ex.: banca de uma data só): vale a data da portaria ou a data da defesa?
26. Projetos de pesquisa com bolsistas contam também em "Orientação de alunos" ou só em "Pesquisa"? (evitar dupla contagem entre tópicos)
27. O texto de cada tópico deve listar item a item (título, portaria, período) ou ser um parágrafo narrativo?

## 8. Perguntas para a TI/DTI do IFMA (ou para investigar)
- Há API/roadmap para PIT/RIT, pasta funcional e portarias? O IFMA vai adotar `/api/pesquisa/projetos/` e `/api/extensao/projetos/` como o IFRN?
- `meu-historico-funcional` inclui portarias com PDF?
- É possível registrar uma aplicação OAuth2 no SUAP IFMA para evitar pedir senha?
- Há objeção a automação da interface web por um usuário autenticado agindo sobre os próprios dados?

---

## 9. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Mudança de tela no SUAP quebra scraper/preenchedor | alto, recorrente | seletores centralizados, testes de contrato com HTML salvo, `--dry-run`, modo diagnóstico que salva screenshot |
| CAPTCHA/Gov.br/2FA | bloqueia automação total | login humano + reuso de sessão; extensão como alternativa |
| Endpoints "será removido" somem | coletor quebra | adaptadores por versão; fallback web |
| Texto gerado afirmar algo falso | responsabilidade do docente | texto sempre ancorado em evidências; revisão obrigatória; nunca enviar |
| Dados de alunos em anexos públicos | LGPD | política de anexos, alerta, redigir/omitir listas |
| Credenciais | vazamento | keyring do SO, execução 100% local, escopos mínimos (Gmail readonly) |
| Nicho pequeno | sustentabilidade | começar com a cliente, medir tempo economizado, expandir para outros IFs com SUAP |

---

## 10. Próximos passos sugeridos (descoberta antes de código)

1. **Sessão guiada com a cliente (30–45 min, gravada):** ela faz um RIT real (ou o último) enquanto narra. Coletar: prints do formulário `pit_rit_v2`, HTML das abas de "Meus planos" e da pasta funcional, PDF do RIT aprovado dela, exemplos de e-mails com atas.
2. **Spike técnico 1 (API):** com a conta dela (ou a nossa, se formos servidores), chamar os endpoints de 2.1 e documentar o que realmente volta.
3. **Spike técnico 2 (web):** Playwright com login humano, salvar sessão, extrair uma aba de "Meus planos" e baixar uma portaria da pasta funcional.
4. **Definir os tópicos do RIT e as regras de dedup/semestre** com base nos dados reais → atualizar este documento.
5. Só então: MVP `login → planos → coletar → organizar → montar` (sem preenchimento), validar com a cliente, e depois `preencher --dry-run`.

---

## Fontes
- OpenAPI SUAP IFMA: https://suap.ifma.edu.br/openapi.json · IFRN: https://suap.ifrn.edu.br/api/openapi.json
- Consulta pública de RITs IFMA: https://suap.ifma.edu.br/pit_rit/planos_individuais_trabalho/
- Manual SUAP módulo professor (IFTO): https://campusparaiso.ifto.edu.br/blog/cgti/wp-content/uploads/sites/9/2024/05/Manual-Suap-Modulo-Professor.pdf
- Manual docente SUAP Ensino (IFB): https://www.ifb.edu.br/attachments/article/45664/Manual_Docente_SUAP_Ensino_IFB2.pdf
- Orientações relatório docente (IFSULDEMINAS TCO): https://portal.tco.ifsuldeminas.edu.br/images/Campus/Normativa_Docente/Orienta%C3%A7%C3%B5es_Docentes_Preenchimento_Relat%C3%B3rios_da_Normativa_Docentes.pdf
- Pgd2 Pitrit Autofill Pro: https://chromeboard.com/extension/pgd2-pitrit-autofill-pro-nebjdbjiehjnedcilflbjaefhfaiblga
- SUAP++: https://chrome.google.com/webstore/detail/suap++/kabkakmojimnlgnmnnmceokclfbdcnfg
- Regulamentação docente IFMA (notícia CONSUP 2019): https://portal.ifma.edu.br/2019/10/01/consup-aprova-regulamentacao-das-atividades-docentes-da-carreira-ebtt/
- Gmail MCP (visão geral): https://www.dragapp.com/blog/gmail-mcp-server/
- scriptLattes / ferramentas Lattes: https://sol.sbc.org.br/index.php/enucompi/article/download/17757/17592
