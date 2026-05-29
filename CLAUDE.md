# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Vision

doction is a minimalist, markdown-first DevOps knowledge system — a quiet personal wiki for thinking, documenting, and operating. No Notion-style blocks or dashboard clutter.

**Stack:**
- FastAPI backend with Jinja2 templates
- HTMX for interactivity (vendored at `app/static/vendor/htmx.min.js`)
- SQLite + FTS5 for storage and full-text search (raw `sqlite3`, no ORM)
- `markdown-it-py` for markdown → HTML
- Docker container deployed on a Raspberry Pi, self-hosted on Gitea with a Gitea runner

## CI/CD Pipeline (`.gitea/workflows/ci-cd.yml`)

Triggered on push/PR to `main`. Three chained jobs (`ci` → `package` → `deploy`), run by the self-hosted Gitea runner `raspi-runner-1` (ARM64, on `proxy_net`, with the host Docker socket mounted):

**`ci` (Lint and test)** — runs in `python:3.13-bookworm`:
- Clones via HTTP using `secrets.GIT_TOKEN` (a Gitea **Actions secret** — *not* the Applications/PAT list; set it at repo or user level, value = a PAT for `dany` with `read:repository`). Missing/invalid → clone fails with "Authentication failed" and the whole run dies here.
- `uv sync --frozen --dev`, then `uv run ruff check .`, then `uv run pytest tests/test.py -q` (120 s timeout)

**`package` (Build and smoke test)** — only on push to `main`, after `ci`:
- Builds `doction:<sha>`, runs it on `proxy_net`, smoke-tests `http://<container>:8000/docs` (30-retry loop; first few retries fail during app startup — normal)

**`deploy` (Deploy to Raspberry Pi)** — only on push to `main`, after `package`:
- Tags `doction:latest`, replaces the running `doction` container (`docker run` on `proxy_net`, `--restart unless-stopped`, `-v /mnt/ssd/doction:/data`, `DATABASE_PATH=/data/doction.db`), health-checks `http://doction:8000/health`, prunes old images
- **No host port published** — nginx already owns host `:8000`; the app is reached only by container name on `proxy_net`.

## Development Commands

```bash
uv sync --dev                       # install deps (use --frozen in CI)
uv run ruff check .                 # lint (auto-fix: ruff check --fix .)
uv run pytest tests/test.py -q      # run all tests
uv run pytest tests/test.py -q -k search   # run a single test by name
uv run uvicorn app.main:app --reload       # local dev server on :8000
docker build -t doction .                  # build image
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
- Sidebar collapse is **pure client-side** (no server round-trip): `toggleSidebar()` in `base.html` toggles `.sidebar-collapsed` on `<html>` and persists it to `localStorage`; an inline `<head>` script reapplies it before paint to avoid a flash. Because navigation is full page loads, this persistence is what keeps the sidebar state across pages.
- Layout widths are driven by two CSS vars in `style.css`: reading/placeholder views use `--measure` (~70ch for legibility); the editor uses the wider `--editor-measure` so both editor panes have room.
- Server-rendered HTML is marked `| safe` in templates; markdown content is trusted (single-user, no auth).

## Deployment

Deployed by the CI/CD `deploy` job to the Raspberry Pi (`rasp-serv`); everything below is the live, verified setup.

- **Public URL**: `https://doction.danilocloud.me` — served by the **nginx** container (reverse proxy, config at `/opt/nginx/nginx.conf` on the host). The server block proxies to `http://doction:8000` over `proxy_net`, using the wildcard cert `*.danilocloud.me` at `/etc/nginx/certs/danilocloud.me/`. Adding/renaming the subdomain or changing the port/container name requires editing that nginx file and reloading (`docker exec nginx nginx -t && docker exec nginx nginx -s reload`).
- **Container**: `doction` on `proxy_net`, `--restart unless-stopped`. No host port is published — reach it only by container name on `proxy_net` (nginx fronts it). Host `:8000` is already taken by nginx; `:3000` by AdGuard.
- **Persistent data**: bind mount `/mnt/ssd/doction:/data` with `DATABASE_PATH=/data/doction.db` (SSD-backed, survives container rebuilds). `/data` must stay writable so the startup seed succeeds.
- **Health/contract**: app serves `GET /docs` (CI smoke test) and `GET /health` → `{"status":"ok"}` (deploy health check) on port `8000`. Startup takes a few seconds — the retry loops in CI account for this.
- **Manual vs automated**: the nginx route + TLS are a one-time host change (outside this repo); everything about the app container (build, test, redeploy) is automated on each push to `main`. You only push code.
