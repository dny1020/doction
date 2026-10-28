# Security Policy

Only the latest image (`ghcr.io/dny1020/doction:latest`) gets fixes. Check what an instance
runs with `curl -s https://your-host/health | jq .version`.

## Reporting a vulnerability

**Do not open a public issue.** Report it privately at
<https://github.com/dny1020/doction/security/advisories/new>, with what an attacker can do,
the version, the optional flags in use (`SEMANTIC_SEARCH`, `OCR_UPLOADS`, `RERANK`) and a
minimal reproduction, ideally a `curl` command. This is a one-person project: expect an
answer within days, not hours.

## Scope

In scope: bypassing authentication (session cookie, JWT or `doction_*` token); one workspace
reaching another's pages, or a `member` doing what only an `owner` may; XSS in rendered
markdown, titles or upload names; SQL injection, path traversal, SSRF through webhooks;
unauthenticated access to `/uploads/*`, MCP `tools/call` or any page; secrets leaking through
logs, errors or the git repo; input whose processing grows faster than its size.

Out of scope: running without TLS, without `SECURE_COOKIES=1` or with the development
`SECRET_KEY`; Postgres exposed to an untrusted network; proportionate resource use such as
large uploads; headers a reverse proxy is expected to add; scanner output with no
demonstrated impact.

## Security model

- Markdown is rendered client-side through a DOMPurify allowlist; wikilinks become router
  tokens, never interpolated HTML.
- The browser uses an httponly session cookie; agents use `Authorization: Bearer` with a
  revocable personal access token (stored as a SHA-256 hash) or a 7-day JWT. Passwords are
  PBKDF2-HMAC-SHA256.
- Access is by workspace membership (`owner` / `member`); page authorship is never an access
  gate.
- No outbound calls at runtime except webhooks you configure: no CDN, no telemetry, no LLM.
- The container runs as a non-root user, and `/uploads/*` is served by an authenticated route.

## Hardening checklist for operators

A production instance needs a real `SECRET_KEY`, `SECURE_COOKIES=1` behind a TLS-terminating
proxy, a generated Postgres password, and **`DISABLE_REGISTRATION=1`** — sign-up is open by
default. Each is explained in [Configuration](docs/configuration.md#required-in-production).
Back up both the data directory and the Postgres volume; one without the other does not
restore ([Operations](docs/operations.md#backup)).
