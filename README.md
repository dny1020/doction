# doction

![Python](https://img.shields.io/badge/python-3.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Version](https://img.shields.io/badge/version-0.2-orange)
![Docker](https://img.shields.io/badge/docker-ready-blue)
![uv](https://img.shields.io/badge/uv-managed-blueviolet)

A minimalist, markdown-first DevOps knowledge wiki — a quiet personal space to think, document, and operate. Calm, low-chrome UI: no blocks, no dashboard noise, just fast capture, search, and reading.

**Live instance:** https://doction.danilocloud.me

## Features

- Markdown pages with server-side rendering (CommonMark + tables + strikethrough)
- Live split editor — markdown source on the left, instant preview on the right
- Full-text search (SQLite FTS5) with highlighted snippets, as you type
- **Semantic search** — local embeddings (`all-MiniLM-L6-v2`), no external API
- **Hybrid search** — combines BM25 + cosine similarity for best results
- **Git versioning** — every page save is a silent git commit; full history browsable via API
- **MCP server** — expose your wiki to AI agents (Claude Code, Cursor, Codex) over stdio
- Collapsible sidebar with persistent state
- REST JSON API with Bearer auth
- Single-user auth, self-hosted — designed to run quietly on a Raspberry Pi

## Stack

- **FastAPI** + Jinja2 templates
- **HTMX** for interactivity (vendored — no frontend build step)
- **SQLite + FTS5** for storage and full-text search (raw `sqlite3`, no ORM)
- **markdown-it-py** for rendering
- **sentence-transformers** (`all-MiniLM-L6-v2`) for local semantic embeddings
- **MCP** (Model Context Protocol) for AI agent integration
- Shipped as a **Docker** image, deployed via **Gitea Actions** to a Raspberry Pi

## Quick start (local)

Requires [uv](https://docs.astral.sh/uv/) and Python 3.13.

```bash
uv sync --dev
uv run uvicorn app.main:app --reload
# open http://localhost:8000
```

Seed content (welcome page + examples) is created when the first user registers. The embedding model (~80MB) downloads on first startup and is cached locally.

## Docker

```bash
docker build -t doction .
docker run -p 8000:8000 -v "$PWD/data:/data" -e DATABASE_PATH=/data/doction.db doction
```

## Configuration

| Env var                      | Default          | Purpose                                                                      |
| ---------------------------- | ---------------- | ---------------------------------------------------------------------------- |
| `DATABASE_PATH`              | `doction.db`     | SQLite file location. In Docker, point it at a mounted volume.               |
| `SECRET_KEY`                 | `dev-secret-key` | JWT signing key. Set a strong random value in production.                    |
| `SENTENCE_TRANSFORMERS_HOME` | system default   | Model cache dir. Set to `/data/models` in Docker to persist across rebuilds. |
| `HF_HUB_OFFLINE`             | unset            | Set to `1` to skip embedding model loading entirely (used in CI).            |

## Shell CLI (`doction.sh`)

A `curl`+`jq` wrapper for the REST API. Requires `curl` and `jq`.

```bash
# One-time setup
export DOCTION_URL=https://doction.danilocloud.me
eval $(./doction.sh login you@example.com yourpassword)
export DOCTION_WS=personal   # optional, default: personal

# List pages as an indented tree
./doction.sh pages

# Create a page from a file
./doction.sh create "Kubernetes Runbook" runbook.md

# Create a subpage
./doction.sh create "BGP Tuning" --parent network-runbook bgp.md

# Update content and rename at once
./doction.sh update my-page --title "New Title" updated.md

# Semantic search
./doction.sh search "deploy rollback strategy" --mode hybrid

# Show git history for a page
./doction.sh history k8s-runbook

# Read a page as it was at a specific commit
./doction.sh at k8s-runbook a1b2c3d

# All commands
./doction.sh help
```

## Search modes

The API supports three search modes via the `mode` query parameter:

```bash
# Full-text search (default)
curl -H "Authorization: Bearer $TOKEN" \
  "https://doction.danilocloud.me/api/search?q=kubernetes&mode=fts"

# Semantic search (cosine similarity on local embeddings)
curl -H "Authorization: Bearer $TOKEN" \
  "https://doction.danilocloud.me/api/search?q=deploy+rollback+strategy&mode=semantic"

# Hybrid — BM25 + cosine, best for most queries
curl -H "Authorization: Bearer $TOKEN" \
  "https://doction.danilocloud.me/api/search?q=incident+runbook&mode=hybrid"
```

If the embedding model isn't loaded yet, `semantic` and `hybrid` fall back silently to FTS.

## Git versioning

Every page save commits the markdown file to a git repo at `/data/pages/`. The history is accessible via the REST API:

```bash
# List commits for a page
curl -H "Authorization: Bearer $TOKEN" \
  "https://doction.danilocloud.me/api/pages/my-runbook/history"

# Get page content at a specific commit
curl -H "Authorization: Bearer $TOKEN" \
  "https://doction.danilocloud.me/api/pages/my-runbook/history/a1b2c3d"
```

Git failures are silent — page saves always succeed even if the commit fails.

## MCP server (AI agent integration)

doction exposes itself as an MCP (Model Context Protocol) server, letting AI agents read and write your wiki directly.

**6 tools:** `list_workspaces`, `list_pages`, `get_page`, `search_pages`, `create_page`, `update_page`

### Homelab setup (agent on PC, doction on Pi, same local network)

**1. Create `/home/danilo/mcp.sh` on the Pi:**
```bash
#!/bin/bash
exec docker exec -i \
  -e DOCTION_EMAIL="you@example.com" \
  -e DOCTION_PASSWORD="yourpass" \
  doction /app/.venv/bin/python -m app.mcp_server
```
```bash
chmod +x /home/danilo/mcp.sh
```

**2. Add to `~/.claude/settings.json` on your machine:**
```json
{
  "mcpServers": {
    "doction": {
      "command": "ssh",
      "args": ["rpi", "/home/danilo/mcp.sh"]
    }
  }
}
```

Claude Code spawns `ssh rpi /home/danilo/mcp.sh` and pipes MCP stdio through the SSH tunnel. No port exposure needed — the Pi stays on the local network only.

**Test the connection:**
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}' \
  | ssh rpi /home/danilo/mcp.sh
```

You should get a JSON response with `serverInfo.name = "doction"` and a list of capabilities.

## Development

```bash
make test           # fast test suite (pytest, no model loading)
make lint           # ruff check
make test-image     # build Docker image, smoke-test /health, delete on pass / keep on fail
```

## Deployment

On every push to `main`, the Gitea Actions pipeline (`.gitea/workflows/ci-cd.yml`) runs three jobs:

1. **ci** — lint (`ruff`) + tests (`pytest`, fast suite only)
2. **package** — build the Docker image and smoke-test it (`GET /docs`)
3. **deploy** — redeploy the `doction` container on the Pi (on `proxy_net`, persistent data at `/mnt/ssd/doction`), fronted by nginx at `doction.danilocloud.me`

The pipeline needs a `GIT_TOKEN` Actions secret (a Gitea PAT for cloning). See `.gitea/workflows/ci-cd.yml` for pipeline details.

**Persistent volumes on the Pi (`/mnt/ssd/doction/`):**
- `doction.db` — SQLite database
- `pages/` — git repo with all page history
- `models/` — cached embedding model (downloads once on first boot, ~80MB)
