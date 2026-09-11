# Security Policy

## Supported versions

doction ships a single moving release line. Only the latest published version gets
fixes; there are no long-term support branches.

| Version | Supported |
| --- | --- |
| latest `0.x` (`ghcr.io/dny1020/doction:latest`) | yes |
| any older tag | no — upgrade first |

The running version is on `GET /health` and in the MCP `initialize` response, so you can
check what you are on without shell access:

```bash
curl -s https://your-host/health | jq .version
```

## Reporting a vulnerability

**Do not open a public issue for a security problem.**

Report it through GitHub's private vulnerability reporting: open
<https://github.com/dny1020/doction/security/advisories/new>. That channel is private
between you and the maintainer, and it is the only one that is monitored.

Please include:

- what an attacker can do, not just what looks wrong;
- the version (`/health`), and whether the optional flags were on (`SEMANTIC_SEARCH`,
  `OCR_UPLOADS`, `RERANK`);
- a minimal reproduction — a `curl` invocation is ideal;
- whether the instance was behind a reverse proxy, and whether `SECURE_COOKIES` was set.

### What to expect

This is a single-maintainer project, not a vendor with an on-call rotation. Realistic
timelines, not SLAs:

| Stage | Target |
| --- | --- |
| Acknowledgement | within 5 days |
| Assessment and severity | within 14 days |
| Fix for a confirmed high-severity issue | next release, or a point release if it is exploitable pre-auth |

You will be credited in the advisory and the changelog unless you ask not to be.

## Scope

In scope, and treated as vulnerabilities:

- authentication or session bypass (session cookie, JWT, or `doction_*` personal access
  token);
- one workspace reading or writing another workspace's pages, or a `member` performing an
  `owner`-only action;
- stored or reflected XSS in rendered markdown, page titles, or uploaded filenames;
- SQL injection, path traversal in page slugs or upload names, or SSRF through the
  outgoing webhook delivery;
- unauthenticated access to `/uploads/*`, to `tools/call` on the MCP endpoint, or to any
  page content;
- secret disclosure through logs, error responses, or the git repo under `DATA_DIR`.

Out of scope:

- anything that requires the operator to have already published the instance without TLS
  or without `SECURE_COOKIES=1` — doction assumes a TLS-terminating reverse proxy in front
  of it, and says so in the README;
- running with the built-in development `SECRET_KEY`. The server logs a warning at
  startup; setting a real key is the operator's job;
- exposing Postgres to an untrusted network. The shipped compose files bind it to
  loopback or an internal-only network;
- denial of service through large uploads, expensive search queries, or embedding a huge
  corpus. There is no per-tenant quota and that is a known design gap, not a
  vulnerability;
- missing security headers that a reverse proxy is expected to add (HSTS, CSP on the
  proxy level);
- findings from an automated scanner with no demonstrated impact.

## Security model, briefly

Knowing the intended boundaries makes reports sharper.

- **Trust boundary.** doction trusts nothing from the request body. Markdown is rendered
  client-side through a DOMPurify allowlist; wikilink targets become router tokens, never
  interpolated HTML.
- **Authentication.** An httponly session cookie for the browser, or `Authorization:
  Bearer` for agents — `doction_*` prefixed personal access tokens (revocable, stored as a
  SHA-256 hash) or a 7-day JWT. Passwords are PBKDF2-HMAC-SHA256.
- **Authorization.** Access is by workspace membership (`owner` / `member`). Page queries
  filter on the workspace alone; the creator and last-editor columns are authorship, never
  an access gate.
- **No outbound calls at runtime**, except webhooks you configure yourself. There is no
  CDN, no telemetry, and no LLM: embeddings and reranking run locally from models baked
  into the image. `npm run check` fails the build if a remote asset creeps into the
  frontend.
- **The container runs non-root** (uid 1000) and `/uploads/*` is served by an
  authenticated route, not a public static mount.

## Hardening checklist for operators

- Set `SECRET_KEY` to a real random value (`openssl rand -hex 32`).
- Set `SECURE_COOKIES=1` and put a TLS-terminating proxy in front.
- Give Postgres a generated password and keep it off any shared network.
- Back up both `DATA_DIR` (git repo + uploads) and the Postgres volume. One without the
  other does not restore.
- **Set `DISABLE_REGISTRATION=1`.** Registration is *open by default*: on a
  publicly reachable instance, anyone who finds the URL can create an account. With the
  flag set, the first user can still register (so a fresh instance is not locked out) and
  everyone after that has to be added as a workspace member by an owner.
