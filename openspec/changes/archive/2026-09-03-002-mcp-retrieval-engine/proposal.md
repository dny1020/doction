## Why

doction is a context server. It stores markdown, indexes it, and hands ranked fragments with
their provenance to whatever agent asked. It does not generate text, and this change does not
change that: `app/embeddings.py` already says so in a comment that has survived three changes —
*doction hace retrieval; la generación la hace el agente conectado por MCP — aquí no vive ningún
LLM* — and the `rag` tool's own description ends with "Does NOT generate text itself." Everything
below makes the retrieval better and the tool surface clearer. Nothing below puts a model that
writes prose inside this process.

That boundary is the reason the rest of the change is worth doing. An agent's answer is only as
good as the fragments it was handed, and today those fragments are cut badly, ranked by a formula
that was never measured against alternatives, and reached through a tool surface that grew one
tool at a time.

**The chunker does not know it is reading markdown.** `meta.chunk_markdown()` splits on blank
lines into ~1000-character windows with 150 characters of overlap, and its own docstring calls it
"tonto y rápido". A heading and the paragraph it introduces land in different chunks whenever the
window boundary falls between them, so the retrieved fragment says *"run `certbot renew` and
reload nginx"* with no indication of which runbook, which section, or which machine it belongs to.
A fenced code block longer than the window is sliced mid-block by a character offset. The
frontmatter is discarded outright — deliberately, to keep it out of the embedding — which also
means the chunk carries no type, no tags, and no title.

**The ranking blend was chosen, not measured.** `semantic_search()` scores every chunk by cosine,
keeps the best chunk per page, then adds a flat `KEYWORD_BOOST = 0.1` to any page that full-text
search also returned. Adding a constant to a cosine score mixes two scales that have no common
unit: the boost is large next to the gap between ranks 3 and 4, and negligible next to the gap
between ranks 1 and 10. `hybrid` mode does something different again — FTS hits first, then
semantic ones above a floor, concatenated. Two blends, neither derived from the numbers.

Those numbers exist. `evals/results/2026-08-24-minilm-en.json` records the run that set today's
configuration, over 27 pages and 28 queries:

| variant | recall@1 | MRR | zero-result | p50 | p95 |
|---|---|---|---|---|---|
| fts-english | 0.25 | 0.30 | 0.43 | 13 ms | 19 ms |
| fts-unaccent-en | 0.36 | 0.46 | 0.36 | 14 ms | 17 ms |
| semantic | 0.64 | 0.72 | 0.07 | 11 ms | 16 ms |
| hybrid | 0.61 | 0.72 | 0.04 | 11 ms | 15 ms |
| hybrid+rerank | 0.57 | 0.73 | 0.04 | 360 ms | 862 ms |

Read it and the shape of the problem is plain. Hybrid buys a lower zero-result rate than semantic
alone and pays 0.03 recall@1 for it — the exact-match half is being drowned rather than combined.
And the reranker is already documented as a net loss: +0.01 MRR, −0.04 recall@1, 29× the median
latency. It stays off, and this change does not turn it on; it tries to earn that MRR without the
cross-encoder.

**`rag_context()` returns whatever the chunker produced.** Six chunks, no deduplication, so two
overlapping windows from the same page can both make the list and spend an agent's context budget
twice on the same sentence. When semantic search is off it falls back to FTS snippets, which are
twelve words of `ts_headline` output — enough to rank a result, not enough to answer from.

**The MCP surface has twenty-one tools and no shape.** `search_pages` is keyword-only,
`sgrep` is semantic-with-a-boost, `rag` is top-k chunks, and an agent has no way to tell from the
descriptions which one to reach for. There is no tag or type filter on any search tool even though
`extract` proves the data supports one. And every write tool replaces a whole page: an agent that
learns one fact has to read the page, splice the text itself, and send the entire body back,
racing anyone else editing it.

## What Changes

- **The chunker becomes markdown-aware.** Sections split at headings, each chunk carries the
  heading path that locates it, and code blocks, tables and mermaid diagrams are never cut in half.
