#!/usr/bin/env python3
"""Migración única: copia los datos de la BD SQLite (era pre-v0.15) a Postgres.

Se corre una sola vez, antes de cortar el tráfico al stack nuevo. Lee la BD SQLite
por ruta, conecta al Postgres apuntado por DATABASE_URL (el mismo env var que usa
la app), crea el esquema si falta, y copia las 9 tablas en orden de dependencia
preservando los `id` originales (así las FK quedan intactas sin tener que
remapear nada). Al final resetea las secuencias SERIAL para que los próximos
INSERT de la app no choquen con los ids migrados.

No toca el repo git de páginas ni los uploads — eso ya vive en el filesystem
(DATA_DIR) y no se mueve.

    DATABASE_URL=postgresql://doction:doction@localhost:5432/doction \\
        uv run python -m scripts.migrate_sqlite_to_postgres /mnt/ssd/doction/doction.db
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from app import db

# Orden de copia: cada tabla después de sus dependencias (FK). `pages.search_vector`
# es una columna generada — nunca se copia ni se incluye en el INSERT, Postgres la
# calcula sola a partir de title/content.
TABLES: list[tuple[str, list[str]]] = [
    ("users", ["id", "email", "password_hash", "created_at", "display_name", "avatar_color"]),
    ("workspaces", ["id", "user_id", "slug", "name", "created_at"]),
    ("workspace_members", ["workspace_id", "user_id", "role", "created_at"]),
    ("pages", [
        "id", "user_id", "workspace_id", "parent_id", "slug", "title", "content",
        "created_at", "updated_at", "git_commit", "embed_dirty", "updated_by", "deleted_at",
    ]),
    ("api_tokens", ["id", "user_id", "name", "token_hash", "created_at", "last_used_at"]),
    ("page_meta", ["page_id", "type", "frontmatter_json"]),
    ("page_tags", ["page_id", "tag"]),
    ("page_links", ["src_page_id", "dst_slug", "workspace_id"]),
    ("page_chunks", [
        "id", "page_id", "workspace_id", "ord", "text", "vector", "model", "created_at",
    ]),
]

# Tablas con PK propia (BIGSERIAL) cuya secuencia hay que resincronizar tras
# insertar ids explícitos. workspace_members/page_meta/page_links/page_tags*
# (*antes de v0.15 sin id propio) no tienen PK autoincremental que resetear.
SERIAL_TABLES = ["users", "workspaces", "api_tokens", "pages", "page_chunks"]


def _read_sqlite(sqlite_path: Path, table: str, columns: list[str]) -> list[tuple]:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        cols = ", ".join(columns)
        rows = conn.execute(f"SELECT {cols} FROM {table}")
        return [tuple(row[c] for c in columns) for row in rows]
    finally:
        conn.close()


def migrate(sqlite_path: Path) -> None:
    if not sqlite_path.exists():
        print(f"error: no existe {sqlite_path}", file=sys.stderr)
        raise SystemExit(2)

    db.init_db()
    with db.connect() as conn:
        if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None:
            print(
                "error: el Postgres destino ya tiene usuarios — esto es una migración "
                "de una sola vez, no corre dos veces sobre una base con datos. "
                "Si de verdad quieres reemplazar los datos, vacía las tablas primero.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        total = 0
        for table, columns in TABLES:
            rows = _read_sqlite(sqlite_path, table, columns)
            if not rows:
                continue
            placeholders = ", ".join(["%s"] * len(columns))
            col_list = ", ".join(columns)
            conn.cursor().executemany(
                f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})", rows
            )
            print(f"  {table}: {len(rows)} filas")
            total += len(rows)

        for table in SERIAL_TABLES:
            conn.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)"
            )

    print(f"ok: {total} filas migradas de {sqlite_path} a {db.masked_database_url()}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("sqlite_path", type=Path, help="ruta al doction.db (SQLite) a migrar")
    args = parser.parse_args()
    migrate(args.sqlite_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
