"""Carga un volcado de markdown en una base de datos desechable.

El volcado tiene la forma de `{DATA}/pages/`: un directorio por workspace con un
`<slug>.md` por página. Un `<slug>.title` opcional al lado conserva el título
cuando no se puede derivar del cuerpo.

El corpus real no está en el repositorio —el wiki es privado y el repositorio es
público—, así que la ruta llega por `EVAL_CORPUS`.
"""

import os
from pathlib import Path

from app import auth, db

DEFAULT_CORPUS = "data/eval-corpus"


def corpus_dir() -> Path:
    return Path(os.environ.get("EVAL_CORPUS") or DEFAULT_CORPUS)


def load(workspace: str) -> tuple[int, int]:
    """Crea usuario + workspace y carga las páginas del volcado. Devuelve (id, páginas)."""
    source = corpus_dir() / workspace
    if not source.is_dir():
        raise SystemExit(f"corpus no encontrado: {source} (define EVAL_CORPUS)")

    db.init_db()
    user_id = db.create_user("eval@localhost", auth.hash_password("eval"))
    workspace_id = int(db.ensure_default_workspace(user_id).id or 0)

    files = sorted(source.glob("*.md"))
    for path in files:
        title_file = path.with_suffix(".title")
        title = title_file.read_text().strip() if title_file.exists() else ""
        db.create_page(
            user_id,
            workspace_id,
            title,
            path.read_text(),
            requested_slug=path.stem,
        )
    return workspace_id, len(files)
