# doction

![Python](https://img.shields.io/badge/python-3.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Docker](https://img.shields.io/badge/docker-ready-blue)

Wiki personal **markdown-first** y knowledge base para agentes. Pensada para devs
backend y DevOps: captura rápida desde la terminal, búsqueda full-text, historial
git por página, API REST y servidor MCP nativo — todo en un contenedor con SQLite.

**Live:** https://doction.danilocloud.me

---

## Cómo funciona

- **Workspaces → páginas → subpáginas.** Cada usuario tiene su workspace `personal`
  por defecto; puedes crear más (trabajo, homelab, etc.).
- **Todo es markdown.** Editor con preview en vivo (HTMX), render con markdown-it.
- **Cada guardado es un commit git** silencioso en `/data/pages/{workspace}/{slug}.md`.
  Si git falla, el guardado nunca se pierde. El historial se consulta por API o MCP.
- **Búsqueda FTS5 (BM25)** sobre título y contenido, con snippets resaltados.
- **Tres formas de usarla:** la web (sidebar + búsqueda), la API REST (curl/scripts)
  y MCP (Claude Code, Cursor o cualquier agente).

## Levantar la app

```bash
cp .env.example .env      # editar SECRET_KEY
docker compose up
# abre http://localhost:8000 y registra el primer usuario
```

El primer registro crea el workspace `personal` con páginas semilla de ejemplo.

| Variable | Descripción |
|---|---|
| `DATABASE_PATH` | Ruta al SQLite. En Docker: `/data/doction.db` |
| `SECRET_KEY` | Clave para firmar JWT. Cambiar en producción. |
| `SECURE_COOKIES` | `1` detrás de TLS (nginx). Apagado por defecto para dev http. |

---

## API REST

### Autenticación

Dos tipos de credencial, ambas como `Authorization: Bearer ...`:

| Credencial | Cómo se obtiene | Duración | Uso |
|---|---|---|---|
| JWT | `POST /api/token` (email + password) | 7 días | sesiones interactivas |
| PAT `doction_...` | `POST /api/tokens` | no expira, revocable | scripts y agentes |

```bash
# 1. JWT con tus credenciales
TOKEN=$(curl -s -X POST https://doction.danilocloud.me/api/token \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpass"}' | jq -r .token)

# 2. PAT de larga vida (el plaintext se muestra UNA sola vez — guárdalo)
curl -s -X POST https://doction.danilocloud.me/api/tokens \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"mi-laptop"}'
# → {"id": 1, "name": "mi-laptop", "token": "doction_..."}

export TOKEN=doction_...
```

### Endpoints

```
POST /api/token                         JWT (7 días)
POST /api/tokens                        crear PAT (plaintext una sola vez)
GET  /api/tokens                        listar PATs (id, name, last_used_at)
DELETE /api/tokens/{id}                 revocar PAT

GET  /api/workspaces                    listar workspaces
POST /api/workspaces                    crear workspace
GET  /api/pages                         listar páginas (árbol con depth)
GET  /api/pages/{slug}                  leer página (JSON)
GET  /api/pages/{slug}/raw              markdown crudo a stdout
POST /api/pages                         crear página
PUT  /api/pages/{slug}                  actualizar página
DELETE /api/pages/{slug}               eliminar página
GET  /api/search?q=...                  búsqueda FTS5
GET  /api/pages/{slug}/history          historial git
GET  /api/pages/{slug}/history/{sha}    contenido en un commit
POST /api/mcp                           MCP (JSON-RPC 2.0)
GET  /health                            health check
```

Todas las rutas de páginas aceptan `?ws=<slug>` para elegir workspace
(por defecto, el primero del usuario).

### Ejemplos

```bash
# crear página desde un archivo markdown
curl -s -X POST https://doction.danilocloud.me/api/pages \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "$(jq -n --arg t 'K8s Runbook' --rawfile c runbook.md '{title:$t,content:$c}')"

# buscar
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://doction.danilocloud.me/api/search?q=kamailio+dispatcher" | jq

# historial git de una página y su contenido en un commit
curl -s -H "Authorization: Bearer $TOKEN" \
  https://doction.danilocloud.me/api/pages/k8s-runbook/history | jq
curl -s -H "Authorization: Bearer $TOKEN" \
  https://doction.danilocloud.me/api/pages/k8s-runbook/history/a1b2c3d | jq -r .content
```

---

## MCP — conectar agentes

Servidor MCP **nativo** (JSON-RPC 2.0 sobre `POST /api/mcp`, streamable HTTP
stateless, sin SDK ni dependencias extra). La misma auth Bearer de la API;
usa un PAT para no renovar credenciales:

```bash
claude mcp add --transport http doction https://doction.danilocloud.me/api/mcp \
  --header "Authorization: Bearer doction_..."
```

Tools disponibles:

| Tool | Qué hace |
|---|---|
| `list_workspaces` | listar workspaces |
| `list_pages` | árbol de páginas de un workspace |
| `get_page` | leer página (markdown + metadata) |
| `search_pages` | búsqueda FTS5 |
| `create_page` | crear página (hace commit git) |
| `update_page` | actualizar página (hace commit git) |
| `get_page_history` | historial git de una página |

Con esto cualquier agente puede consultar tus runbooks en contexto desde
cualquier repo, o capturar decisiones y notas mientras trabajas.

Probar a mano (el `initialize` no requiere auth y devuelve la versión desplegada):

```bash
curl -s -X POST https://doction.danilocloud.me/api/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26"}}' | jq
```

---

## Desarrollo y deploy

```bash
uv sync --dev
uv run uvicorn app.main:app --reload   # dev server :8000
make test           # pytest
make lint           # ruff check
make test-image     # build + smoke-test /health, borra imagen si pasa
```

**Deploy = push a `main`.** Gitea Actions (runner self-hosted en la Pi) corre
lint + tests dentro de la imagen (`docker build --target test`), construye
`doction:{version}`, recrea el contenedor con health check y limpia imágenes
viejas. Si los tests fallan, el contenedor actual sigue corriendo.
