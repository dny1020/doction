## Context

See `proposal.md` for why. The constraints that shape the approach:

- `docs/` has seven operator pages and an index. Five links inside it point above the docs root,
  at `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `DESIGN.md` and `CHANGELOG.md`.
- `scripts/check_docs_reachable.py` already fails when a tracked document references an
  untracked file. It skips `https:`, `mailto:` and anchors, so it says nothing about whether a
  link resolves inside a built site.
- The Docker `test` stage runs `uv sync --frozen`, which installs the `dev` group. Anything put
  there is installed on every CI test build.
- Routes are registered on one `APIRouter` in `app/main.py`: 51 paths, 59 operations, no tags,
  no summaries, one response schema, 21 docstrings in Spanish.
- `FastAPI(title="doction", lifespan=lifespan)` takes no version, so the served document
  declares FastAPI's default 0.1.0.
- GitHub Pages is not enabled on the repository. The Pages API returns 404.

## Goals / Non-Goals

Design-level boundaries beyond the proposal's scope:

- **Goal:** the two consistency gates run in the existing `make check` and CI gate, with no new
  gate command to remember.
- **Goal:** the site build is reproducible locally with the same command CI runs.
- **Non-goal:** publishing the interface reference as generated HTML from the schema. The
  reference stays prose that a test holds to the schema. Generated HTML would need the payload
  shapes that the proposal excludes.
- **Non-goal:** versioned documentation. One published version, matching `main`.

## Decisions

### The behaviour tests assert current behaviour, not desired behaviour

The four documented surprises are tested as they are: block-list metadata yields no tags,
`OR` compiles to a conjunction, a stopword-only query is empty, terms are prefixes. A test that
asserted the *desired* behaviour would fail today and would have to be skipped, which is how a
gate becomes decoration.

The consequence is deliberate and is what makes the gate useful: a later change that teaches the
parser block lists breaks these tests. That is the signal, not a nuisance. Each test carries the
path of the page it defends, so the failure says which document to update.

*Alternative considered:* doctests or literate examples inside the documentation. Rejected
because the four behaviours involve Postgres and the compiled query, so the harness would need a
database and the documentation would carry setup noise. The tests live with the other tests and
name the document instead.

### The endpoint-coverage gate compares the reference against `app.openapi()`

The test reads the documented endpoint list out of the reference page and compares it as a set
against the operations `app.openapi()` reports. Both directions fail: an operation with no entry,
and an entry for an operation that is no longer served.

This needs a machine-readable list in a human page. The reference keeps its endpoints in a fenced
block with one operation per line, method first, which is the shape the README already uses, so
the parser is a split rather than a markdown implementation.

*Alternative considered:* generating the reference page from the schema at build time. Rejected
for this change: with one response shape across 59 operations the generated page would be a list
of paths, and a generated page cannot carry the prose that makes a reference worth reading.

*Alternative considered:* comparing against the route table in `app.main` rather than the served
schema. Rejected because the served schema is what a client actually reads, and it is the thing
the requirement is about.

### Tags come from the path prefix, assigned explicitly

Operations get tags by area: tokens, workspaces, pages, search, intelligence, webhooks, uploads,
system. They are written on each decorator rather than derived from the path at import time, so
the grouping is readable where the route is declared and does not depend on a naming convention
holding.

`FastAPI(...)` gains `version=app.version.VERSION`, which is already the single source the image
tag, `/health` and MCP follow.

### MkDocs, in its own dependency group, with the site root at the repository root

MkDocs resolves relative `.md` links natively and `--strict` turns a broken internal link into a
failed build, which is the requirement's verification. It is Python, which the project prefers,
and `uv` already manages the environment.

Two structural choices:

- **Own `docs` dependency group**, not `dev`, so the Docker `test` stage keeps installing four
  tools rather than a documentation toolchain.
- **`docs_dir` covers the root documents too.** The five escaping links stay relative and stay
  checked by the reachability gate. The mechanism is a nav that includes `README.md`,
  `CONTRIBUTING.md`, `SECURITY.md`, `DESIGN.md` and `CHANGELOG.md` from where they are, rather
  than copies. Copies would put one fact in two files, which is the failure the `contribution`
  capability exists to prevent.

*Alternative considered:* plain GitHub Pages with default Jekyll. Rejected: relative `.md` links
break and there is no strict mode, so the requirement would have no verification.

*Alternative considered:* rewriting the five links to `https://github.com/...`. Rejected
explicitly in the spec: it makes the build pass by removing those links from the reachability
gate.

### Publication is a separate workflow from CI

The strict build runs in `ci.yaml` beside the licence, changelog and reachability checks, because
it reads repository files rather than the built image. The Pages deployment is its own workflow
on pushes to `main`, with `pages: write` and `id-token: write` and nothing else, matching how
`release.yaml` takes only the permission it needs.

Enabling Pages is a repository setting the maintainer turns on. The workflow fails until then,
which is the right failure: it says the setting is missing rather than silently publishing
nothing.

## Risks / Trade-offs

- **The behaviour tests will one day fail on a legitimate fix** → That is the design. The
  failure message names the document to update, so the cost is one edit and the benefit is that
  the documentation cannot silently go stale.
- **The endpoint gate parses a human page** → Kept trivial: one fenced block, one operation per
  line, method first. If the format drifts the test fails loudly rather than passing by parsing
  nothing, and it asserts a plausible minimum count for the same reason the reachability test
  does.
- **MkDocs and its theme are new dependencies** → Confined to a non-default group, so they reach
  CI's documentation job and a maintainer's machine, and nothing else. No runtime dependency
  changes.
- **The nav duplicates structure that `docs/README.md` already expresses** → Accepted. The index
  page is what a reader on GitHub sees and the nav is what a reader on the site sees. Keeping
  both means one page can fall out of step with the nav; the strict build catches a link that
  breaks, not an entry that is missing, so this stays a review habit rather than a gate.
- **Translating 21 docstrings touches 21 routes** → No behaviour changes, and the full gate runs
  afterwards. The risk is a typo in a docstring, which is visible in the published reference.

## Migration Plan

No data or schema change, no runtime behaviour change. Deployment is the ordinary path: the
version in `pyproject.toml` is bumped because `publish` runs on every push to `main` and
republishes an unbumped version tag, which the roadmap records as a known defect.

Rollback: the documentation site is static and a previous commit republishes it. The code change
is limited to the FastAPI constructor, route decorators and docstrings, so reverting the commit
is sufficient.

## Open Questions

- Whether the published site gets a custom domain or stays on `github.io`. It changes a DNS
  record and a `CNAME` file, and neither the specs, the approach, nor the tasks depend on the
  answer.
