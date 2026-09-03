## 1. Baseline before anything

- [ ] 1.1 Add a `chunker` identity field to the harness output so two runs across this change say
      what produced them; without it the before-and-after is unlabelled.
- [ ] 1.2 Run the harness against the current code and the full `data/eval-corpus` dump, and commit
      the result. The committed 2026-08-24 runs were 27 pages; a run over three workspaces is not
      comparable to them, so this is the only baseline this change may cite.
- [ ] 1.3 Record in the result file the corpus size, query count, model and chunker, and verify a
      reader can tell it apart from the August runs.

## 2. Markdown-aware chunking

- [ ] 2.1 Replace `meta.chunk_markdown()` with a section-aware splitter: split at headings, keep a
      heading with the prose it introduces, and split within a section at paragraph boundaries only
      when it exceeds the ceiling.
- [ ] 2.2 Keep fenced code blocks, tables and mermaid diagrams whole, letting the ceiling yield
      when one block exceeds it. Verify with a test per block type, including a fence longer than
      the ceiling and a boundary that would fall inside a table.
- [ ] 2.3 Return the heading path with each chunk, and make the path part of the embedded text so
      two identically worded sections in different pages do not produce identical vectors.
- [ ] 2.4 Add the heading path and section anchor to `page_chunks` with `CREATE ... IF NOT EXISTS`
      columns, matching how `init_db()` already converges.
- [ ] 2.5 Expose the chunk's frontmatter-derived type and tags alongside it without embedding the
      raw frontmatter block as prose.
- [ ] 2.6 Store a chunker identity beside `model` and re-queue pages whose chunks came from a
      different one, reusing the `mark_stale_model_dirty` mechanism. Verify search keeps working
      mid-reindex and that a converged deployment re-queues nothing.
- [ ] 2.7 Run the harness. Chunking alone must hold recall@1 and MRR against the 1.2 baseline
      before any ranking work starts, so the two effects stay separable.

## 3. Rank fusion

- [ ] 3.1 Make each retriever return its own ranked list, unmixed: lexical from `db.search_pages`,
      vector from the cosine pass, neither aware of the other's score.
- [ ] 3.2 Implement Reciprocal Rank Fusion over the two lists and delete `KEYWORD_BOOST`. Verify by
      test that no lexical score is ever compared with or added to a vector score.
- [ ] 3.3 Collapse the two blends into one: `sgrep` and the sidebar's `hybrid` must produce the
      same ordering for the same query. Keep `keyword` and `semantic` as single-retriever modes.
- [ ] 3.4 Keep `SEARCH_MIN_SCORE` as a floor on the vector list before fusion, and verify a page
      the lexical retriever ranks first is not suppressed by it.
- [ ] 3.5 Return per-list ranks and the heading path on every hit, so an ordering can be checked
      rather than trusted.
- [ ] 3.6 Verify fusion is deterministic, ties included, with a test that runs the same query twice
      against unchanged data.
- [ ] 3.7 Add the ranking parameters to `GET /api/system`, and verify a search request cannot
      override them.
- [ ] 3.8 Run the harness. RRF must beat `hybrid`'s 0.61 recall@1 while holding its 0.04
      zero-result rate; if it cannot do both, record the trade and decide explicitly.

## 4. Assembled context

- [ ] 4.1 Deduplicate `rag_context()` output: overlapping fragments from one page collapse to one,
      while distinct sections of the same page both survive.
- [ ] 4.2 Replace the fixed `k=6` with a size budget, leaving a fragment out entirely rather than
      truncating it, and say in the response when the context was cut.
- [ ] 4.3 Carry page, heading path and score on every fragment.
- [ ] 4.4 Make the lexical fallback return page text rather than the twelve-word `ts_headline`
      extract, which is enough to rank a result and not enough to answer from.
- [ ] 4.5 Verify every returned fragment appears verbatim in a stored page, and that an empty
      result is reported as empty rather than filled with something composed.

## 5. MCP tools

- [ ] 5.1 Add `search_knowledge`: hybrid search with `tag` and `type` filters applied during
      retrieval, not after. Reuse the `page_meta` / `page_tags` joins that `db.extract_pages`
      already uses.
- [ ] 5.2 Verify a filter that matches nothing returns empty rather than falling back to unfiltered
      results, and that a page which would rank below the cut without the filter can appear with it.
- [ ] 5.3 Rename `rag` to `get_rag_context` and `list_pages` to `get_workspace_tree`, the latter
      returning a hierarchy rather than a flat list with `depth`.
- [ ] 5.4 Rename `get_page` to `read_page_raw` and return the parsed frontmatter alongside the
      untouched body. Verify the returned content is byte-identical to what a write must preserve.
- [ ] 5.5 Keep every old tool name as an alias for one release, and verify an agent configured
      against the previous names still works.
- [ ] 5.6 Rewrite the five descriptions so an agent can tell them apart without trying them, and
      so every write tool is identifiable as a write.
- [ ] 5.7 Verify the read-only tools change no page, no index entry and no delivery queue.

## 6. Section writes

- [ ] 6.1 Add a section-addressed write to `app/db.py`: locate a heading, replace its body up to
      the next heading of the same or higher level, leave every other byte untouched.
- [ ] 6.2 Route it through the existing page-update path so history, re-indexing and webhooks
      behave exactly as for any other write. Verify all three with tests.
- [ ] 6.3 Append the section when the heading does not exist, at the requested level.
- [ ] 6.4 Refuse when the page has two sections with the same heading at the same level, rather
      than picking one.
- [ ] 6.5 Decide and document whether a missing page is created or reported, and make the tool
      description say which.
- [ ] 6.6 Verify two agents writing different sections of one page at overlapping times both keep
      their edit.
- [ ] 6.7 Expose it as `upsert_page_section` over MCP.

## 7. Evaluation

- [ ] 7.1 Extend `queries.json` so an expectation can name a section, not only a page slug, and add
      queries whose answer lives in a subsection of a long page.
- [ ] 7.2 Add query cases for the filters `search_knowledge` promises: by tag, by type, and both.
- [ ] 7.3 Replace the `KEYWORD_BOOST` sweep with a sweep over RRF's constant, so `--sweep` does not
      point at a constant that no longer exists.
- [ ] 7.4 Verify the automated test suite asserts no recall or MRR threshold and passes on a
      machine with no corpus.

## 8. Verification

- [ ] 8.1 Final harness run against the 1.2 baseline: recall@1 and MRR at or above it, zero-result
      rate no worse, latency reported. Commit the result.
- [ ] 8.2 Confirm no language model is loaded, called or configured anywhere in the retrieval path.
- [ ] 8.3 Confirm the `search` spec's existing scenarios still hold, in particular that a query of
      a page's own words returns that page first.
- [ ] 8.4 Confirm change 001's capabilities are untouched: no frontend file changed.
- [ ] 8.5 Run the Python gate: `uv run ruff check . && uv run ruff format --check . && uv run
      pyright app tests && uv run pytest`.
