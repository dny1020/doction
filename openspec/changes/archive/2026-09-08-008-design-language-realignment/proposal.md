# Realign the application with DESIGN.md

## Why

`DESIGN.md` is now declared the visual source of truth for doction. The application was not built
against it. It was built against a *different* source: change 005 adopted the design language of
`personal_homepage`, and change 007 tidied the component layer on top of it. Both did their job
well — the token discipline is real, there are no literal colours outside the token blocks, and
every font is self-hosted — but they aim at a target `DESIGN.md` does not name.

The result is an application that is internally consistent and externally off-identity. It is a
calm blue-accented technical app on near-white paper. `DESIGN.md` asks for warm paper, dark green
ink, restrained orange, and a tactile surface.

The gap is not a long list of small defects. It is four decisions, and everything else follows
from them.

| | today | `DESIGN.md` |
|---|---|---|
| accent | `#1B4FA0` blue | `#D97745` orange + `#173B35` ink green |
| canvas / surface | `#FAF9F5` / `#FFFFFF` | `#F5F1E8` / `#F9F7F1` |
| display face | Instrument Serif | Fraunces |
| radii | 4 / 8 / 12 / 16 | 6 / 7 / 10 / 12 / 14 |
| paper texture | none | part of the identity |

Two of those reverse a decision change 005 made deliberately and for a stated reason, so this
proposal has to answer that reason rather than step over it.

## Scope

**The application only.** The landing page and `/docs` are explicitly out of scope. Everything
below concerns `app/static/style.css` and the React SPA under `frontend/src/`.

## The conflict that has to be settled first

Change 005 replaced orange with blue because **orange on warm paper does not carry text**. That is
measurement, not taste, and `DESIGN.md`'s own palette does not survive it:

| pair | ratio | needed |
|---|---|---|
| `--accent #D97745` on `--background #F5F1E8` | 2.79:1 | 4.5:1 for text |
| `--accent #D97745` on `--surface #F9F7F1` | 2.94:1 | 4.5:1 for text |
| `--accent-hover #BE6035` on `--background` | 3.79:1 | 4.5:1 for text |
| `--foreground-subtle #8B918C` on `--background` | 2.85:1 | 4.5:1 for text |
| `--foreground-dark-subtle #777168` on `--background-dark` | 3.74:1 | 4.5:1 for text |
| `--border #D8D2C5` on `--background` | 1.34:1 | 3:1 to bound a control |

The `visual-language` spec already requires 4.5:1 for accent text and 3:1 for a control boundary,
and `DESIGN.md` §23 makes accessibility part of the design system. Adopting the palette literally
would fail both documents at once.

**`DESIGN.md` resolves this itself.** §2 lists orange's jobs as *small icons, active indicators,
highlights, status indicators, small decorative elements* — none of them body text — and then names
ink green as "the preferred color for primary buttons and important UI controls", with §10 spelling
out the primary button as `#173B35` on `#F9F7F1`. Ink green measures **10.87:1** on the paper.

So the split this proposal takes is the one `DESIGN.md` already implies:

- **Ink green is the interactive accent.** Links, primary buttons, the active item, focus rings,
  selection. It is what a person clicks and what a person reads.
- **Orange is the identity marker.** The indicator bar beside the active item, small icons, status
  dots, the highlight rule, the avatar. It is never the only carrier of a meaning, and it never
  sets text on paper.
- Where orange genuinely has to set text, `#B05324` (4.53:1) is its readable form.
- In the dark theme the roles hold, and `--accent-dark #E08A59` measures **6.85:1**, so orange can
  do more there than it can on paper.

This keeps the product recognisably orange without asking anyone to read at 2.8:1.

## What changes

**Tier 0 — decisions, no code.** The accent split above, and four derived values that replace
`DESIGN.md` colours that cannot be used as written: `--foreground-subtle` → `#696F6A` (4.56:1), the
dark `--foreground-dark-subtle` → `#857E74` (4.51:1), a control-boundary token `--border-strong`
→ `#8B8778` (3.19:1) that `DESIGN.md` has no equivalent for, and its dark counterpart `#696257`
(3.00:1). `DESIGN.md` §28's token block is amended to record these.

**Tier 1 — the palette and the shapes.** The surface, ink, line and accent tokens move to the
`DESIGN.md` values as amended. Pure white stops being a surface. The radius scale moves to
6/7/10/12/14; the pill survives only on the three genuinely circular things that use it today.
Shadows drop to the §9 pair. This is a token-block edit: because there are no literal colours
anywhere else in the stylesheet, the whole interface follows.

**Tier 2 — the type scale.** Body 15 → 16px, small 13 → 14px, and the rest onto the §6 steps. The
five `calc(var(--text-*) * 1.15)` heading sizes introduced to compensate for Instrument Serif's
small x-height become real steps, which is what "nothing is set outside the scale" already asks
for.

**Tier 3 — the display face.** Instrument Serif → Fraunces, subset to the ranges the app renders,
self-hosted like everything else. This is the one item with a cost worth stating rather than
assuming, so it carries its own decision in `design.md`.

**Tier 4 — paper texture.** A single low-intensity texture on the app canvas at the low end of the
§4 range, suppressed on the editor, tables, forms, dense views, modals and code blocks per §16.

## What is not in scope

- The landing page and `/docs`. Untouched.
- Layout, navigation structure, copy, behaviour. Nothing moves and nothing is added.
- Motion. The 120/200 ms pair stays; §21's 120/180/260 is close enough that changing it buys
  nothing and re-tests everything.
- The component layer from change 007. The primitives are correct and stay; only the values they
  spend change.
- Icons. `lucide-react` is already the icon system §11 asks for.
