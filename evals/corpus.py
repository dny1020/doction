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


def _sources(workspace: str) -> list[Path]:
    """Los directorios a cargar. `all` los junta todos en un mismo workspace.

    Juntarlos no es cosmético: la recuperación filtra por workspace, así que cargar
    tres workspaces por separado mide lo mismo tres veces. En uno solo, las páginas
    de los otros dos se convierten en distractores y la tarea se parece más a un
    wiki de verdad. Los slugs no chocan entre volcados; si algún día chocan, el
    segundo fallaría al crearse y se vería.
    """
    root = corpus_dir()
    if workspace == "all":
        dirs = sorted(d for d in root.iterdir() if d.is_dir())
        if not dirs:
            raise SystemExit(f"corpus vacío: {root} (define EVAL_CORPUS)")
        return dirs
    source = root / workspace
    if not source.is_dir():
        raise SystemExit(f"corpus no encontrado: {source} (define EVAL_CORPUS)")
    return [source]


def load(workspace: str) -> tuple[int, int]:
    """Crea usuario + workspace y carga las páginas del volcado. Devuelve (id, páginas)."""
    sources = _sources(workspace)

    db.init_db()
    user_id = db.create_user("eval@localhost", auth.hash_password("eval"))
    workspace_id = int(db.ensure_default_workspace(user_id).id or 0)

    files = sorted(path for source in sources for path in source.glob("*.md"))
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
