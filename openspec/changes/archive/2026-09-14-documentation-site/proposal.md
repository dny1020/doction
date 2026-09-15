## Why

Everything in `docs/` is written for whoever runs doction. Seven pages cover installing,
configuring, operating, troubleshooting and connecting an agent, and not one of them explains
how to *use* the wiki. A new user is left to discover pages, wikilinks, tags, frontmatter,
search and the graph by experiment.

That gap matters more than a missing chapter, because the behaviour they will meet is not the
behaviour they will guess. Four cases, each measured against the code rather than assumed:

| What a user writes | What happens |
| --- | --- |
| `tags:` followed by `- kamailio` on the next line | no tags at all; the parser takes `key: value` and inline `[a, b]` only |
| `kamailio OR asterisk` | compiles to `'kamailio':* & 'asterisk':*`; `or` is an English stopword and is dropped, so *either* becomes *both* |
| `the` | empty tsquery, zero results |
| `cat` | matches "catalog"; every term is a prefix |

None of that is a defect to fix in this change. It is behaviour to write down, in the same way
the project already documents why the stemmer is English and why the reranker ships disabled.

The API reference has the opposite problem: the schema exists and describes almost nothing. The
application serves `/openapi.json`, `/docs` and `/redoc` publicly, and on the live instance all
three answer 200. Measured on the document it builds today:

| | |
| --- | --- |
| Paths | 51 |
| Operations | 59 |
| Operations with a response schema for a 2xx | 1 |
| Operations carrying a tag | 0 |
| Operations with any description | 21, all in Spanish |
| Declared API version | 0.1.0, while `/health` reports 0.31.8 |

So "generate the reference from the schema the app already serves" would publish 59 endpoints,
ungrouped, describing the shape of one response, under the wrong version number. The README's
hand-written endpoint list covers 25 of the 59, which is the drift that happens when the only
record of a route is prose nobody checks.

## What Changes

- **User documentation.** New pages under `docs/` covering writing a page and the page tree,
  wikilinks and how a broken link is represented, tags, frontmatter, the three search modes and
  the absence of a query syntax, and the graph view. Each documented behaviour is one that was
  measured, including the four above.
- **Documented behaviour is held to the code by tests.** The parsing and search behaviours the
  documentation asserts get tests that fail when the code stops behaving that way. A later
  change that teaches the frontmatter parser block lists then fails a test naming the page that
  has to change, rather than leaving the documentation quietly wrong.
- **The reference is complete against the served surface.** A test compares the documented
  endpoint list against `app.openapi()`, so a route added without documentation fails the gate.
- **The OpenAPI document describes the right software.** The declared version comes from
  `app.version` instead of FastAPI's 0.1.0 default, and operations gain tags and summaries so
  the reference is grouped rather than a flat list of 59.
- **The 21 Spanish route docstrings become English**, because they are published as the API
  descriptions and the project's own convention is English. This is the published surface only;
  the wider mixed-language question stays on the roadmap.
- **A published site.** MkDocs on GitHub Pages, built in CI with `--strict` so a broken internal
  link fails the build. Five links inside `docs/` point above the docs root, at the README,
  `CONTRIBUTING.md`, `SECURITY.md`, `DESIGN.md` and `CHANGELOG.md`; the site build resolves them
  by including those documents rather than rewriting them to external URLs, which would remove
  them from `scripts/check_docs_reachable.py` and weaken one gate to satisfy another.
- **`/docs`, `/redoc` and `/openapi.json` stay public and get documented**, including that
  Swagger UI fetches its assets from a CDN and so does not work on an instance with no outbound
  network.

## Capabilities

### New Capabilities

- `documentation`: what the project owes a reader who wants to use doction rather than operate
  it, that documented behaviour is verified against the code rather than asserted, that the
  reference covers the whole served surface and names the version it describes, and that the
  published site is built from the tracked documentation and fails rather than publishes a
  broken link.

### Modified Capabilities

None. The version the OpenAPI document declares is a property of the reference, so it belongs to
the new capability rather than to `system-status`, which is about what a running deployment
reports to an authenticated client.

## Impact

- **Docs.** New user-facing pages under `docs/`, plus `docs/README.md` gaining them in its index.
- **Code.** `app/main.py`: the `FastAPI(...)` construction gains a version, and the 59 route
  decorators gain tags and summaries. The 21 Spanish docstrings on those routes are translated.
  No route behaviour changes.
- **Tests.** New tests for the documented parsing and search behaviours, and one comparing the
  documented endpoints against the served schema.
- **CI.** A strict site build, and a Pages deployment. GitHub Pages is not currently enabled on
  the repository, so that is a setting the maintainer turns on.
- **Dependencies.** MkDocs goes in its own `docs` dependency group, not `dev`. The Docker `test`
  stage runs `uv sync --frozen`, which installs `dev`, so putting a documentation toolchain
  there would add it to every CI test build for nothing.
- **Roadmap.** The deferred items reach `ROADMAP.md`, as the `contribution` capability requires:
  response models across the handlers, and the Community phase.

## Non-Goals

- **Pydantic response models across the 59 handlers.** Every handler returns `Response` or
  `JSONResponse`, so the schema has no output shapes to infer. Fixing that properly means
  touching every route and is its own change. This one makes the reference grouped, versioned
  and complete in its coverage of endpoints, not in its description of every payload.
- **The Community phase.** Sponsors, a public demo instance and Discussions are the fifth phase
  of the maturity plan and mostly account-level setup, not work in this repository.
- **Resolving the mixed Spanish and English codebase.** Only the docstrings that are published
  as API descriptions are translated here. The convention question stays a roadmap decision.
- **Fixing the documented behaviours.** The frontmatter parser, the absent query syntax and
  prefix matching are described as they are. Changing them is separate work, and the tests added
  here are what will point at the documentation when it happens.
- **Restructuring `docs/` or the README.** The existing operator pages keep their shape; this
  change adds to the index rather than reorganising it.
