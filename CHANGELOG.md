# Changelog

All notable changes to doction. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[semantic](https://semver.org/), still on `0.x` — minor versions may change behaviour.

The version in `pyproject.toml` is the single source: `app/version.py` reads it at import,
so `GET /health`, the MCP `initialize` response, and the published image tag all agree.
Check what a deployment is actually running with `curl -s $DOCTION/health | jq .version`.

This file was reconstructed from the git history at 0.31.3. Entries before that are
summarised per release rather than exhaustive.

## Unreleased

Nothing yet.

## 0.31.4 — 2026-09-12

### Added

- Repository governance: `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`,
  `CODEOWNERS`, issue and pull request templates.
- Documentation set under `docs/`: installation, configuration reference, architecture,
  operations, agents and MCP, troubleshooting.
- Dependabot for four ecosystems: `uv`, npm in `frontend/`, Docker base images, and GitHub
  Actions.
- `Security` workflow: CodeQL for Python and JavaScript, `pip-audit` against the locked
  environment, `npm audit` for the frontend, Trivy against the runtime image, and
  dependency review on pull requests.

### Changed

- **Relicensed to GPL-3.0-only.** `LICENSE` now carries the verbatim GNU General Public
  License version 3, and `pyproject.toml` declares `license = "GPL-3.0-only"`.

  Releases up to and including 0.31.3 were published under MIT, and that grant is not
  withdrawn: anyone who received those versions keeps those terms. Relicensing is not
  retroactive.

  Every bundled dependency was checked for compatibility first. All are one-way compatible
  with GPL-3.0 — MIT, BSD-2/3-Clause, ISC, Apache-2.0, MPL-2.0, Blue Oak 1.0.0, CC0, and
  LGPL-3.0-only for `psycopg`. Nothing in the tree is GPL-2.0-only or proprietary, which is
  what would have blocked it.

  For a self-hosted wiki: running it and modifying your own copy carry no obligation, and
  hosting it for other people is not distribution. Distributing it, modified or not, means
  passing on the source under the same licence.
- **The frontend gate now runs on pull requests.** CI built only `--target test`, so
  `npm run check` reached CI exclusively through the publish job — after merge. A failing
  frontend lint broke the publish instead of blocking the pull request. A `web` job now
  builds that stage on every pull request, and `publish` waits on both.
- **`npm run check` runs the unit tests.** `vitest` existed and was wired to
  `npm run test`, which nothing called: not `make check`, not the Docker `web` stage, not
  CI. The 42 markdown-rendering tests never gated anything.
- README screenshots regenerated against the current React SPA. The previous ones predated
  it, showed a private wiki's page titles, and claimed 12 MCP tools where there are 27.

### Fixed

- `APP_BASE` is derived from a build-time `define` instead of `import.meta.env.BASE_URL`.
  The test harness got the basename by setting `base: '/app/'` in `vitest.config.js`, and a
  newer vitest stops propagating `base` into `BASE_URL`, so `APP_BASE` collapsed to `''`
  and the six wikilink tests compared against unprefixed hrefs. Never a production
  problem — the build still takes `base` from `vite.config.js` — but it cost the harness
  the ability to reproduce the real basename, and those tests are the only thing checking
  that wikilink anchors carry it. `MCP_PATH` already travelled as a `define` for exactly
  this reason; `APP_BASE` now does too.
- The `web` build stage runs on `node:22-slim`. Putting vitest in `npm run check` pulled in
  jsdom and undici, whose `engines` require Node >= 22.19.0, so the gate failed on
  `node:20` and only there.
- `aquasecurity/trivy-action` was referenced at a tag that does not exist, so the image
  scan failed at job setup before running a step.

### Security

- Third-party GitHub Actions are pinned to commit SHAs with the version in a trailing
  comment. `docker/login-action` and `docker/build-push-action` run in `publish`, where the
  token carries `packages: write`, so a mutable tag there was a supply-chain hole. CodeQL's
  `security-and-quality` suite had flagged it.
- `npm audit` and `pip-audit` moved to the weekly cron, off push and pull request. What
  they detect was not introduced by the change that triggered the run, and on `main` the
  result was a red mark that stayed until a patched version existed and could be merged. A
  permanently red workflow is one that gets ignored. `dependency-review` remains the pull
  request gate, since it only inspects what a pull request introduces.
- Dependency updates for the react, eslint and vite families are grouped, because these
  declare peers on each other and a single-package bump cannot install at all.
- Documented that registration is **open by default**, and that `DISABLE_REGISTRATION=1`
  is what closes it. It was absent from the README's configuration table.

### Removed

- `package-lock.json` at the repository root: an empty lockfile with no `package.json`
  beside it. The real one is `frontend/package-lock.json`.

## 0.31.x — 2026-09-08 to 2026-09-09

The design system moves from specified to implemented, and `DESIGN.md` becomes a
description of what is built rather than an intention.

### Changed

- `DESIGN.md` rewritten so every token in it was read out of `app/static/style.css`. When
  the two disagree the document is now the defect.
- The chrome stops competing with the canvas: page content owns the light surface, the
  sidebar its own.
- The sidebar hugs the window, and the dark theme stops being green.
- A scrollbar of the application's own, and room around the table of contents.
- The `Makefile` now matches the documented commands rather than inventing any.

### Fixed

- One control for one action when the sidebar is collapsed, instead of two that did the
  same thing.

## 0.28.0 – 0.30.0 — 2026-09-07 to 2026-09-08

### Changed

- The shared visual language reaches every surface: the sidebar, trash, editor, settings,
  the reader, the inbox, the graph and the authentication screens.
- Shared components extracted out of Settings and applied consistently.

### Fixed

- The Pages label lost its inset (0.28.1).

## 0.27.x — 2026-09-05 to 2026-09-06

### Fixed

- The Inbox crashed on every visit, and the capture shortcut opened two things at once.

### Changed

- README caught up with the MCP surface and the graph view.

## 0.26.x — 2026-09-04 to 2026-09-05

### Added

- The visual language as an OpenSpec capability: warm paper, one blue, three type families
  with assigned roles.

### Changed

- mermaid diagrams and syntax highlighting follow the palette; frontmatter stops rendering
  as body content.
- The document body returns to the text face.

### Fixed

- The web build stage gets the stylesheet its asset check reads.

## 0.25.0 — 2026-09-04

The retrieval round. Every constant here cites a measurement in `evals/results/`.

### Added

- Markdown is chunked **by heading**, not by character offset, and chunks are packed by
  their own heading with ties broken on it.
- The two rankings are fused by **reciprocal rank** rather than a constant weight.
- Assembled context is bounded by a character budget and stops repeating passages.
- `upsert_page_section`, so an agent can write one section without rewriting the page.
- Ranking configuration is reported back to the caller, and chunks carry their metadata.

## 0.24.0 — 2026-08-23

### Fixed

- **Spanish retrieval.** Search now runs on a named Postgres text-search configuration,
  `doction`: `unaccent` chained ahead of `english_stem`. `to_tsvector('english',
  'Renovación')` indexed the accented token, so searching `renovacion` missed the page
  entirely. `unaccent()` cannot be called directly in a generated column, since it is
  `STABLE` rather than `IMMUTABLE`; inside a named configuration it can.
- The stemmer stays English by measurement: `spanish_stem` scored 0.00 MRR on English
  queries against Spanish pages. A multilingual encoder was measured and rejected — six
  times the size, and worse on both Spanish paraphrase and conceptual queries.

## 0.23.0 — 2026-08-21

The v2 page model. Design recorded in `SPEC.md`.

### Added

- `move_page`, `rename_page` with aliases so old wikilinks keep resolving, `delete_page`
  as a soft delete, and `list_children`.
- Quick capture and a notes feed; the Inbox is unfiled memos.
- **Outgoing webhooks**, signed HMAC-SHA256 and delivered from a worker thread.
  `db.emit_event()` enqueues inside the transaction that made the write, so no event is
  emitted for a write that rolled back.
- The app is installable, and Inter is self-hosted.

### Fixed

- iOS Safari layout, and filing an Inbox memo actually files it.

## 0.16.0 – 0.18.2 — 2026-07-06 to 2026-07-16

### Added

- Local ML with no LLM: link and tag suggestions, near-duplicate detection, extractive
  TextRank summaries, and workspace insights over PageRank.
- Opt-in OCR of uploads via the `tesseract` binary.
- Opt-in cross-encoder reranker — **and the measurement that says to leave it off**: on
  the real corpus it buys 0.01 MRR, loses recall@1 (0.57 vs 0.61), and costs 29× the
  median latency.
- `hybrid` search mode, used by the sidebar, with a relevance floor to cut noise. Semantic
  alone let an exact term lose to an unrelated page.
- An eslint + prettier + build gate for the frontend.

## 0.14.0 – 0.15.1 — 2026-06-30 to 2026-07-05

### Changed

- **The frontend is a React SPA** (Vite, plain JSX). The Jinja templates are gone and the
  single-page app is the only UI. Keyboard shortcuts, a command palette, settings, trash,
  history and i18n came with it.
- The backend types its data with dataclasses.
- Logging is configured from environment variables.
- The PostgreSQL layer moves to GIN indexes for full-text search.

### Added

- Opt-in registration closing, and a Spanish catalog.

## 0.9 – 0.12.1 — 2026-06-15 to 2026-06-20

### Added

- Multi-user collaborative workspaces with `owner` / `member` roles.
- Git history and diffs in the interface.
- Local semantic embeddings with no LLM.

## 0.1 – 0.8 — 2026-06-06 to 2026-06-15

The first working version.

### Added

- Native MCP server at `POST /api/mcp`, JSON-RPC 2.0, written without an SDK.
- Personal access tokens for agents and MCP.
- REST JSON API with Bearer authentication.
- Per-page git history: one commit per save.
- Stable slugs, subpages and workspace isolation.
- Sidebar tree, right-side table of contents, image paste, theme and language toggles.
- CI on GitHub Actions publishing multi-arch images to GHCR.
