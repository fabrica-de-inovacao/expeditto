# Mapa do SUAP IFMA para o RIT (sessão autenticada, 2026-09-29)

> Levantamento feito navegando com a conta da cliente via Playwright MCP, **somente leitura** (GETs; nada salvo/enviado).
> Não registrar aqui dados pessoais de terceiros (alunos, colegas). IDs abaixo são exemplos estruturais.

## 0. Técnica de coleta que funcionou

- Após login humano, **toda coleta pode ser feita com `fetch()` na mesma sessão** (cookie `__Host-sessionid`) — sem clicar em nada.
- Abas das páginas (`.tab-pane.ajax-rendered`) carregam via `GET <página>?tab=<nome>` com header `X-Requested-With: XMLHttpRequest`.
  Atenção: no perfil do servidor a resposta traz **todas** as tabelas do perfil, não só a aba pedida → identificar tabela pelos cabeçalhos.
- A **API REST aceita a sessão web** (SessionAuth) em vários endpoints → um único login humano serve para web + API.

## 1. Planos e status — `/edu/professor/?tab=planoatividades&ano-periodo=AAAA.P`

- `select[name=ano-periodo]`: 2019.1 … 2026.2.
- Bloco **Dados da Avaliação**: Avaliador do Plano, Plano Enviado, Plano Aprovado, Avaliador do Relatório, Relatório Enviado, Relatório Aprovado, Responsável pela Publicação, Relatório Publicado, **Histórico** (pareceres PIT/RIT com autor e data).
- **Quadro Resumo** (C.H. semanal por categoria) + atividades do catálogo marcadas no PIT, por categoria.
- Links de ação revelam o estado (máquina de estados inferida):

| Link presente | Estado |
|---|---|
| `/pit_rit_v2/cadastrar_plano_individual_trabalho/{prof}/{ano}/{p}/` + `/enviar_plano/{id}/` | plano não enviado |
| `/pit_rit_v2/preencher_relatorio_individual_trabalho/{id}/` | **plano aprovado, RIT a preencher** ← alvo |
| `/pit_rit_v2/entregar_relatorio/{id}/` | RIT salvo/devolvido, aguardando entrega |
| `/pit_rit_v2/relatorio_atividade_docente_pdf/{id}/` | RIT existe (PDF) |
| `/pit_rit_v2/plano_atividade_docente_pdf/{id}/` | PDF do PIT |

- Observado na conta: **5 semestres com RIT pendente** (2020.2, 2025.1, 2025.2, 2026.1, 2026.2) e um lote de ~10 RITs entregues no mesmo dia (16/09/2026). Pareceres da chefia pedem explicitamente *"anexar comprovações"* / *"incluir comprovações: projetos e resoluções"*.

## 2. Formulário do RIT — `/pit_rit_v2/preencher_relatorio_individual_trabalho/{id}/`

Form Django, `POST multipart` para a mesma URL, botão **Salvar** (`relatorioindividualtrabalhoprofessor_form`). **Salvar ≠ Entregar** (entrega é outra rota) → a ferramenta pode salvar tudo e deixar a entrega para a docente.

| Tópico | Texto (CKEditor) | Arquivo (≤ 10 MB) |
|---|---|---|
| Ensino: Preparação, Manutenção e Apoio | `obs_apoio_ensino` | `arquivo_apoio_ensino` |
| Ensino: Programas e Projetos de Ensino | `obs_programas_projetos_ensino` | `arquivo_programas_projetos_ensino` |
| Ensino: Atendimento/Orientação de Alunos | `obs_orientacao_alunos` | `arquivo_orientacao_alunos` |
| Ensino: Reuniões Pedagógicas | `obs_reunioes` | `arquivo_reunioes` |
| Pesquisa | `obs_pesquisa` | `arquivo_pesquisa` |
| Extensão | `obs_extensao` | `arquivo_extensao` |
| Gestão e Representação Institucional | `obs_gestao` | `arquivo_gestao` |
| Alterações de Atividades | `alteracoes` | — |

`accept` não restringe tipo de arquivo no HTML (validar no servidor).

## 3. Abas de "Meus planos" — `/edu/professor/?tab=…`

