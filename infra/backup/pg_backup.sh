#!/usr/bin/env bash
# Novex — Postgres backup (audit 2026-10-04, T11).
#
# Dumps the production database from the running `novex-postgres` container
# into $BACKUP_DIR as a compressed custom-format dump and keeps the newest
# $KEEP files. Safe to run while the site is live (pg_dump uses a snapshot).
#
#   Run by hand:  /root/novex/infra/backup/pg_backup.sh
#   Cron (weekly, Sunday 03:00):
#     0 3 * * 0 /root/novex/infra/backup/pg_backup.sh >> /var/log/novex-backup.log 2>&1
#
# Restore: see infra/backup/README.md.
set -euo pipefail

CONTAINER="${CONTAINER:-novex-postgres}"
BACKUP_DIR="${BACKUP_DIR:-/root/novex-backups}"
KEEP="${KEEP:-8}"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

stamp="$(date +%Y-%m-%d_%H%M)"
target="$BACKUP_DIR/novex_${stamp}.dump"
partial="$target.partial"

echo "[$(date -Is)] backup start → $target"

# Credentials come from the container's own environment, so nothing secret
# lives in this script or in cron.
docker exec "$CONTAINER" sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --compress=9 --no-owner' > "$partial"

# A dump that pg_restore cannot list is broken — never keep it as a backup.
if ! docker exec -i "$CONTAINER" pg_restore --list > /dev/null < "$partial"; then
  echo "[$(date -Is)] ERROR: dump failed verification, removing $partial" >&2
  rm -f "$partial"
  exit 1
fi
mv "$partial" "$target"
chmod 600 "$target"

# Rotation: keep the newest $KEEP dumps.
ls -1t "$BACKUP_DIR"/novex_*.dump 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -r rm -f

size="$(du -h "$target" | cut -f1)"
count="$(ls -1 "$BACKUP_DIR"/novex_*.dump | wc -l)"
echo "[$(date -Is)] backup ok: $target ($size), $count copies kept"
