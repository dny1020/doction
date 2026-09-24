## Context

`scripts/build_docs.py` stages a tree (`build/docs/`) with the root documents at the top and
`docs/` underneath, because pages in `docs/` link to `../README.md`, `../SECURITY.md` and so on,
and MkDocs cannot reach outside `docs_dir`. `--strict` is always on. The `documentation` spec
forbids turning those links into external URLs to make a build pass.

In that staged shape, `README.md` is the site root and `docs/README.md` is `/docs/`. A new
`docs/index.md` would collide with `docs/README.md` (MkDocs logs "Excluding … because it
conflicts", which fails `--strict`) and would be served at `/docs/`, not `/`.

The application's visual language is in `DESIGN.md` and `app/static/style.css`; its fonts are
vendored in `app/static/vendor/fonts/` as woff2.

## Goals / Non-Goals

**Goals:** landing at `/` without changing the staged tree's shape; the app's tokens and fonts
in the site with zero network requests; no new dependency, no JavaScript.

**Non-Goals:** reproducing the app's layout (sidebar gradient, 72px gutter, TOC spacing).
Material's layout stays; only its tokens, type and header change.

## Decisions

### 1. Merge `docs/README.md` into `docs/index.md`

The landing and the docs index answer the same question — where do I go next — so one file does
both. Its page map (the "what each page answers" tables) and its conventions move into the
landing. Alternatives: keep `docs/README.md` and exclude it from staging (breaks the two links
to it, and leaves two indexes to keep in sync); rename the landing to something other than
`index.md` (the user asked for `docs/index.md`, and it would still not be the root).

Cost: GitHub's folder view of `docs/` no longer shows an index automatically. The landing is
plain Markdown and readable on GitHub, and the root README links to it.

### 2. A MkDocs hook moves two pages' output paths

`scripts/docs_hooks.py`, registered with `hooks:` in `mkdocs.yml` (a MkDocs 1.4+ built-in, no
plugin), implements `on_files` and replaces two `File` objects with copies carrying an explicit
`dest_uri`:

- `docs/index.md` → `index.html` (the site root)
- `README.md` → `introduction/index.html`

MkDocs resolves links by **source** path and renders them relative to each page's output URL,
so every relative link in both files keeps resolving and `--strict` keeps checking them. The
hook runs after MkDocs' own README/index conflict check, which is why the root README does not
trip it. Replacing the `File` (instead of assigning `dest_uri`) avoids stale `cached_property`
values for `url` and `abs_dest_path`.

Alternatives: staging `docs/index.md` at the root (its relative links break, or must be
rewritten at build time — a hidden transformation); redirects (needs a plugin, and `/` would
still be the README).

### 3. Theme through tokens, one stylesheet

`docs/assets/doction.css` declares the app's tokens (copied from `DESIGN.md` §2, §8) and maps
Material's `--md-*` variables onto them, once for `[data-md-color-scheme="default"]` and once
for `slate`. Material's `palette` keeps two schemes with `primary: custom` / `accent: custom`
so it emits no colours of its own. The header uses the chrome tokens (`--nav-bg`, `--nav-ink`)
in both themes, as the app's sidebar does: the chrome recedes, the document leads.

Type roles follow `DESIGN.md` §3: Manrope for everything, Instrument Serif only for the page H1,
JetBrains Mono for code. H2/H3 stay in Manrope 600. Code highlighting uses the app's
highlight.js roles (strings `--code-green`, numbers `--code-orange`, comments `--code-muted`,
the rest `--code-text`) through Material's `--md-code-hl-*` variables.

Landing components are Material-native: `attr_list` for `.md-button`, `md_in_html` +
`grid cards` for the section grids. They degrade to readable Markdown on GitHub.

### 4. Fonts: copied at build time, `font: false`

`theme.font: false` removes the Google Fonts request. `build_docs.stage()` copies
`app/static/vendor/fonts/*.woff2` into `build/docs/docs/assets/fonts/`; `doction.css` declares
`@font-face` for them with relative URLs. The app stays the single source of the binaries;
nothing new is committed. Only the Latin and Latin-ext subsets the app already vendors are used.

### 4b. Two more off-site requests, found by scanning the build

- **`repo_url`** makes Material's JavaScript fetch stars and forks from `api.github.com` on
  every page load. It is replaced by `extra.social`, a plain link with no fetch; the header
  repository widget goes away.
- **The README's badges** are remote images (shields.io, GitHub). The hook's
  `on_page_markdown` drops lines that are only a remote image from the site's copy of
  `README.md`; the repository page keeps them. Local screenshots are untouched.

`extra.generator: false` also drops the "Made with Material" footer line.

### 5. Logo

`docs/assets/logo.svg` is the lucide `terminal` glyph the app uses as its brand icon
(`Sidebar.jsx`, `favicon.svg`), stroked in `--nav-green` since it sits on the chrome in both
themes. The favicon is a separate `docs/assets/favicon.svg`: a browser tab is not the chrome, so
it follows the OS scheme (`--green` on light, `--nav-green` on dark), as the app's favicon does.
Hex values are the sRGB conversions of those oklch tokens, since an SVG loaded as an image
cannot read the page's custom properties.

### 6. Navigation

```
Home                  docs/index.md          (/)
Getting started       Introduction (README.md), Installation, Configuration
Using doction         Writing pages, Linking, Tags & metadata, Search, Graph
Developer             REST API, MCP, Architecture
Operations            Operations, Troubleshooting
Project               Contributing, Security, Design, Changelog, Roadmap,
                      AGENTS.md, Code of conduct, How this project plans work
```

`AGENTS.md`, `CODE_OF_CONDUCT.md` and `openspec/README.md` stay in Project: they are in the nav
today and pages link to them; dropping them is not in scope. Material's `navigation.tabs` is not
enabled — five sections fit the sidebar.

## Risks / Trade-offs

- [Material internals] The hook depends on `File(..., dest_uri=...)` and `Files.remove/append`,
  public in MkDocs 1.6. → The hook is ~20 lines; a MkDocs upgrade that breaks it fails `make
  docs` loudly, not silently.
- [Token drift] The docs stylesheet copies token values rather than importing `style.css`
  (which would drag in the whole app stylesheet and absolute `/static/` font URLs). → The copied
  set is small and cites `DESIGN.md`; `DESIGN.md` is already the declared reference.
- [Material 2.0 notice] The build prints Material's MkDocs-2.0 warning. Unrelated to this
  change; the dependency pin stays `mkdocs>=1.6`.

## Migration Plan

Documentation-only. Rollback is reverting the commit. `site_url` changes the canonical URLs in
the built site; nothing is deployed by this change.