| Aba (`tab`) | Colunas relevantes | Comprovante pronto (PDF) |
|---|---|---|
| `disciplinas` | Período, Diário, Turma, Campus, Tipo, Semestral | `/edu/meu_diario/{id}/{n}/` (+ API `meus-diarios`) |
| `estagios` (5 tabelas: estágio vigente, concluído, aprendizagem, atividade profissional efetiva, atividade equivalente) | Aluno, Concedente, **Data de Início**, **Data Prevista p/ Encerramento**, C.H., Situação | — (link `/estagios/pratica_profissional/{id}/`) |
| `projetofinal` (orientação e coorientação) | **Ano Período Letivo**, Tipo, Título, Aluno, Situação, **Data da Apresentação** | `/edu/declaracao_participacao_projeto_final_pdf/{id}/coorientador/…` |
| `banca` (filtros `ano_letivo`, `periodo_letivo`, `tipo`) — presidente e examinador | Ano Período Letivo, Título, Data da Apresentação | `/edu/declaracao_participacao_projeto_final_pdf/{id}/{presidente\|examinador_interno\|examinador_externo\|terceiro_examinador}/` |
| `projetos` (extensão e pesquisa) | Edital, Projeto | `/projetos/emitir_certificado_extensao_pdf/{id}/`, `/pesquisa/emitir_declaracao_participacao_pdf/{id}/` |
| `orientacaopos`, `pos_graduacao`, `minicursos` | (vazias nesta conta) | — |

## 4. Perfil do servidor — `/rh/servidor/{matricula}/?tab=…`

| Aba | Conteúdo | Uso no RIT |
|---|---|---|
| `pasta_funcional` (79 docs) | Tipo de Arquivo, Nome, Inserido em, Descrição, Protocolo | **Gestão/Representação, Reuniões, bancas** |
| `participacoes_extensoes` (27) | = aba `projetos` (extensão) de Meus planos | **duplicata exata** → dedup por id do projeto |
| `participacoes_pesquisas` (38) | = aba `projetos` (pesquisa) | **duplicata exata**; oferece também `/pesquisa/emitir_certificado_pdf/{id}/` |
| `participacoes_ensino` (9) | projetos de ensino | **só existe aqui** → fonte de "Programas e Projetos de Ensino" (`/projetos_ensino/emitir_certificado_participacao_pdf/{id}/`) |
| `historico_funcoes` | cargos/funções com início/fim (ex.: coordenação de curso desde 2023) | Gestão |
| `ocorrencias_afastamentos` | afastamentos com período (viagens a serviço, capacitação) | justificativas / Alterações |
| `diarias_passagens` (55) | PCDP: motivo ("Participar da Reunião do CONSUP"), datas | **evidência de reuniões/representação** |
| `cfs` | cursos de formação do servidor (encontros pedagógicos) | Reuniões pedagógicas / capacitação |
| Link "Currículo Lattes" | `/cnpq/curriculo/{id}/` | fonte extra (publicações) |

### Pasta funcional em detalhe
- Tipos (contagem nesta conta): **Designação para compor comissões/conselhos/bancas (49)**, Programas Institucionais PRONATEC/MEDIOTEC/ETEC (3), Designação de FCC (2), substituto eventual (4), e vários irrelevantes para o RIT (progressão, plano de saúde, exercício anterior…). → **o campo "Tipo de Arquivo" já é um classificador**.
- Dois formatos: **documento eletrônico** (53) e **PDF enviado** (26).
- Documento eletrônico: texto HTML em `/documento_eletronico/conteudo_documento/{id}/` (fácil de parsear); PDF em `/documento_eletronico/imprimir_documento_pdf/{id}/carta/` (também PDF/A).
- O texto traz o que precisamos para semestre e papel: nº da portaria, data, processo, papel ("Presidente", "Membros"), e **vigência** ("A Comissão terá vigência no período de 18.08.2026 a 18.11.2026"; NDE "2025 a 2027").
- "Inserido em" **não** é a data da atividade. Descrição frequentemente vazia ("Adicionar Descrição") → extrair do texto da portaria.

## 5. API REST com a sessão web

| Endpoint | Resultado |
|---|---|
| `/api/edu/meus-diarios/{ano}/{p}/` | 200 — diários com aulas, participantes, materiais |
| `/api/rh/meu-historico-funcional/` | 200 — eventos funcionais em HTML (sem portarias de comissão) |
| `/api/v2/minhas-informacoes/participacoes-projetos/` | 200 — só edital+título |
| `/api/projetos/` | 200 — **8.474 projetos da instituição com `dt_inicio`/`dt_final`** → join por título/id para datas |
| `/api/rh/minhas-ocorrencias-afastamentos/` | 200 |
| `/api/rh/eu/` | 401 (exige JWT) |
| `/api/edu/meus-periodos-letivos/` | 404 |

Página de projeto de pesquisa tem "Início da Execução"/"Término da Execução" (ex.: 01/09/2021–31/08/2022 → atravessa 2021.2 e 2022.1).

## 6. Mapeamento fonte → tópico do RIT (proposta inicial, validar com a cliente)

