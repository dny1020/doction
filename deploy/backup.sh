#!/usr/bin/env bash
# doction backup — snapshot consistente de /data: BD SQLite + repo git de páginas + uploads.
# Lo ejecuta el systemd timer en la Pi (doction-backup.timer) o a mano con `make backup`.
# No para la app: el backup de SQLite usa la API online (.backup), seguro con WAL.
set -euo pipefail

DATA_DIR="${DOCTION_DATA:-/mnt/ssd/doction}"
BACKUP_DIR="${DOCTION_BACKUP_DIR:-/mnt/ssd/doction-backups}"
KEEP="${DOCTION_BACKUP_KEEP:-7}"
DB_PATH="${DATABASE_PATH:-$DATA_DIR/doction.db}"

ts="$(date +%Y%m%d-%H%M%S)"
dest="$BACKUP_DIR/$ts"
mkdir -p "$dest"

# Backup online de SQLite vía python3 (sin dependencia del CLI sqlite3). WAL-safe.
if [ -f "$DB_PATH" ]; then
  python3 - "$DB_PATH" "$dest/doction.db" <<'PY'
import sqlite3, sys
src, dst = sqlite3.connect(sys.argv[1]), sqlite3.connect(sys.argv[2])
with dst:
    src.backup(dst)
src.close(); dst.close()
PY
fi

# Repo git de páginas + uploads (si existen).
[ -d "$DATA_DIR/pages" ]   && tar czf "$dest/pages.tar.gz"   -C "$DATA_DIR" pages
[ -d "$DATA_DIR/uploads" ] && tar czf "$dest/uploads.tar.gz" -C "$DATA_DIR" uploads

echo "doction backup -> $dest"

# Retención: conservar los últimos $KEEP snapshots, borrar el resto.
ls -1dt "$BACKUP_DIR"/*/ 2>/dev/null | tail -n "+$((KEEP + 1))" | xargs -r rm -rf
