# Visual system

This document describes the design **as implemented**, not as intended. Every value
here is in `app/static/style.css` and can be verified by reading it. When the two
disagree, the defect is in this document before it is in the stylesheet.

Concept: modern technical notebook. Warm, editorial, restrained, with no look of a
generated template.

---

## 1. Intent

doction should feel like a quality technical knowledge system, not a dashboard and not
a generic notes app.

### Principles

1. The document is the visual protagonist.
2. Few visual decisions, but deliberate ones.
3. Material is felt more than it is seen.
4. Hierarchy is built with typography, rhythm, alignment and tone, not with cards.
5. Technical content uses monospace, controlled density, and restrained color.
6. Design neither adds nor removes functionality, routes, panels, or information.

### Anti-patterns

Do not implement purple or electric-blue gradients, visible-noise backgrounds,
parchment or retro aesthetics, everything inside cards, borders wider than 8px, pills
except genuinely round ones, large or repeated shadows, glassmorphism, "AI" or "MCP"
labels as decoration, invented panels or metrics, neon graphs, or imitations of Notion,
GitBook, Obsidian, or Linear.

---

## 2. Color

All color goes through `oklch()`. Contrast ratios are always measured against the
**worst** surface the token appears on, never against the page: a value measured only
against the canvas passes review and then fails on a row with the pointer over it.

### Light theme

```css
:root {
  /* Surfaces: warm technical paper */
  --background:     oklch(0.965 0.012 94);
  --surface:        oklch(0.982 0.008 92);
  --surface-raised: oklch(0.994 0.004 90);
  --surface-muted:  oklch(0.936 0.016 91);
  --surface-inset:  oklch(0.908 0.020 91);

  /* Ink: dark green, not blue */
  --ink:        oklch(0.245 0.030 151);  /* 15.00:1 */
  --ink-strong: oklch(0.185 0.026 150);
  --ink-muted:  oklch(0.445 0.025 151);  /*  7.01:1 */
  --ink-subtle: oklch(0.501 0.020 151);  /*  4.50:1 */

  /* Functional green: what gets clicked and what gets read */
  --green:       oklch(0.365 0.055 151);  /* 9.69:1 */
  --green-hover: oklch(0.315 0.052 151);
  --green-soft:  oklch(0.915 0.030 151);
  --green-ring:  oklch(0.365 0.055 151 / 0.60);  /* 3.03:1 */

  /* Orange: signal, not a dominant color */
  --orange:     oklch(0.635 0.155 52);   /* decoration */
  --orange-ink: oklch(0.515 0.133 52);   /* 4.50:1, marks that inform */

  /* Lines */
  --border-subtle:  oklch(0.875 0.018 90);
  --border-default: oklch(0.600 0.024 90);  /* 3.00:1, delimits controls */

  /* State */
  --danger:      oklch(0.525 0.185 28);  /* 4.51:1 */
  --danger-soft: oklch(0.911 0.046 28);
  --ok-soft:     oklch(0.981 0.030 148);

  /* Composite surfaces, precomputed */
  --callout-bg: oklch(0.960 0.022 63.2);
  --input-bg:   oklch(0.987 0.007 97.3);

  /* Code */
  --code-inline-bg: oklch(0.915 0.030 151);
  --code-bg:        oklch(0.205 0.024 151);
  --code-text:      oklch(0.930 0.018 96);
  --code-muted:     oklch(0.690 0.025 120);
  --code-green:     oklch(0.760 0.110 142);
  --code-orange:    oklch(0.780 0.130 61);
}
```

### Dark theme

The selector is `[data-theme="dark"]` on `<html>`, **not** `.dark`: the theme toggle,
`index.html`'s anti-flash script, and Preferences all depend on it.

```css
[data-theme="dark"] {
  --background:     oklch(0.170 0.006 150);
  --surface:        oklch(0.205 0.007 150);
  --surface-raised: oklch(0.238 0.008 150);
  --surface-muted:  oklch(0.238 0.008 150);
  --surface-inset:  oklch(0.265 0.008 150);

  --ink:        oklch(0.925 0.016 93);   /* 12.24:1 */
  --ink-strong: oklch(0.975 0.007 93);
  --ink-muted:  oklch(0.720 0.018 100);  /*  6.16:1 */
  --ink-subtle: oklch(0.639 0.018 110);  /*  4.54:1 */

  --green:      oklch(0.745 0.090 145);  /* 6.97:1 */
  --green-ring: oklch(0.745 0.090 145 / 0.53);  /* 3.00:1 */
  --orange:     oklch(0.735 0.135 57);   /* 6.27:1 */

  --border-default: oklch(0.538 0.025 150);  /* 3.03:1 */
  --code-bg:        oklch(0.115 0.014 150);
}
```

**Dark chroma is deliberately low.** At 0.018–0.023 the charcoal reads as green, and
combined with the chrome, the whole app ends up tinted. Green is reserved for where it
says something: accent, active element, and code.

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

