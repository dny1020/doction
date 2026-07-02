#!/usr/bin/env bash
# doction backup — snapshot consistente de todo el estado: dump de Postgres + repo git de
# páginas + uploads. Lo ejecuta el systemd timer en la Pi (doction-backup.timer) o a mano
# con `make backup`. No para nada: pg_dump toma un snapshot consistente vía MVCC sin
# bloquear escrituras, igual que antes hacía la API online de SQLite.
set -euo pipefail

DATA_DIR="${DOCTION_DATA:-/mnt/ssd/doction}"
BACKUP_DIR="${DOCTION_BACKUP_DIR:-/mnt/ssd/doction-backups}"
KEEP="${DOCTION_BACKUP_KEEP:-7}"
PG_CONTAINER="${DOCTION_PG_CONTAINER:-doction-postgres}"
PG_USER="${POSTGRES_USER:-doction}"
PG_DB="${POSTGRES_DB:-doction}"

ts="$(date +%Y%m%d-%H%M%S)"
dest="$BACKUP_DIR/$ts"
mkdir -p "$dest"

# Dump en formato custom (comprimido, restaurable con pg_restore). pg_dump corre DENTRO
# del contenedor de Postgres (ya trae el cliente); el resultado sale por stdout al host.
docker exec "$PG_CONTAINER" pg_dump -U "$PG_USER" -d "$PG_DB" -Fc > "$dest/doction.dump"

# Repo git de páginas + uploads (si existen).
[ -d "$DATA_DIR/pages" ]   && tar czf "$dest/pages.tar.gz"   -C "$DATA_DIR" pages
[ -d "$DATA_DIR/uploads" ] && tar czf "$dest/uploads.tar.gz" -C "$DATA_DIR" uploads

echo "doction backup -> $dest"

# Retención: conservar los últimos $KEEP snapshots, borrar el resto.
ls -1dt "$BACKUP_DIR"/*/ 2>/dev/null | tail -n "+$((KEEP + 1))" | xargs -r rm -rf
