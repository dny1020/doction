"""Loads a markdown dump (`{DATA}/pages/` layout) into a throwaway database.

The corpus is private and not in the repository; its path comes from `EVAL_CORPUS`.
"""

import os
from pathlib import Path

from app import auth, db

DEFAULT_CORPUS = "data/eval-corpus"


def corpus_dir() -> Path:
    return Path(os.environ.get("EVAL_CORPUS") or DEFAULT_CORPUS)


def _sources(workspace: str) -> list[Path]:
    """The directories to load. `all` merges them into one workspace, so each dump's pages
    act as distractors for the others.
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
    """Create a user and workspace, load the dump's pages, and return (id, page count)."""
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
    """Tag each page with the dump it came from, so the tag filter can be scored.

    Written to `page_tags`, not the markdown: changing the body would change the vectors.
    """
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT id, slug FROM pages WHERE workspace_id = %s", (workspace_id,)
        ).fetchall()
        conn.cursor().executemany(
            "INSERT INTO page_tags (page_id, tag) VALUES (%s, %s)",
            [(r["id"], origins[r["slug"]]) for r in rows if r["slug"] in origins],
        )
