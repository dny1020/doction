# Visual system

This document describes the design **as implemented**, not as intended. Every value
here is in `app/static/style.css` and can be verified by reading it. When the two
disagree, the defect is in this document before it is in the stylesheet.

Concept: a quiet notebook. The canvas is a flat off-white (graphite in dark theme), the
document rests on a white card, and the sidebar is the same material one step deeper. The
reference is Memos (usememos/memos): its surfaces, sidebar and card shape were measured and
adapted here, not its code. Restrained, with no look of a generated template.

---

## 1. Intent

doction should feel like a quality technical knowledge system, not a dashboard and not
a generic notes app.

### Principles

1. The document is the visual protagonist.
2. Few visual decisions, but deliberate ones.
3. The canvas is flat; depth comes from a card resting on it, drawn with a line.
4. Cards hold units of content (the document, a capture); inside them hierarchy is
   built with typography, rhythm, alignment and tone, never with nested cards.
5. Technical content uses monospace, controlled density, and restrained color.
6. Design neither adds nor removes functionality, routes, panels, or information.

### Anti-patterns

Do not implement purple or electric-blue gradients, visible-noise backgrounds,
parchment or retro aesthetics, cards inside cards, borders wider than 8px, pills
except genuinely round ones, large or repeated shadows, glassmorphism, "AI" or "MCP"
labels as decoration, invented panels or metrics, neon graphs, or imitations of Notion,
GitBook, Obsidian, or Linear. Memos is the one deliberate reference (see the concept above):
its tones and shapes, adapted, never its components or its code.

---

## 2. Color

All color goes through `oklch()`. Contrast ratios are always measured against the
**worst** surface the token appears on, never against the page: a value measured only
against the canvas passes review and then fails on a row with the pointer over it.

### Light theme

```css
:root {
  /* Surfaces: off-white canvas, white cards */
  --background:     oklch(0.982 0.005 95);
  --surface:        oklch(1 0 0);
  --surface-raised: oklch(1 0 0);
  --surface-muted:  oklch(0.950 0.010 95);
  --surface-inset:  oklch(0.925 0.014 93);
  --nav-bg:         oklch(0.966 0.008 99);   /* the sidebar */

  /* Ink: warm neutral grey */
  --ink:        oklch(0.244 0.027 96);
  --ink-strong: oklch(0.190 0.010 100);
  --ink-muted:  oklch(0.433 0.018 99);
  --ink-subtle: oklch(0.490 0.012 97);   /* 4.5:1 on --surface-inset */

  /* Functional green: what gets clicked and what gets read */
  --green:       oklch(0.365 0.055 151);
  --green-hover: oklch(0.315 0.052 151);
  --green-soft:  oklch(0.915 0.030 151);
  --green-ring:  oklch(0.365 0.055 151 / 0.60);  /* ≥3.25:1 composited */

  /* Orange: signal, not a dominant color */
  --orange:     oklch(0.635 0.155 52);   /* decoration */
  --orange-ink: oklch(0.515 0.133 52);   /* 4.50:1, marks that inform */

  /* Lines */
  --border-subtle:  oklch(0.885 0.007 97);
  --border-default: oklch(0.620 0.012 97);  /* 3:1, delimits controls */

  /* State */
  --danger:      oklch(0.525 0.185 28);
  --danger-soft: oklch(0.911 0.046 28);
  --ok-soft:     oklch(0.981 0.030 148);

  /* Composite surfaces, precomputed */
  --callout-bg: oklch(0.960 0.022 63.2);
  --input-bg:   oklch(1 0 0);

  /* Code: a quiet inset with the document's own inks */
  --code-inline-bg: oklch(0.915 0.030 151);
  --code-bg:        oklch(0.960 0.008 95);
  --code-text:      oklch(0.244 0.027 96);
  --code-muted:     oklch(0.490 0.012 97);
  --code-green:     oklch(0.365 0.055 151);
  --code-orange:    oklch(0.515 0.133 52);
}
```

