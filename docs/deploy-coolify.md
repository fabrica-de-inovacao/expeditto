# Site e instalador no Coolify (expeditto.fabitz.com.br)

O site é estático: a página (`site/index.html`), os scripts de instalação (`install.ps1`, `install.sh`) e os
SVGs do mascote, servidos por um nginx (`site/Dockerfile`, `site/nginx.conf`).

## Criar no Coolify 4.3.x

1. **Projects → + Add → "Expeditto"** (ambiente `production`).
2. No projeto: **+ New → Public Repository** (ou "Private Repository (with GitHub App)", se preferir).
   - Repositório: `https://github.com/vnschneider/expeditto`, branch `main`.
   - **Build Pack: Dockerfile**.
   - **Base Directory: `/site`**. Dockerfile Location: `/Dockerfile`.
3. Em **Configuration → General**:
   - **Domains**: `https://expeditto.fabitz.com.br` (o Coolify emite o certificado do Let's Encrypt; o DNS já
     aponta para a VPS).
   - **Ports Exposes**: `80`.
   - Rede: a padrão do Coolify (o proxy Traefik/Caddy do próprio Coolify roteia o domínio). Nada a expor no host.
4. **Deploy**. Depois, em **Webhooks / Automatic Deployment**, deixe o deploy automático a cada push na `main`.

## Conferir

```bash
curl -sI https://expeditto.fabitz.com.br/install.sh | grep -i content-type   # text/plain; charset=utf-8
curl -s  https://expeditto.fabitz.com.br/install.ps1 | head -5
```

## Regenerar o mascote do site

Os SVGs saem do mesmo desenho do terminal:

```bash
uv run python site/gerar_mascote.py
```

## Origem da instalação

Até o pacote ir para o PyPI (Fase 6), os scripts instalam do `.zip` da branch `main` do GitHub. Por isso o
instalador só enxerga o que estiver na `main`. Depois da publicação, trocar a origem padrão nos dois scripts para
`expeditto`. Não usar o PyPI como tentativa com fallback antes disso: se alguém registrar o nome primeiro, o
instalador baixaria o pacote de outra pessoa.