| Tópico | Fontes |
|---|---|
| Preparação/Apoio ao Ensino | diários do semestre (API), planos de ensino, cursos CFS |
| Programas e Projetos de Ensino | `participacoes_ensino`, portarias "Programas Institucionais" |
| Atendimento/Orientação de Alunos | `estagios`, `projetofinal`, `banca`, bolsistas de projetos |
| Reuniões Pedagógicas | portarias de NDE/Colegiado, atas (Gmail), CFS encontros pedagógicos |
| Pesquisa | projetos de pesquisa + declarações/certificados |
| Extensão | projetos de extensão + certificados |
| Gestão e Representação | `historico_funcoes`, portarias de comissões/conselhos, PCDP de reuniões (CONSUP) |

## 7. Perfil do usuário: contexto útil × dados que NÃO coletamos

Fontes: `/rh/servidor/{matricula}/?tab=dados_gerais`, `/edu/professor/?tab=…`, `/cnpq/curriculo/{id}/`.

### 7.1 Contexto útil (coletar no setup → `perfil.json`)

| Dado | Onde | Uso |
|---|---|---|
| Nome usual / nome de registro, matrícula SIAPE | dados_gerais | cabeçalho dos textos e busca do nome nas portarias |
| E-mail institucional e e-mail acadêmico (`@acad.ifma.edu.br`) | dados_gerais | **as duas contas** a vasculhar no Gmail (D20) |
| Campus, Setor SUAP, lotação/exercício | dados_gerais | calendário do campus (D17), filtro de portarias do campus |
| Cargo, classe/padrão, **jornada (DE/40h/20h)**, regime | dados_gerais | C.H. semanal esperada; o texto do RIT cita o regime |
| Titulação (ex.: Mestre + RSC-III) e matéria de ingresso | dados_gerais / professor | contexto para os textos |
| Participa do PGD | dados_gerais | se sim, o fluxo muda (PGD2 × pit_rit_v2) |
| Função atual e histórico de funções (ex.: coordenação de curso desde 2023) | `historico_funcoes` / dados_gerais | Gestão (D13, D16) |
| Afastamentos com período | `ocorrencias_afastamentos` | justificam C.H. menor → "Alterações de Atividades" |
| Horários semanais | `/edu/professor/?tab=horarios` | confere C.H. de aula |
| **Lattes importado no SUAP** (data de atualização, ID Lattes) | `/cnpq/curriculo/{id}/` | ver 7.2 |
| Grupos de pesquisa | Lattes importado | Pesquisa |

### 7.2 Lattes importado pelo SUAP
- Não é preciso acessar `lattes.cnpq.br` (que tem CAPTCHA): o SUAP guarda uma cópia estruturada com data de atualização.
- Seções úteis: artigos, trabalhos em anais, resumos, livros e capítulos, apresentações, cursos ministrados, produção técnica, patentes/marcas, **orientações em andamento e concluídas**, **projetos de pesquisa/extensão/desenvolvimento**, **participação em bancas** (TCC e comissões julgadoras), organização de eventos, participação em congressos/seminários/encontros.
- Limites: a granularidade é o **ano** (às vezes "Início: 2025"), e o Lattes é **autodeclaração, não comprovante**. Uso:
  1. **Detector de lacunas:** item do Lattes no ano sem evidência no SUAP → pendência ("você tem este artigo de 2025; tem o comprovante?").
  2. Enriquecer o texto (títulos completos, eventos).
  3. Fonte de itens que o SUAP não tem (publicações, bancas externas).

### 7.3 Dados sensíveis — NUNCA coletar, guardar ou mandar ao LLM
CPF, RG, título de eleitor, PIS/PASEP, dados bancários, endereço, telefones pessoais, data de nascimento, estado civil, filiação, raça/etnia, tipo sanguíneo, dependentes, contracheques. O parser de `dados_gerais` trabalha com **allowlist** de campos (7.1); todo o resto é descartado na leitura.

### 7.4 Privilégios da conta
Contas com função de coordenação veem menus administrativos (admin de diários, cursos, PIT/RIT de outros, relatórios de importação do Lattes). A ferramenta **só acessa rotas do próprio usuário** (allowlist de rotas); nunca rotas `/admin/`, `djtools/breadcrumbs_reset` ou dados de outros servidores.

## 8. Download de comprovantes (verificado)

| Origem | URL | Resposta |
|---|---|---|
| Declaração de banca (por papel) | `/edu/declaracao_participacao_projeto_final_pdf/{id}/{papel}/` | PDF direto |
| Certificado de extensão | `/projetos/emitir_certificado_extensao_pdf/{id}/` | PDF direto |
| Declaração de pesquisa | `/pesquisa/emitir_declaracao_participacao_pdf/{id}/` | PDF direto |
| Certificado de projeto de ensino | `/projetos_ensino/emitir_certificado_participacao_pdf/{id}/` | PDF direto |
| PDF enviado na pasta funcional | `/arquivo/visualizar_arquivo_pdf/{hash}` | PDF direto |
| Documento eletrônico (portaria) | `/documento_eletronico/imprimir_documento_pdf/{id}/carta/` | **tarefa assíncrona** ↓ |

