# Design — current retrieval, and the exact deltas

Written from the code as it stands after change 001. Line references are to that tree.

## 1. Chunking

| Requirement | State | Where |
|---|---|---|
| Split on markdown headings | **Missing** — splits on blank lines into ~1000-char windows | `app/meta.py:119` |
| Heading path on each chunk | **Missing** — a chunk is a bare string | `app/meta.py:150` |
| Path included in the embedding | **Missing** | `app/embeddings.py` `reindex_page` |
| Frontmatter reachable from a chunk | **Missing** — discarded before chunking, by design | `app/meta.py:125` |
| Code blocks kept whole | **Missing** — an over-long paragraph is sliced by character offset | `app/meta.py:134-142` |
| Tables and mermaid kept whole | **Missing** — same path, no block awareness |
| Re-index on chunker change | **Partial** — the mechanism exists, keyed on the model only | `app/embeddings.py` `mark_stale_model_dirty` |

`chunk_markdown(text, max_chars=1000, overlap=150)` parses off the frontmatter, splits the body on
blank lines, and greedily packs paragraphs into windows. A paragraph longer than the window is cut
at `para[i : i + max_chars]` — a character offset, with no idea whether it is inside a fence. Its
docstring is honest about this: *"Tonto y rápido (no usa el tokenizer)"*. It was the right call for
a first index and it is the thing standing between a good encoder and good fragments.

**Storage.** `page_chunks` holds `(page_id, workspace_id, ord, text, vector, model, created_at)`
(`app/db.py:326`). There is no column for a heading path or a section anchor, so the delta is two
columns plus the `IF NOT EXISTS` create that `init_db()` already uses for everything.

**Re-indexing already converges on one axis.** `mark_stale_model_dirty()` re-queues pages whose
chunks came from a different encoder, and `enrichment_worker` drains the queue. The chunker needs
the same treatment: a chunker identity stored beside `model`, compared at startup. Without it, a
deployment that upgrades keeps serving chunks cut the old way until someone edits each page.

## 2. Ranking

| Requirement | State | Where |
|---|---|---|
| Independent ranked lists per retriever | **Partial** — both exist, neither is kept as a ranking | `app/embeddings.py:300`, `app/db.py` `search_pages` |
| Rank fusion | **Missing** — a constant is added to a cosine score | `app/embeddings.py:39` `KEYWORD_BOOST = 0.1` |
| One blend, not two | **Missing** — `sgrep` boosts, `hybrid` concatenates | `app/embeddings.py:392-410` |
| Provenance on a result | **Partial** — `via` says the retriever; no heading path, no per-list rank | `app/embeddings.py` |
| Deduplicated context | **Missing** — `rag_context` returns top-k rows as they come | `app/embeddings.py:415` |
| Context budget | **Missing** — fixed `k=6` |
| Fragments returned whole | **Partial** — semantic chunks are whole; the FTS fallback returns 12-word extracts | `app/db.py:1436` |
| No LLM in the path | **Covered** | `app/embeddings.py`, `app/suggest.py` |
| Ranking config in the system report | **Partial** — flags are reported; the constants are not | `app/main.py` `/api/system` |

There are two different blends in one file. `semantic_search()` keeps the best chunk per page by
cosine, then adds `KEYWORD_BOOST` to any page that `db.search_pages` also returned. `search(mode=
"hybrid")` ignores that entirely: it lists the FTS hits first, then appends the semantic hits above
`SEARCH_MIN_SCORE` that are not already present. So `sgrep` and the sidebar rank differently, and
neither ordering came out of the harness.

**The evidence for changing it is already committed.** From `evals/results/2026-08-24-minilm-en.json`,
27 pages and 28 queries:

| variant | recall@1 | MRR | zero-result | p50 | p95 |
|---|---|---|---|---|---|
| fts-english | 0.25 | 0.30 | 0.43 | 13 ms | 19 ms |
| fts-unaccent-en | 0.36 | 0.46 | 0.36 | 14 ms | 17 ms |
| semantic | 0.64 | 0.72 | 0.07 | 11 ms | 16 ms |
| hybrid | 0.61 | 0.72 | 0.04 | 11 ms | 15 ms |
| hybrid+rerank | 0.57 | 0.73 | 0.04 | 360 ms | 862 ms |

Hybrid trades 0.03 recall@1 for a lower zero-result rate. That is the concatenation showing: FTS
hits go first whether or not they are better than the semantic hit below them. RRF is the change
that should recover it, and the table is the thing it has to beat.

**The reranker is measured and rejected**, and this change does not revisit it: `+0.01` MRR,
`−0.04` recall@1, 29× median latency. `RERANK_CANDIDATES` and the ONNX cross-encoder stay where
they are, off.

