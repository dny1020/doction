# Visual system

This document describes the design **as implemented**, not as intended. Every value
here is in `app/static/style.css` and can be verified by reading it. When the two
disagree, the defect is in this document before it is in the stylesheet.

Concept: **a drafting set**. Each workspace is a sheet of blueprint in its own colour; the
navigation is drawn on that sheet, with a fine grid, and the document rests on drafting
paper beside it. Pages carry what a drawing carries: a title block with their coordinates,
numbered sections, registration marks on the corners. Diazo yellow marks where you are, in
every workspace. The colour is information: it tells you which workspace you are in before
you read a word.

---

## 1. Intent

doction should feel like a quality technical knowledge system, not a dashboard and not
a generic notes app.

### Principles

1. The document is the visual protagonist; the sheet frames it and never competes.
2. Colour means something: the workspace's hue is where you are, the mark is "you are
   here". Nothing is coloured only to be colourful.
3. The canvas behind a document is flat. The grid belongs to the sheet, never to paper.
4. Depth is drawn, not blurred: a line, a hard offset shadow, a registration mark.
5. Technical content uses monospace, controlled density, and restrained color.
6. Design neither adds nor removes functionality, routes, panels, or information.

### Anti-patterns

Do not implement gradients, glows, blurred or layered soft shadows, glassmorphism, noise
over paper, gradient text, icon tiles above every heading, cards inside cards, pills
except genuinely round ones, "AI" or "MCP" labels as decoration, invented panels or
metrics, neon graphs, or imitations of Notion, GitBook, Obsidian, or Linear.

---

## 2. Color

All color goes through `oklch()`. Contrast ratios are always measured against the
**worst** surface the token appears on, never against the page: a value measured only
against the canvas passes review and then fails on a row with the pointer over it. Every
ratio below is the minimum over the six workspace tones.

### The workspace's hue

`--ws-h` and `--ws-c` are set on `<html>` by `frontend/src/workspaceTone.js`, from the
active workspace's slug, so a workspace keeps its colour on every device without anything
stored. With no workspace (login, register) the stylesheet's default stays: prussian, the
brand's own.

| Tone | `--ws-h` | `--ws-c` |
|---|---|---|
| prussian | 258 | 0.085 |
| petrol | 215 | 0.050 |
| indigo | 285 | 0.085 |
| plum | 335 | 0.085 |
| forest | 155 | 0.065 |
| tile | 30 | 0.085 |

Petrol and forest carry less chroma because at 0.085 the sheet and the accent leave sRGB.
Six is the size of the set on purpose: enough to tell workspaces apart, few enough that each
one was measured.

### Light theme

```css
:root {
  --ws-h: 258;  --ws-c: 0.085;

  /* Surfaces: drafting paper, never pure white */
  --background:     oklch(0.975 0.004 90);
  --surface:        oklch(0.992 0.003 90);
  --surface-muted:  oklch(0.950 0.010 95);
  --surface-inset:  oklch(0.925 0.014 93);
  --nav-bg:         oklch(0.32 var(--ws-c) var(--ws-h));   /* the sheet */

  /* Ink: warm neutral grey */
  --ink:        oklch(0.244 0.027 96);
  --ink-strong: oklch(0.190 0.010 100);
  --ink-muted:  oklch(0.433 0.018 99);
  --ink-subtle: oklch(0.490 0.012 97);   /* 4.5:1 on --surface-inset */

  /* Accent: the workspace's hue, for what gets clicked and what gets read */
  --accent:      oklch(0.45 calc(var(--ws-c) + 0.025) var(--ws-h));  /* ≥5.7:1 on inset */
  --accent-soft: oklch(0.935 0.030 var(--ws-h));
  --accent-ring: oklch(0.45 calc(var(--ws-c) + 0.025) var(--ws-h) / 0.60);

  /* The mark: diazo yellow, the same everywhere */
  --mark:    oklch(0.88 0.14 95);
  --on-mark: oklch(0.22 0.02 258);

  /* Lines */
  --border-subtle:  oklch(0.885 0.007 97);
  --border-default: oklch(0.620 0.012 97);  /* 3:1, delimits controls */

  /* Composite surfaces */
  --callout-bg:     oklch(0.975 0.030 95);
  --code-inline-bg: oklch(0.945 0.020 var(--ws-h));
  --code-bg:        oklch(0.25 calc(var(--ws-c) * 0.75) var(--ws-h));
}
```