Tarefa assíncrona (`djtools process2`):
1. `GET /documento_eletronico/imprimir_documento_pdf/{id}/carta/` → redireciona para `/djtools/process2/{uuid}/`.
2. Polling `GET /djtools/process_progress2/0/{uuid}/` → texto `percentual::mensagem::arquivo::url::erro`.
3. Quando `mensagem` e `arquivo` estiverem preenchidos → `GET /djtools/process_progress2/1/{uuid}/` = PDF.
- Texto da portaria para parsing (sem gerar PDF): `/documento_eletronico/conteudo_documento/{id}/`.

Efeitos colaterais observados: emissões e tarefas aparecem no histórico de acessos do usuário e criam registros de tarefa. Isso é aceitável, mas a ferramenta deve **cachear** os PDFs por id e não gerar de novo a cada execução.
Sessão: a página mostra "Sessão expira em 01:30:00" → sessão de 90 min, renovada a cada uso.

## 9. Comprovantes adicionais (validados em 2026-09-29)

### 9.1 Declarações anuais de orientação de estágio
Na aba `?tab=estagios` há três menus ("Emitir Declaração de Orientação de Estágios", "…de Aprendizagens", "Emitir Declaração" para atividades profissionais efetivas). Cada menu lista os anos disponíveis:

`GET /edu/emitir_declaracao_de_orientacao_pdf/{professor_id}/{estagios|aprendizagens|atividadesprofissionaisefetivas}/{ano|0}/` → PDF direto.

- A declaração é **anual e consolidada**: lista todos os estágios da modalidade ativos no ano (aluno, curso, concedente, período, situação). `0` = todos os anos.
- Estágio de "atividade equivalente" não tem declaração.
- Mapeamento URL da linha → modalidade: `pratica_profissional`→`estagios`, `aprendizagem`→`aprendizagens`, `atividade_profissional_efetiva`→`atividadesprofissionaisefetivas`.

### 9.2 Equipe dos projetos (papel do docente)
`GET /{pesquisa|projetos|projetos_ensino}/projeto/{id}/?tab=equipe` (XHR). A mesma resposta traz "Início/Término da Execução".

| Tipo | Layout | Papel | Outros campos |
|---|---|---|---|
| Pesquisa, Ensino | tabela `Membro · Situação · Categoria/Titulação · Bolsista · Coordenador · Carga Horária · Opções` | coluna Coordenador: `Sim` / `Sub` / `Não` | links na linha: Plano de Trabalho, Certificado, **Declaração de Participação**, **Declaração de Orientação** |
| Extensão | cartões `div.general-box` em seções "Coordenadores / Bolsistas / Voluntários" | etiquetas `span.status` (Coordenador, Subcoordenador, Voluntário, Bolsista) + `dt Função:` | `Carga Horária Semanal:`, links: Plano de Trabalho, Certificado, Declaração de Orientação |

A linha do docente é localizada pelo link `/rh/servidor/{matricula}/`.

- `…/emitir_declaracao_orientacao_pdf/{id}/`: comprova a orientação de discente no projeto (regra P1).
- `…/emitir_declaracao_participacao_pdf/{id}/`: comprovante para projeto **em andamento** (o certificado só sai na conclusão).
- A situação "Inativado" na participação faz o SUAP não emitir certificado nem declaração.

### 9.3 Validade dos documentos emitidos
Alguns PDFs trazem "Código verificador … Válido até: dd/mm/aaaa":

| Documento | Validade observada |
|---|---|
| Declaração de participação em banca/TCC | ~30 dias |
| Declaração de orientação de estágio | ~90 dias |
| Certificado de projeto de ensino | ~1 ano |
| Portarias, certificados de pesquisa e extensão | sem validade |

A ferramenta lê a validade no próprio PDF, registra no manifest (`ItemAcervo.validade`) e emite de novo quando o documento está vencido.

### 9.4 Declaração de docência (comprovante dos diários)
Na aba `?tab=disciplinas`, o menu "Emitir Declaração de Docência" lista os anos:

`GET /edu/declaracaodocencia_pdf/{professor_id}/{ano}/` → PDF direto (sem ano = todos os anos).

- É **anual** e oficial (código verificador, "Declaração de Vínculo Docente", validade ~30 dias).
- Por curso, traz: disciplina, período (AAAA/P), CH, créditos, diário, tipo (Semestral/Anual), **% atribuído** e **% ministrado** (carga horária registrada no diário).
- Contém o CPF do próprio docente (é o documento oficial dele; vai no anexo como o SUAP emite, D10).
- Descartado como alternativa: a impressão do diário (`/edu/diario_pdf/{id}/{etapa}/`), que é por etapa, traz a lista de alunos e não é declaração.
