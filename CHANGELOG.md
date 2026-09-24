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

## 0.32.0 — 2026-09-24

A finished-product pass over the application and https://doction.site, and one visual language
across both: green for the brand and "you are here", orange only for notes. No API or MCP
contract changed.

### Added

- **The documentation site presents itself when shared or indexed**: a `robots.txt` naming the
  sitemap, a title and description of its own on every page (derived from the page when it
  declares none), a descriptive home title, and Open Graph / Twitter card tags with a social
  image built from the design tokens.
- **A 404 in doction's voice** on the site, linking Installation, REST API, MCP and Home,
  instead of the framework's generic page.
- **The site build checks what it built**: it fails, naming the page, when a page lacks its
  title, description or social tags, when `robots.txt` is missing, or when anything would load
  from another host — the offline guarantee was previously verified by hand.

### Changed

- **One brand mark, in green.** The terminal glyph is `--nav-green` in the app's sidebar (it
  was orange), and the app's favicon and installable-app icons, still in the retired blue
  palette, now match the documentation site. `icon-512.png` is full-bleed, as its `maskable`
  entry requires. `theme-color` and the manifest use the current canvas and chrome tokens.
  `DESIGN.md` records the brand mark.
- **The app and doction.site assign colour the same way.** Green marks the brand and "you
  are here": the active page, table-of-contents entry and settings section carry a 2px green
  rule in the app (it was orange; the green measures 6.92:1 against the active surface), and
  the site's active navigation entry carries the same rule. Orange is left for one job, the
  rule beside quotations and admonitions. Breadcrumb separators are subtle ink.
- The wordmark is "doction" in the sidebar and the webhook help text, as everywhere else.
- The favicon, manifest and touch icon are linked with a content hash, like the stylesheet,
  so a changed icon reaches the browser instead of waiting out its favicon cache.
- A browser address outside the application that matches nothing — `/settings`,
  `/w/x/graph` — redirects to the same path under `/app` instead of answering with raw JSON.
  API clients and requests that do not ask for HTML keep the JSON 404.

### Fixed

- Links in running text on the documentation site are underlined, as they are in the app:
  they were distinguished by colour alone (WCAG 1.4.1, reported by axe-core in both themes).

## 0.31.11 — 2026-09-24

Documentation, CI and repository hygiene, plus the fixes for issues #42, #44 and #45. No API
or MCP contract changed.

### Added

- **Public documentation site at https://doction.site.** `docs/index.md` is a landing page
  (what doction is, how it works, the REST and MCP entry points, self-hosting, a map of every
  page), served at the root by a small MkDocs hook with the README at `/introduction/`. The
  site uses the application's own visual language — its tokens, the vendored Manrope,
  Instrument Serif and JetBrains Mono, the terminal mark — and loads nothing from a
  third-party host: no Google Fonts, no GitHub API call, no remote badge images.
  `pages.yaml` redeploys it on every push to `main` that touches the documentation.

### Changed

- CI on `main` takes about 4 minutes instead of 10. The `test`, `web` and `publish` jobs
  shared one build-cache scope and overwrote each other, so only 3 of 59 steps were ever
  cached; each now has its own, and `publish` reuses the `web` job's layers (6:48 → 0:49).
  The SPA stage is built once on the build host instead of again under QEMU for arm64. The
  runtime's `apt-get upgrade` layer is refreshed weekly (`APT_REFRESH`, the ISO week) so a
  working cache does not freeze Debian's security fixes.
- `openspec/` and `AGENTS.md` are no longer versioned: both are maintainer-local, gitignored
  like `CLAUDE.md`, and no tracked document points at them. `make spec` skips when
  `openspec/` is absent.
