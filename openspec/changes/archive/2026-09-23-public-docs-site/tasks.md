## 1. Build plumbing

- [x] 1.1 Add `scripts/docs_hooks.py` (`on_files`: `docs/index.md` → `index.html`, `README.md` → `introduction/index.html`) and register it under `hooks:` in `mkdocs.yml`; verify `site/index.html` is the landing and `site/introduction/index.html` the README after `make docs`
- [x] 1.2 Stage `app/static/vendor/fonts/*.woff2` into `build/docs/docs/assets/fonts/` from `scripts/build_docs.py`; verify the files are present in `site/docs/assets/fonts/`
- [x] 1.3 Set `theme.font: false`, custom palette, logo/favicon, `extra_css`, `attr_list` + `md_in_html`, and `site_url: https://doction.site/` in `mkdocs.yml`; verify `grep -r "fonts.googleapis\|fonts.gstatic\|cdn" site/` finds nothing

## 2. Visual language

- [x] 2.1 Write `docs/assets/doction.css`: `@font-face` for the vendored faces, app tokens for light and dark (from `DESIGN.md`), Material `--md-*` mapped onto them, header on the chrome tokens, Instrument Serif for H1 only; verify every colour in the file appears in `DESIGN.md`/`style.css`
- [x] 2.2 Add `docs/assets/logo.svg` (lucide terminal glyph in `--nav-green`) and `docs/assets/favicon.svg` (scheme-aware); verify both render

## 3. Content

- [x] 3.1 Write `docs/index.md`: statement + CTAs (Get started, API, MCP), Why doction, Built for humans and coding agents, How it works, Features (only README/reference-documented ones), API + MCP, Self-hosted, Architecture, documentation map (from `docs/README.md`), conventions, Get started; verify each feature claim against README/reference
- [x] 3.2 Delete `docs/README.md` and repoint `README.md:27` and `AGENTS.md:40` to `docs/index.md`; verify `make docs-reachable` passes
- [x] 3.3 Regroup `nav` in `mkdocs.yml` as in design §6, keeping every page currently in the nav; verify `make docs` builds strictly with no "not included in nav" or conflict warnings

## 4. Validation

- [x] 4.1 Run `make docs-reachable`, `make docs` and `openspec validate public-docs-site --strict`; all pass
- [x] 4.2 Scan built HTML for external resource references (`<link>`, `<script>`, `@font-face`, `<img>` pointing off-site); none
- [x] 4.3 Serve with `make docs-serve` and review the landing in light and dark themes, desktop and phone width
