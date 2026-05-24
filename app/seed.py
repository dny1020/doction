"""Seed initial content so a fresh instance is never empty."""

from __future__ import annotations

from app import db

WELCOME = """\
# Welcome to MiniDocMost

A quiet, markdown-first place to think, document, and operate.

- **Capture** notes fast — title, write markdown, save.
- **Search** everything from the sidebar (full-text, instant).
- **Read** in a calm, focused pane.

Use the **+ New** button to create your first page, or edit this one to make it yours.
"""

RUNBOOK = """\
# Runbook: Deploy to Raspberry Pi

A short example of the kind of operational note this wiki is built for.

## Steps

1. Push to `main` — the Gitea runner builds the image.
2. The `package` job runs a smoke test against `/docs`.
3. On success, pull and restart the container on the Pi.

```bash
docker pull api-test:latest
docker rm -f minidocmost || true
docker run -d --name minidocmost -p 8000:8000 \\
  -v /srv/minidocmost:/data api-test:latest
```

> Tip: keep the SQLite database on a mounted volume (`/data`) so notes
> survive container rebuilds.
"""

MARKDOWN_NOTES = """\
# Markdown Cheatsheet

| Element | Syntax |
| --- | --- |
| Heading | `# H1` … `###### H6` |
| Bold | `**text**` |
| Italic | `*text*` |
| Code | `` `inline` `` or fenced ``` blocks |
| Link | `[label](https://example.com)` |
| List | `- item` |

~~Strikethrough~~ and tables are supported out of the box.
"""

_SEED_PAGES = [
    ("Welcome to MiniDocMost", WELCOME),
    ("Runbook: Deploy to Raspberry Pi", RUNBOOK),
    ("Markdown Cheatsheet", MARKDOWN_NOTES),
]


def seed_if_empty() -> None:
    if db.count_pages() > 0:
        return
    for title, content in _SEED_PAGES:
        db.create_page(title, content)