### Dark theme

The selector is `[data-theme="dark"]` on `<html>`, **not** `.dark`: the theme toggle,
`index.html`'s anti-flash script, and Preferences all depend on it.

```css
[data-theme="dark"] {
  --background:     oklch(0.240 0.008 255);
  --surface:        oklch(0.275 0.009 255);
  --surface-raised: oklch(0.320 0.010 255);
  --surface-muted:  oklch(0.300 0.010 255);
  --surface-inset:  oklch(0.330 0.012 255);
  --nav-bg:         oklch(0.210 0.009 255);

  --ink:        oklch(0.920 0.006 255);
  --ink-strong: oklch(0.970 0.004 255);
  --ink-muted:  oklch(0.790 0.007 255);
  --ink-subtle: oklch(0.735 0.008 255);  /* 4.5:1 on --surface-inset */

  --green:      oklch(0.780 0.090 145);
  --green-ring: oklch(0.780 0.090 145 / 0.55);  /* ≥3.36:1 composited */
  --orange:     oklch(0.760 0.135 57);

  --border-subtle:  oklch(0.360 0.010 255);
  --border-default: oklch(0.590 0.012 255);  /* 3:1 */
  --code-bg:        oklch(0.215 0.008 255);
}
```

**Dark is graphite, not charcoal.** A soft blue-grey at chroma 0.008–0.012 keeps long
reading comfortable and leaves green as the only hue that says something: accent, active
element, and code.

### Orange marks a note

Green is the interactive and identity hue: links, the brand mark, and "you are here" — the
active page, table-of-contents entry and settings section all carry a 2px green rule. Orange
has one job left: the rule beside a quotation or an admonition, which says "this is set
apart from the text". The application and the documentation site assign the two the same way.

On paper the orange measures 2.48:1, below the 3:1 an informative mark needs.
That's why there are two:

- `--orange` **decorates** and can go unseen: a rule, a mark next to a word that is
  already written. If no one loses anything by not seeing it, this is the one.
- `--orange-ink` **informs**, and that's why it measures 4.50:1.

The question that decides which one to use is what whoever doesn't see the mark loses.

On graphite, orange does reach the ratio, so in dark theme a single value covers both
roles. The rule doesn't change between themes; what changes is how many shades it takes
to meet it.

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
- **JetBrains Mono** — code, paths, shortcuts, timestamps and metadata. Never a
  sentence. That last rule is what makes the app read as documentation rather than as
  an application with content inside it.

Titles used to be set in Instrument Serif. Next to Memos-style cards the serif read as a
second voice, so the title is now set apart by size and weight alone, here and on the
documentation site, and the serif is no longer vendored.

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
| Metadata | data | 11px | 1.45 |

The page title uses the same 28px step as the document H1. 52px is reserved for a landing
hero.

Weight 400 for text, 500 for controls and navigation, 600 for titles and headings. Avoid 700.

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
├── Fixed sidebar: 280px, pinned to the edge
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
  the shell: applied to the whole thing, the panel ended up floating with the
  background peeking out to its left.
- Content **starts** 72px from the side. Centering it would make the margin depend on
  the window's width.
- The table of contents sits 40px from the card and 24px from the right edge. The card's
  line already separates it from the text, so the old 96px of whitespace only made the
  card narrower; the card takes whatever width the window leaves (816px at 1440).
  Below 1120px the table of contents is hidden.
- The document sits on one white card (`.page`): a 1px `--border-subtle` line, 8px radius,
  32px by 48px of padding (20 by 16 under 820px), no shadow. It grows to 960px, so on a wide
  window the text runs about 860px.

---

## 5. Spacing

A 4px base, plus one optical step below it.

