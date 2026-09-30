# Arquitetura remota (VPS, multiusuário) — investigação ARQUIVADA

> **Status: arquivado em 2026-09-29 (D46).** Foi um estudo de viabilidade; o produto segue **local**. Fica como referência se um dia houver versão institucional.

> 2026-09-29. Motivação: o MCP deve rodar numa VPS, ser acionado remotamente e atender vários docentes.
> Isso também resolve a portabilidade (D44): Claude, ChatGPT e Gemini falam com **MCP remoto** (streamable HTTP + OAuth 2.1).

## 1. O que muda e o que não muda

| Camada | Protótipo local | Remoto |
|---|---|---|
| Núcleo (coleta, classificação, anexos, textos, formulário) | funções Python | **igual** (já recebe `SuapClient` e manifest como parâmetros) |
| Interface | CLI + MCP stdio | **MCP HTTP** (FastMCP) + **mini app web** (FastAPI) no mesmo processo; CLI continua como modo local |
| Identidade do usuário | implícita (máquina dele) | **OAuth 2.1 no MCP** (login do docente) |
| Sessão SUAP | keyring local | **cofre no servidor**, cifrada, TTL curto, por usuário |
| Acervo | `~/suap-rit` | armazenamento por usuário (volume cifrado → depois S3/MinIO) + Postgres |
| Execução | síncrona | **jobs** em fila (coleta leva minutos) com progresso |
| E-mail | conector do host (D41) | igual; backup OAuth vira fluxo web normal no servidor (D42) |

## 2. Visão geral

```
 Claude / ChatGPT / Gemini ──(MCP streamable HTTP + OAuth 2.1)──┐
                                                                ▼
                    ┌────────────── VPS (HTTPS, Caddy) ──────────────┐
 Navegador do       │  FastAPI app                                    │
 docente ──────────▶│   ├─ /mcp        FastMCP (tools, auth)          │
 (login, conectar   │   ├─ /auth/*     OAuth Proxy → Google (@ifma)   │
  SUAP, baixar      │   ├─ /suap/*     conectar/renovar sessão SUAP   │
  anexos, enviar    │   └─ /arquivos/* anexos (links assinados), upload│
  comprovantes)     │  Workers (fila) → núcleo suap_rit → SUAP IFMA   │
                    │  Postgres (usuários, jobs, manifests)           │
                    │  Cofre (sessões SUAP, tokens) · Armazenamento   │
                    └─────────────────────────────────────────────────┘
 Extensão Chrome "Conectar SUAP" ──(cookie de sessão, autenticado)──▶ /suap/sessao
```

## 3. Os três problemas difíceis

### 3.1 Quem é o usuário (login no MCP)
- **Recomendado: "Entrar com Google" restrito ao domínio `@ifma.edu.br`** via OAuth Proxy do FastMCP. Só escopos `openid email profile` → **sem verificação do Google e sem aviso** (diferente do Gmail). Todo servidor do IFMA já tem conta Google institucional.
- Alternativa futura: OAuth do próprio SUAP (identidade = matrícula). Exige a TI cadastrar a aplicação: a conta da docente vê "Aplicações OAUTH2", mas sem permissão de criar.
- Vínculo e-mail ↔ matrícula: no primeiro "Conectar SUAP" o servidor lê a matrícula da sessão e grava o vínculo; sessões de outra matrícula são recusadas depois.

### 3.2 A sessão web do SUAP no servidor (o ponto decisivo)
O login do SUAP tem CAPTCHA, código e Gov.br, e o token OAuth do SUAP não abre as páginas web (D45). O servidor precisa receber a **sessão web** do docente. Opções:

| Opção | Como funciona | Senha passa pelo servidor? | UX | Avaliação |
|---|---|---|---|---|
| **A. Extensão "Conectar SUAP"** (recomendada) | O docente loga no SUAP normalmente no Chrome dele; a extensão (autenticada no nosso serviço) envia o cookie `__Host-sessionid` ao servidor; reenvia sozinha enquanto ele usa o SUAP | **Não** | Um clique; funciona com Gov.br/CAPTCHA | Melhor segurança e UX; exige publicar extensão (Chrome Web Store) |
| **B. Navegador remoto com "live view"** | O servidor abre um Chromium e manda ao docente um **link** que mostra a tela de login do SUAP (streaming); ele loga ali; o servidor guarda o cookie | **Sim** (digitada num navegador do servidor) | É o fluxo de "link" que você imaginou | Funciona sem instalar nada; exige confiança maior e infraestrutura (Xvfb/noVNC ou Browserless/Steel) |
| C. Guardar usuário/senha e logar sozinho | — | Sim, **armazenada** | — | ❌ CAPTCHA/2FA impedem e é risco inaceitável |

