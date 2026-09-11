# Troubleshooting

Symptom first. Each entry says what to check and why the failure looks the way it does.

## The server will not start

### `RuntimeError: SECRET_KEY must be set to a real secret when SECURE_COOKIES is enabled`

Working as intended. With `SECURE_COOKIES=1` — the signal that you are in production
behind TLS — doction refuses to boot on an unset key or on one of the placeholders shipped
in `.env.example` (`change-me`, `changeme`, `dev-secret-key`).

```bash
openssl rand -hex 32
```

Put that in `SECRET_KEY` and restart. Changing the key invalidates every existing session
cookie and JWT; personal access tokens are unaffected, because they are not signed with
it.

### `/health` returns `"db": "error"`, or startup hangs on the database

The app is up and Postgres is not reachable. In order:

```bash
docker compose ps                      # is the postgres container running and healthy?
docker compose logs postgres | tail -30
```

The most common cause is `DATABASE_URL` pointing at a hostname that does not resolve from
inside the app container. The default is `postgresql://doction:doction@postgres:5432/doction`,
where `postgres` is a Compose *service name* — it resolves inside the Compose network and
nowhere else. Running the app outside Compose means that host does not exist.

### Permission errors on `/data` or `/logs`

The container runs non-root as uid 1000. A bind mount created by `docker` itself is owned
by root, and the app cannot write to it.

```bash
mkdir -p data/logs
sudo chown -R 1000:1000 data
```

Create the directories before the first `up`, which is why the Compose file's header says
to.

## Search problems

### An accented word does not match its unaccented spelling

If `renovacion` does not find a page titled "Renovación TLS", accent folding is not
active. It depends on the `unaccent` extension, and if the database role cannot
`CREATE EXTENSION unaccent`, doction logs it and falls back to the stemmer alone rather
than refusing to boot.

```bash
docker compose logs doction | grep -i unaccent
docker exec -it doction-postgres psql -U doction -d doction -c 'CREATE EXTENSION IF NOT EXISTS unaccent;'
```

Restart the app after creating it. On the next boot the `search_vector` columns converge
to the accent-folding expression, which is one table rewrite plus a GIN index rebuild, and
it happens by itself.

### Semantic search returns nothing, or falls back to keyword

Three things have to be true, in this order:

```bash
curl -s -H "Authorization: Bearer $TOKEN" $DOCTION/api/system | jq .semantic_search
```

1. `SEMANTIC_SEARCH=1` is set **and the process picked it up**. The `/api/system` field is
   the authoritative answer, not the environment you believe you set.
2. The model loaded. It loads lazily on the first query, so check the logs *after* running
   a search, not after a restart.
3. Pages have been embedded. The worker is asynchronous — a page written a second ago is
   full-text searchable immediately and semantically searchable a little later.

Every intelligence response carries a `mode` field. If it says a keyword mode, doction is
telling you it degraded rather than failing, which is by design.

### Search results contain raw markdown

Snippets are extracted from the stored markdown, so table pipes, `##`, and `[[…]]` can
appear in the excerpt. Cosmetic; the ranking is unaffected.

## The web UI

### A change under `frontend/` does not appear

The bundle is built, not served from source. `app/static/app/` is gitignored and produced
by the Docker build.

```bash
make build-web      # or: cd frontend && npm run build
```

**This includes `app/static/style.css`.** It is linked with a content hash that only
changes on build, so a CSS edit measured against a running dev server describes the
*previous* stylesheet. This wastes more time than any other item on this page.

### `/app` serves nothing on a fresh clone

Same cause. Run the frontend build once after cloning, or use the published image, which
already contains the bundle.

### Uploads fail with 413

The reverse proxy, not doction. nginx defaults to a 1 MB body limit.

```nginx
client_max_body_size 25m;
```

### A pasted screenshot is not searchable

OCR is opt-in. Set `OCR_UPLOADS=1`, and check that `OCR_LANGS` names packs present in the
image (default `eng+spa`). OCR runs as a background task and a failure never breaks the
upload, so the only evidence is in the logs.

## Agents and MCP

### `tools/call` returns an authentication error, `initialize` works

Correct behaviour: `initialize` and `tools/list` are open so a client can discover the
server, and `tools/call` needs a Bearer token.

```bash
curl -s -X POST $DOCTION/api/mcp \
  -H "Authorization: Bearer doction_..." \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | jq '.result.tools | length'
# 27
```

### A token stopped working

Either it was revoked, or it was a JWT and expired — JWTs last 7 days, personal access
tokens last until revoked. `GET /api/tokens` lists the live personal access tokens. A lost
plaintext cannot be recovered, only replaced: doction stores a SHA-256 hash.

### An agent cannot see a workspace

Access is workspace membership, not authorship. A token carries its user's memberships,
and `pages.user_id` (creator) and `pages.updated_by` (last editor) are authorship — never
permissions. Add the user as a member with
`POST /api/workspaces/{slug}/members`.

## Deployment

### The deployed version is not what I expected

Deploys are manual. Nothing on the host reacts to a push, so an image published by CI is
not running until someone pulls it.

```bash
curl -s $DOCTION/health | jq .version
```

If it is behind: `docker compose pull && docker compose down && docker compose up -d`.

### `docker compose pull` cannot find the image

The GHCR package has to stay public for a host to pull without logging in. Check the
package's visibility in the repository's Packages settings.

### Pages exist but search finds nothing, after a restore

You restored one half. The database is the index; `DATA_DIR` is the content. Restoring the
volume without the dump leaves pages on disk that no row describes. See the restore
procedure in [Operations](operations.md), and note the dump-before-tar ordering.

## Getting help

Open an issue with the version from `/health`, the optional flags you have on, and a
reproduction — a `curl` invocation separates a server bug from a browser one. Raise
`LOG_LEVEL=DEBUG` first and include the relevant lines, with tokens redacted.

Security problems go to [the private advisory channel](https://github.com/dny1020/doction/security/advisories/new),
never a public issue.
