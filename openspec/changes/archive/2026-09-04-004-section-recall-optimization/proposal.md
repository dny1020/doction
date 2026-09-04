## Why

Change 003 measured section recall for the first time and got **0.38**: for five of the eight
queries that declare an expected heading, retrieval finds the right page and hands back the wrong
section of it. That is the exact failure heading-aware chunking was built to fix, and it was
invisible until there was a number for it.

A read-only diagnostic over the real corpus and the real encoder — no code changed — says the
hypothesis is right, and sharpens it. Four ways of packing the text before embedding, scored on
whether the query's best-matching section is the expected one, with the average cosine between
sibling sections of one page alongside:

| variant | packed text | sibling similarity | section recall |
|---|---|---|---|
| A, today | `Page > Ancestor > Section\n\nbody` | 0.685 (max 0.943) | 3/8 = 0.38 |
| B | `# Section\n\nbody` | 0.509 (max 0.848) | **6/8 = 0.75** |
| C | `Page: … \| Section: …\nbody` | 0.662 | 3/8 = 0.38 |
| D, control | `body` | 0.470 | 3/8 = 0.38 |

Variant A reproduces the harness's 0.38 exactly, which is the diagnostic validating itself.

**The problem is the ancestors, not the prefix.** Every section of one page shares the page title
and the ancestor chain, so that shared text is pure noise for telling siblings apart — and there is
a lot of it: sibling sections currently sit at 0.685 average cosine, with one pair at 0.943. Two
sections that answer different questions are nearly the same vector. Variant C barely moves because
the full page title is still in there.

**But the immediate heading is doing real work.** Variant D has the *least* shared text and the
lowest sibling similarity, and it does not improve recall: stripping the heading entirely makes
`dar permisos de administrador` pick the page preamble instead of the section that answers. Less
prefix is not the lever. The lever is dropping what siblings share while keeping what distinguishes
them.

**Two queries fail under every variant**, so packing is not the whole story. `where are the secrets
stored` picks the preamble over `Archivos de secretos`, and `how do I update a docker image` picks
`Rollback a imagen anterior` over `Actualizar un servicio especifico`. Both have a heading whose
words overlap the query heavily while the body does not. That is a different lever, and it is what
phase 2 is for.

**This collides with a decision 002 made deliberately.** The `chunking` spec says the path "MUST be
part of the text that is embedded", justified by: a section called "Renewal" only means something
next to its page, and two identically worded sections in different pages must not produce the same
vector. That reasoning is still sound for *cross-page* discrimination and is exactly wrong for
*intra-page* discrimination. The two goals pull in opposite directions and the current spec only
names one of them. This change has to resolve that honestly rather than quietly delete a
requirement because an experiment preferred it.

## What Changes

- **Three packing variants are measured end to end**, not just intra-page: the full harness, so the
  effect on page recall is visible next to the effect on section recall.
- **The winning variant ships only if page ranking holds.** Section recall must reach 0.65 and
  page recall@1 must not fall more than 0.02 from 0.68 hybrid / 0.71 semantic, with MRR held at
  0.75 / 0.77.
- **Cross-page collision is measured, not assumed.** If a variant drops the page title from the
  embedding, the change must show that two identically worded sections in different pages still
  rank apart — the property 002 added the title to protect.
- **A heading-match tiebreak is evaluated** for the two queries no packing fixes: when a query's
  terms appear in a section's own heading, that section breaks ties within its page. Evaluated as
  a separate step so its contribution is attributable, and shipped only if it earns its place.
- **The `chunking` spec stops prescribing the mechanism** and states the two outcomes it actually
  needs: a fragment must be locatable, and sibling sections must not collapse into near-identical
  vectors. The current wording mandates one implementation and names only one of the two goals.

Out of scope, deliberately:

- **No new model, no reranker.** Both were measured and rejected, twice.
- **No re-tuning of `RRF_K`, `RRF_VECTOR_WEIGHT` or `SEARCH_MIN_SCORE`.** If section recall moves
  the right ranking constants, that is a finding for its own change — the same discipline 003 held.
- **No change to what a chunk *is*.** Section boundaries, block integrity and the stored heading
  path all stay; only the string handed to the encoder is under test.

## Decisions taken during implementation

- **`search(mode="semantic")` is accepted as the weaker mode**, at 0.64 recall@1 against hybrid's
  0.68. It is an explicitly named API mode a caller opts into, and no doction surface uses it: the
  sidebar, the REST default and every MCP tool go through hybrid or through assembled context. The
  alternative was keeping page context in the embedding, which is what made siblings
  indistinguishable in the first place. Recorded rather than fixed.
- **Assembled context targets 60 ms**, three times hybrid's 20 ms. It loads the workspace's vectors
  once, fuses, then packs and deduplicates, and deduplication compares each candidate against every
  fragment already kept. That is the cost of assembling an answer's worth of context rather than
  ordering a list, and it is paid by an agent-facing call, not by a keystroke in the sidebar. Two
  earlier versions cost 187 ms and 418 ms; both were defects, not the price of the design.

- **The cross-page collision is resolved at retrieval, not in the vector.** Two identically worded
  sections do produce the same vector, and that is correct: with the same text there is nothing
  *in the section* to tell them apart. What separates them is page ranking, where the lexical
  channel sees the title. Putting a page identifier back into the embedded text was tried and
  measured — the full slug costs 0.10 of section recall, a six-character hash costs 0.07 of page
  recall@1 in hybrid and in assembled context and buys nothing in section recall, because an opaque
  token is random direction added to every comparison. The `chunking` delta was amended to require
  the outcome instead of the mechanism, which is what this change existed to do.

## Capabilities

### Modified Capabilities

- `chunking`: the requirement that the heading path be part of the embedded text is replaced by the
  two properties that requirement was standing in for. The path stays stored and returned either
  way; what changes is that the spec stops naming an implementation and starts naming a measurable
  outcome, including the one it was missing.

### Unmodified

`retrieval-ranking`, `retrieval-evaluation`, `mcp-tools` and `search` are untouched. If the
heading-match tiebreak ships, it changes how ties are broken inside an existing fused ordering,
which `retrieval-ranking` already permits — it requires fusion by rank and forbids mixing score
scales, and a tiebreak on an exact heading match does neither.

## Impact

- **`app/embeddings.py`**: `_embed_text()` changes shape; possibly a tiebreak in the vector
  ranking. `meta.CHUNKER_ID` bumps, because the embedded text changes and every stored vector
  becomes stale — this one genuinely needs the re-index that 003's did not.
- **`evals/`**: a way to run the harness under a packing variant so the three can be compared in
  one run rather than three edits; more section-level expectations, since eight queries is a thin
  basis for a 0.65 target.
- **Not affected**: the frontend, the MCP tool surface, the chunker's boundaries, the stored path,
  and the ranking constants.
- **Deployment**: first start after this re-embeds every page. On the Pi that is minutes of CPU on
  the existing worker, with search degrading to keyword until it finishes, which is the behaviour
  `chunking` already specifies.
