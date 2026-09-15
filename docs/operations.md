# Operations

Running doction after the install. Everything here assumes the two-container shape from
[Installation](install.md).

## Health and version

```bash
curl -s $DOCTION/health | jq
# {"status":"ok","db":"ok","version":"0.31.3"}
```

`status` is the process, `db` is the Postgres connection. A `200` with `"db":"error"` means
the app is up and the database is not — check the database container before anything else.

`GET /api/system` (authenticated) adds which optional features actually resolved as
enabled. Use it to confirm a flag took effect rather than trusting the environment you
believe you set:

```bash
curl -s -H "Authorization: Bearer $TOKEN" $DOCTION/api/system | jq
# {"version":"0.31.3","db":"ok","semantic_search":true,"rerank":false,"ocr_uploads":false, ...}
```

For a remote deployment where you have no shell, the MCP endpoint answers unauthenticated:

```bash
curl -s -X POST $DOCTION/api/mcp -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26"}}' \
  | jq .result.serverInfo.version
```

## Verifying an image you pulled

Every published image carries an SBOM and SLSA provenance, so you can answer "what is in
this" and "where did it come from" without unpacking layers or asking the maintainer.

```bash
# What is inside it: every package and version, as SPDX.
docker buildx imagetools inspect ghcr.io/dny1020/doction:0.31.5 \
  --format '{{ json .SBOM }}'

# Where it came from: the CI run that built it, its steps and its resolved inputs.
docker buildx imagetools inspect ghcr.io/dny1020/doction:0.31.5 \
  --format '{{ json .Provenance }}'
```

The provenance names the GitHub Actions run that produced the image, so you can compare it
against the commit the release claims. Both attestations are attached to the image index as
extra manifests, which is why `docker manifest inspect` shows entries whose platform reads
`unknown/unknown`.

Release notes for a version live on its GitHub Release, generated from `CHANGELOG.md`.
Releases start at 0.31.5; earlier tags predate the automation and have none, because the
changelog describes that history in ranges rather than per version.

## Backup

**Two halves, and one without the other does not restore.** The database is an index of the
files; the files are the content.

| What | Where | Why |
| --- | --- | --- |
| Pages and uploads | `DATA_DIR` (`/data`) — a git repo plus uploaded files | The content and its full history |
| Database | the Postgres volume | Search index, tags, link graph, users, tokens, workspaces |
| Logs | `LOG_DIR` (`/logs`) | Diagnostic only. Do not back up. |

A minimal, correct backup:

```bash
#!/bin/sh
set -eu
STAMP=$(date +%F)
DEST=/srv/backups/doction/$STAMP
mkdir -p "$DEST"

# Database first, then files. A page committed between the two shows up in the files
# without a row; reindexing on restore fixes that. The other order loses the page.
docker exec doction-postgres pg_dump -U doction -Fc doction > "$DEST/doction.dump"
tar -C /srv/doction -czf "$DEST/data.tar.gz" pages uploads

sha256sum "$DEST"/* > "$DEST/SHA256SUMS"
```

The ordering comment is the part that matters. Dump the database *before* archiving the
files, so any page written between the two steps exists on disk without an index row —
recoverable by reindexing. The reverse order produces an index row for a file you do not
have, which is not recoverable.

There is no automatic backup and no rollback built in. This is a cron job you write.

## Restore

Test this before you need it. An untested backup is not a backup.

```bash
# 1. Stop the app. Leave Postgres running.
docker stop doction

# 2. Verify the archive before touching anything.
cd /srv/backups/doction/<date> && sha256sum -c SHA256SUMS

# 3. Restore the database into a scratch database first, never over the live one.
docker exec -i doction-postgres createdb -U doction doction_restore
docker exec -i doction-postgres pg_restore -U doction -d doction_restore --clean < doction.dump

# 4. Sanity-check it: row counts and the newest page.
docker exec -i doction-postgres psql -U doction -d doction_restore \
  -c 'select count(*) from pages' -c 'select slug, updated_at from pages order by updated_at desc limit 5'

# 5. Only now swap. Restore the files, point DATABASE_URL at the restored database
#    (or rename the databases), and start the app.
tar -C /srv/doction -xzf data.tar.gz
docker start doction
```

