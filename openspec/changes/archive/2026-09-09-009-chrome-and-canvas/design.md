# Design

## 1. The technique: redefine token names in a scope

The sidebar is not rewritten rule by rule. It gets a block that **redefines the token names
the existing rules already read**, and everything inside it re-themes on its own.

This works because `var()` resolves at the element that matched, using that element's
*inherited* custom properties — not at the place the rule is written. So a rule declared far
away as bare `.page-list a.active` still resolves `--accent-soft` from the `<a>`, which
inherits from `.sidebar`. Selector location is irrelevant; DOM position is everything.

That single fact is what makes this change small. The three cross-cutting selector lists that
looked dangerous — press transitions, focus, coarse-pointer targets — need no edits at all.
Two of them set no colour, and the third re-themes by itself.

### Three layers, so the dark theme is three declarations

```
:root                    --nav-*        the chrome palette, 16 values
[data-theme="dark"]      --nav-bg, --nav-hover, --nav-accent-soft
.sidebar                 the mapping, written once, theme-agnostic
```

Only the ground and its two dependent steps move between themes. The chrome inks, lines and
accent are derived against the worst of all four grounds, so one set serves both.

| token | value | worst of four grounds | needs |
|---|---|---|---|
| `--nav-fg-1` | `#EDE7DC` | 10.49:1 | 4.5 |
| `--nav-fg-2` | `#B8B0A4` | 6.01:1 | 4.5 |
| `--nav-fg-3` | `#A69F94` | 4.92:1 | 4.5 |
| `--nav-border-strong` | `#6A7F77` | 3.02:1 | 3.0 |
| `--nav-accent` | `#C7DAD2` | 8.84:1 | 4.5 |
| `--nav-marker` | `#D97745` | 4.10:1 | 3.0 |

Dark ink `#172522` on the orange active fill: **5.04:1**.

## 2. Decision: what pins the dark-theme ground

`--nav-bg` in the dark theme is `#1B2A26`, and the number is not free. The avatar is the one
element in the sidebar whose colour does **not** come from a token — `Sidebar.jsx:249` sets it
inline from the user's identity colour, and those eight colours are deliberately iso-luminant.
The avatar disc is a control boundary, so it needs 3:1 against whatever it sits on.

| ground | worst avatar colour vs ground |
|---|---|
| `#12241F` (light theme chrome) | 3.31:1 |
| `#1B2A26` (dark theme chrome) | 3.06:1 |
| `#1C332C` (one step lighter) | 2.76:1 ✗ |

So the dark chrome cannot go lighter. That constraint is recorded in the token comment,
because the next person to nudge it for aesthetic reasons will otherwise break a boundary
they were not looking at.

**Honest note on the same value:** `#1B2A26` against the dark canvas `#171614` measures
1.21:1. That is *better* than the separation the app ships today (`--surface-sunken` against
`--bg` is 1.05:1), and the panel edge has always been carried by `border-right`. So this is
not an accessibility problem. It is a craft call: at near-equal luminance the green reads as a
colour cast rather than a deliberate panel, and the border does the real work.

## 3. Decision: the dialog has to re-enter the canvas

`PageActions` renders `<dialog class="confirm-dialog">` **inside** the sidebar tree, then
opens it with `showModal()`, which paints it centred over the light canvas. Custom properties
inherit down the DOM, and top-layer promotion changes stacking, not inheritance — so it would
arrive wearing the chrome palette and render as a dark modal, while the *identical*
`.confirm-dialog` from `ConfirmProvider` renders light. One class, two appearances.

There is no "inherit from root" mechanism; `initial` and `revert` on a custom property give
the guaranteed-invalid value. Re-declaring is the only route.

**Chosen:** a `--canvas-*` alias family in `:root` that captures each canvas token by
reference, and one re-entry block scoped to `.sidebar .confirm-dialog` that maps them back.
Aliases rather than literals, so the canvas palette stays defined in exactly one place and the
dark theme still resolves correctly.

Scoped to the dialog **only**. `.ws-menu` and `.avatar-menu` are anchored inside the sidebar
and must stay dark.

## 4. Decision: split the code token, and unify the block across themes

`--code-bg` is read by both `.prose code` (inline) and `.prose pre` (block). Darkening it
would turn every `` `foo` `` inside a sentence into a black chip — loud, and the opposite of
what the brief asks for. So the token splits: the light tint stays and serves inline code
only; `--code-block-*` is new and serves the block.

Then the block is made **identical in both themes**. The dark syntax palette that already
ships measures well against `#141917` — keyword 8.52, string 9.17, number 8.06, title 10.93,
variable 6.60, comment 5.26 — so unifying *deletes* the six light `--syn-*` values rather than
re-deriving them. A code block that looks the same in both themes is also precisely the
reference's image: a terminal inset in a book.

It costs one thing. In the dark theme the block sits at 1.02:1 against the canvas, so the
border has to carry the edge; `--code-block-border` is set to clear the canvas on its own.

**A separate defect this exposes.** `prose.js:104` only adds `.hljs` to fences that declare a
language. A fence with no language keeps `color: var(--fg-1)` — dark ink on the new dark
ground, **1.05:1**, invisible. The colour must be declared on `.prose pre` itself rather than
delegated to `.hljs`. This is a latent bug the current light block hides.

## 5. Decision: scope the metadata strip

`.meta` has two definitions and **thirteen call sites** — the reader's strip, but also subpage
dates, notes, history, trash, the editor, and three settings sections. Restyling the bare
class would put a border under every date in the application.

The strip is therefore `.page-header .meta` only. The shared `.meta` and the page-view
override are left exactly as they are.

## 6. Known consequences, signed rather than discovered

- **The sidebar's colour transition has never fired.** `style.css:511` re-declares
  `transition` at the same specificity as the shared list at 297 and wins on source order. The
  dark panel will therefore *snap* on theme toggle while the canvas fades. A 200 ms cross-fade
  of a large dark panel is arguably worse than a snap, so this stays — but as a decision.
- **Mermaid stays on paper.** `prose.js` reads its palette from `documentElement`, outside the
  chrome scope, so diagrams keep the canvas colours while code goes dark. Defensible — a
  diagram is an illustration and code is a terminal — but it is a visible split.
- **The `--canvas-*` aliases depend on block order.** `:root` and `[data-theme="dark"]` have
  equal specificity; the dark block wins by being later in the file. Reordering them would
  silently freeze the aliases on light values. Recorded in a comment.
- **`.code-copy` and `.heading-anchor` stay orphaned.** Their CSS now points at a light surface
  that the block no longer uses. They are dead today and reviving them would be new behaviour,
  so they are left dead and noted.

## 7. Verification

- The 102-screen capture, both themes, three widths, before and after.
- The contrast verifier extended with the four chrome grounds and the code ground. Zero
  failures.
- The two `.confirm-dialog` instances compared side by side; they must look identical.
- A fence with no language opened and confirmed readable.
- A keyboard pass across the chrome/canvas boundary, since the focus ring changes hue at it.