White on the accent (the primary button) is ≥6.8:1; the accent on its own soft tint is
≥5.9:1.

### Dark theme

The selector is `[data-theme="dark"]` on `<html>`, **not** `.dark`: the theme toggle,
`index.html`'s anti-flash script, and Preferences all depend on it.

```css
[data-theme="dark"] {
  /* Night paper, tinted by the workspace's hue at chroma ≤0.024 */
  --background:     oklch(0.200 0.015 var(--ws-h));
  --surface:        oklch(0.235 0.020 var(--ws-h));
  --surface-inset:  oklch(0.290 0.024 var(--ws-h));
  --nav-bg:         oklch(0.17 calc(var(--ws-c) * 0.55) var(--ws-h));

  --ink:        oklch(0.920 0.006 255);
  --ink-subtle: oklch(0.735 0.008 255);   /* ≥5.9:1 on --surface-inset */

  --accent:      oklch(0.80 0.09 var(--ws-h));   /* ≥7.3:1 on inset */
  --accent-soft: oklch(0.32 0.045 var(--ws-h));

  --border-subtle:  oklch(0.320 0.025 var(--ws-h));
  --border-default: oklch(0.560 0.035 var(--ws-h));  /* ≥3.0:1 on inset */
  --callout-bg:     oklch(0.270 0.030 90);
  --code-bg:        oklch(0.15 calc(var(--ws-c) * 0.5) var(--ws-h));
}
```

### The mark says "you are here"

The accent is the interactive hue: links, primary actions, focus, inline code, the table of
contents' active rule. The mark has the other job. It is the 3px rule on the active page in
the tree, the rule beside a note, the primary button's offset shadow, the brand glyph on the
sheet, and the strings in a code block. It is the same yellow in every workspace and both
themes, so "you are here" reads the same everywhere.

On paper the mark measures well below 3:1, so it **never carries text there**: it is a rule
or a shadow beside something already said. On the sheet it passes as text (8.9:1), which is
why the brand glyph and the sign-in button can use it.

---

## 3. Typography

Two families, self-hosted at `app/static/vendor/fonts/`. doction is served on a LAN,
over a VPN, and sometimes with no route to the internet, so a request to a CDN would
fail exactly where it's used most.

```css
--font-ui:      'Manrope', 'Inter', system-ui, -apple-system, sans-serif;
--font-display: var(--font-ui);
--font-mono:    'JetBrains Mono', ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace;
--font-data:    var(--font-mono);
```

- **Manrope** — everything that is not code or data, titles included. Vendored at 400,
  500 and 600.
- **JetBrains Mono** — code, paths, shortcuts, timestamps, metadata, section numbers and
  table headers. Never a sentence. That rule is what makes the app read as documentation
  rather than as an application with content inside it.

`Inter` appears in the stack but **is not vendored**: the real fallback is `system-ui`.

### Scale

```css
--text-xs:   0.6875rem;  /* 11px — metadata */
--text-sm:   0.75rem;    /* 12px */
--text-base: 0.875rem;   /* 14px — interface */
--text-nav:  0.8125rem;  /* 13px — navigation */
--text-md:   1rem;       /* 16px — document body */
--text-lg:   1.125rem;   /* 18px */
--text-xl:   1.375rem;   /* 22px */
--text-2xl:  1.75rem;    /* 28px */
--text-3xl:  2.25rem;    /* 36px */
--text-4xl:  3.25rem;    /* 52px — landing hero only */
```

