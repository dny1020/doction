## 1. Assembled context: deduplicate and bound

- [ ] 1.1 Add a size budget to `rag_context()` in characters, replacing the fixed `k=6`. Verify a
      long workspace returns fewer, whole fragments rather than six of arbitrary length.
- [ ] 1.2 Leave a fragment out entirely when it does not fit, never truncated, and say in the
      response that the context was cut. Verify no returned fragment is a prefix of a stored one.
- [ ] 1.3 Deduplicate fragments that repeat a passage: same section, or bodies overlapping past a
      threshold. Verify two near-identical fragments from one page collapse to one.
- [ ] 1.4 Verify two *distinct* sections of the same page both survive — they answer different
      parts of the question, and collapsing them would be the opposite bug.
- [ ] 1.5 Verify every fragment still carries its page, its heading path and its score, and that
      each appears verbatim in a stored page.

## 2. Keyword fallback returns page text

- [ ] 2.1 Make `rag_context()`'s fallback return section text from the page body instead of
      `ts_headline` output. Verify on a deployment with semantic search off that a fragment is a
      whole section, not twelve words.
- [ ] 2.2 Leave search results alone: `/api/search` and `search_knowledge` keep their highlighted
      extracts, which is what the sidebar renders in `<mark>`. Verify the highlight still works.
- [ ] 2.3 Verify the fallback honours the same budget and deduplication as the vector path — one
      contract, two sources.

## 3. Ranking parameters in the system report

- [ ] 3.1 Add the fusion constant, the vector weight and the score floor to `GET /api/system`,
      read-only, beside the retrieval flags.
- [ ] 3.2 Verify a request cannot override them, and that the reported values are the ones the
      running process uses rather than defaults read from source.
- [ ] 3.3 Show them in the settings System section, as informational rows like the rest.

## 4. Chunk frontmatter

- [ ] 4.1 Carry a page's frontmatter `type` and tags with each of its chunks, without embedding the
      raw frontmatter block as prose. Verify the embedded text is unchanged by this.
- [ ] 4.2 Store them beside the chunk's path and return them with a retrieved fragment, so an agent
      can tell a runbook from a meeting note without a second call.
- [ ] 4.3 Bump the chunker identity so existing deployments re-index on first start, and verify
      search keeps working mid-reindex.

## 5. Evaluation coverage

- [ ] 5.1 Let a query in `queries.json` name an expected section as well as an expected page, and
      keep page-only expectations working unchanged.
- [ ] 5.2 Teach the harness to score a section-level expectation: whether the retrieved fragment
      came from the expected section, reported separately from page-level recall so the two are not
      conflated.
- [ ] 5.3 Add queries whose answer lives in one section of a long page, with the expected section
      named. These measure the heading context that 002's chunker exists to preserve and that has
      never been scored.
- [ ] 5.4 Add tag-filtered cases that exercise `search_knowledge`'s filter, including one where the
      filter must lift a page that would otherwise rank below the cut.
- [ ] 5.5 Verify the harness still runs, and the existing 28 queries still score, with the new
      fields absent.

## 6. Verification

- [ ] 6.1 Run the harness against `2026-09-04-baseline-002-final.json`: recall@1 and MRR at or
      above it, zero-result rate no worse, latency reported. Commit the result.
- [ ] 6.2 Do not re-tune `RRF_K`, `RRF_VECTOR_WEIGHT` or `SEARCH_MIN_SCORE` in this change. If the
      new section-level cases say a constant is wrong, record it as a finding for its own change —
      tuning against a metric this change invented would make the benchmark meaningless.
- [ ] 6.3 Confirm the four live specs this change exists to satisfy now hold: `retrieval-ranking`
      on deduplication, budget, fallback text and configuration visibility; `chunking` on
      frontmatter; `retrieval-evaluation` on query coverage.
- [ ] 6.4 Confirm nothing in the MCP tool surface or the frontend changed except the two new
      informational rows.
- [ ] 6.5 Run the Python gate: `uv run ruff check . && uv run ruff format --check . && uv run
      pyright app tests && uv run pytest`.
- [ ] 6.6 Run the frontend gate if the settings section changed: `cd frontend && npm run check`.
