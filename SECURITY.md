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

- Always set a strong, unique `SECRET_KEY` (e.g. `openssl rand -hex 32`). The default is
  an insecure dev value and logs a warning.
- Run behind a TLS-terminating reverse proxy and set `SECURE_COOKIES=1`.
- Bind the container to localhost (`-p 127.0.0.1:8000:8000`) and expose it only through the
  proxy.
- Treat Personal Access Tokens (`doction_*`) as secrets — they are shown once, are
  long-lived, and can be revoked via `DELETE /api/tokens/{id}`.
- Back up the `/data` volume (SQLite + git repo); it holds all state.
