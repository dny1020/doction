## 1. Baseline before anything

- [x] 1.1 Add a `chunker` identity field to the harness output so two runs across this change say
      what produced them; without it the before-and-after is unlabelled.
- [x] 1.2 Run the harness against the current code and the full `data/eval-corpus` dump, and commit
      the result. The committed 2026-08-24 runs were 27 pages; a run over three workspaces is not
      comparable to them, so this is the only baseline this change may cite.
- [x] 1.3 Record in the result file the corpus size, query count, model and chunker, and verify a
      reader can tell it apart from the August runs.

## 2. Markdown-aware chunking

- [x] 2.1 Replace `meta.chunk_markdown()` with a section-aware splitter: split at headings, keep a
      heading with the prose it introduces, and split within a section at paragraph boundaries only
      when it exceeds the ceiling.
- [x] 2.2 Keep fenced code blocks, tables and mermaid diagrams whole, letting the ceiling yield
      when one block exceeds it. Verify with a test per block type, including a fence longer than
      the ceiling and a boundary that would fall inside a table.
- [x] 2.3 Return the heading path with each chunk, and make the path part of the embedded text so
      two identically worded sections in different pages do not produce identical vectors.
- [x] 2.4 Add the heading path and section anchor to `page_chunks` with `CREATE ... IF NOT EXISTS`
      columns, matching how `init_db()` already converges.
- [ ] 2.5 Expose the chunk's frontmatter-derived type and tags alongside it without embedding the
      raw frontmatter block as prose.
- [x] 2.6 Store a chunker identity beside `model` and re-queue pages whose chunks came from a
      different one, reusing the `mark_stale_model_dirty` mechanism. Verify search keeps working
      mid-reindex and that a converged deployment re-queues nothing.
- [x] 2.7 Run the harness. Chunking alone must hold recall@1 and MRR against the 1.2 baseline
      before any ranking work starts, so the two effects stay separable.

## 3. Rank fusion

- [x] 3.1 Make each retriever return its own ranked list, unmixed: lexical from `db.search_pages`,
      vector from the cosine pass, neither aware of the other's score.
- [x] 3.2 Implement Reciprocal Rank Fusion over the two lists and delete `KEYWORD_BOOST`. Verify by
      test that no lexical score is ever compared with or added to a vector score.
- [x] 3.3 Collapse the two blends into one: `sgrep` and the sidebar's `hybrid` must produce the
      same ordering for the same query. Keep `keyword` and `semantic` as single-retriever modes.
- [x] 3.4 Keep `SEARCH_MIN_SCORE` as a floor on the vector list before fusion, and verify a page
      the lexical retriever ranks first is not suppressed by it.
- [x] 3.5 Return per-list ranks and the heading path on every hit, so an ordering can be checked
      rather than trusted.
- [x] 3.6 Verify fusion is deterministic, ties included, with a test that runs the same query twice
      against unchanged data.
- [ ] 3.7 Add the ranking parameters to `GET /api/system`, and verify a search request cannot
      override them.
- [x] 3.8 Run the harness. RRF must beat `hybrid`'s 0.61 recall@1 while holding its 0.04
      zero-result rate; if it cannot do both, record the trade and decide explicitly.

## 4. Assembled context

- [ ] 4.1 Deduplicate `rag_context()` output: overlapping fragments from one page collapse to one,
      while distinct sections of the same page both survive.
- [ ] 4.2 Replace the fixed `k=6` with a size budget, leaving a fragment out entirely rather than
      truncating it, and say in the response when the context was cut.
- [x] 4.3 Carry page, heading path and score on every fragment.
- [ ] 4.4 Make the lexical fallback return page text rather than the twelve-word `ts_headline`
      extract, which is enough to rank a result and not enough to answer from.
- [x] 4.5 Verify every returned fragment appears verbatim in a stored page, and that an empty
      result is reported as empty rather than filled with something composed.

## 5. MCP tools

- [x] 5.1 Add `search_knowledge`: hybrid search with `tag` and `type` filters applied during
      retrieval, not after. Reuse the `page_meta` / `page_tags` joins that `db.extract_pages`
      already uses.
- [x] 5.2 Verify a filter that matches nothing returns empty rather than falling back to unfiltered
      results, and that a page which would rank below the cut without the filter can appear with it.
- [x] 5.3 Rename `rag` to `get_rag_context` and `list_pages` to `get_workspace_tree`, the latter
      returning a hierarchy rather than a flat list with `depth`.
- [x] 5.4 Rename `get_page` to `read_page_raw` and return the parsed frontmatter alongside the
      untouched body. Verify the returned content is byte-identical to what a write must preserve.
