# Site do Expeditto (expeditto.fabitz.com.br): página + scripts de instalação, servidos pelo nginx.
# No Coolify: recurso "Dockerfile" apontando para este repositório, Base Directory `/site`, porta 80.
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html install.ps1 install.sh favicon.svg mascote-*.svg /usr/share/nginx/html/
HEALTHCHECK --interval=30s --timeout=3s CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