Proposta: **A como caminho principal, B como alternativa** para quem não pode instalar a extensão.

Sessão dura ~90 min por inatividade: o worker **renova ao usar** (cada requisição estende); o MCP responde "conecte o SUAP" quando a sessão expira. Nunca guardamos senha.

### 3.3 Dados de muitos servidores num só lugar (LGPD e segurança)
O acervo tem dados pessoais (CPF nas declarações, nomes de alunos, portarias). Com vários usuários, o servidor vira alvo valioso e **operador de dados** de servidores públicos.
- Isolamento por usuário em tudo (pasta/bucket, linhas no banco); nenhuma tool aceita `usuario_id` do cliente, que vem sempre do token.
- Cifragem: sessões SUAP e tokens com chave do servidor (ex.: `age`/KMS), TTL de horas; arquivos em volume cifrado.
- Retenção: apagar acervo N dias após a entrega do RIT (configurável); botão "apagar meus dados".
- Escrita no SUAP continua restrita ao "Salvar" (allowlist); `entregar_relatorio` bloqueado.
- Logs sem conteúdo pessoal; trilha de auditoria (quem salvou o quê, quando).
- **Institucional**: para escala no IFMA, formalizar com a TI/encarregado de dados (termo de uso, base legal, hospedagem). Para o piloto com poucos docentes: consentimento explícito de cada um.
- Tráfego: todas as coletas saem do IP da VPS → limitar concorrência por usuário e global, com cache agressivo. Avisar a TI para não cair em bloqueio.

## 4. Ferramentas MCP no modo remoto

As mesmas do plano (prototipo-2 §3), com três ajustes:
1. **Jobs assíncronos**: `coletar_semestre` / `montar_anexos` / `salvar_no_suap` devolvem `job_id` e emitem progresso; `status_job(job_id)`.
2. **Arquivos por link**: anexos e prévias são entregues como **link assinado temporário** da nossa app (o host não recebe PDFs grandes).
3. **Conectar SUAP**: `status_sessao` devolve o link "Conectar SUAP" (extensão ou navegador remoto) quando não há sessão válida.

`registrar_ata` continua igual (o host lê o e-mail com o conector dele e nos envia os dados).

## 5. Impacto no código atual

| Módulo | Mudança |
|---|---|
| `config.py` / `acervo.py` | `home()` global → **`Armazenamento` por usuário** (interface: local por diretório → S3) |
| `auth.py` | keyring → **`CofreSessoes`** (por usuário, cifrado, TTL); `login_interativo` fica só na CLI |
| `coleta.py`, `anexos.py`, `textos.py`, `formulario.py` | recebem o armazenamento do usuário (hoje usam `config.home()`); sem outras mudanças |
| `client.py` | igual (allowlist, escrita só no "Salvar") + limitador de taxa |
| novo `servidor/` | FastAPI + FastMCP (HTTP) + OAuth Proxy Google + rotas `/suap`, `/arquivos` + fila (Arq/RQ com Redis) + Postgres |
| nova `extensao/` | extensão Chrome (Manifest V3) "Conectar SUAP" |

A CLI continua útil para desenvolvimento e para quem quer rodar tudo local.

## 6. Fases

1. **Piloto (1 VPS, até ~10 docentes)**: Docker Compose (app + Postgres + Redis + Caddy), OAuth Google @ifma, conexão SUAP pela **opção B** (mais rápida de entregar) ou pela extensão em modo desenvolvedor, volume cifrado, consentimento individual.
2. **Extensão publicada** e retenção/auditoria completas.
3. **Institucional**: acordo com a TI do IFMA (OAuth SUAP para identidade, app Gmail interno, hospedagem), S3/MinIO, observabilidade.

## 7. Decisões a confirmar
- R1. Identidade: Google @ifma.edu.br (recomendado) × OAuth do SUAP (depende da TI).
- R2. Conexão do SUAP no piloto: navegador remoto por link (B) × extensão (A) — ou B agora e A em seguida.
- R3. Quem opera a VPS e responde pelos dados (você/projeto × IFMA), retenção padrão (sugestão: 30 dias após a entrega).
- R4. Onde hospedar (Brasil, por LGPD/latência) e domínio.
