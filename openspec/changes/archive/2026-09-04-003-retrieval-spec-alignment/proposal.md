## Why

Change 002 was archived with 39 of its 46 tasks done. Archiving promoted its specs to
`openspec/specs/`, so four requirements are now live contracts that the code does not honour. A
spec the implementation contradicts is worse than no spec: it stops describing the system and
starts describing an intention, and the next person to read it will believe it.

This change closes the gap. It adds no new requirements — every line below is already written in
`retrieval-ranking`, `chunking` or `retrieval-evaluation`.

**Assembled context is neither deduplicated nor bounded.** `retrieval-ranking` says the context
returned to an agent "SHALL NOT contain the same passage twice" and "SHALL be bounded by a size
budget rather than a fixed number of fragments". `rag_context()` returns exactly six chunks in
score order with no comparison between them. Dropping chunk overlap in 002 made verbatim
near-duplicates much rarer, which is why this was not urgent, but rarer is not the same as absent:
two adjacent sections of one page can still restate the same instruction, and six of them can still
blow past a small model's context window because nothing counts characters. The spec also forbids
truncating a fragment to fit, which nothing currently enforces because nothing currently fits
anything.

**The keyword fallback still hands back ranking extracts.** The same spec says that when vector
search is unavailable "the fragments are page text, not the short highlighted extracts used to rank
results". `rag_context()`'s fallback returns `ts_headline` output: twelve words, chosen to show a
person why a result matched. That is enough to rank a page and not enough to answer from, so on a
deployment with `SEMANTIC_SEARCH=0` — which is the default — the tool that exists to feed an agent
feeds it fragments of sentences.

**The ranking parameters are invisible.** `retrieval-ranking` requires that they "be properties of
the running deployment, readable through the existing system report". `RRF_K` and
`RRF_VECTOR_WEIGHT` decide the order of every hybrid result and appear nowhere in `GET /api/system`.
Two deployments on the same version can rank differently and neither can say so. The weight in
particular is a measured value with a sweep behind it; hiding it makes that measurement
unreproducible from outside.

**A chunk's frontmatter does not travel with it.** `chunking` says a page's declared type and tags
"are retrievable alongside the chunk". The chunker parses the frontmatter off and keeps the heading
path; the type and tags are dropped. An agent that retrieves a passage cannot tell whether it came
from a runbook or a meeting note without a second call.

**Two capabilities are tested but unmeasured.** `retrieval-evaluation` requires the query set to
cover "each kind the tool surface claims to serve", and names section-level retrieval explicitly:
"queries whose answer is in one section of a long page, and the expected result names that section".
Every expectation in `queries.json` is a page slug. So the heading context that 002's chunker exists
to preserve is verified by unit tests and has never been scored, and the same is true of
`search_knowledge`'s tag filter. The change that introduced both capabilities could not measure
either.

## What Changes

- **`rag_context()` deduplicates and packs to a budget.** Fragments that repeat a passage collapse;
  distinct sections of one page both survive. A character budget replaces the fixed six, a fragment
  that does not fit is left out whole rather than cut, and the response says when it was truncated.
- **The keyword fallback returns section text.** When there are no vectors, fragments come from the
  page body — the same sections the chunker produces — instead of `ts_headline` extracts. Search
  results keep their highlighted extracts; only assembled context changes.
- **`GET /api/system` reports the ranking parameters**, read-only, beside the retrieval flags it
  already reports.
- **Chunks carry their page's type and tags**, without the raw frontmatter block being embedded as
  prose.
- **The query set grows a section-level expectation and filter cases**, and the harness scores
  whether the retrieved fragment came from the expected section rather than only the expected page.

Two things this change deliberately does **not** do:

- **No re-tuning.** `RRF_K`, `RRF_VECTOR_WEIGHT` and `SEARCH_MIN_SCORE` keep the values 002
  measured. Adding section-level scoring will produce a number that invites tuning; tuning against
  a metric the same change invented is how a benchmark stops meaning anything. If the new cases say
  the constants are wrong, that is a finding and its own change.
- **No new retrieval capability.** No filter that a spec does not already promise, no new tool, no
  model.

## Capabilities

### Modified Capabilities

- `system-status`: the report gains the ranking parameters. `retrieval-ranking` already requires
  them to be readable through this report; `system-status` governs what the report contains, so it
  is the spec that has to say so.

### Unmodified

`retrieval-ranking`, `chunking` and `retrieval-evaluation` are the specs being satisfied, not
changed. Nothing here adds a requirement to them — if implementation reveals one of them is wrong,
that is a separate change and should be argued as such rather than edited into alignment with
whatever got built.

## Impact

- **`app/embeddings.py`**: `rag_context()` gains deduplication, a budget and a truncation flag; the
  keyword fallback stops using `ts_headline` output.
- **`app/db.py`**: a way to fetch section text for the keyword fallback, and chunk type/tags read
  back with the chunk.
- **`app/meta.py`** and **`page_chunks`**: the chunk's frontmatter-derived type and tags stored
  beside its path. This is another chunker-identity bump, so it re-indexes on first start exactly
  as 002 did.
- **`app/main.py`**: two more read-only rows in the system report.
- **`evals/`**: `queries.json` gains section and filter expectations; the harness learns to score a
  section-level expectation and to run a filtered query.
- **Not affected**: the frontend, the MCP tool surface, ranking behaviour, and the constants
  themselves.
