# Chrome and canvas are different materials

## Why

Change 008 aligned the *palette* with `DESIGN.md`. It did not touch the *structure*: the
sidebar and the document are painted on the same warm paper, so the application reads as one
continuous surface with no hierarchy between the navigation and the thing being read.

The reference design the user supplied resolves exactly that. A deep ink-green sidebar
separates chrome from content, the document gets air and a metadata strip, and code blocks
contrast as a terminal inset rather than a slightly grey box.

This is a visual change only. No feature is added or removed, no route moves, no data
changes, and the information architecture is untouched. **No `.jsx` file changes**, because
the DOM does not change — the whole redesign is `app/static/style.css`.

## What changes

**The navigation chrome becomes a dark ink-green region.** Not a new theme: a region, in both
themes. It is expressed by scoping a token override onto `.sidebar` that redefines the token
*names* the existing rules already read, so `.search-field`, `.ws-trigger`, `.page-list a`,
`.btn`, `.row`, `.avatar-menu`, `.new-btn`, `.eyebrow` and `.snippet` re-theme with no rule
edits at all.

**The document surface gets the editorial treatment.** Uppercase mono breadcrumbs, a bordered
metadata strip, more air under the title, a quieter table of contents, and blockquotes as a
technical note with an orange left rule.

**Code blocks become one dark surface in both themes.** The existing dark syntax palette
already measures well against `#141917`, so unifying deletes the light `--syn-*` set instead
of re-measuring it, and gives the terminal-inset look the reference is built around.

**Orange finally gets a solid use.** On the dark chrome the identity orange can be a filled
active state with dark ink on it at 5.04:1 — the first place in the product where orange
carries weight rather than decorating.

## What is deliberately not in scope

The reference shows several things doction does not have. Copying them would be inventing
product, not restyling it:

| in the reference | in doction | decision |
|---|---|---|
| per-page relations mini-graph | `Graph.jsx` is workspace-wide and takes no page | out |
| machine-access panel (REST/MCP/RAG/GIT) | no such data exists | out |
| page owners, reading time | absent from the `/view` payload | out |
| LIBRARY / KNOWLEDGE / SYSTEM groups | one group and a footer | out, that is re-organising |
| Trash and system as sidebar links | they live in the avatar menu and settings | out |
| version in the sidebar footer | only in Settings → System | out |
| code copy button, heading anchors | CSS exists but is orphaned, no JS emits it | out, that is new behaviour |
| 01/02 section numbering | does not exist | out, decoration nobody asked for |
| the title's second line in orange | where a title wraps is not controllable | out, it would be arbitrary |

The metadata strip therefore carries **the two fields that exist**: last-updated date and last
editor. The title stays in ink.

Also unchanged: layout, motion, the change 007 primitives, and the landing page and `/docs`.
