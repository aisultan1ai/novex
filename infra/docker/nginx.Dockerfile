FROM nginx:1.27-alpine

RUN apk add --no-cache openssl

COPY infra/nginx/nginx.conf /etc/nginx/nginx.conf
COPY infra/nginx/init-cert.sh /docker-entrypoint.d/10-init-cert.sh
RUN chmod +x /docker-entrypoint.d/10-init-cert.sh

EXPOSE 80 443