Restoring the files but not the database, or the other way round, leaves the two out of
sync. The schema converges on boot, so the tables will be correct — but rows describing
pages that are not on disk, or pages with no rows, stay wrong until reindexed.

## Upgrading

Deploys are manual. Nothing on the host reacts to a push on its own.

```bash
cd /opt/doction          # wherever your compose.yaml and .env live
docker compose pull
docker compose down
docker compose up -d
curl -s http://127.0.0.1:8000/health | jq .version
```

Before you pull:

- **Take a backup.** There is no rollback procedure, and the image tag you were on is your
  only way back.
- **Read `CHANGELOG.md`** for the versions you are skipping.

What happens on the first boot of a new image:

- The schema converges. `CREATE TABLE IF NOT EXISTS` for anything new, and
  `search_vector` columns rebuilt only if their generation expression changed. That
  rebuild is one table rewrite plus a GIN index, and it runs by itself.
- Rolling *back* to an older image is safe for the same reason: the older code compares
  the same expressions and converges the column back.

### Rolling back

Pin the previous tag and restart:

```bash
# in compose.yaml: image: ghcr.io/dny1020/doction:0.31.2
docker compose up -d
```

This works because the schema converges in both directions. It does **not** undo data
changes — pages edited under the new version stay edited.

## Logs

Two destinations, always: stdout and a rotated file under `LOG_DIR`.

```bash
docker compose logs -f doction          # stdout
tail -f /srv/doction/logs/doction.log   # the rotated file
```

Mount `LOG_DIR` as its own volume. In Docker, a log directory that is not mounted
disappears with the container, which is exactly when you want to read it.

To raise verbosity, set `LOG_LEVEL=DEBUG` and restart. It reaches application logs, not
just uvicorn's — the root logger is configured at import time for that reason.

## Capacity and resource use

The reference deployment runs on modest self-hosted hardware (a Raspberry Pi) with the
app container capped at `768m`, with `SEMANTIC_SEARCH=1` on and the reranker off. That
limit has room to spare.

The two optional models are what move the number. The embedding model is ~23 MB on disk;
enabling the reranker on top needs roughly 80–100 MB more resident memory, which is the
figure to budget against a tight container limit.

Both models load **lazily**, on the first query that needs them, not at boot. Sizing a
container against its startup usage is how you get an out-of-memory kill an hour later.
Measure after a search, not after a restart.

Watch, in rough order of what actually goes wrong:

- **Disk on the `DATA_DIR` volume.** Every save is a commit. The repo grows and never
  shrinks on its own.
- **Postgres volume**, dominated by `page_chunks` when semantic search is on.
- **Memory**, if you enabled the reranker inside a tight container limit.

## Webhooks

Outgoing webhooks are signed HMAC-SHA256 and delivered from a worker thread, never on the
request path. `db.emit_event()` enqueues into `webhook_deliveries` *inside the transaction
that made the write*, so an event is never emitted for a write that rolled back, and
`delivery_worker()` drains the queue separately with backoff.

Events: `page.created`, `page.updated`, `page.deleted`, `page.moved`, `page.renamed`.

Inspect deliveries per webhook with `GET /api/webhooks/{id}/deliveries` — that is where a
failing endpoint shows up, since a failed delivery never surfaces in the request that
caused it.

## Routine maintenance

There is very little, by design.

- **Rotate personal access tokens** you gave to agents. `GET /api/tokens` lists them,
  `DELETE /api/tokens/{id}` revokes one immediately.
- **Empty the trash.** Deletes are soft: `GET /api/trash` lists them,
  `POST /api/trash/{slug}/restore` brings one back, `POST /api/trash/{slug}/purge` removes
  it for good.
- **Check `workspace_insights`** occasionally. Orphans and broken links are wiki rot, and
  it is the only thing that reports them.
- **Confirm the deployed version after every deploy.** Manual deploys are how a host ends
  up running something you did not think it was running.
