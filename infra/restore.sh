#!/usr/bin/env bash
# doction restore — restaura un snapshot creado por backup.sh.
# Para la app durante la restauración (Postgres sigue arriba, pg_restore lo necesita).
#   uso: restore.sh <dir-de-backup>   (p.ej. /mnt/ssd/doction-backups/20260618-033000)
set -euo pipefail

SRC="${1:?uso: restore.sh <dir-de-backup>}"
DATA_DIR="${DOCTION_DATA:-/mnt/ssd/doction}"
COMPOSE="${DOCTION_COMPOSE:-/opt/doction/compose.yaml}"
PG_CONTAINER="${DOCTION_PG_CONTAINER:-doction-postgres}"
PG_USER="${POSTGRES_USER:-doction}"
PG_DB="${POSTGRES_DB:-doction}"

[ -f "$SRC/doction.dump" ] || { echo "no se encontró $SRC/doction.dump" >&2; exit 1; }

echo "Esto SOBRESCRIBE la base de datos y $DATA_DIR con el backup de $SRC."
read -r -p "¿Continuar? [y/N] " ans
case "$ans" in y|Y) ;; *) echo "cancelado"; exit 1 ;; esac

# Para la app para que nadie escriba mientras se restaura (Postgres sigue arriba).
docker compose -f "$COMPOSE" stop doction 2>/dev/null || true

# BD: --clean --if-exists deja caer y recrear cada objeto, restauración idempotente
# aunque la base ya tenga tablas.
docker exec -i "$PG_CONTAINER" pg_restore -U "$PG_USER" -d "$PG_DB" \
  --clean --if-exists < "$SRC/doction.dump"

# Páginas + uploads: reemplazar por completo desde el tar.
[ -f "$SRC/pages.tar.gz" ]   && { rm -rf "$DATA_DIR/pages";   tar xzf "$SRC/pages.tar.gz"   -C "$DATA_DIR"; }
[ -f "$SRC/uploads.tar.gz" ] && { rm -rf "$DATA_DIR/uploads"; tar xzf "$SRC/uploads.tar.gz" -C "$DATA_DIR"; }

docker compose -f "$COMPOSE" up -d 2>/dev/null || true
echo "restaurado desde $SRC"
