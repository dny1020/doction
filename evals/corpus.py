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
    origins: dict[str, str] = {}
    for path in files:
        origins[path.stem] = path.parent.name
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

    _tag_by_origin(workspace_id, origins)
    return workspace_id, len(files)


def _tag_by_origin(workspace_id: int, origins: dict[str, str]) -> None:
    """Etiqueta cada página con el volcado del que salió, para poder medir el filtro.

    El corpus real no trae etiquetas —una sola página tiene una, y es un color
    hexadecimal que el parser confundió con un `#tag`—, así que sin esto el filtro de
    `search_knowledge` no se puede puntuar contra nada.

    Se escriben directamente en `page_tags` y no en el markdown a propósito: tocar el
    cuerpo cambiaría el texto que se embebe, y con ello los vectores y toda la tabla.
    Las corridas anteriores dejarían de ser comparables por añadir una etiqueta. La
    procedencia es un hecho real de cada página; lo sintético es solo dónde se guarda.
    """
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT id, slug FROM pages WHERE workspace_id = %s", (workspace_id,)
        ).fetchall()
        conn.cursor().executemany(
            "INSERT INTO page_tags (page_id, tag) VALUES (%s, %s)",
            [(r["id"], origins[r["slug"]]) for r in rows if r["slug"] in origins],
        )
