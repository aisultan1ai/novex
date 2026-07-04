#!/bin/sh
# Creates a temporary self-signed cert if Let's Encrypt cert doesn't exist yet.
# This lets nginx start before the first certbot run.
DOMAIN="${DOMAIN:-localhost}"
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"

if [ ! -f "${CERT_DIR}/fullchain.pem" ]; then
    echo "[init-cert] No SSL cert found for ${DOMAIN}, creating temporary self-signed cert..."
    mkdir -p "${CERT_DIR}"
    openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
        -keyout "${CERT_DIR}/privkey.pem" \
        -out "${CERT_DIR}/fullchain.pem" \
        -subj "/CN=${DOMAIN}" 2>/dev/null
    echo "[init-cert] Done. Run certbot to get a real certificate."
fi
