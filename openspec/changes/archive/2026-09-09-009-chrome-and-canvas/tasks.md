# Tasks

Every edit is in `app/static/style.css` plus one amendment to `DESIGN.md`. **No `.jsx` file
changes**, because the DOM does not change.

## 1. Baseline

- [x] 1.1 Baseline captured: **102 screens** at 0.29.0, both themes, 1440/900/390 px, in
      `shots/before009/`.
- [x] 1.2 Extend the contrast verifier with the four chrome grounds (`#12241F`, `#1B302A`,
      `#1B2A26`, `#22352F`) and the code ground `#141917`, and record the starting numbers.

## 2. The chrome palette

- [x] 2.1 `:root` — the `--nav-*` family, 16 values, each carrying its measured ratio in a
      comment the way the existing block does.
- [x] 2.2 `:root` — the `--canvas-*` alias family, `var()` references only, with a comment
      saying the aliases depend on `[data-theme="dark"]` staying *after* `:root` in the file.
- [x] 2.3 `[data-theme="dark"]` — three declarations: `--nav-bg`, `--nav-hover`,
      `--nav-accent-soft`. Note in the comment that `#1B2A26` is pinned by the avatar disc at
      3.06:1 and cannot go lighter.
- [x] 2.4 `.sidebar` — the mapping block. It must include the nine tokens the first draft
      missed: `--accent-press`, `--accent-ring`, `--fg-on-accent`, `--accent-hover`, the four
      shadows, and the danger pair. Without `--accent-press` the active page measures 1.06:1;
      without `--accent-ring` every focus ring in the chrome disappears.
- [x] 2.5 `.sidebar .confirm-dialog` — the canvas re-entry block, scoped to the dialog only.
      `.ws-menu` and `.avatar-menu` stay dark.
- [x] 2.6 Active tree item: filled `--marker` with dark ink. The first solid orange in the
      product.

## 3. The code surface

- [x] 3.1 Split the token: `--code-bg`/`--code-border` keep the light tint and serve inline
      code only; add `--code-block-bg #141917`, `-border`, `-fg #E9E3D8`, `-fg-dim`,
      `-accent`, `-danger`.
- [x] 3.2 Move the six `--syn-*` values to the dark-measured set in `:root`, and delete the
      `[data-theme="dark"]` overrides for code and syntax. One surface, one palette, both
      themes.
- [x] 3.3 `.prose pre` — background, border and **`color`** declared on the block itself, so a
      fence without a language is still legible. `.prose code` untouched.
- [x] 3.4 Re-point all twelve `.hljs*` rules at the block tokens.
- [x] 3.5 Set `--code-block-border` so the inset keeps an edge against the dark canvas, where
      the ground itself measures only 1.02:1.

## 4. The document

- [x] 4.1 Breadcrumbs: data face, uppercase, tracked, tertiary ink. `.crumb-sep` takes
      `--marker` — it is `aria-hidden`, so a non-measuring colour is legitimate there.
- [x] 4.2 Remove `.crumb-current` from the `font-family: inherit` list. Once the breadcrumbs
      *are* the data face, that declaration contradicts itself.
- [x] 4.3 `.page-header .meta` — the metadata strip, scoped strictly. The bare `.meta` has
      thirteen call sites and must not move.
- [x] 4.4 Page header: more air under the title, a thin rule separating header from body.
- [x] 4.5 Table of contents: one carrier for the active state, not two. Today it colours the
      text *and* the rail.
- [x] 4.6 Blockquote as a technical note: left `--marker` rule, sunken ground, no decorative
      quotation marks.

## 5. Record the decisions

- [x] 5.1 `DESIGN.md` §13 — the chrome tokens with their measurements, and the avatar
      constraint on the dark ground. Required by the governance requirement in
      `visual-language`.
- [x] 5.2 `DESIGN.md` §18 — the code block is one surface in both themes, and inline code is
      not that surface.

## 6. Verification

- [x] 6.1 Re-captured all 102 screens and compared against the baseline. Same screen set, no
      layout regressions: the mobile drawer inherits the chrome correctly (it is the same
      element), settings keeps its functional orange rail, and the metadata strip holds at
      390 px without overflowing.
- [x] 6.2 Contrast pass parsed from the stylesheet: canvas, chrome (four grounds) and code.
      **0 failures.** Tightest margins: chrome `--nav-border-strong` 3.04:1, code `--syn-comment`
      5.26:1, canvas `--fg-2` 4.53:1.
- [x] 6.3 Both dialogs captured side by side. The one declared **inside** the sidebar (the row
      menu) now paints in the canvas palette, identical to the one from `ConfirmProvider`.
      Without the re-entry block it would have rendered dark over a light page.
- [x] 6.4 Rendered a page with three cases side by side: a fence **with** a language, a fence
      with **none**, and inline code in a sentence. All three correct in both themes — the
      unhighlighted fence reads at 13.92:1 because the colour is on the block, and inline code
      stayed on the light tint.
- [x] 6.5 Keyboard pass done. The focus ring resolves to the chrome accent inside the sidebar
      and is clearly visible on the dark ground; it keeps the canvas accent outside.
- [x] 6.6 `.sidebar-toggle--show` is a sibling of `<Sidebar>` in the DOM, so it never inherited
      the override and keeps the canvas palette on the light ground. Confirmed in the captures.
- [x] 6.7 Hex literals outside the token blocks: **0**. `rgba()` outside them: **0**. Unused
      tokens: **0**. Two literals I introduced mid-work (`#172522` for the ink on the orange
      fill, and the chrome shadows) were pulled back into the token family.
- [x] 6.8 `npm run check` passes including the local-assets guard; ruff, ruff format and
      pyright all clean.