- Pending work is tracked in GitHub issues (#60–#65) rather than a roadmap file.
- The README is a short tour — screenshots, a quick start, the licence. Documentation that
  said the same thing in two places now says it once and links: features and the page map
  on `docs/index.md`, licence obligations and the production checklist in
  `docs/configuration.md` and `docs/operations.md`, the code-scanning policy in
  `SECURITY.md`, the relicensing history in the README.
- `DESIGN.md` is in English, and comments, docstrings and log messages across `app/`,
  `tests/`, `scripts/` and `evals/` were trimmed and translated to English. No behaviour
  change.
- The sign-off check skips Dependabot pull requests.

### Fixed

- Search snippets no longer show markdown syntax — table pipes, heading marks, wikilink
  brackets or mermaid source. The syntax is stripped before the words are chosen, so ranking
  is unchanged (#44).
- The graph view's force layout is readable: labels are centred under their node and sized
  into the simulation, so they no longer overlap (#45).
- The seeded deploy runbook described a retired Gitea runner and SQLite; it now describes the
  deployment that exists (#42).
- `scripts/changelog.py` refuses `Unreleased` as a version instead of printing that section
  as release notes.

### Removed

- `ROADMAP.md` and `.graphifyignore`.

### Dependencies

- **`react` and `react-dom` 18.3.1 → 19.3.0** (major).
- `lucide-react` 1.43.0 → 1.47.0, `prettier` 3.9.6 → 3.9.8.
- `pyjwt` 2.13.0 → 2.14.0, `onnxruntime` 1.29.0 → 1.30.0, `ruff` 0.16.6 → 0.16.8,
  `pyright` 1.1.411 → 1.1.414.
- GitHub Actions: `docker/setup-buildx-action` 4.4.1, `docker/build-push-action` 7.4.0,
  `docker/setup-qemu-action` 4.4.0, `astral-sh/setup-uv` 10.1.0.

## 0.31.10 — 2026-09-14

Repository hygiene. No application behaviour changed — this release touches demo
content, documentation wording, an OpenSpec rationale, a local tooling config, and a
handful of dead files.

### Changed

- doction no longer frames itself around a specific device. The seeded demo runbook,
  `docs/install.md`, `docs/operations.md`, and the rationale prose in the
  `client-resilience`, `visual-language`, and `retrieval-ranking` specs now describe the
  actual constraint (self-hosted, modest hardware, often behind a VPN with no public
  route) instead of naming "Raspberry Pi" as the product's identity. The Raspberry Pi
  stays as a real, measured example where docs already cited concrete numbers — this is
  wording, not a retraction of those measurements.
- `.graphifyignore` no longer duplicates `.gitignore`. It kept 3 entries whose exclusion
  Graphify does not already get for free — `app/static/vendor/` (vendored, minified,
  git-tracked on purpose), `graphify-out/`, and a broader `*.log` — down from 25. This
  also fixes a real bug: a duplicated `.env.*` rule was re-excluding `.env.example` from
  the knowledge graph even though `.gitignore`'s own `!.env.example` exception says it
  should be readable.

### Removed

- `.agents/skills/.openspec-target`, a tracked leftover from an agent-tooling scaffold
  retired in `cb5e85d` (it named `codex`, not this project's tooling, and nothing
  referenced it).
- The empty `tools/` directory, unreferenced and without git history.

## 0.31.9 — 2026-09-14

End-user documentation, and two gates that keep documentation from going quietly wrong.

### Added

- **Documentation for using the wiki**, not only for running it: writing pages, linking,
  tags and the metadata block, searching, the graph, and a complete REST reference. The
  behaviour they describe was measured against a running instance.
- **A published documentation site**, built with MkDocs from the tracked documentation and
  deployed to GitHub Pages. The build runs with `--strict`, so an internal link that does
  not resolve fails instead of publishing. `make docs` builds it, `make docs-serve` previews
  it, and the toolchain lives in a `docs` dependency group that the Docker test stage does
  not install.
- **Tests that hold the documentation to the code.** The documented parsing and search
  behaviours now fail a test when the code stops behaving that way, and the failure names the
  page to update. A second test compares the documented endpoint list against the served
  OpenAPI schema in both directions, so a route added without documentation fails the gate.

### Changed

- `/openapi.json` now declares the running version instead of FastAPI's `0.1.0` default, so
  the schema, `/health` and the image tag agree.
- All 59 operations carry a tag, so `/docs` and the reference are grouped by area rather
  than being one flat list.
- The 21 route docstrings that are published as API descriptions are now in English, matching
  the project's stated convention. No behaviour changed.

## 0.31.8 — 2026-09-14

No application code changed. This release exists because the image content changed and
publishing different content under an existing version tag contradicts what
`release-integrity` is for — see the roadmap entry about `publish` running on every push.

### Added

- **`AGENTS.md`**, shipped, explaining the one thing nothing else did: behaviour here is
  specified before it is written, `openspec/specs/` holds the contracts and
  `openspec/changes/archive/` holds the reasoning. The repository was already shipping 112
  OpenSpec files while `CONTRIBUTING.md` mentioned openspec once, as a command inside the
  gate, and the README and `docs/` not at all. It is a map rather than a copy: everything
  already documented elsewhere is a pointer, because one truth in two files becomes two
  facts that disagree.
- **`openspec/README.md`**, explaining the two directories and how to read a capability
  versus an archived change — including that the notes at the end of an archived `tasks.md`
  are where a decision's reasoning lives.
- **`ROADMAP.md`**, making nine identified-and-deferred items visible, in priority order,
  with no dates. Each names where it was identified. Five became labelled issues; four are
  decisions for the maintainer and say so, because an issue tracker misrepresents a decision
  as available work.
- **A discoverability check** (`scripts/check_docs_reachable.py`), in the gate and in CI: no
  tracked document may reference an untracked file. `CLAUDE.md` and `.claude/` are gitignored
  deliberately, which makes a document citing them a dead end for everyone but the
  maintainer.
- **A sign-off check** (`scripts/check_signoff.py`) on pull requests. Every commit must carry
  a `Signed-off-by` matching its author, certifying the terms the work is offered under. It
  was verified against constructed commits rather than trusted, since every commit in this
  project's history is a direct push to `main` and the check will not fire for a long time.

### Changed

- `CONTRIBUTING.md` now says proposals precede code, points at the workflow it never named,
  requires sign-off with the exact commands, and states the consequence: sign-off transfers
  no copyright, so doction cannot be relicensed without every contributor's permission. It
  also records that an item a change defers reaches the roadmap rather than staying in that
  change's notes.

## 0.31.7 — 2026-09-14

### Security

- **Fixed a quadratic denial of service in wikilink parsing.** The pattern scanned
  `[[`-repeated content with an unterminated tail in time proportional to the square of its
  length: 24 KB cost 7.9 seconds of CPU, while 80 KB of legitimate wikilinks cost 3.6 ms.
  `extract_links` runs inside the page save, synchronously, in the request path, and there was
  no limit on page size, so any workspace member could make one request consume minutes of
  CPU. On a single-process deployment that blocks everything.

  Excluding `[` from the target class is what removes the quadratic behaviour, since a scan
  started at the wrong position can no longer run past the next `[`. Measured at 1869 ms →
  0.10 ms on the adversarial shape, with identical results on real wikilinks. A regression
  test asserts the *ratio* between adversarial and benign input of the same length, and was
  verified to fail against the old pattern.

  Found by CodeQL (`py/polynomial-redos`), where it had sat unread for weeks among twenty
  findings that were not real.

- **Page content is now limited to 1 MiB.** Not the fix for the above — that is in the
  pattern — but a ceiling on what any single request can cost when a parser later turns out
  to be worse than believed. The value is ~55x the longest markdown document in this
  repository. Enforced where REST and MCP converge, because MCP calls the database layer
  directly and would have bypassed a check on the request models.

- **The runtime image no longer carries pip or uv.** The application starts from a
  virtualenv that is already built, so neither is needed to run it. That removes
  `setuptools` (CVE-2025-47273, CVE-2026-59890) and `msgpack` (GHSA-6v7p-g79w-8964) with
  them: both were vendored inside pip rather than installed as packages.

- **Debian security updates are applied in the runtime image**, closing 13 findings against
  `libpcre2-8-0`, `libsqlite3-0`, `gzip`, `libc6` and `libc-bin`. Each had a fixed version
  published within the same Debian release, so none was dismissible. This adds about 75 MB
  to the image: Docker layers are additive, so upgrading a package writes the new files
  above while the originals remain below.

- **The code scanning queue is triaged, and staying triaged is now the rule.** Eleven
  findings were dismissed with a specific written reason rather than the words "false
  positive"; eight were fixed in code. `CONTRIBUTING.md` and `SECURITY.md` record that an
  alert is fixed or dismissed-with-reason and never left undecided, and that an additional
  scanner — OpenSSF Scorecard is the pending case — is enabled only once the queue is at
  zero.

### Fixed

- `scripts/changelog.py` reported an error naming `--declared`, a flag renamed to `--check`
  when it was introduced, and had a code path a static analyser read as leaving a variable
  unassigned. Both corrected.
- Four tests performed a `DELETE` inside an `assert`, so running under `python -O` would have
  stripped the request and passed without testing anything.
- Two wrapped SQL statements in the schema list are now explicitly parenthesised. Adjacent
  string literals in a list are indistinguishable from a forgotten comma.

## 0.31.6 — 2026-09-13

### Added

- **A GitHub Release is published when a version tag is pushed**, with that version's
  `CHANGELOG.md` section as its body. 40 tags existed and no releases did, so nothing on the
  repository said what a version contained. The workflow triggers on
  `v[0-9]+.[0-9]+.[0-9]+` rather than `v*`: this repository carried a mistyped tag named
  `rm`, and the looser pattern would have published a release for it. Releases start here and
  are not backfilled — the changelog describes earlier history in ranges, so per-version
  notes for those 30 tags do not exist and would have to be invented.
- **Published images carry an SBOM** (1312 packages, SPDX-2.3) and SLSA provenance at
  `mode=max`, which records the build steps and resolved inputs rather than only the builder.
  Provenance was already being emitted at `mode=min` by default; what changed is the detail
  level. `docs/operations.md` documents how to read both from an image you pulled.
- **A version with no `CHANGELOG.md` entry now fails the gate.** Release notes are derived
  from that file, so a version nobody described is a release nobody can read.
  `scripts/changelog.py` is one parser with two callers: the gate asserts the version
  declared in `pyproject.toml` has a section, and the release workflow prints that section as
  its notes. It checks the declared version rather than the tag, because at tag time the tag
  already exists and the ruleset below forbids deleting it.

### Changed

- The four model downloads retry transient failures (`--retry 5 --retry-delay 5`). The 0.31.4
  publish died on HTTP 429 from Hugging Face; the content is pinned by revision and verified
  by checksum, so that was availability, not integrity, and a release stopped by a momentary
  rate limit is a release stopped for no reason. `--retry-all-errors` is deliberately omitted
  so a 404 or a renamed revision still fails promptly.

### Security

- **A published version tag can no longer be moved or deleted.** A ruleset blocks deletion,
  non-fast-forward, and any update to a `v*` tag. The middle rule alone was not enough and
  the test proved it: moving a tag to a *later* commit is a fast-forward, which
  `non_fast_forward` permits. For a version, every move is wrong.
- The stray `rm` tag is gone. It had only ever existed locally.

## 0.31.5 — 2026-09-12

### Changed

- **Relicensed to AGPL-3.0-only.** `LICENSE` carries the verbatim GNU Affero General Public
  License version 3 (661 lines, the FSF text, sha256 `0d96a4ff…079abcb0`).

  The reason is narrow. doction is hosted for people, and the plain GPL attaches its
  obligation to *distributing* a copy. An operator never hands anyone a copy, so a modified
  fork could be sold as a hosted service with its changes kept private. The AGPL's section
  13 attaches the obligation to network use instead, which is the case doction actually has.

  **Relicensing is not retroactive.** Releases through 0.31.3 were published under MIT and
  0.31.4 under GPL-3.0-only. Both grants stand and are not withdrawn: anyone who received
  those versions keeps those terms. AGPL-3.0-only applies from this release onwards.

  Dependency compatibility was re-established for AGPL-3.0 before the change: MIT, BSD-2/3,
  ISC, Apache-2.0, MPL-2.0, PSF-2.0, 0BSD, Zlib, CC0, CC-BY-4.0, Blue Oak 1.0.0, and
  LGPL-3.0-only for `psycopg`. Nothing in the tree is GPL-2.0-only or proprietary.

### Added

- `SOURCE_URL` and a licence field on `GET /api/system`, surfaced in Settings, so a running
  instance offers its source to the people using it. It defaults to this repository, so an
  unmodified deployment complies with no configuration, and it is configurable because an
  operator who modifies doction owes their users *their* source, not this project's.
- A licence-consistency check in `make check`. The licence is declared in seven places and
  one of them, the published repository description, said "MIT licensed" two releases after
  MIT was replaced without anyone noticing. The check reads `pyproject.toml` as the single
  authored source and fails when any other declaration disagrees.

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
