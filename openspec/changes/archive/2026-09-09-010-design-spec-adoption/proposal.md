# Adopt the rewritten design specification

## Why

`DESIGN.md` has been rewritten from end to end. It is no longer prose guidance: it is a
technical specification in `oklch()`, with its own token vocabulary, a type scale, exact
geometry, and CSS rules ready to be copied. The code does not satisfy it, and in four places
it does the opposite, because change 009 was implemented against the document that came
before.

The stylesheet's token discipline is intact — no colour literal outside the token blocks — so
the work is large but mechanical rather than exploratory.

**Scope: CSS, plus `prose.js` and two font families.** No `.jsx` changes.

## What contradicts what was just built

| shipped in 009 | the rewritten document |
|---|---|
| fractal-noise texture on `body` | §7 forbids noise filters and visible grain; asks for a 112° gradient |
| active item as a solid orange fill | §8 asks for a faint green ground with a 2px inset orange rule |
| Fraunces as the display face | §3 asks for `Instrument Serif`, the face removed in 0.29.0 |
| one code surface in both themes | §2 gives `--code-bg` a different value per theme |

The last one modifies a requirement archived yesterday. It is amended, not ignored.

## The finding that shapes the work

**The document's values are unmeasured, and several revert accessibility fixes this repository
made deliberately.**

| role | today | per the document | consequence |
|---|---|---|---|
| focus ring | 4.33:1 | **1.25:1** (dark 1.06:1) | invisible focus, worse than the bug fixed in 009 |
| control boundary | 3.07:1 | **1.67:1** | inputs and secondary buttons lose their edge |
| `--ink-subtle`, 46 text sites | 4.54:1 | **3.87:1** | body text below the floor |
| `--danger` | 5.52:1 | 4.27:1 | below the floor |
| `--warning` | — | 2.40:1 | below the floor |

`--orange-soft` and `--orange-hover` also fall outside the sRGB gamut.

The governance requirement already in the spec settles this: derive the closest value on the
same hue that meets the threshold, and write it back into `DESIGN.md` with its measurement.
That is the pattern approved in 008 and 009.

## What changes

**The token vocabulary moves to the document's names.** This is a permutation, not a rename:
`--border-strong` means a different thing in each vocabulary, the type scale shifts by one
step, and `--code-bg` is outright inverted — today it is the light inline tint, in the document
it is the dark block. A single-pass substitution would compile, leave no undefined token, and
be wrong.

**Colour moves to `oklch()`**, so the document and the stylesheet hold literally the same text.
`color-mix()` is not adopted: Safari 15.4 through 16.1 rejects it and fails silently to
transparent, and the project has no autoprefixer. Its two uses are precomputed as flat tokens,
which also makes them measurable.

**Geometry follows §4**: a 760px reading column instead of `90ch`, a 72px gutter where there
are 32px today, the table of contents pushed from 48px to 64px, a 280px sidebar, and the
desktop top bar — whose DOM node already exists at every width and is only hidden by CSS.

**Type follows §3**: Manrope vendored as the interface face, Instrument Serif back as display,
Fraunces out, and the markdown H2 and H3 moving from serif to the interface face.

## Deliberately not in scope

The desktop top bar is shown but cleaned up with CSS: its toggle can only *open* a sidebar that
is already open on desktop, and its overflow menu repeats three of the four buttons directly
below it. Making that bar genuinely useful — a section name in settings, a title for the graph
route, a right-hand slot that is not a duplicate — needs JSX and belongs to a later round.

No feature, route, data or navigation grouping changes.
