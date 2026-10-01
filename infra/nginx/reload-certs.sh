#!/bin/sh
# Reloads nginx every 6h so certificates renewed by the certbot container
# are picked up without a manual restart (nginx reads certs only on (re)load).
(
    while :; do
        sleep 21600
        nginx -s reload 2>/dev/null && echo "[reload-certs] nginx reloaded"
    done
) &