```css
--space-0:  2px;   --space-1:  4px;   --space-2:  8px;   --space-3: 12px;
--space-4: 16px;   --space-5: 20px;   --space-6: 24px;   --space-7: 28px;
--space-8: 32px;   --space-9: 36px;   --space-12: 48px;  --space-14: 56px;
--space-10: 40px;  --space-16: 64px;  --space-20: 80px;  --space-24: 96px;
```

`--space-0` exists because there are seventeen places with 2px gaps under 11 and
12px text, and bumping them to 4 fattens every badge and every inline mark.

Document rhythm: 56px above an H2, 36px above an H3, 24px below a paragraph, 28px
around a code block or a note.

---

## 6. Radius, borders and shadows

```css
--radius-xs: 4px;   --radius-sm: 6px;   --radius-md: 8px;   --radius-lg: 8px;
--radius-xl: 12px;  --radius-pill: 999px;

--shadow-1: 0 1px 2px  oklch(0.20 0.02 150 / 0.05);
--shadow-2: 0 4px 14px oklch(0.20 0.02 150 / 0.07);
--shadow-3: 0 12px 32px oklch(0.20 0.02 150 / 0.10);
```

Controls 6px; cards and code 8px; modals 12px. The pill survives only on what's genuinely
round: avatars and theme dots.

Shadows are for what floats — menus, popovers, modals. A card that rests on the page gets
a line, not a shadow.

---

## 7. Material

The canvas is a **flat tone**: off-white in the light theme, graphite in the dark one, with
nothing painted over it. **No gradients, sheens, noise, grain, textures, or paper
images.** Depth comes from white cards resting on it, each drawn with a line.

---

## 8. Chrome

Navigation is **the canvas one step deeper** (`--nav-bg`), separated from the content by a
1px `--border-subtle` line. It used to be a dark green panel in both themes; next to
Memos-style cards that read as a second application, so the sidebar now uses the same
tokens as everything else and needs no palette of its own.

The active page is a **filled row**: `--surface-inset` behind it, weight 500 and the strong
ink, so colour never travels alone. Hover uses the same surface without the weight. The
workspace selector is a labelled button with no boundary until hovered; the search field
keeps its 3:1 boundary because it is a field.

In both themes the sidebar is a shade darker than the canvas (0.966 against 0.982 in
light, 0.210 against 0.240 in dark), so it recedes.

### The brand mark

The terminal glyph (`>_`, lucide `terminal`) is **green on every surface**: `--green` in the
sidebar; the light-on-dark green in the documentation site's header and in the
installable-app icons, which keep the earlier dark green ground; and in a browser tab, the
dark green on a light tab and the light green on a dark one. SVGs used as images and PNGs
cannot read custom properties, so those files carry the tokens' sRGB values (`#27472f`,
`#88bc89`, `#030d05`), read from the browser rather than converted by hand.

It used to be orange in the sidebar and blue in the favicon, a leftover of an earlier palette.
One colour means the tab, the home screen, the application and its documentation are
recognisably the same product.

---

## 9. Document

- A compact header inside the document's card: breadcrumbs, the title at 28px, then one row with the metadata on
  the left and the page's actions on the right, closed by a line. Edit, New subpage and
  History are visible there; Delete lives in the ⋯ menu beside them and is confirmed, so
  the irreversible action is never the easiest one to hit.
- The document's first block begins within 160px of the top of the title. Its own top
  margin is dropped, because the header already closes with a line.
- The top bar shows the page title (on desktop) and its ⋯ menu of page actions (at every
  width) only after the page's own title has scrolled under it, so a page never says its
  name, or offers its actions, twice on one screen.
- Breadcrumbs in the data face, uppercase, 11px. Their separator carries the decorative
  orange: it's `aria-hidden`, so it owes no one contrast.
- Metadata strip with the two fields that exist, last-updated date and last editor.
  There's no owner and no reading time.
- Links in green. A wikilink to a page that doesn't exist yet is painted dim: there,
  it's something to be written, not an error.
