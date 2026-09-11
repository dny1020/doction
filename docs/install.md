# Installation

doction is two containers: the app, and a Postgres it talks to. There is no third
service, no broker, and no external API. The published image is multi-arch, so the same
tag runs on amd64 and on a Raspberry Pi.

## Requirements

| | Minimum | Comfortable |
| --- | --- | --- |
| Architecture | amd64 or arm64 | — |
| RAM for the app container | 256 MB | 768 MB |
| RAM extra, with `SEMANTIC_SEARCH=1` | +150 MB | — |
| RAM extra, with `RERANK=1` | +100 MB | — |
| Disk | the git repo of your pages, plus uploads, plus the Postgres volume | — |
| Postgres | 16 | 16 |

A Raspberry Pi 4 with 2 GB runs it with semantic search on. The reference deployment caps
the app container at 768 MB.

## Option 1: Docker Compose

The `compose.yaml` in the repo root wires both containers and is the fastest path to a
working instance.

```bash
git clone https://github.com/dny1020/doction.git
cd doction

cp .env.example .env
# Edit .env: POSTGRES_PASSWORD and SECRET_KEY are the two that matter.
# openssl rand -hex 24   → POSTGRES_PASSWORD
# openssl rand -hex 32   → SECRET_KEY

mkdir -p data/logs   # so the bind mounts get your uid; the container runs as uid 1000
docker compose up -d
```

Open <http://localhost:8000> and register. **The first account is the one that matters** —
registration is open by default, so create yours immediately, then set
`DISABLE_REGISTRATION=1` and restart.

Postgres is published on `127.0.0.1:5432` only, so `psql` works locally without exposing
the database to the network.

## Option 2: Plain `docker run`, behind a proxy

For a host where you manage the reverse proxy yourself. This is the shape the reference
deployment uses.

```bash
docker network create doction-net

docker run -d --name doction-postgres --restart unless-stopped --network doction-net \
  -e POSTGRES_USER=doction \
  -e POSTGRES_PASSWORD=$(openssl rand -hex 24) \
  -e POSTGRES_DB=doction \
  -v /srv/doction/postgres:/var/lib/postgresql/data \
  postgres:16-alpine

docker run -d --name doction --restart unless-stopped --network doction-net \
  -p 127.0.0.1:8000:8000 \
  -e SECRET_KEY=$(openssl rand -hex 32) \
  -e DATABASE_URL=postgresql://doction:<the-password-above>@doction-postgres:5432/doction \
  -e SECURE_COOKIES=1 \
  -e DISABLE_REGISTRATION=1 \
  -e SEMANTIC_SEARCH=1 \
  -v /srv/doction:/data \
  -v /srv/doction/logs:/logs \
  ghcr.io/dny1020/doction:latest
```

Two details that are easy to get wrong:

- **Publish on loopback**, `-p 127.0.0.1:8000:8000`, not `-p 8000:8000`. Otherwise the app
  is reachable directly, bypassing the proxy and its TLS.
- **Put Postgres on an internal network only.** It needs no published port at all. The
  reference deployment gives it a separate `db_net` so the database stays unreachable even
  if the proxy is misconfigured.

Then terminate TLS in nginx, Caddy, or Traefik pointing at `http://127.0.0.1:8000`.

### nginx, minimal

```nginx
server {
    listen 443 ssl http2;
    server_name wiki.example.com;

    ssl_certificate     /etc/letsencrypt/live/wiki.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/wiki.example.com/privkey.pem;

    # Uploaded images and PDFs. Raise it if you paste large screenshots.
    client_max_body_size 25m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

`client_max_body_size` is the one people forget. nginx defaults to 1 MB, so an upload
larger than that fails at the proxy with a 413 before doction ever sees it.

## Option 3: From source

For development, or to run without Docker. You still need a Postgres somewhere.

```bash
uv sync --dev
cd frontend && npm install && npm run build && cd ..

export DATABASE_URL=postgresql://doction:doction@localhost:5432/doction
export SECRET_KEY=$(openssl rand -hex 32)
export DATA_DIR=./data LOG_DIR=./data/logs

uv run uvicorn app.main:app --reload
```

The frontend build step is not optional. `app/static/app/` is gitignored — the Docker
build produces it — so from a fresh clone the `/app` route serves nothing until you run
`npm run build` (or `make build-web`).

## Verifying the install

```bash
curl -s http://localhost:8000/health | jq
# {"status":"ok","db":"ok","version":"0.31.3"}
```

`db: "ok"` means the schema was created and is reachable. The schema is built with
`CREATE TABLE IF NOT EXISTS` on every boot, so first start and every start after it run
the same code path — there is no migration step to remember and no migration ladder to
keep in order.

To check the agent surface without authenticating:

```bash
curl -s -X POST http://localhost:8000/api/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26"}}' | jq .result.serverInfo
# {"name":"doction","version":"0.31.3"}
```

That is also the way to confirm which version a remote deployment is actually running,
which matters because deploys are manual.

## What to do next

1. Register the first user, then set `DISABLE_REGISTRATION=1`.
2. Create a personal access token for your agent: see [Agents and MCP](mcp.md).
3. Set up backups before you rely on it: see [Operations](operations.md). Both the volume
   and the database, or the restore does not work.
