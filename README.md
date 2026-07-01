# doction

[![CI](https://github.com/dny1020/doction/actions/workflows/ci.yaml/badge.svg)](https://github.com/dny1020/doction/actions/workflows/ci.yaml)
![Python](https://img.shields.io/badge/python-3.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)
[![GHCR](https://img.shields.io/badge/ghcr.io-dny1020%2Fdoction-blue?logo=docker)](https://github.com/dny1020/doction/pkgs/container/doction)

A self-hosted, markdown-first wiki and knowledge base built for humans **and** AI agents.
Markdown pages with per-page git history, full-text search (FTS5) plus optional local
semantic search, a REST API, and a **native MCP server** to plug agents in. Everything runs
in a single container backed by SQLite — no external services, no API keys.

> **Why doction?** Unix-style and self-contained. Your notes are plain markdown in a git
> repo; search runs locally; agents talk to it over a standard MCP interface. doction does
> *retrieval* — the language model lives in your agent, not here.

![doction — page view with sidebar, tags and git-tracked markdown](docs/assets/ui.png)
<!-- NOTE: this screenshot predates the React SPA (now served at /app); regenerate against the current UI. -->

---

## Features

- **Markdown-first** — pages, workspaces, `[[wikilinks]]`, `#tags`, and YAML frontmatter.
- **Full-text search** — SQLite FTS5/BM25, zero external dependencies.
- **Local semantic search** (opt-in) — ONNX embeddings (MiniLM) baked into the image:
  `sgrep` (meaning-based search) and `rag` (retrieval with provenance). Fully offline, no
  API keys; gracefully degrades to FTS5 when disabled.
- **Per-page git history** — every save is a commit; browse diffs and previous versions.
- **REST API** + **native MCP server** (JSON-RPC 2.0, 13 tools) for agents.
- **Self-contained** — one container, SQLite, starts with zero configuration.

## How it works

```
            ┌──────────────────────────── doction (single container) ──────────────────────┐
  Browser ──┤  React SPA at /app                                                            │
  curl    ──┤  REST  /api/*          SQLite (pages, FTS5, tags, links, chunks)              │
  Agent   ──┤  MCP   /api/mcp        git repo (one commit per save)                         │
            │                        embeddings worker (async, opt-in) ─┐ MiniLM ONNX       │
            └───────────────────────────────────────────────────────────┴───────────────────┘
```

On every save, doction commits the page to git and extracts its metadata (frontmatter,
tags, wikilinks) into indexed tables. When semantic search is enabled, a background worker
chunks and embeds the page without blocking the app. doction handles **retrieval**; text
generation (summaries, RAG answers) is done by the agent connected over MCP — there is no
LLM inside doction.

---

## Quick start

No clone required (multi-arch image, amd64 + arm64):

```bash
docker run -d --name doction -p 8000:8000 \
  -e SECRET_KEY=$(openssl rand -hex 32) \
  -v doction-data:/data \
  ghcr.io/dny1020/doction:latest
# open http://localhost:8000 and register the first user
```

Or from source (local build):

```bash
cp .env.example .env   # edit SECRET_KEY
docker compose up
```

### Configuration

| Variable | Description | Default |
|---|---|---|
| `SECRET_KEY` | Key used to sign JWTs. **Change in production.** | insecure dev value |
| `DATABASE_PATH` | Path to the SQLite file. | `/data/doction.db` |
| `SECURE_COOKIES` | `1` when behind TLS (reverse proxy). | off |
| `SEMANTIC_SEARCH` | `1` enables local semantic search (`sgrep` / `rag`). | off |
| `LOG_LEVEL` | Root logger level (`DEBUG`/`INFO`/`WARNING`/…). | `INFO` |
| `LOG_DIR` | Directory for the rotated log file (also mirrored to stdout). | `/logs` |

> The embedding model (~22 MB) ships inside the image. It is only loaded into RAM when
> `SEMANTIC_SEARCH=1`; when off, it costs nothing.

---

## REST API

### Authentication

```bash
DOCTION=http://localhost:8000

# JWT (valid 7 days)
TOKEN=$(curl -s -X POST $DOCTION/api/token \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpass"}' | jq -r .token)

# Long-lived PAT (the plaintext is shown ONCE)
curl -s -X POST $DOCTION/api/tokens \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"my-laptop"}'
# → {"id": 1, "name": "my-laptop", "token": "doction_..."}

export TOKEN=doction_...
```

### Endpoints

```
POST   /api/token                        JWT (7 days)
POST   /api/tokens                       create PAT
GET    /api/tokens                       list PATs
DELETE /api/tokens/{id}                  revoke PAT

GET    /api/workspaces                   list workspaces
POST   /api/workspaces                   create workspace
GET    /api/pages                        page tree
GET    /api/pages/{slug}                 read page (JSON)
GET    /api/pages/{slug}/raw             raw markdown
POST   /api/pages                        create page
PUT    /api/pages/{slug}                 update page
DELETE /api/pages/{slug}                 delete page
GET    /api/search?q=...                 full-text search (FTS5)
GET    /api/search?q=...&mode=semantic   semantic search (sgrep)
GET    /api/pages/{slug}/history         git history
GET    /api/pages/{slug}/history/{sha}   content at a commit
POST   /api/mcp                          MCP (JSON-RPC 2.0)
GET    /health                           health check
```

All page routes accept `?ws=<slug>` to select a workspace.

### Examples

```bash
# create a page from a markdown file
curl -s -X POST $DOCTION/api/pages \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "$(jq -n --arg t 'K8s Runbook' --rawfile c runbook.md '{title:$t,content:$c}')"

# search
curl -s -H "Authorization: Bearer $TOKEN" "$DOCTION/api/search?q=kamailio" | jq

# git history
curl -s -H "Authorization: Bearer $TOKEN" \
  "$DOCTION/api/pages/k8s-runbook/history" | jq
```

---

## MCP — connecting agents

Native MCP server (JSON-RPC 2.0, stateless, no SDK). Use a PAT as the Bearer token:

```bash
claude mcp add --transport http doction $DOCTION/api/mcp \
  --header "Authorization: Bearer doction_..."
```

Once connected, the agent sees all 13 tools:

![doction MCP server connected inside an agent — authenticated](docs/assets/mcp.png)

| Tool | What it does |
|---|---|
| `list_workspaces` | list workspaces |
| `list_members` | list members of a workspace |
| `list_pages` | page tree |
| `get_page` | read a page (markdown + metadata) |
| `search_pages` | full-text search (FTS5/BM25) |
| `create_page` | create a page + git commit |
| `update_page` | update a page + git commit |
| `get_page_history` | a page's git history |
| `extract` | structured query by frontmatter `type:` / tags (no LLM) |
| `list_backlinks` | pages linking here via `[[wikilink]]` |
| `related_pages` | neighbor pages by shared tags (knowledge graph) |
| `sgrep` | semantic search blended with keyword boost |
| `rag` | top-k chunks with provenance for the agent to synthesize |

`initialize` and `tools/list` are open; `tools/call` requires a Bearer token. Probe the
deployed version without auth:

```bash
curl -s -X POST $DOCTION/api/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26"}}' | jq
```

---

## Development

```bash
uv sync --dev
uv run uvicorn app.main:app --reload   # dev server on :8000
make test           # pytest
make lint           # ruff check
make test-image     # build + smoke-test /health
```

Stack: FastAPI (REST + native MCP) serving a React SPA (Vite, built into the image at
`/app`), SQLite FTS5 (no ORM), and ONNX embeddings via onnxruntime + tokenizers. See
[CONTRIBUTING.md](CONTRIBUTING.md) to get started.

## Deployment

A new image is published on every push to `main`: GitHub Actions runs lint + tests inside
the image (`docker build --target test`) and pushes `ghcr.io/dny1020/doction:{version}` and
`:latest` (amd64 + arm64).

For production, run the container behind a TLS-terminating reverse proxy:

```bash
docker run -d --name doction --restart unless-stopped -p 127.0.0.1:8000:8000 \
  -e SECRET_KEY=$(openssl rand -hex 32) \
  -e SECURE_COOKIES=1 \
  -e SEMANTIC_SEARCH=1 \
  -v /srv/doction:/data \
  -v /srv/doction-logs:/logs \
  ghcr.io/dny1020/doction:latest
```

Terminate TLS in nginx/Caddy/Traefik pointing at `http://127.0.0.1:8000`. All state lives
in the `/data` volume (SQLite + git repo) — back that up and you're done. Logs (console +
rotated file) live in the separate `/logs` volume; they're diagnostic only, not part of
the backup. An opinionated
pull-based deploy example (`docker compose` + systemd) lives in [`infra/`](infra/).

## License

MIT — see [LICENSE](LICENSE).
