## Why

The documentation site is about to be published at `https://doction.site`, and today it is a
stock MkDocs Material site: indigo palette, Roboto, and a home page that is the repository
README. Two of those are more than cosmetic:

- **It is not offline.** Material's default font setting makes every page request Roboto from
  `fonts.googleapis.com` / `fonts.gstatic.com` (measured in the built `site/index.html`). The
  application itself vendors its fonts precisely because it runs on a LAN or VPN with no route
  out; its documentation should not be the one piece that breaks there.
- **It does not look like doction.** The app has a documented visual language (`DESIGN.md`):
  warm paper, green ink, a dark green chrome, Manrope / Instrument Serif / JetBrains Mono. A
  reader moving between the product and its documentation meets two unrelated designs.

The home page is also the wrong entry point for a public site. The README is a long tour
written for someone browsing the repository; a visitor to `doction.site` needs a short page
that says what doction is, how it works, and where to go next — REST API, MCP, installation,
architecture.

## What Changes

- **A landing page, `docs/index.md`,** served at the site root: what doction is, why, how it
  works, the features that exist today (taken from the README and the reference, nothing new),
  a prominent REST + MCP section linking `api.md` and `mcp.md`, self-hosting, architecture, and
  a closing call to action to the installation guide.
- **`docs/README.md` is merged into the landing and removed.** MkDocs maps both files to the
  same page and, under `--strict`, the conflict fails the build; keeping both would also mean
  two indexes of the same pages. Its page map and conventions move into the landing. The two
  links that point at it (`README.md`, `AGENTS.md`) are repointed to `docs/index.md`.
- **The landing is served at `/`, the README at `/introduction/`.** The staged tree keeps its
  shape (so every relative link resolves unchanged); a native MkDocs hook
  (`scripts/docs_hooks.py`, no new dependency) only changes where two pages are written.
- **The site adopts doction's visual language** through one stylesheet in `docs/assets/`
  that maps Material's variables to the app's tokens, in both themes, and a logo that is the
  app's own terminal glyph. No new design system: every value comes from `DESIGN.md` /
  `app/static/style.css`.
- **The site works fully offline.** Material's font loading is turned off; the app's
  already-vendored fonts are copied into the staged tree at build time (no duplicated
  binaries in git). No CDN, no JavaScript added.
- **Navigation is regrouped** into Getting started / Using doction / Developer / Operations /
  Project. Every page that is in the nav today stays in it.
- **`site_url` becomes `https://doction.site/`.** DNS, a `CNAME` file and the Pages settings
  are out of scope.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `documentation`: adds that the published documentation works with no outbound network
  access, carries the product's visual language rather than a generic theme, and opens on a
  page that routes a first-time reader to the REST API, MCP, installation and architecture
  references.

## Impact

- **Docs:** new `docs/index.md`, `docs/assets/doction.css`, `docs/assets/logo.svg`; removed
  `docs/README.md`; link updates in `README.md` and `AGENTS.md`.
- **Build:** `mkdocs.yml` (theme, `extra_css`, `hooks`, nav, `site_url`, a few native Markdown
  extensions: `attr_list`, `md_in_html`); `scripts/build_docs.py` stages the vendored fonts;
  new `scripts/docs_hooks.py`.
- **Not touched:** application code, API, MCP, frontend, CI workflows, dependencies.

## Non-Goals

- DNS, `CNAME`, GitHub Pages configuration or deploy triggers.
- Rewriting the reference pages. They keep their content; only their position in the nav moves.
- A new design system, a frontend framework, or custom JavaScript for the site.
- New product claims, metrics or features beyond what the README and reference already state.