| Element | Family | Size | Line height |
|---|---|---|---|
| Page title | interface, 600 | 28px | 1.2 |
| Document H1 | interface, 600 | 28px | 1.2 |
| H2 | interface, 600 | 22px | 1.3 |
| H3 | interface, 600 | 16px | 1.45 |
| Document body | interface | 16px | 1.78 |
| Interface | interface | 14px | 1.45 |
| Navigation | interface | 13px | 1.3 |
| Metadata, title block, table header | data | 11px | 1.45 |

Weight 400 for text, 500 for controls and navigation, 600 for titles, headings and the
active page. The landing hero is the one place set at 700.

Tracking tightens with size: −0.025em on the page title and document H1, −0.015em on H2
and H3, −0.035em on the hero.

---

## 4. Grid

```css
--sidebar-width:      280px;
--toc-width:          208px;
--topbar-height:       56px;
--document-max-width: 760px;   /* reading measure */
--page-card-width:    960px;   /* the card, at most */
--document-gutter:     72px;
--shell-max-width:   1720px;
```

```text
Viewport
├── Fixed sidebar (the sheet): 280px, pinned to the edge
└── Main area
    ├── Top bar: 56px
    └── Document zone (max. 1720px)
        ├── Left margin: 72px
        ├── Document card: max. 960px
        ├── Gap: 40px
        ├── Table of contents: 208px
        └── Right margin: 24px
```

Composition rules:

- The sidebar **anchors to the window's edge**. The 1720px cap limits the content, not
  the shell.
- Content **starts** 72px from the side. Centering it would make the margin depend on
  the window's width.
- Below 1120px the table of contents is hidden.
- The document sits on one paper card (`.page`): a 1px `--border-subtle` line, 3px radius,
  32px by 48px of padding (20 by 16 under 820px), no shadow, and a 2px accent
  registration mark on its top-left and bottom-right corners.

---

## 5. Spacing

A 4px base, plus one optical step below it.

```css
--space-0:  2px;   --space-1:  4px;   --space-2:  8px;   --space-3: 12px;
--space-4: 16px;   --space-5: 20px;   --space-6: 24px;   --space-7: 28px;
--space-8: 32px;   --space-9: 36px;   --space-12: 48px;  --space-14: 56px;
--space-10: 40px;  --space-16: 64px;  --space-20: 80px;  --space-24: 96px;
```

Document rhythm: 56px above an H2, 36px above an H3, 24px below a paragraph, 28px
around a code block or a note.

---

## 6. Radius, borders and shadows

```css
--radius-xs: 2px;   --radius-sm: 2px;   --radius-md: 3px;   --radius-lg: 3px;
--radius-xl: 4px;   --radius-pill: 999px;

--shadow-hard:       3px 3px 0 var(--mark);
--shadow-hard-press: 1px 1px 0 var(--mark);
--shadow-hard-lift:  4px 4px 0 var(--mark);
```

A drawing has almost square corners: controls 2px, cards and code 3px, modals 4px. The pill
survives only on what's genuinely round: avatars and theme dots.

The primary button carries a **hard offset shadow** in the mark, never a blurred one, and
presses into the sheet: it moves 2px and the shadow shrinks to 1px. On a pointer that can
hover it lifts 1px the other way and the shadow grows to 4px. doction.site's primary button
does the same. Menus, popovers and
modals keep their soft floating shadows (`--shadow-1/2/3`); a card that rests on the page
gets a line, not a shadow.

---

## 7. Material

The **canvas** is a flat tone: drafting paper in the light theme, night paper tinted by the
workspace in the dark one, with nothing painted over it. The **sheet** — the sidebar, the
sign-in panel, the documentation site's header and landing hero — carries a 16px drafting
grid at 6% of its own ink. The grid never reaches the document, a table, a form, the editor
or a modal.

---

## 8. Chrome

