# doction

![Python](https://img.shields.io/badge/python-3.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Docker](https://img.shields.io/badge/docker-ready-blue)

Wiki personal markdown-first. Captura rápida, búsqueda FTS, historial git por página.

**Live:** https://doction.danilocloud.me

---

## Levantar el contenedor

### Local

```bash
cp .env.example .env      # editar SECRET_KEY
docker compose up
# abre http://localhost:8000
```

### Producción (Raspberry Pi)

Push a `main` → Gitea Actions (runner self-hosted en la Pi): corre lint + tests
dentro de la imagen (`docker build --target test`), construye `doction:{version}`
y recrea el contenedor en `proxy_net` con health check. Si los tests fallan, el
contenedor actual sigue corriendo.

---

## Configuración (`.env`)

| Variable | Descripción |
|---|---|
| `DATABASE_PATH` | Ruta al SQLite. En Docker: `/data/doction.db` |
| `SECRET_KEY` | Clave para firmar JWT. Cambiar en producción. |

---

## API REST

Autenticación por Bearer token:

```bash
curl -X POST http://localhost:8000/api/token \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpass"}'
# → {"token": "...", "token_type": "bearer"}

export TOKEN=<token>
```

Endpoints:

```
POST /api/token                         obtener token
GET  /api/workspaces                    listar workspaces
POST /api/workspaces                    crear workspace
GET  /api/pages                         listar páginas (árbol)
GET  /api/pages/{slug}                  leer página
POST /api/pages                         crear página
PUT  /api/pages/{slug}                  actualizar página
DELETE /api/pages/{slug}               eliminar página
GET  /api/search?q=...                  buscar (FTS5)
GET  /api/pages/{slug}/history          historial git
GET  /api/pages/{slug}/history/{sha}    versión en un commit
POST /api/mcp                           MCP (JSON-RPC 2.0, streamable HTTP)
GET  /health                            health check
```

---

## MCP

Servidor MCP nativo (sin SDK, sin deps extra): JSON-RPC 2.0 sobre `POST /api/mcp`,
modo stateless, misma auth Bearer que la API REST. Tools: `list_workspaces`,
`list_pages`, `get_page`, `search_pages`, `create_page`, `update_page`,
`get_page_history`.

```bash
claude mcp add --transport http doction https://doction.danilocloud.me/api/mcp \
  --header "Authorization: Bearer $TOKEN"
```

---

## Búsqueda

Full-text search con SQLite FTS5 (BM25), sobre título y contenido. Devuelve snippets con highlights.

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/search?q=kubernetes"
```

---

## Historial git

Cada guardado hace un commit silencioso en `/data/pages/`. El SHA queda en la DB.

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/pages/mi-runbook/history

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/pages/mi-runbook/history/a1b2c3d
```

Los errores de git nunca interrumpen el guardado.

---

## Desarrollo

```bash
make test           # pytest
make lint           # ruff check
make test-image     # build + smoke-test /health, borra imagen si pasa
```
