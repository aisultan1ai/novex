FROM nginx:1.27-alpine

COPY infra/nginx/nginx.conf /etc/nginx/nginx.conf
COPY infra/nginx/routes.conf /etc/nginx/conf.d/default.conf

EXPOSE 80