# Tags and metadata

A page can carry tags two ways: inline in the text, or in a metadata block at the top. Both are
parsed on every save into the same place, so a tag written either way behaves the same
afterwards.

## Inline tags

Write `#tag` anywhere in the body:

```markdown
Notes on #kamailio and #sip-trunk.
```

The rules, all measured:

| Written | Becomes | Why |
| --- | --- | --- |
| `#Kamailio` | `kamailio` | tags are lowercased |
| `#sip-trunk` | `sip-trunk` | hyphens and underscores are part of a tag |
| `#2026` | nothing | a tag must start with a letter |
| `` `#incode` `` | nothing | inline code is removed before the scan |
| `#infence` inside ``` fences | nothing | fenced blocks are removed too |

The exclusion of code is the reason a shell comment, a CSS colour or a C preprocessor directive
in a fenced block does not become a tag. It is also why a page documenting tags can show
examples.

## The metadata block

A page may open with a block delimited by `---`:

```markdown
---
title: SIP Trunk Runbook
tags: [kamailio, sip]
---

The body starts here.
```

**This block is not YAML.** It is a small dependency-free parser, and it understands exactly two
shapes: `key: value`, and an inline list `key: [a, b]`. That distinction is the single most
common way to lose a tag without being told, so it is worth stating as a measurement:

```
---                           ---
tags:                         tags: [kamailio, sip]
  - kamailio                  ---
  - sip
---                           → tags: kamailio, sip        ✓

→ tags: (none)    ✗
```

The block-list form is valid YAML and is silently ignored. Nothing warns, the save succeeds, and
the page ends up with no tags. If you are used to Jekyll, Hugo or Obsidian, this is the one place
doction will surprise you, and the fix is to write the list inline.

A second consequence of the same parse: the lines that were not understood stay where they are.
`GET /api/pages/{slug}/raw` on a page with a block list shows the block exactly as written, list
items included.

The block is part of the page content. It is stored with the page and it is indexed for search,
so a word that appears only in the metadata block is still findable.

## Finding pages by tag

Tags are stored per page and are what the tag filters in the interface are built from. Note that
**search has no field syntax**: `tag:voip` in a query is not a tag filter, it is two ordinary
terms, one of which is the literal word "tag". See [searching](search.md#there-is-no-query-syntax).

## Suggested tags

`GET /api/pages/{slug}/suggest-tags` proposes tags by comparing the page's terms against the rest
of the workspace, using TF-IDF. It needs no embeddings and no model, so it works on any instance.

Every suggestion response carries a `mode` field saying how it was produced, which is the honest
answer to "why did it suggest that": a suggestion from term statistics and one from a semantic
model are not the same claim.

## Where to go next

- [Searching](search.md), including what a query actually does
- [Linking pages](linking.md), the other way pages relate
