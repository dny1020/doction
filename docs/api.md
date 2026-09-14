# REST API

doction's server is JSON only. It stores raw markdown, renders nothing, and every surface below
returns JSON unless the table says otherwise.

This page lists every operation the application serves. It is not maintained by hand: a test
compares the list below against the schema the running application produces, and fails if an
endpoint is added without an entry or an entry survives an endpoint's removal. If you are reading
a copy of this page that came with a release, it was complete for that release.

## Authentication

Three ways in, for three different callers:

| Credential | How to get it | Lifetime |
| --- | --- | --- |
| Session cookie | `POST /api/auth/login` | 7 days, `httponly` |
| JWT | `POST /api/token` | 7 days |
| Personal access token | `POST /api/tokens` | until revoked |

```bash
# long-lived token for an agent or a script; the plaintext is shown ONCE
curl -s -X POST $DOCTION/api/tokens -b cookies.txt \
  -H 'content-type: application/json' -d '{"name": "my-laptop"}'
# → {"id": 1, "name": "my-laptop", "token": "doction_..."}

curl -s $DOCTION/api/pages -H "authorization: Bearer $TOKEN"
```

A token beginning `doction_` is looked up as a personal access token; anything else is tried as a
JWT. Send it in `authorization: Bearer`.

Four operations need no credential: `GET /health`, `GET /api/i18n`, `POST /api/auth/login` and
`POST /api/auth/register`. Registration is **open by default**, so an instance on a reachable
address lets anyone create an account until you set `DISABLE_REGISTRATION=1`.

## Workspaces

Every page belongs to a workspace, and page operations act on the workspace in the request
context rather than one named in the path. Add `?ws=<slug>` to any page operation to pick one
explicitly, or switch the session's default with `POST /api/workspaces/{slug}/switch`.

Workspaces are shared by membership, with roles `owner` and `member`. Members are added by an
existing account's email, because the server sends no mail.

## The interactive documentation

The application also serves its own schema and two browsers for it:

| Path | What it is |
| --- | --- |
| `/openapi.json` | the OpenAPI document, generated from the running routes |
| `/docs` | Swagger UI |
| `/redoc` | ReDoc |

**All three are public and need no authentication.** Verified against a live instance: each
answers 200 with no credential. They describe the shape of the surface, which is public knowledge
for an open-source application, but they do enumerate it. If that is not what you want on a
reachable instance, block the three paths at your reverse proxy.

Both browsers fetch their JavaScript and CSS from a public CDN. On an instance with no outbound
network access they load a blank page, while `/openapi.json` keeps working, because the document
itself is served locally.

The document declares the same version `/health` reports, so you can tell which build you are
reading.

Response bodies are not described in the schema: the handlers return JSON directly rather than
through declared models, so `/docs` shows request shapes and status codes but not response
shapes. Adding those is [roadmap](../ROADMAP.md) work, tracked rather than forgotten.

## Every endpoint

```
# auth
POST   /api/auth/login
POST   /api/auth/logout
POST   /api/auth/register
POST   /api/token
GET    /api/tokens
POST   /api/tokens
DELETE /api/tokens/{token_id}

# account
POST   /api/lang/{code}
GET    /api/me
POST   /api/settings/password
POST   /api/settings/profile

# workspaces
GET    /api/workspaces
POST   /api/workspaces
DELETE /api/workspaces/{slug}
PUT    /api/workspaces/{slug}
GET    /api/workspaces/{slug}/export
GET    /api/workspaces/{slug}/members
POST   /api/workspaces/{slug}/members
DELETE /api/workspaces/{slug}/members/{member_id}
POST   /api/workspaces/{slug}/switch

# pages
GET    /api/notes
GET    /api/pages
POST   /api/pages
DELETE /api/pages/{slug}
GET    /api/pages/{slug}
PUT    /api/pages/{slug}
GET    /api/pages/{slug}/children
GET    /api/pages/{slug}/history
GET    /api/pages/{slug}/history/{sha}
GET    /api/pages/{slug}/history/{sha}/diff
POST   /api/pages/{slug}/move
GET    /api/pages/{slug}/raw
POST   /api/pages/{slug}/rename
POST   /api/pages/{slug}/restore/{sha}
GET    /api/pages/{slug}/view
GET    /api/trash
POST   /api/trash/{slug}/purge
POST   /api/trash/{slug}/restore

# search
GET    /api/search

# intelligence
GET    /api/graph
GET    /api/insights
GET    /api/pages/{slug}/suggest-links
GET    /api/pages/{slug}/suggest-tags
GET    /api/pages/{slug}/summary

# webhooks
GET    /api/webhooks
POST   /api/webhooks
DELETE /api/webhooks/{webhook_id}
GET    /api/webhooks/{webhook_id}/deliveries

# uploads
POST   /api/uploads
GET    /uploads/{name}

# mcp
POST   /api/mcp

# system
GET    /api/i18n
GET    /api/system
GET    /health

# app
GET    /
GET    /app
GET    /app/{full_path}
GET    /login
GET    /register
```

## What each group is for

**auth** and **account** cover getting in and the signed-in user's own settings. A personal
access token is shown once at creation and stored only as a hash, so a lost token is revoked and
replaced rather than recovered.

**workspaces** covers creating, sharing and exporting. `export` returns a zip of markdown files,
one per page, which is the supported way to take your content elsewhere.

**pages** is the bulk of the surface: the tree, one page's content, the move and rename
operations, git history, and the trash. [Writing pages](writing-pages.md) walks through it in
the order you would actually use it.

**search** is one operation with three modes. What a query does to what you typed is worth
reading before you rely on it: see [searching](search.md).

**intelligence** is the local machine learning: link and tag suggestions, an extractive summary,
the workspace insights and the wikilink graph. Every response carries a `mode` field saying how
it was produced, because a result from term statistics and one from an embedding model are
different claims. None of it calls out to a third party, and the embedding-backed parts degrade
to simpler methods when `SEMANTIC_SEARCH` is off.

**webhooks** delivers page events to a URL you control, signed with HMAC-SHA256. The delivery
list is read-only, so inspecting it never triggers a retry.

**uploads** takes an image pasted into the editor and serves it back through an authenticated
route, so an image in a private workspace does not become a public URL.

**mcp** is the whole Model Context Protocol server, 27 tools behind one JSON-RPC endpoint. See
[agents and MCP](mcp.md).

**system** is what a monitor or an operator reads: `/health` for liveness and readiness, and
`/api/system` for the version, database state and which retrieval features are on.

**app** is the browser-facing surface rather than an API: the single-page application and the
redirects that lead to it.

## Errors

| Status | When |
| --- | --- |
| 400 | the request is well-formed but refused, such as page content over the 1 MiB limit |
| 401 | no credential, or one that does not check out |
| 404 | the thing does not exist, **or it exists and is not yours** |
| 409 | a conflict, such as registering an email that already exists |
| 422 | the body does not match the expected shape |
| 429 | too many failed login attempts for that address and address pair |

The 404-for-forbidden behaviour is deliberate. Answering 403 for a workspace you cannot see would
confirm that it exists.