On charcoal, orange does reach the ratio, so in dark theme a single value covers both
roles. The rule doesn't change between themes; what changes is how many shades it takes
to meet it.

---

## 3. Typography

Three families, self-hosted at `app/static/vendor/fonts/`. doction is served on a LAN,
over a VPN, and sometimes with no route to the internet, so a request to a CDN would
fail exactly where it's used most.

```css
--font-ui:      'Manrope', 'Inter', system-ui, -apple-system, sans-serif;
--font-display: 'Instrument Serif', Georgia, 'Times New Roman', serif;
--font-mono:    'JetBrains Mono', ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace;
--font-data:    var(--font-mono);
```

- **Manrope** — navigation, body, forms, buttons, tables and controls. Vendored at
  400, 500 and 600.
- **Instrument Serif** — only the page title and the document's H1. One weight.
- **JetBrains Mono** — code, paths, shortcuts, timestamps and metadata. Never a
  sentence. That last rule is what makes the app read as documentation rather than as
  an application with content inside it.

`Inter` appears in the stack but **is not vendored**: that would be paying twice for a
case that can't happen, since both faces would come from the same origin. The real
fallback is `system-ui`.

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
--text-4xl:  3.25rem;    /* 52px */
```

| Element | Family | Size | Line height |
|---|---|---|---|
| Page title | display | 52px | 1.03 |
| Document H1 | display | 36px | 1.15 |
| H2 | interface, 600 | 22px | 1.3 |
| H3 | interface, 600 | 16px | 1.45 |
| Document body | interface | 16px | 1.78 |
| Interface | interface | 14px | 1.45 |
| Navigation | interface | 13px | 1.3 |
| Metadata | data | 11px | 1.45 |

H2 and H3 use the interface face, not the serif: at 22 and 16px the serif's x-height is
too small to carry weight as a heading.

Weight 400 for text, 500 for controls and navigation, 600 only for interface headings.
Avoid 700.

---

## 4. Grid

```css
--sidebar-width:      280px;
--toc-width:          220px;
--topbar-height:       56px;
--document-max-width: 760px;
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
        ├── Reading column: max. 760px
        ├── Gap: 96px
        └── Table of contents: 220px
```

Composition rules:

- The sidebar **anchors to the window's edge**. The 1720px cap limits the content, not
  the shell: applied to the whole thing, the panel ended up floating with the
  background peeking out to its left.
- Content **starts** 72px from the side. Centering it would make the margin depend on
  the window's width.
- The table of contents breathes at 96px from the document. It's small, gray text next
  to reading text, and whitespace is the only thing that separates them.
- No giant white card around the document.

---

## 5. Spacing

A 4px base, plus one optical step below it.

```css
--space-0:  2px;   --space-1:  4px;   --space-2:  8px;   --space-3: 12px;
--space-4: 16px;   --space-5: 20px;   --space-6: 24px;   --space-7: 28px;
--space-8: 32px;   --space-9: 36px;   --space-12: 48px;  --space-14: 56px;
--space-16: 64px;  --space-20: 80px;  --space-24: 96px;
```

`--space-0` exists because there are seventeen places with 2px gaps under 11 and
12px text, and bumping them to 4 fattens every badge and every inline mark.

Document rhythm: 56px above an H2, 36px above an H3, 24px below a paragraph, 28px
around a code block or a note.

---

## 6. Radius, borders and shadows

```css
--radius-xs: 2px;   --radius-sm: 4px;   --radius-md: 6px;   --radius-lg: 8px;
--radius-pill: 999px;

--shadow-1: 0 1px 2px  oklch(0.20 0.02 150 / 0.05);
--shadow-2: 0 4px 14px oklch(0.20 0.02 150 / 0.07);
--shadow-3: 0 12px 32px oklch(0.20 0.02 150 / 0.10);
```

Standard interface radius 4px; code 6px; modals 8px. The pill survives only on what's
genuinely round: avatars and theme dots.

Shadows are for what floats — menus, popovers, modals. A surface that rests on the page
gets a line, not a shadow.

---

## 7. Material

Material is tonal, not textural. **No noise, visible grain, textures, or paper
images.**

```css
--material: linear-gradient(
  112deg,
  var(--material-sheen) 0%,
  transparent 32%,
  var(--material-warm) 100%
);
```

Strength changes between themes: on charcoal, the same value that works on paper
paints a hard-edged diagonal band across the document instead of just being felt.

| | light | dark |
|---|---|---|
| `--material-sheen` | 0.18 | 0.030 |
| `--material-warm` | 0.05 | 0.018 |

---

## 8. Chrome

Navigation **is not paper**: it's a region of dark green ink, in both themes, and the
document is the light surface next to it. That contrast is what gives hierarchy: the
chrome recedes, the document leads.

```css
--nav-bg:        oklch(0.145 0.028 151);  /* top end of the gradient */
--nav-bg-end:    oklch(0.115 0.022 151);  /* bottom end */
--nav-hover:     oklch(0.185 0.030 151);
--nav-active-bg: oklch(0.310 0.040 151 / 0.72);
--nav-edge:      oklch(0.330 0.030 151);  /* the edge, measured against the CANVAS */

