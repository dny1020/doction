# The small design system

## Direction

Editorial, technical, calm. The reference is a well-set reference work and a good developer tool,
not a SaaS dashboard. Three consequences that decide most arguments:

**Chrome recedes, content does not.** Borders are the quietest thing that still separates. Shadows
mark what is genuinely floating and nothing else. There is one accent and it already recedes.

**Repetition is the point.** A list of API tokens and a list of page versions are the same shape
because they are the same idea. Someone who learns one screen has learned the others. Variety
between screens reads as unfinished, not as rich.

**Density is uniform.** The distance between two rows does not depend on which screen you opened.

## The primitives

Seven pieces. Everything on every screen is one of these, a page-specific arrangement of them, or
prose.

### Surface

A panel that holds content. Three roles, and the pairing is fixed per role so that elevation
means something:

| role | radius | shadow | used by |
|---|---|---|---|
| panel — sits on the page | `--r-lg` | none, `--border` | settings cards, subpage cards, the graph canvas |
| raised — floats over content | `--r-md` | `--shadow-md` | menus, popovers, the connection detail |
| modal — takes the screen | `--r-lg` | `--shadow-lg` | the palette, the confirm dialog, shortcuts, auth |

Today the same role gets `--r-sm` on one screen and `--r-md` on another. Fixing the pairing is
most of what makes the application feel like one product.

### List and Row

One list container and one row. The row has three optional parts — a leading name, a middle that
flexes, and trailing meta — and one padding, which comes from the scale. Separators are a
modifier on the list, not a property each row re-decides.

The nine list families and eight row families collapse here. Where a screen genuinely needs
something else, it says so with a modifier rather than a new family.

### Field

One text input. One border, one radius, one padding, one focus. Today six definitions disagree on
all four. The bare-looking ones — the editor textarea, the title, the palette input — stay bare,
but as a documented modifier rather than as a separate control that happens to look different.

### Section label

The small uppercase label above a group. `sidebar-eyebrow`, `subpages-eyebrow`,
`settings-card-title` and `settings-group-title` are one thing.

### Meta

A date, a count, a status, a role, a slug. Set in the data face, at the smallest size in the
scale, in secondary ink. Change 005 established the rule; this applies it everywhere rather than
in the nine places it reached.

### Empty state

`EmptyState` exists and is used on some screens. Every empty case uses it, including the ones that
currently render a bare `<p class="muted">`. An empty screen is where a product most obviously
looks unfinished.

### Focus

One language everywhere: the accent ring. The competing outline-with-offset is removed. Both are
visible and accessible; having two is the problem.

## What this deliberately does not add

No new component that no screen needs today. No variant that exists to look designed. If a
primitive has one caller, it is not a primitive and the style belongs on that screen.

## How it is verified

Two halves, and neither alone is enough.

**The countable half** rules out drift: no rule sets spacing, font size or radius outside the
scale; every elevated surface matches its role's pairing; one focus treatment remains; the class
count has gone down. Each is a grep. A lower count is evidence that the primitives are actually
being used — it is not the objective, and it is never a reason to merge two things that mean
different things.

**The half that decides** is the walkthrough: every screen, both themes, against the baseline
captures. The question there is not whether the screens match each other but whether moving
between them feels like one product. A reader and a settings pane should differ; they should
differ in content, not in vocabulary.


## Baseline, measured 2026-09-07 before any edit

```
BASELINE de 007-interface-polish — app/static/style.css
medido sobre 2842 líneas

  clases distintas ............... 310
  familias (primer segmento) ..... 75
  familias con 4+ clases ......... 24
  contenedores de lista .......... 13  → delivery-list, history-list, member-list, page-list, palette-list, relations-list, results, shortcuts-list, skeleton-list, subpages-grid, token-list, ws-manage, ws-menu-list
  filas de lista ................. 19  → avatar-menu-item, conn-row, delivery, history-item, member-row, page-row, palette-item, profile-row, settings-fact, settings-nav-item, settings-row, skeleton-row, subpage-card, task-list-item, toc-item, token-reveal-row, token-row, ws-item, ws-manage-row
  definiciones de campo .......... 7  → .workspace-input, .search-field, .title-input, .editor-textarea, .auth-input, .settings-input, .palette-input
  superficies elevadas ........... 11 en 5 parejas radio+sombra
      var(--r-lg)      var(--shadow-lg)
      var(--r-md)      var(--shadow-lg)
      var(--r-md)      var(--shadow-md)
      var(--r-pill)    var(--shadow-xs)
      var(--r-sm)      var(--shadow-md)
  espaciado en px crudo .......... 25 declaraciones
  font-size fuera de la escala ... 7  → 0.85em, 10.5px, 10px, 11px, 16px
  lenguajes de foco .............. 4
      box-shadow: 0 0 0 3px var(--accent-ring);
      opacity: 1;
      outline: 2px solid var(--accent); outline-offset: 2px; transition: outline-color var(--d
      outline: none; box-shadow: 0 0 0 3px var(--accent-ring);
```

The wider scan found more than the first pass reported: 13 list containers and 19 row
treatments, not 9 and 8, and five elevation pairings rather than four. The proposal's
numbers were corrected to these.

## What the baseline already shows

Findings from the capture pass, before any change:

- **The Inbox is the only list in the application with bullet markers.** It also repeats the note
  title as its own excerpt, and unlike Trash it has no description line under the heading. Three
  differences on the simplest screen there is.
- **Search snippets leak frontmatter.** A captured note shows `--- type: memo --- revisar el` in
  the sidebar results. The same defect was fixed in the Inbox excerpt; the search path has it too.
- **The command palette is not centred.** It centres on the viewport while the sidebar occupies
  220px of it, so it sits visibly left of the content it floats over.
- **Two 404s, two layouts.** Inside the shell the message is centred in the content column; the
  standalone one centres in the viewport. Same words, different composition.
- **Trash, Inbox and History each state a row differently.** Trash puts the date in a pill beside
  the title, History puts it in a line of dot-separated metadata, Inbox puts it on its own line
  below. All three are the same idea: a thing, and when.
- **Settings is the most consistent area** and the one with the most classes — 33. Its cards are
  the closest thing the application has to a house style, which makes it the right place to
  extract the primitives from rather than to invent them.

## Delivery defect found while verifying Settings

`app/static/style.css` is served without a version in its URL while the JS bundle is
content-hashed. A browser that has the old stylesheet cached and the new bundle uncached renders
the new markup against the old rules — which is exactly what happened during verification: the
tokens card lost its surface and its list grew bullet markers.

This is not a visual-polish defect, and it is not in this change's scope, but this change makes it
matter: a large CSS rewrite is precisely when a stale stylesheet does visible damage. The fix is
to version the href the way the bundle already is. Raised for a decision rather than done here.

## The rule for variants

A list that uses `row` keeps `row`'s behaviour unless there is a clear *functional* reason to
differ. Saving a screen some vertical space is not one.

This came up over the reader's mentions list, which is taller now that it respects the 44px touch
floor like every other row. The compact variant was declined: introducing an exception because a
screen could occupy fewer pixels is how a design system stops being one. If a document with very
many backlinks turns out to need something else, that is a density-and-collapsing problem to solve
on its own terms, not a reason to reopen the row.
