"""Loads a markdown dump into a throwaway database.

The dump has the shape of `{DATA}/pages/`: one directory per workspace, one `<slug>.md`
per page, with an optional `<slug>.title` beside it when the title cannot be derived.

The real corpus is not in the repository — the wiki is private and the repository is
public — so its path arrives through `EVAL_CORPUS`.
"""

import os
from pathlib import Path

from app import auth, db

DEFAULT_CORPUS = "data/eval-corpus"


def corpus_dir() -> Path:
    return Path(os.environ.get("EVAL_CORPUS") or DEFAULT_CORPUS)


def _sources(workspace: str) -> list[Path]:
    """The directories to load. `all` merges them into one workspace.

    Merging is not cosmetic: retrieval filters by workspace, so loading three separately
    measures the same thing three times. In one, the other two's pages become distractors
    and the task looks more like a real wiki.
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

    The real corpus carries no usable tags. These are written straight into `page_tags`
    and not into the markdown on purpose: touching the body would change the embedded
    text, and with it the vectors and every earlier run's comparability.
    """
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT id, slug FROM pages WHERE workspace_id = %s", (workspace_id,)
        ).fetchall()
        conn.cursor().executemany(
            "INSERT INTO page_tags (page_id, tag) VALUES (%s, %s)",
            [(r["id"], origins[r["slug"]]) for r in rows if r["slug"] in origins],
        )
