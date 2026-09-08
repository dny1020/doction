# Design

## 1. Where the application actually stands

Measured on `app/static/style.css` (2706 lines) and `frontend/src/` at `b3df89f`.

### What already satisfies DESIGN.md

These are not accidents and they should not be re-litigated during the work.

- **Token discipline is complete.** Colour values appear in the `:root` and `[data-theme="dark"]`
  blocks and nowhere else. `grep` finds zero hex literals and zero `rgba()` outside the token
  blocks in the 2366 lines after them. §28 is already satisfied in structure; only the values are
  wrong.
- **Everything is self-hosted.** Three families, 236 KB of subset woff2, and
  `frontend/scripts/check-local-assets.js` fails the build if anything reaches for a CDN. §29's
  constraint is enforced mechanically.
- **The icon system is Lucide**, via `lucide-react`. §11 is met.
- **Data and prose are set apart.** JetBrains Mono is reserved for values and code and forbidden in
  a sentence. `DESIGN.md` §5 asks for the same assignment.
- **Elevation is one language.** Change 007 collapsed 11 surfaces across 5 radius+shadow pairings
  into three roles. §12's "a sheet or panel, not a floating Bootstrap component" is already how
  `.card` is drawn: a line, no shadow.
- **Both themes are designed, not inverted**, and every token is defined in both.
- **The pill is not abused.** `--r-pill` has three callers: the avatar, the profile preview and the
  theme swatch dots. All three are genuinely circular, which is the exception §8 allows.
- **Reduced motion is handled**, focus is one language, and the mobile drawer exists. §21–§23 are
  in reasonable shape.

### What diverges

| # | §  | item | today | DESIGN.md |
|---|----|------|-------|-----------|
| 1 | 2  | accent hue | `#1B4FA0` blue | `#D97745` orange |
| 2 | 2  | primary control colour | the blue accent | `#173B35` ink green |
| 3 | 2  | canvas | `#FAF9F5` | `#F5F1E8` |
| 4 | 2  | surface | `#FFFFFF` | `#F9F7F1` |
| 5 | 2  | sunken / hover | `#F0EDE6` / `#EAE6DD` | derived from `--background-subtle` |
| 6 | 3  | dark canvas | `#161614` | `#171614` |
| 7 | 3  | dark surface | `#1E1E1B` | `#211F1B` |
| 8 | 4  | paper texture | absent | part of the identity |
| 9 | 5  | display face | Instrument Serif | Fraunces |
| 10| 6  | body / small | 15px / 13px | 16px / 14px |
| 11| 6  | heading sizes | `calc(--text-3xl * 1.15)` ×5 | steps on the scale |
| 12| 8  | radii | 4 / 8 / 12 / 16 | 6 / 7 / 10 / 12 / 14 |
| 13| 9  | shadows | four steps, `xs`…`lg` | one near-invisible pair |
| 14| 10 | primary button | accent fill | `#173B35` fill, `#F9F7F1` text |
| 15| 18 | code block | `--surface-sunken` | `#E9E6DE` light / `#11110F` dark |
| 16| 19 | field height | 34–36px, 44px on touch | 40–44px |
| 17| 7  | spacing scale | 2/4/8/12/16/24/32/48/64 | 8/12/16/24/32/48/64/96/128 |

Items 3–7, 12, 13, 15 and 16 are token edits and cost almost nothing given the discipline above.
Item 17 is a near-match: the app's scale is the same ladder plus two optical steps below 8px and
minus the two marketing steps above 64px. The small steps earn their place in a dense productivity
UI, and 96/128 belong to surfaces this change does not touch. **No action.**

Items 1, 2, 14 are the accent question. Items 9 and 11 are the type question. Item 8 is new work.

## 2. Decision: how orange and ink green divide the work

**Context.** Change 005 removed orange for a measured reason and the archived proposal records it:
"`#E07020` is a warm, attention-seeking hue on a warm paper, and it is used for links, the active
page, primary buttons and focus rings alike." `DESIGN.md` now asks for orange back. Both cannot be
satisfied by putting orange where the blue is today.

**Measurements.** WCAG 2.1 contrast against `--background #F5F1E8`:

All ratios are worst case across the five light surfaces a token appears on — background,
background-subtle, surface, surface-elevated and the §13 active-item ground `#E8E4DA` — not against
the page alone.

| colour | worst case | verdict |
|---|---|---|
| `#D97745` accent | 2.48:1 | decoration only; carries nothing |
| `#BE6035` accent-hover | 3.35:1 | decoration only |
| `#A34D21` derived | 4.54:1 | orange that carries something |
| `#173B35` ink green | 9.65:1 | text, and comfortable |
| `#0F302B` ink green hover | 11.19:1 | text |

**Options considered.**

*Orange everywhere the blue is today.* Rejected. It fails the `visual-language` spec's 4.5:1
requirement on links and reintroduces exactly what change 005 measured and removed.

*Orange darkened until it reads.* Rejected as the primary route. `#B05324` passes but is a burnt
red-brown; a whole interface set in it is not the warm annotation orange `DESIGN.md` describes, and
§2 says "do not turn the entire interface orange" regardless.

*Ink green interactive, orange as marker.* **Chosen.** It is what `DESIGN.md` §2 and §10 already
say when read together, and it gives the product a stronger identity than either colour alone:
green ink for what you act on, orange for what the page is pointing at.

**Orange then splits once more, by consequence.** At 2.48:1 the identity orange does not reach even
the 3:1 a non-text UI component needs, so an active-item indicator drawn only in `#D97745` is a
signal some people cannot see. Rather than darken the identity colour, orange keeps both forms:
`--accent` `#D97745` for marks that carry nothing and may go unseen, `--accent-ink` `#A34D21` for
marks that carry something. The test is what a reader loses if the mark is invisible.

