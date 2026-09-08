## Why

Change 005 settled the *tokens*: one accent, three type families with roles, a 4px spacing base,
a radius scale, contrast that holds in both themes. What it did not touch is the layer above —
the components those tokens are spent on. That layer grew one screen at a time, and it shows.

**The stylesheet defines 310 classes across 75 families, 24 of them four classes or more**, and the families overlap
almost entirely in purpose:

| the same job | how many treatments |
|---|---|
| a list container | 13 |
| a row in a list | 19 |
| a text input | 7 |
| an elevated surface | 11 surfaces, 5 different radius + shadow pairings |
| a focus indicator | 4 declarations, 2 visual languages |

`.history-list`, `.token-list`, `.delivery-list`, `.member-list`, `.ws-manage`, `.relations-list`,
`.results`, `.palette-list` and `.page-list` are nine answers to "a list of things". Some carry a
top border, some do not; the rows inside them pad by `var(--sp-1) 0`, `var(--sp-2) 0`, `2px 0`,
`var(--sp-2) var(--sp-3)` and `var(--sp-3) var(--sp-4)` depending on which screen you are on. A
menu is `--r-md` with `--shadow-md` in one place and `--r-sm` with the same shadow in another.
`.workspace-input` rounds at `--r-sm` while every other field rounds at `--r-md`.

**25 declarations set spacing in raw pixels** outside the scale — `2px`, `6px`, `11px`, `18px`,
`28px`, and one `3px 6px 3px 8px`. **Seven font sizes bypass the type scale**, including `10px`
and `10.5px`, which are two sizes below the smallest token and below the legibility floor the
visual-language spec already states.

None of this is visible as a bug. It is visible as the thing you noticed: an application that
works but does not feel finished. Every screen is individually reasonable and no two are quite
the same, so the interface never recedes and the content never becomes the subject.

## What Changes

**A primitive layer, and the 25 families collapse into it.** A small set of shared pieces —
surface, list, row, field, section label, meta text, empty state — each defined once. Every
existing screen is re-expressed in those pieces.

Fewer classes is the *consequence*, not the goal. The goal is that moving between two screens
feels like staying inside one product. Screens are not meant to look identical — a reader and a
settings pane have different jobs — they are meant to speak the same language. Where consistency
and a lower count disagree, consistency wins and the count stays where it is.

**One focus language.** Today an accent outline with an offset and an accent ring coexist,
applied by which element you happen to be on. One of them wins everywhere.

**Nothing below the floor.** The seven literal font sizes go; the raw pixel spacing goes.
Everything reads from the scale that already exists.

**One density.** A row is a row whether it holds a token, a delivery, a member or a version, and
the 44px touch floor holds throughout.

## What does not change

Architecture, data model, URLs, navigation, page and subpage structure, workspaces, search,
the editor, the graph, backlinks, tags, MCP, authentication. No screen is added, none is removed,
and no interaction learns a new behaviour. The graph keeps its own route and stays one feature
among several rather than the identity of the product.

The 005 tokens are not reopened. Colour, type families and the spacing base were settled against
measured contrast and this change spends them better rather than revisiting them.

## Priorities, in order

When two improvements compete, the earlier one wins:

1. Content and legibility
2. Visual hierarchy
3. Consistency between screens
4. Spacing and density
5. Typography
6. Interactive states
7. Light and dark
8. Responsive behaviour
9. Fewer duplicate variants and classes

## Impact

- **Modified spec**: `visual-language` gains the consistency requirements the token requirements
  imply but do not yet state.
- **Code**: `app/static/style.css` is the bulk of it. JSX changes only where a screen has to name a
  shared class instead of its own, never to change what it renders.
- **No new dependency, no new asset, no backend change.**

## Out of scope

- New screens, panels or layouts. Designing something that does not exist is not polish.
- Animation beyond what is already there. The existing motion stays as it is.
- Anything that would make a screen prettier by making it do more.