- [x] 5.5 Keep every old tool name as an alias for one release, and verify an agent configured
      against the previous names still works.
- [x] 5.6 Rewrite the five descriptions so an agent can tell them apart without trying them, and
      so every write tool is identifiable as a write.
- [x] 5.7 Verify the read-only tools change no page, no index entry and no delivery queue.

## 6. Section writes

- [x] 6.1 Add a section-addressed write to `app/db.py`: locate a heading, replace its body up to
      the next heading of the same or higher level, leave every other byte untouched.
- [x] 6.2 Route it through the existing page-update path so history, re-indexing and webhooks
      behave exactly as for any other write. Verify all three with tests.
- [x] 6.3 Append the section when the heading does not exist, at the requested level.
- [x] 6.4 Refuse when the page has two sections with the same heading at the same level, rather
      than picking one.
- [x] 6.5 Decide and document whether a missing page is created or reported, and make the tool
      description say which.
- [x] 6.6 Verify two agents writing different sections of one page at overlapping times both keep
      their edit.
- [x] 6.7 Expose it as `upsert_page_section` over MCP.

## 7. Evaluation

- [ ] 7.1 Extend `queries.json` so an expectation can name a section, not only a page slug, and add
      queries whose answer lives in a subsection of a long page.
- [ ] 7.2 Add query cases for the filters `search_knowledge` promises: by tag, by type, and both.
- [x] 7.3 Replace the `KEYWORD_BOOST` sweep with a sweep over RRF's constant, so `--sweep` does not
      point at a constant that no longer exists.
- [x] 7.4 Verify the automated test suite asserts no recall or MRR threshold and passes on a
      machine with no corpus.

### Notes on what shipped, and what did not

- **Two effects, measured separately.** The chunker and the fusion were run through the harness
  one at a time, so their contributions are attributable. Baseline 0.57 recall@1 → chunker 0.61 →
  fusion 0.68 on hybrid; `semantic` went 0.64 → 0.71 on the chunker alone.
- **The fusion is weighted, which classic RRF is not.** Unweighted it measured 0.64, below plain
  semantic's 0.71: the two lists are not equally good on this corpus (keyword 0.46 MRR against the
  vectors' 0.77), so an equal vote drags the better one down. Sweeping RRF's `k` from 10 to 100
  changed nothing at all; the vector weight is the lever, its plateau starts at 1.5, and 2.0 is the
  low end of it. Both sweeps are committed.
- **Class A regressed on purpose.** Concatenation put keyword hits first unconditionally, which
  happened to be excellent for unaccented Spanish. Fusion brings hybrid to exactly semantic's level
  there (0.90 → 0.79) and buys 0.10 and 0.12 MRR on the two classes where hybrid was worst.
- **Hybrid still trails semantic by 0.03 recall@1** — one query in twenty-eight. It equals it on
  four of the five query classes and is behind only on English questions.
- **The markdown surgery lives in `meta.py`, not `db.py`.** The task said the write goes in `db.py`
  and it does; the parsing sits with the rest of the markdown parsing, because moving a parser into
  the database layer would cross a boundary this project already keeps.

**Left unimplemented, and now live specs the code does not yet satisfy:**

- **4.1, 4.2, 4.4** — `rag_context` still returns a fixed six chunks with no deduplication and no
  size budget, and its keyword fallback still returns twelve-word `ts_headline` extracts rather
  than page text. The `retrieval-ranking` spec's requirement that assembled context be
  deduplicated and bounded is therefore not met. Dropping chunk overlap made near-duplicates much
  rarer, which is why this was not urgent, but it is not the same as done.
- **3.7** — the ranking parameters are not in `GET /api/system`, so the `retrieval-ranking`
  requirement that they be readable as deployment state is not met.
- **2.5** — a chunk's frontmatter type and tags are not returned alongside it.
- **7.1, 7.2** — the query set has no section-level expectations and no filter cases, so chunking's
  heading context and `search_knowledge`'s filters are tested for behaviour but not measured for
  quality.

## 8. Verification

- [x] 8.1 Final harness run against the 1.2 baseline: recall@1 and MRR at or above it, zero-result
      rate no worse, latency reported. Commit the result.
- [x] 8.2 Confirm no language model is loaded, called or configured anywhere in the retrieval path.
- [x] 8.3 Confirm the `search` spec's existing scenarios still hold, in particular that a query of
      a page's own words returns that page first.
- [x] 8.4 Confirm change 001's capabilities are untouched: no frontend file changed.
- [x] 8.5 Run the Python gate: `uv run ruff check . && uv run ruff format --check . && uv run
      pyright app tests && uv run pytest`.
