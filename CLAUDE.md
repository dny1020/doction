# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Vision

MiniDocMost is a minimalist, markdown-first DevOps knowledge system — a quiet personal wiki for thinking, documenting, and operating. No Notion-style blocks or dashboard clutter.

**Stack:**
- FastAPI backend with Jinja2 templates
- HTMX for interactivity (vendored at `app/static/vendor/htmx.min.js`)
- SQLite + FTS5 for storage and full-text search (raw `sqlite3`, no ORM)
- `markdown-it-py` for markdown → HTML
- Docker container deployed on a Raspberry Pi, self-hosted on Gitea with a Gitea runner

## CI/CD Pipeline (`.gitea/workflows/ci-cd.yml`)

Triggered on push/PR to `main`. Two jobs:

**`ci` (Lint and test)** — runs in `python:3.13-bookworm`:
- Clones via HTTP using `secrets.GIT_TOKEN` (PAT stored as `GIT_TOKEN` in Gitea)
- Installs dependencies with `uv sync --frozen --dev`
- Lint: `uv run ruff check .`
- Test: `uv run pytest tests/test.py -q` (120 s timeout)

**`package` (Build and smoke test)** — runs only on push to `main`, after `ci`:
- Builds Docker image tagged `api-test:<sha>`
- Starts container on the `proxy_net` Docker network
- Smoke-tests `http://<container>:8000/docs` with a 30-second retry loop

## Development Commands

```bash
uv sync --dev                       # install deps (use --frozen in CI)
uv run ruff check .                 # lint (auto-fix: ruff check --fix .)
uv run pytest tests/test.py -q      # run all tests
uv run pytest tests/test.py -q -k search   # run a single test by name
uv run uvicorn app.main:app --reload       # local dev server on :8000
docker build -t mini-docmost .             # build image
```

After changing dependencies, run `uv lock` and commit `uv.lock` — CI runs `uv sync --frozen` and fails on a stale lock.

## Architecture

Application layout under `app/`:
- `main.py` — FastAPI app, all routes, and the `lifespan` that runs `db.init_db()` + `seed.seed_if_empty()` on startup.
- `db.py` — SQLite layer. `connect()`/`init_db()` create the `pages` table plus a `pages_fts` FTS5 index kept in sync by triggers. `DATABASE_PATH` env var sets the DB location (read at call time, so tests point it at a temp file). Slugs are derived via `slugify()` + `unique_slug()`.
- `markdown.py` — single `render_markdown()` using `markdown-it-py` (CommonMark + tables + strikethrough).
- `seed.py` — seeds a welcome page + example notes only when the DB is empty.
- `templates/` — Jinja2; `base.html` is the sidebar+content shell, `partials/` holds HTMX fragments (`search_results.html`, `sidebar_list.html`).

Key conventions:
- This is a **non-packaged** uv project (`[tool.uv] package = false`). `app` is importable because uvicorn adds the working dir to `sys.path`, and pytest via `pythonpath = ["."]`.
- HTMX flows: sidebar live search → `GET /search`; live edit preview → `POST /preview`. Both return raw HTML fragments, not full pages.
- Server-rendered HTML is marked `| safe` in templates; markdown content is trusted (single-user, no auth).

## Deployment Notes

- The app must expose `GET /docs` on port `8000` for the CI smoke test to pass (FastAPI provides `/docs` automatically). `GET /health` returns `{"status":"ok"}`.
- In Docker, `DATABASE_PATH=/data/minidocmost.db`; `/data` must stay writable so the startup seed succeeds. Mount a volume at `/data` to persist notes across rebuilds.
- The Gitea runner joins the `proxy_net` Docker network; containers started during CI must also use `--network proxy_net` to be reachable by name.
- AdGuard is running on `localhost:3000`; Gitea listens on the same host — keep this in mind when configuring internal service URLs.