Navigation is **the sheet** (`--nav-bg`): the workspace's hue, dark in both themes. A region
that changes material redefines the palette's token *names* in its own scope rather than
restating rules: `.sidebar, .auth-sheet` map `--ink`, `--ink-muted`, `--border-*`,
`--surface*`, `--accent`, `--danger` and the rest onto `--sheet-*` values, so every shared
component inside renders correctly on the sheet without a rule of its own. The menus that
open inside the sidebar take the sheet's palette with them.

Measured on the sheet's worst ground, the hovered row, in all six tones: ink ≥9.0:1, muted
ink ≥5.4:1 (≥7.8:1 dark), control boundary ≥4.0:1 (≥3.4:1 dark).

The active page is a **filled row** with the mark's 3px rule on its left edge, weight 600
and the strong ink, so colour never travels alone. Hover uses the same fill without the rule
or the weight. The rule is drawn from its middle when a row becomes the current page.

### The brand mark

The terminal glyph (`>_`, lucide `terminal`) is **the mark's yellow on the sheet**, in the
sidebar, on the sign-in panel and in the documentation site's header. In a browser tab and
on a home screen it is the same glyph on a prussian square, so it reads on light and dark
tabs alike. SVGs used as images and PNGs cannot read custom properties, so those files carry
the tokens' sRGB values: `#14325d` (the default sheet) and `#f4d660` (the mark). The
manifest's colours are the sheet; the address bar follows the canvas, `#f8f7f4` light and
`#12161d` dark.

Everywhere it is drawn, the glyph has a 2.5 stroke: 22px in the sidebar, 26px on the sign-in
panel, 24px in the docs header and the favicon. When the brand first appears, the prompt's
cursor blinks twice and then holds.

---

## 9. Document

- A compact header inside the document's card: breadcrumbs, the title at 28px, the
  **title block**, then the page's actions on the right, closed by a line. Edit is the
  primary action; New subpage and History are visible beside it; Delete lives in the ⋯ menu
  and is confirmed, so the irreversible action is never the easiest one to hit.
- The **title block** is a drawing's: ruled cells in the data face, each with an 11px
  uppercase label — the page's slug, its last update to the minute, and its last editor.
  Under 820px the cells stack.
- The document's first block begins within 160px of the top of the title. Its own top
  margin is dropped, because the header already closes with a line.
- The top bar shows the page title (on desktop) and its ⋯ menu (at every width) only after
  the page's own title has scrolled under it. Until then it draws no bottom rule either.
- Breadcrumbs in the data face, uppercase, 11px; the separator is the accent and
  `aria-hidden`.
- **H2 sections are numbered** `01`, `02`… in the data face and the accent, by a CSS
  counter: a numbering that no markdown has to carry.
- Links in the accent, underlined. A wikilink to a page that doesn't exist yet is painted
  dim and dashed: something to be written, not an error.
- No markdown section sits inside a container.

### Notes

A 3px mark rule over a whisper of the same yellow, square corners, no italics.

### Tables

Rules between rows only, no vertical lines and no header fill. The header is set like the
title block: data face, 11px, uppercase, muted ink, closed by a `--border-default` line.
Cells are 14px with tabular figures. doction.site does the same.

### Code

The **block** is a piece of the sheet: `--code-bg`, dark in both themes, with strings in the
mark and numbers in a light accent. Text ≥13:1, comments ≥7.4:1 and strings ≥11:1 against
it, in all six tones. Its text color is declared on the block, not on the highlighter,
because highlighting only applies to fences that declare a language.

**Inline code** doesn't share that surface. It is the accent on a tint of its own hue,
typography inside a sentence.

---

## 10. Table of contents

208px wide, sticky, 40px from the card. Interface typography at 13px and the label at 12px.
No card and no floating background. The active state has a single carrier: a 2px accent
rule, with the text stepping up to the primary ink.

---

## 11. Controls

