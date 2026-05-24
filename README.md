# MiniDocMost

A minimalist, markdown-first DevOps knowledge wiki — a quiet personal space to think, document, and operate. Calm, low-chrome UI inspired by Claude.ai: no blocks, no dashboard noise, just fast capture, search, and reading.

**Live instance:** https://doction.danilocloud.me

## Features

- Markdown pages with server-side rendering (CommonMark + tables + strikethrough)
- Live split editor — markdown source on the left, instant preview on the right
- Full-text search (SQLite FTS5) with highlighted snippets, as you type
- Collapsible sidebar (collapsed/expanded state is remembered across pages)
- Single-user, no auth, self-hosted — designed to run quietly on a Raspberry Pi

## Stack

- **FastAPI** + Jinja2 templates
- **HTMX** for interactivity (vendored — no frontend build step)
- **SQLite + FTS5** for storage and search (raw `sqlite3`, no ORM)
- **markdown-it-py** for rendering
- Shipped as a **Docker** image, deployed via **Gitea Actions** to a Raspberry Pi

## Quick start (local)

Requires [uv](https://docs.astral.sh/uv/) and Python 3.13.

```bash
uv sync --dev
uv run uvicorn app.main:app --reload
# open http://localhost:8000
```

Seed content (a welcome page and a couple of examples) is created automatically on first run.

## Lint & tests

```bash
uv run ruff check .              # lint (auto-fix: ruff check --fix .)
uv run pytest tests/test.py -q   # run the test suite
```

## Docker

```bash
docker build -t doction .
docker run -p 8000:8000 -v "$PWD/data:/data" -e DATABASE_PATH=/data/doction.db doction
# open http://localhost:8000
```

## Configuration

| Env var         | Default          | Purpose                                                        |
| --------------- | ---------------- | -------------------------------------------------------------- |
| `DATABASE_PATH` | `minidocmost.db` | SQLite file location. In Docker, point it at a mounted volume. |

## Routes

| Route                  | Purpose                          |
| ---------------------- | -------------------------------- |
| `GET /`                | Home (most recent page)          |
| `GET /pages/{slug}`    | Read a page                      |
| `GET /new`             | New-page form                    |
| `POST /pages`          | Create a page                    |
| `GET /pages/{slug}/edit` / `POST /pages/{slug}` | Edit / update   |
| `POST /pages/{slug}/delete` | Delete a page               |
| `GET /search?q=`       | Full-text search (HTMX fragment) |
| `POST /preview`        | Live markdown preview (HTMX)     |
| `GET /health`          | Liveness check                   |
| `GET /docs`            | OpenAPI docs                     |

## Deployment

On every push to `main`, the Gitea Actions pipeline (`.gitea/workflows/ci-cd.yml`) runs three jobs:

1. **ci** — lint + tests
2. **package** — build the Docker image and smoke-test it
3. **deploy** — redeploy the `doction` container on the Pi (on `proxy_net`, persistent data at `/mnt/ssd/doction`), fronted by nginx at `doction.danilocloud.me`

The pipeline needs a `GIT_TOKEN` Actions secret (a Gitea PAT for cloning). See [CLAUDE.md](CLAUDE.md) for the full pipeline and homelab infrastructure details.