## 3. MCP surface

`app/mcp.py` is a native JSON-RPC server, no SDK, with **21 tools** in `TOOLS` and a matching
`TOOL_HANDLERS` map. `initialize` and `tools/list` are open; `tools/call` requires Bearer auth.

| Proposed tool | Nearest existing | Delta |
|---|---|---|
| `search_knowledge` | `search_pages` (`mcp.py:288`) keyword-only, and `sgrep` (`mcp.py:430`) semantic | **Rename + merge + filters.** One hybrid search with `tag` and `type`; neither existing tool has a filter |
| `get_rag_context` | `rag` (`mcp.py:499`) | **Rename + contract.** Handler is `embeddings.rag_context`; needs dedup, heading paths and a budget |
| `get_workspace_tree` | `list_pages` (`mcp.py:274`) | **Rename + shape.** Returns a flat DFS list with `depth`; the tree can be rebuilt client-side, but the tool promises a hierarchy |
| `read_page_raw` | `get_page` (`mcp.py:279`) | **Rename + frontmatter.** `db.get_page` returns the stored body, so the raw text is already right; the parsed frontmatter is not returned alongside it |
| `upsert_page_section` | `update_page` (`mcp.py:369`) | **New.** `update_page` replaces the whole body — an agent must read, splice and send everything back |

Filters are not a new capability, only a new place for one: `db.extract_pages()` (`app/db.py:1556`)
already filters a workspace by frontmatter `type` and by tag, joining `page_meta` and `page_tags`.
The delta is applying the same joins on the search path instead of only on `extract`.

**Renaming is the risk in this section.** An agent configured against `sgrep` breaks the moment the
name goes away, mid-conversation, with an error it cannot act on. The old names stay as aliases
for one release.

**`upsert_page_section` is the only genuinely new capability**, and its hard part is not MCP. It
needs a section-addressed write in `app/db.py`: locate a heading in the stored markdown, replace
its body up to the next heading of the same or higher level, and write the result through the
existing `update_page` path so git history, re-indexing and webhooks all behave normally. Two
sub-problems worth naming now: a page with two identical headings is ambiguous (the spec says
refuse), and two agents writing different sections concurrently must both survive, which the
current read-modify-write from the client side cannot promise.

## 4. Evaluation harness

| Requirement | State | Where |
|---|---|---|
| Harness exists, outside pytest | **Covered** | `evals/retrieval.py` |
| Query set with expected pages | **Covered** — 28 queries in five classes | `evals/queries.json` |
| Baselines committed | **Covered** — two runs, 2026-08-24 | `evals/results/` |
| Metrics: recall@1, MRR, zero-result, p50/p95 | **Covered** | `evals/retrieval.py:111` |
| Corpus kept out of the repository | **Covered** | `evals/corpus.py:16` |
| A run records its conditions | **Partial** — records model, corpus size, query count; not the chunker |
| Section-level queries | **Missing** — every expected answer is a page slug |
| A baseline for *this* change | **Missing** — the committed runs predate it |

The harness is in good shape and needs extending, not building. It creates a throwaway database,
loads a markdown dump, indexes it with the real ONNX model, and prints one table comparing four FTS
variants, semantic, hybrid and rerank. `--sweep` scans `SEARCH_MIN_SCORE` and `KEYWORD_BOOST`.

Three concrete gaps:

- **`KEYWORD_BOOST` has a sweep and RRF has no knob to sweep.** RRF's `k` constant needs the
  equivalent, or the sweep becomes dead code pointed at a constant that no longer exists.
- **Expectations are page-level.** `queries.json` entries name expected slugs. Measuring whether
  chunking preserved a heading path requires an expected *section*, which the schema does not
  express today.
- **A run does not record the chunker.** Two runs across this change will differ by chunker and by
  ranking, and the result files will not say so. One field, added before the baseline run.

**The corpus is present on this machine** at `data/eval-corpus/` (three workspaces: `personal`,
`work`, `bussisnes`), which is what makes the baseline runnable at all. It is gitignored and stays
that way — the committed baseline was 27 pages, so a run against the full three-workspace dump is
**not** comparable to it and a fresh baseline is required before any logic changes.

## What this change does not touch

- The embedding model. Swapping it invalidates every stored vector and was already measured and
  rejected once (`paraphrase-multilingual-MiniLM-L12-v2`: 135 MB vs 23 MB, and worse on both
  Spanish paraphrase and conceptual queries).
- The cross-encoder reranker, which stays off.
- The frontend, in its entirety.
- Auth, git-backed history, webhooks, and every capability specified by change 001.