- **Ranking becomes Reciprocal Rank Fusion.** Lexical and vector retrieval each produce a ranked
  list and RRF combines them by position rather than by score, which removes the scale problem that
  `KEYWORD_BOOST` papers over. `keyword`, `semantic` and `hybrid` stay as modes; hybrid's internals
  change.
- **`rag_context()` deduplicates and packs.** Overlapping fragments from a page collapse, each
  fragment carries its heading path, and the result honours a context budget instead of a fixed k.
- **Five tools are named and specified as the agent-facing contract**: `search_knowledge`,
  `get_rag_context`, `get_workspace_tree`, `read_page_raw` and `upsert_page_section`. Four of them
  are the existing capability given a clear name and a filter; the fifth is genuinely new.
- **`upsert_page_section` lets an agent write one section** instead of replacing a page, so two
  agents editing different parts of a runbook do not overwrite each other.
- **Every ranking change is gated on the harness.** The baseline is re-established first, on the
  current code, and no change to `embeddings.py` or to the chunker lands without a run that holds
  or improves recall@1 and MRR against it.

Three things are deliberately **not** in this change:

- **No LLM, anywhere.** Not for query expansion, not for reranking, not for summarising a chunk
  before returning it. `suggest.py` already does local ML without one and that is the ceiling.
- **The cross-encoder reranker is not turned on.** It is measured and rejected on this corpus. If
  RRF closes the MRR gap without it, the flag can eventually be deleted; that is a later change.
- **No new embedding model.** The multilingual encoder was measured and rejected (0.30 vs 0.44 on
  Spanish paraphrase, 135 MB vs 23 MB). Changing the encoder invalidates every stored vector and is
  its own change with its own eval run.

## Capabilities

### New Capabilities

- `chunking`: how a markdown page is divided for indexing, and what context each piece keeps so a
  fragment retrieved on its own still says where it came from.
- `retrieval-ranking`: how lexical and vector retrieval are combined into one ordering, and what
  the assembled context an agent receives must contain.
- `mcp-tools`: the contract doction offers agents over MCP — which tools exist, what they take,
  what they return, and what they are forbidden from doing.
- `retrieval-evaluation`: the measurement discipline that gates changes to retrieval quality.

### Modified Capabilities

- `search`: its requirements are about what search finds — diacritic folding, a page retrieved by
  its own words, no regression on English technical vocabulary, no mixing of encoder spaces. RRF
  changes how results are ordered, so those requirements become the floor the new ranking must
  clear rather than a description of the old one. The scenarios stand; one requirement gains the
  statement that ordering is fused by rank.

Unmodified: everything from change 001. This change touches no frontend file.

## Impact

- **`app/meta.py`**: `chunk_markdown()` is replaced. Its callers (`db.create_page`,
  `db.update_page`, `embeddings.reindex_page`) keep their signatures; what changes is what a chunk
  contains.
- **Schema**: `page_chunks` gains the heading path and the section anchor. `init_db()` creates the
  columns with `IF NOT EXISTS`, and existing rows are re-embedded by the worker that already
  re-queues pages whose vectors came from a different encoder.
- **`app/embeddings.py`**: `semantic_search()` and `search()` are restructured around RRF;
  `KEYWORD_BOOST` goes away; `rag_context()` gains deduplication and a budget. `SEARCH_MIN_SCORE`
  survives as a floor on the vector list before fusion.
- **`app/mcp.py`**: five tool definitions added or renamed, with the old names kept as aliases for
  one release so a configured agent does not break mid-conversation.
- **`app/db.py`**: a section-addressed write for `upsert_page_section`, and a tag filter on the
  search path.
- **`evals/`**: a baseline run committed before any logic changes, then one run per ranking change.
  The query set grows to cover what the new tools promise; the corpus stays out of the repository.
- **Not affected**: the frontend, the auth model, git-backed page history, webhooks, and the
  embedding model itself.
