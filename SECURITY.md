# Security Policy

## Supported versions

doction is released as a rolling image. Security fixes target the latest published version
(`ghcr.io/dny1020/doction:latest`). Please run a current image before reporting an issue.

## Reporting a vulnerability

**Please do not open a public issue for security vulnerabilities.**

Instead, report privately via GitHub's [Security Advisories](https://github.com/dny1020/doction/security/advisories/new)
("Report a vulnerability"). If that is unavailable, open a minimal issue asking for a
private contact channel — without disclosing details.

When reporting, please include:

- A description of the vulnerability and its impact.
- Steps to reproduce (a proof of concept if possible).
- Affected version / image digest.

We aim to acknowledge reports within a few days and will keep you updated on remediation.
Once a fix is released, we're happy to credit you unless you prefer to remain anonymous.

## Hardening notes for operators

doction is self-hosted; deployment security is your responsibility. Recommended baseline:

- Always set a strong, unique `SECRET_KEY` (e.g. `openssl rand -hex 32`). In dev (no
  `SECURE_COOKIES`) a warning is logged; with `SECURE_COOKIES=1` the app **refuses to start**
  without a real key.
- Run behind a TLS-terminating reverse proxy and set `SECURE_COOKIES=1` (this also enables
  HSTS). The app sends `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` and a
  `Content-Security-Policy` on every response.
- Bind the container to localhost (`-p 127.0.0.1:8000:8000`) and expose it only through the
  proxy.
- Treat Personal Access Tokens (`doction_*`) as secrets — they are shown once, are
  long-lived, and can be revoked via `DELETE /api/tokens/{id}`.
- Failed logins are rate-limited per (IP, email); repeated failures return `429`.
- Back up the `/data` volume (SQLite + git repo + uploads); it holds all state. Use the
  provided `infra/backup.sh` (daily via `doction-backup.timer`) and `infra/restore.sh` —
  see `infra/README.md`.