```css
.btn-primary { height: 32px; background: var(--accent); box-shadow: var(--shadow-hard); }
.btn         { height: 32px; background: var(--surface); border: 1px solid var(--border-default); }
.field       { min-height: 36px; background: var(--input-bg); border: 1px solid var(--border-default); }
.field:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-ring); }
```

The focus ring is the accent at 60% (55% dark), so it follows the workspace; on the sheet it
is the mark at 70%. A focus indicator needs 3:1 against both the control and what is behind
it, and every proposal to lower it goes against a correction made twice already.

### Touch

On a coarse pointer every field is 16px, the title excepted, or Safari zooms in on focus and
never zooms back; small buttons keep their look and get a 44px hit area from a
pseudo-element. Installed to the home screen (`display-mode: standalone`) the page has no
rubber-band or pull-to-refresh.

### Scrollbar

Custom, not the system's. Defined once and inherited by the tree, the workspaces menu and
the table of contents, so it follows the theme.

### Sign-in

Login and register are half sheet, half paper. The sheet (prussian, the brand's tone) holds
the wordmark, one sentence, and a stamp in the data face; the paper holds the form. Under
820px the sheet sits above the form.

### Theme toggle

One component (`ThemeToggle.jsx`) in the sidebar footer, on login and on register, next to
the language toggle. It shows the theme it switches to: lucide `moon` in light, `sun` in dark.
doction.site's header uses the same two lucide icons, so the control reads the same on both.

### One control, one action

With the sidebar collapsed, only **one** button to expand it is visible: the one in the top
bar.

---

## 12. Graph

Nodes with no glow and no effects. The resting node is a surface with an accent outline;
the hovered one fills with the accent, and the fill and the label's ink carry the state.
Relationships are cartographic lines, not constellations.

An **orphan** page dims instead of alarming, because it isn't an error; a **broken** link is
drawn dashed in the danger tone, because here it genuinely is a finding.

---

## 13. Motion

```css
--ease-standard: cubic-bezier(0.2, 0, 0, 1);
--duration-fast: 120ms;   /* color, background, border, the button press */
--duration-base: 180ms;   /* shadow, opacity, a theme or workspace change */
--duration-slow: 240ms;   /* the sidebar, the sign-in entrance */
```

Color, background, border, shadow and opacity, plus the 1–2px translate of a pressed or
lifted button. The motions with a purpose:

- **The sidebar closes like a drawer.** Its width animates over contents of fixed width, so
  nothing rewraps on the way, and the page moves with it on the same timing. It turns hidden
  only once closed, which also takes it out of the tab order. On mobile it slides in and out.
- **Switching workspace fades the sheet** into the new tone.
- **Content rises 6px** on navigation; search results stagger 30ms per row. On login and
  register the sheet's lines rise in order, then the form. The confirm dialog rises in.
- The current page's mark rule is drawn, and the brand's cursor blinks twice.

No bounces, continuous animations or parallax. `prefers-reduced-motion: reduce` turns all of
it into an instant change.

---

## 14. How it's verified

These rules are checked, not trusted.

- **Contrast over every tone**, measured from the token values for all six workspace hues,
  in both themes, against each token's worst ground — canvas, card, inset, the sheet and its
  hovered row, the code block, and the notes' background. Zero failures is the condition
  for shipping.
- **Gamut**: a color outside sRGB gets remapped by the browser to something the author
  didn't choose, so a ratio calculated on the original value describes a color no one
  sees. That is why petrol and forest carry less chroma.
- **No color literal outside the token blocks**, and no token with zero callers.
- **SVGs are XML.** A comment may not contain `--`; a token name written into an SVG's
  comment made the favicon unparseable, and an image that fails to parse fails silently.
- **In a real browser, not only in screenshots**, at desktop and phone width, both themes.
- **Rebuild before measuring.** The stylesheet is linked with a content hash that only
  changes on build; without `make build-web` the measurement describes the previous
  stylesheet.
