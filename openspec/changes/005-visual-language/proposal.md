## Why

doction looks like a competent app. It should look like a reference work — something a person
opens to find an answer and an agent reads to build one. The two audiences want the same thing from
the surface: that what is *data* be instantly separable from what is *prose*, and that nothing else
compete for attention.

The design language to adopt already exists and is already documented, in `personal_homepage`'s
`DESIGN.md`: warm paper, near-black ink, one blue, three type families with strict roles. Two
things make it the right source rather than an arbitrary restyle.

**The substrate is already shared.** doction's canvas is `#FAF9F5` and the reference's is
`#faf9f6` — the same warm paper, arrived at independently. The 4px spacing base and its steps match.
Shadows are already under 8% opacity in both. What differs is not the foundation but the
vocabulary built on it.

**The one rule that carries the product idea is already written there.** The reference reserves
monospace for data — dates, counts, tags, org names, repository paths — and forbids it for
sentences. doction is full of data pretending to be prose: slugs, tags, heading paths, page counts,
timestamps, delivery statuses, the retrieval constants in the system report, the version. Today
they are set in the same face and weight as the text around them. Putting them in mono and prose in
a text face is the single change that makes the interface read as documentation rather than as an
app with content in it. Everything else below is in service of that.

**What is actually wrong today**, beyond taste:

- **The accent is orange.** `#E07020` is a warm, attention-seeking hue on a warm paper, and it is
  used for links, the active page, primary buttons and focus rings alike. The reference's `#1b4fa0`
  is the only hue on its page and it recedes; on documentation, an accent that recedes is correct.
- **`--font-serif` is a lie.** It points at Inter and carries a comment saying nothing uses it. A
  token that names one thing and holds another is worse than no token.
- **Controls are bounded by a decorative line.** `--border` at `#E6E2D8` measures about 1.3:1
  against the canvas and is the only boundary on inputs, buttons and the workspace selector. The
  reference separates `hairline` (decorative, may be invisible) from `border-control` (must be
  seen), and that distinction is an accessibility fix, not a preference.
- **Radii are tighter than the family they belong to**: 4/6/10/14 against 8/12/16/24. Small radii
  read as dense and technical; this is a place where the reference's are better for reading.

## What Changes

- **One accent, and it is the blue.** Every use of orange moves to `#1b4fa0` and its soft
  companion. Danger keeps its own hue, because a destructive action is not an accent.
- **Type gets roles.** A serif for the single largest heading of a view and nothing else; a text
  face for everything readable; mono for data and never for a sentence. The `--font-serif` token
  stops lying.
- **Controls get a boundary that can be seen.** A second line token, distinct from the decorative
  hairline, on anything a person clicks or types into.
- **Radii move to the 8/12/16/24 family**, keeping the pill.
- **The dark theme is redesigned, not recoloured.** The reference is light-only warm paper and has
  no answer here; doction has a full dark palette and a toggle, so the dark counterpart is original
  work that must hold the same contrast ratios and the same one-accent rule.

Deliberately **not** in this change:

- **No motion changes.** The `rise` entrance, the 120/200 ms durations, the easing, the transitions
  on menus, palette and toasts, and the `prefers-reduced-motion` override all stay exactly as they
  are. The reference's two-curve system is not adopted; what exists works and is not the problem.
- **No layout, no behaviour, no copy.** Nothing moves, nothing is added or removed, no interaction
  changes. The sidebar is still a tree, settings still has six sections, the editor is still split.
  Only colour, type, line and radius.
- **No new capability and no new dependency beyond fonts.** Which fonts, and how many, is decided by
  measurement against the air-gap budget rather than by copying the reference's three.

## Capabilities

### New Capabilities

- `visual-language`: which colours exist and what each is for, which type family is allowed where,
  what may bound a control, and the rule that data and prose are never set alike. It states the
  vocabulary and the constraints it must satisfy — contrast ratios, both themes, and the air-gap —
  rather than a stylesheet.

### Modified Capabilities

- `app-shell`: its touch-target requirement ends with "on devices with a fine pointer, control
  sizes and spacing MUST remain exactly as they are today", and a scenario restating it. That was
  written to stop the touch adaptation from leaking into desktop density, and read literally it
  forbids any future visual change at all. It is narrowed to what it meant: adapting for touch must
  not alter density. A deliberate redesign is not a side effect.

## Impact

- **`app/static/style.css`**: the token block and every rule that hardcodes a colour. This is the
  whole change; it is one file plus fonts.
- **`app/static/vendor/fonts/`**: whatever families survive the budget, as woff2, subset to the
  ranges the interface actually renders. The `self-hosting` spec forbids any external request and
  `npm run check` enforces it, so a font that cannot be vendored cannot be used.
- **`frontend/index.html`**: the `@font-face` block lives in the served stylesheet, so likely
  nothing — but the theme-flash script reads `data-theme` and must keep working against the new
  palette.
- **Not affected**: every `.jsx` file, the backend, the MCP surface, retrieval, and the markdown
  renderer's output. If a component needs editing to restyle it, that is a signal the change is
  drifting out of scope.
- **KaTeX and highlight.js** ship their own typography and colours. Both must sit correctly on the
  new paper, and the highlight theme may need its palette revisited — that is styling, not
  behaviour.
