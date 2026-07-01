#!/usr/bin/env bash
# doction restore — restaura un snapshot creado por backup.sh.
# Para el contenedor durante la restauración para dejar /data consistente.
#   uso: restore.sh <dir-de-backup>   (p.ej. /mnt/ssd/doction-backups/20260618-033000)
set -euo pipefail

SRC="${1:?uso: restore.sh <dir-de-backup>}"
DATA_DIR="${DOCTION_DATA:-/mnt/ssd/doction}"
DB_PATH="${DATABASE_PATH:-$DATA_DIR/doction.db}"
COMPOSE="${DOCTION_COMPOSE:-/opt/doction/compose.yaml}"

[ -f "$SRC/doction.db" ] || { echo "no se encontró $SRC/doction.db" >&2; exit 1; }

echo "Esto SOBRESCRIBE $DATA_DIR con el backup de $SRC."
read -r -p "¿Continuar? [y/N] " ans
case "$ans" in y|Y) ;; *) echo "cancelado"; exit 1 ;; esac

# Parar la app para una restauración consistente (ignora si no hay compose/contenedor).
docker compose -f "$COMPOSE" stop 2>/dev/null || true

# BD: borrar WAL/SHM viejos y reemplazar el archivo.
rm -f "$DB_PATH" "$DB_PATH-wal" "$DB_PATH-shm"
cp "$SRC/doction.db" "$DB_PATH"

# Páginas + uploads: reemplazar por completo desde el tar.
[ -f "$SRC/pages.tar.gz" ]   && { rm -rf "$DATA_DIR/pages";   tar xzf "$SRC/pages.tar.gz"   -C "$DATA_DIR"; }
[ -f "$SRC/uploads.tar.gz" ] && { rm -rf "$DATA_DIR/uploads"; tar xzf "$SRC/uploads.tar.gz" -C "$DATA_DIR"; }

docker compose -f "$COMPOSE" up -d 2>/dev/null || true
echo "restaurado desde $SRC"
