# doction

[![CI](https://github.com/dny1020/doction/actions/workflows/ci.yaml/badge.svg)](https://github.com/dny1020/doction/actions/workflows/ci.yaml)
![Python](https://img.shields.io/badge/python-3.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)
[![GHCR](https://img.shields.io/badge/ghcr.io-dny1020%2Fdoction-blue?logo=docker)](https://github.com/dny1020/doction/pkgs/container/doction)

Wiki personal markdown-first y knowledge base para agentes. Captura rápida desde
la terminal, búsqueda FTS5, historial git por página, API REST y servidor MCP nativo
— todo en un contenedor con SQLite.

**Live:** https://doction.danilocloud.me

---

## Levantar la app

Sin clonar nada (amd64 + arm64):

```bash
docker run -d --name doction -p 8000:8000 \
  -e SECRET_KEY=$(openssl rand -hex 32) \
  -v doction-data:/data \
  ghcr.io/dny1020/doction:latest
# abre http://localhost:8000 y registra el primer usuario
```

O desde el repo (build local):

```bash
cp .env.example .env   # editar SECRET_KEY
docker compose up
```

| Variable | Descripción |
|---|---|
| `DATABASE_PATH` | Ruta al SQLite. En Docker: `/data/doction.db` |
| `SECRET_KEY` | Clave para firmar JWT. Cambiar en producción. |
| `SECURE_COOKIES` | `1` detrás de TLS (nginx). Apagado por defecto. |

---

## API REST

### Autenticación

```bash
# JWT (7 días)
TOKEN=$(curl -s -X POST https://doction.danilocloud.me/api/token \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpass"}' | jq -r .token)

# PAT de larga vida (el plaintext se muestra UNA sola vez)
curl -s -X POST https://doction.danilocloud.me/api/tokens \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"mi-laptop"}'
# → {"id": 1, "name": "mi-laptop", "token": "doction_..."}

export TOKEN=doction_...
```

### Endpoints

```
POST   /api/token                        JWT (7 días)
POST   /api/tokens                       crear PAT
GET    /api/tokens                       listar PATs
DELETE /api/tokens/{id}                  revocar PAT

GET    /api/workspaces                   listar workspaces
POST   /api/workspaces                   crear workspace
GET    /api/pages                        árbol de páginas
GET    /api/pages/{slug}                 leer página (JSON)
GET    /api/pages/{slug}/raw             markdown crudo
POST   /api/pages                        crear página
PUT    /api/pages/{slug}                 actualizar página
DELETE /api/pages/{slug}                 eliminar página
GET    /api/search?q=...                 búsqueda FTS5
GET    /api/pages/{slug}/history         historial git
GET    /api/pages/{slug}/history/{sha}   contenido en un commit
POST   /api/mcp                          MCP (JSON-RPC 2.0)
GET    /health                           health check
```

Todas las rutas de páginas aceptan `?ws=<slug>` para elegir workspace.

### Ejemplos

```bash
# crear página desde archivo markdown
curl -s -X POST https://doction.danilocloud.me/api/pages \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "$(jq -n --arg t 'K8s Runbook' --rawfile c runbook.md '{title:$t,content:$c}')"

# buscar
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://doction.danilocloud.me/api/search?q=kamailio" | jq

# historial git
curl -s -H "Authorization: Bearer $TOKEN" \
  https://doction.danilocloud.me/api/pages/k8s-runbook/history | jq
```

---

## MCP — conectar agentes

Servidor MCP nativo (JSON-RPC 2.0, stateless, sin SDK). Usa un PAT como Bearer:

```bash
claude mcp add --transport http doction https://doction.danilocloud.me/api/mcp \
  --header "Authorization: Bearer doction_..."
```

| Tool | Qué hace |
|---|---|
| `list_workspaces` | listar workspaces |
| `list_pages` | árbol de páginas |
| `get_page` | leer página (markdown + metadata) |
| `search_pages` | búsqueda FTS5 |
| `create_page` | crear página + commit git |
| `update_page` | actualizar página + commit git |
| `get_page_history` | historial git |

Probar sin auth (devuelve la versión desplegada):

```bash
curl -s -X POST https://doction.danilocloud.me/api/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26"}}' | jq
```

---

## Desarrollo y deploy

```bash
uv sync --dev
uv run uvicorn app.main:app --reload   # dev :8000
make test           # pytest
make lint           # ruff check
make test-image     # build + smoke-test /health
```

**Push a `main`** → GitHub Actions corre lint + tests en imagen (`docker build --target test`)
y publica `ghcr.io/dny1020/doction:{version}+latest` (amd64 + arm64).

La Raspberry Pi se actualiza sola: un systemd timer hace `docker compose pull` cada 5 minutos
y recrea el contenedor solo si el digest cambió. Detalles en [`deploy/`](deploy/README.md).