**Consequence for the spec.** The `visual-language` requirement "One accent, and it recedes" is
written as *one hue for every emphatic role*. That is no longer true, so it is modified rather than
quietly broken: one hue for interactive emphasis, one for identity marking that never carries a
meaning by itself, one for danger. The requirement's real content — that the accent recedes, that
destructive is not accent, that anything readable holds 4.5:1 — is unchanged.

## 3. Decision: derived tokens DESIGN.md does not supply

Four values in `DESIGN.md` §2/§3 cannot be used as written. Each is replaced by the *lightest*
value on the same hue that meets the threshold, so the palette's character survives.

| role | DESIGN.md | worst case | replacement | worst case |
|---|---|---|---|---|
| `--foreground-muted` | `#66706B` | 4.27:1 | `#5F6864` | 4.53:1 |
| `--foreground-subtle` | `#8B918C` | 2.48:1 | `#626763` | 4.54:1 |
| `--foreground-dark-muted` | `#A7A096` | 4.42:1 | `#938B7E` | 4.54:1 |
| `--foreground-dark-subtle` | `#777168` | 3.15:1 | `#918B81` | 4.52:1 |
| functional orange | *(none)* | — | `#A34D21` | 4.54:1 |
| control boundary (light) | *(none)* | — | `#858173` | 3.07:1 |
| control boundary (dark) | *(none)* | — | `#766D61` | 3.00:1 |

The first derivation of these measured against `--background` alone and every value it produced
failed somewhere else in the interface — on a hovered row, on a sunken panel, on an elevated menu.
The reference surface is the worst case a token appears on, and that rule is now written into
`DESIGN.md` §28 rather than left as something the next person has to rediscover.

`DESIGN.md` has one `--border` where the application needs two: §19 puts a `1px solid var(--border)`
on every input, and at 1.34:1 that is a control some people cannot find. The existing
`--border-strong` split stays; `--border #D8D2C5` keeps its §12/§13 decorative job unchanged.

`DESIGN.md` §28 is amended with these four so the source of truth stays the source of truth. That
amendment is the only edit this change makes to `DESIGN.md`.

## 4. Decision: Instrument Serif → Fraunces

**Cost.** Instrument Serif is 33 KB across two subsets, one weight, no italic. Fraunces is a
variable font with `SOFT` and `WONK` axes; the full latin variable face is several times that.

The `visual-language` requirement "The visual language costs nothing at runtime" says a family is
paid for on every cold load and must earn its place. It does not say the cheapest family wins — it
says the cost is stated. Fraunces is named by the source of truth, it is the family that carries
the editorial character `DESIGN.md` §1 is built around, and the app renders it in exactly one role.

**Chosen:** adopt Fraunces, static instances at the weights the app actually paints, subset to the
latin and latin-ext ranges already used, no italic. **If the subset lands above 80 KB**, keep
Instrument Serif and record the waiver in `DESIGN.md` §5 rather than shipping a font the Pi pays
for on every cold load. The measurement decides, not the preference.

**Measured:** the serif is painted at weight 400 and nowhere else, so the family costs two files —
17 968 B and 17 288 B, **35 256 B** total, against Instrument Serif's 32 636 B. A 2 620 B increase
buys the family the source of truth names. The variable face was never in play: static instances at
one weight are a fraction of it, and the `SOFT`/`WONK` axes have no role in this language.

A side effect: the five `calc(var(--text-*) * 1.15)` rules exist only to compensate for Instrument
Serif's small x-height. Fraunces is a different fit, so the compensation is re-measured and folded
into real scale steps either way.

## 5. Decision: how much texture, and where

§4 wants texture perceived as tactility, not as a visible layer, at 0.025–0.06 opacity. §16 says
the app carries less than the landing and docs, and names six surfaces that get none: editors,
tables, forms, dense data views, modals, code blocks.

**Chosen:** one inline SVG fractal-noise data URI on the app canvas, authored as `--paper-texture`
so its intensity is one value. No asset file, no request, nothing for `check-local-assets.js` to
police. Suppressed on the six §16 surfaces by painting texture only on `body`, never on
`--surface` or `--surface-sunken`.

**The two themes need different intensities.** Light grain on charcoal reads about twice as strong
as the same grain on paper, and §3 warns the dark theme must never look brown or muddy. Light
carries 0.025, the bottom of the §4 range; dark carries 0.012. Same fibre, same token name, one
value each.

**Suppression is by cascade, not by rule.** The editor textarea, the preview, the sidebar, cards,
modals, the palette and code blocks all paint their own background already, so none of them
inherits the fibre and no `background-image: none` overrides were needed. One surface did leak:
`.prose td` is transparent, so texture read through the cells of every table. The table now paints
`--surface`, which is what §16 asks for and what the cascade could not supply on its own.

It goes last in the task order because it is the one item that is purely additive: if it reads as
noise at any point, it is deleted and nothing else in the change depends on it.

## 6. Verification

The change is visual, so the gate cannot be only `npm run check`.

- Screenshots of every app screen in both themes, before and after, at the three §22 breakpoints.
- A contrast pass over the final token block, every pair recorded as a number in `tasks.md`, the
  way the current stylesheet's comments already do.
- `grep` for hex literals and `rgba()` outside the token blocks must stay at zero.
- `grep` for `calc(var(--text-` must reach zero.
- Delivered font bytes recorded, and the Fraunces decision resolved against the 80 KB line.
