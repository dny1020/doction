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
- denial of service through work that is expensive but *proportionate*: large uploads, a
  costly search, embedding a huge corpus. There is no per-tenant quota and that is a known
  design gap rather than a vulnerability. **Disproportionate cost is in scope**: an input
  whose processing grows faster than its size — a quadratic parser, say — is a vulnerability,
  because a small request buys a large amount of work. One such bug has already been found
  and fixed here;
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

## Scanners and their queue

CodeQL (`security-and-quality`) analyses Python and JavaScript; Trivy scans the published
runtime image. Both report into the repository's Security tab, and both run weekly as well as
on changes.

**A finding is fixed or dismissed with a written reason — never left undecided.** Dismissals
record what specifically makes the finding inapplicable, so a later reader can judge whether
the argument still holds. If no specific reason can be stated, the finding is not a false
positive and stays open.

**An additional scanner is enabled only when that queue is at zero.** OpenSSF Scorecard is
the pending case: it publishes its results as SARIF into this same queue, so turning it on
while a backlog exists would make its findings indistinguishable from the backlog. That is
not a hypothetical concern — this queue once held a real quadratic denial of service that
went unread for weeks because twenty false positives were sitting on top of it.

Where a finding names a component the application does not use, the component is removed
rather than dismissed. A dismissal has to be re-justified on every rescan; a component that
is not shipped cannot be found again.

## Hardening checklist for operators

A production instance needs a real `SECRET_KEY`, `SECURE_COOKIES=1` behind a TLS-terminating
proxy, a generated Postgres password, and **`DISABLE_REGISTRATION=1`** — sign-up is open by
default. Each is explained in [Configuration](docs/configuration.md#required-in-production).
Back up both the data directory and the Postgres volume; one without the other does not
restore ([Operations](docs/operations.md#backup)).