--nav-ink:            oklch(0.928 0.014 93);   /* 11.37:1 */
--nav-ink-strong:     oklch(0.975 0.007 93);   /* 13.08:1 */
--nav-ink-muted:      oklch(0.720 0.018 100);  /*  5.68:1 */
--nav-ink-subtle:     oklch(0.659 0.018 110);  /*  4.52:1 */
--nav-border-default: oklch(0.556 0.025 150);  /*  3.01:1 */
--nav-green:          oklch(0.745 0.090 145);  /*  6.42:1 */
--nav-orange:         oklch(0.635 0.155 52);   /*  3.88:1 */
```

The chrome **is darker than the document even in dark theme**. If it's lighter, the
panel advances instead of receding, and the app reads as a single mass.

Its four real floors are the gradient's two ends plus the active element's background
composited over each. Everything on top of it is measured against the worst of the
four.

The active element carries a faint green surface and a 2px green left rule, **not** a
fill: the rule marks the edge (6.92:1 against the active surface), and weight plus ink do
the rest, so color never travels
alone.

### The brand mark

The terminal glyph (`>_`, lucide `terminal`) is **green on every surface**: `--nav-green` in the
sidebar and the documentation site's header, where it sits on the chrome at 6.42:1; the same
colour on `--nav-bg` in the installable-app icons; and in a browser tab, which is not the
chrome, `--green` on a light tab and `--nav-green` on a dark one. SVGs used as images and PNGs
cannot read custom properties, so those files carry the tokens' sRGB values (`#27472f`,
`#88bc89`, `#030d05`), read from the browser rather than converted by hand.

It used to be orange in the sidebar and blue in the favicon, a leftover of an earlier palette.
One colour means the tab, the home screen, the application and its documentation are
recognisably the same product.

### How it's implemented

The chrome redefines token **names** within its scope instead of rewriting the rules it
contains. `var()` resolves at the element that matches, against the properties that
element inherits, so everything living inside re-themes itself automatically.

Two consequences learned by measuring:

- **Every name the chrome redefines has to be redefined again at the re-entry to the
  canvas.** A forgotten name doesn't fail loudly: it resolves to the canvas value,
  which is the wrong one exactly where it was forgotten.
- **What's declared inside but painted outside has to return to the canvas.** The
  move-and-rename dialog lives in the tree, but `showModal()` paints it centered over
  the document; without returning it, it came out dark while the identical dialog
  elsewhere in the app came out light.

### The floor can't be lightened

The avatar disc takes its color from an inline `style`, not a token, and it's a control
boundary that needs 3:1. Against the current floor it measures 3.68:1. Lightening the
chrome would drop it below the threshold without anything in the sidebar giving it
away.

---

## 9. Document

- Header with air above it and a line closing it below.
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

The **block** is a dark slab, a terminal inset inside a book. Its text color is
declared on the block, not on the highlighter: highlighting only applies to fences
that declare a language, and a bare fence would inherit the document's ink over the
slab.

**Inline code** doesn't share that surface. It's typography inside a sentence, green on
faint green; on the slab, every `` `foo` `` in a paragraph would be a black pill.

Highlighting is reduced to three signals over the code's ink: dimmed comments, strings
in green, numbers in orange. Everything else stays `--code-text`.

---

## 10. Table of contents

220px wide, sticky position, 96px from the document. Interface typography at 12px and
the label in the data face at 11px. No card and no floating background.

The active state has **a single carrier**: the orange rule. The text steps up to the
primary ink, which is already enough contrast without relying on color. Saying it with
color and with the rule at once turns up the volume of the whole table of contents.

---

## 11. Controls

```css
.button-primary  { height: 32px; background: var(--green); border-radius: var(--radius-sm); }
.button-secondary{ height: 32px; background: transparent; border: 1px solid var(--border-default); }
.input           { min-height: 36px; background: var(--input-bg); border: 1px solid var(--border-default); }
.input:focus     { border-color: var(--green); box-shadow: 0 0 0 3px var(--green-ring); }
```

The focus ring measures 3.03:1 in light and 3.00:1 in dark. A focus indicator needs
3:1, and this one has had to be raised twice for falling short: any proposal to lower
it goes against a deliberate correction.

### Scrollbar

Custom, not the system's. Defined once and inherited by the three places that scroll —
the tree, the workspaces menu, and the table of contents — so inside the chrome it
re-themes itself. 8px wide, thumb rounded to its own width and thinner than the track
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
  token blocks are parsed and every pair is calculated against the six floors — light
  canvas, dark canvas, the chrome's two ends, the code slab, and the notes' composited
  background. Zero failures is the condition for shipping.
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
