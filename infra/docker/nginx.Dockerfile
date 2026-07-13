FROM nginx:1.27-alpine

RUN apk add --no-cache openssl

COPY infra/nginx/nginx.conf /etc/nginx/nginx.conf
# The base image ships a default.conf serving /usr/share/nginx/html — remove
# it so our routes.conf (proxy to frontend/backend) is the only server block.
RUN rm -f /etc/nginx/conf.d/default.conf
COPY infra/nginx/routes.conf /etc/nginx/conf.d/routes.conf
COPY infra/nginx/init-cert.sh /docker-entrypoint.d/10-init-cert.sh
RUN chmod +x /docker-entrypoint.d/10-init-cert.sh

EXPOSE 80 443