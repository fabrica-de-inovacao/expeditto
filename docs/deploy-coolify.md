# Site e instalador no Coolify (expeditto.fabitz.com.br)

O site é estático: a página (`site/index.html`), os scripts de instalação (`install.ps1` e `install.sh`) e os
SVGs do mascote. No Coolify ele usa o **Build Pack "Static"**: o Coolify copia a pasta para uma imagem nginx dele,
e o proxy do Coolify (Traefik) cuida do domínio e do certificado HTTPS. Não há Dockerfile próprio.

## Recurso no Coolify 4.x

- **Projeto:** "Expeditto" (ambiente `production`), no servidor da VPS, na rede padrão do Coolify.
- **Tipo:** Public Repository → `https://github.com/vnschneider/expeditto`, branch `main`.
- **Build Pack:** Static · **Base Directory:** `/site` · porta `80`.
- **Domínio:** `https://expeditto.fabitz.com.br` (o DNS já aponta para a VPS; o Let's Encrypt é automático).
- **Custom Nginx Configuration:** o conteúdo de `site/nginx.conf`. É obrigatória: o nginx padrão não conhece `.ps1`
  e serviria o `install.ps1` como binário, o que quebra o `irm | iex`. A configuração também esconde os arquivos de
  manutenção (`.py`, `.conf`). Mudou a configuração? Faça um **Redeploy**: o Coolify grava a configuração na imagem
  durante o build, e um simples Restart não a aplica.
- **Deploy automático:** a cada push na `main` (webhook do GitHub ou deploy manual).

Pela API ou pelo MCP do Coolify (`@fndchagas/coolify-mcp`), o equivalente é criar uma aplicação pública com
`build_pack: "static"`, `base_directory: "/site"`, `ports_exposes: "80"`, `domains` e
`custom_nginx_configuration` (o arquivo em base64).

## Conferir

```bash
curl -sI https://expeditto.fabitz.com.br/install.ps1 | grep -i content-type   # text/plain; charset=utf-8
curl -sI https://expeditto.fabitz.com.br/install.sh  | grep -i content-type   # text/plain; charset=utf-8
curl -s  -o /dev/null -w "%{http_code}\n" https://expeditto.fabitz.com.br/nginx.conf   # 404
```

No Windows, `irm https://expeditto.fabitz.com.br/install.ps1` deve devolver o texto do script.

## Regenerar o mascote do site

Os SVGs saem do mesmo desenho do terminal:

```bash
uv run python site/gerar_mascote.py
```

## Origem da instalação

Até o pacote ir para o PyPI (Fase 6), os scripts instalam do `.zip` da branch `main` do GitHub, e por isso o
instalador só enxerga o que estiver na `main`. Depois da publicação, trocar a origem padrão nos dois scripts para
`expeditto`. Não usar o PyPI como primeira tentativa antes disso: se alguém registrar o nome antes, o instalador
baixaria o pacote de outra pessoa.

Fontes: [Build Pack Static](https://coolify.io/docs/applications/build-packs/static),
[Nixpacks e diretórios](https://coolify.io/docs/applications/build-packs/nixpacks).