- Dividers: a thin line and plenty of vertical space.
- No markdown section sits inside a container.

### Notes

2px orange left rule over a faint warm background, no italics: whole paragraphs in
italics read worse.

### Code

The **block** is a quiet inset on the card: `--code-bg` with a 1px `--border-subtle` line
and an 8px radius, in the document's own inks. In dark theme it is a shade darker than the
card. Its text color is declared on the block, not on the highlighter: highlighting only
applies to fences that declare a language.

**Inline code** doesn't share that surface. It's typography inside a sentence, green on
faint green.

Highlighting is reduced to three signals over the code's ink: dimmed comments, strings
in green, numbers in orange. Everything else stays `--code-text`.

---

## 10. Table of contents

208px wide, sticky position, 40px from the card. Interface typography at 13px, the
navigation step, and the label at 12px. No card and no floating background.

The active state has **a single carrier**: the green rule. The text steps up to the
primary ink, which is already enough contrast without relying on color. Saying it with
color and with the rule at once turns up the volume of the whole table of contents.

---

## 11. Controls

```css
.button-primary  { height: 32px; background: var(--green); border-radius: var(--radius-sm); /* 6px */ }
.button-secondary{ height: 32px; background: transparent; border: 1px solid var(--border-default); }
.input           { min-height: 36px; background: var(--input-bg); border: 1px solid var(--border-default); }
.input:focus     { border-color: var(--green); box-shadow: 0 0 0 3px var(--green-ring); }
```

The focus ring measures at least 3.25:1 in light and 3.36:1 in dark, composited over the
canvas, the card and the sidebar. A focus indicator needs
3:1, and this one has had to be raised twice for falling short: any proposal to lower
it goes against a deliberate correction.

### Scrollbar

Custom, not the system's. Defined once and inherited by the three places that scroll —
the tree, the workspaces menu, and the table of contents — so it follows the theme. 8px wide, thumb rounded to its own width and thinner than the track
thanks to a transparent border.

### One control, one action

With the sidebar collapsed, only **one** button to expand it should be visible: the one
in the top bar. The floating button that used to exist for that was removed once the
bar became visible at every width.

---

## 12. Graph

Nodes with no glow and no effects. The resting node is a surface with a green outline;
the active one fills with green and carries a minimal orange signal on the outline.
Relationships are cartographic lines, not constellations. The background uses soft
tonal depth, no grids.

Two states specific to doction that the general vocabulary doesn't name: an **orphan**
page dims instead of alarming, because it isn't an error, just something no one has
connected yet; a **broken** link is drawn dashed in the danger tone, because here it
genuinely is a finding.

---

## 13. Motion

```css
--ease-standard: cubic-bezier(0.2, 0, 0, 1);
--duration-fast: 120ms;   /* color, background, border */
--duration-base: 180ms;   /* shadow, opacity */
--duration-slow: 240ms;   /* the mobile drawer */
```

Only color, background, border, shadow and opacity. No bounces, dramatic entrances,
continuous animations, or parallax.

---

## 14. How it's verified

These rules are checked, not trusted.

- **Contrast measured from the stylesheet itself**, not from a hand-written table: the
  token blocks are parsed and every pair is calculated against each theme's floors —
  canvas, card, inset, sidebar, the code block, and the notes' composited background. Zero failures is the condition for shipping.
- **Gamut**: a color outside sRGB gets remapped by the browser to something the author
  didn't choose, so a ratio calculated on the original value describes a color no one
  sees.
- **No color literal outside the token blocks**, and no token with zero callers.
- **In a real browser, not only in screenshots.** Two defects from the last round — a
  diagonal band in the material and an oversaturated brown note — were obvious on
  screen and weren't caught in 102 automated screenshots.
- **Rebuild before measuring.** The stylesheet is linked with a content hash that only
  changes on build; without `make build-web` the measurement describes the previous
  stylesheet.
