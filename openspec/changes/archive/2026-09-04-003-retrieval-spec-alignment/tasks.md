## 1. Assembled context: deduplicate and bound

- [x] 1.1 Add a size budget to `rag_context()` in characters, replacing the fixed `k=6`. Verify a
      long workspace returns fewer, whole fragments rather than six of arbitrary length.
- [x] 1.2 Leave a fragment out entirely when it does not fit, never truncated, and say in the
      response that the context was cut. Verify no returned fragment is a prefix of a stored one.
- [x] 1.3 Deduplicate fragments that repeat a passage: same section, or bodies overlapping past a
      threshold. Verify two near-identical fragments from one page collapse to one.
- [x] 1.4 Verify two *distinct* sections of the same page both survive — they answer different
      parts of the question, and collapsing them would be the opposite bug.
- [x] 1.5 Verify every fragment still carries its page, its heading path and its score, and that
      each appears verbatim in a stored page.

## 2. Keyword fallback returns page text

- [x] 2.1 Make `rag_context()`'s fallback return section text from the page body instead of
      `ts_headline` output. Verify on a deployment with semantic search off that a fragment is a
      whole section, not twelve words.
- [x] 2.2 Leave search results alone: `/api/search` and `search_knowledge` keep their highlighted
      extracts, which is what the sidebar renders in `<mark>`. Verify the highlight still works.
- [x] 2.3 Verify the fallback honours the same budget and deduplication as the vector path — one
      contract, two sources.

### Notes on sections 1 and 2

- **The budget is 6000 characters**, about 1500 tokens, which leaves room for a question and an
  answer and lands close to the six fragments it replaces — so the default behaviour resembles the
  old one without being a count. `limit` still works for a caller that wants fewer.
- **A fragment that does not fit is skipped, not stopped at.** Stopping would leave the budget
  unused because one large fragment happened to sit second; truncating would return text the page
  does not contain. Skipping is the only option that does neither.
- **Deduplication recognises three shapes**: two chunks of one section (pieces of a block the
  ceiling split), literal containment, and 80% shared words. The threshold is high and only applies
  above twenty words, because two short sentences on one topic share almost everything and the
  expensive mistake is dropping a section that answered.
- **The lexical fallback chunks the page on the fly**, since no worker runs and no chunks are stored
  when semantic search is off. It picks the section with the most query terms, so the fragment is
  the one the vector channel would have returned. It costs one page fetch per hit, on the degraded
  path only.
- **Tokenising caught a real bug.** Folding case and accents was not enough: `` `certbot `` with its
  backtick attached did not match `certbot`, so the section that answered lost to the page's
  opening paragraph. The picker now tokenises the way `db._fts_query` does.
- **Search results were left alone.** The sidebar still renders `ts_headline` extracts with their
  highlight; only assembled context changed. A test pins that.

## 3. Ranking parameters in the system report

- [x] 3.1 Add the fusion constant, the vector weight and the score floor to `GET /api/system`,
      read-only, beside the retrieval flags.
- [x] 3.2 Verify a request cannot override them, and that the reported values are the ones the
      running process uses rather than defaults read from source.
- [x] 3.3 Show them in the settings System section, as informational rows like the rest.

## 4. Chunk frontmatter

- [x] 4.1 Carry a page's frontmatter `type` and tags with each of its chunks, without embedding the
      raw frontmatter block as prose. Verify the embedded text is unchanged by this.
- [x] 4.2 Store them beside the chunk's path and return them with a retrieved fragment, so an agent
      can tell a runbook from a meeting note without a second call.
- [x] 4.3 ~~Bump the chunker identity~~ **Not needed, and not done.** The type and tags are read
      from `page_meta` and `page_tags` with a JOIN instead of copied onto `page_chunks`. Those
      tables are already kept current by `_index_page_meta` on every write, so there is nothing to
      re-index: the embedded text is unchanged, so a bump would re-embed every page to produce
      identical vectors. The JOIN is also the only version that stays correct — copied tags would
      go stale the moment someone retagged a page and would not recover until its next edit.

## 5. Evaluation coverage

- [x] 5.1 Let a query in `queries.json` name an expected section as well as an expected page, and
      keep page-only expectations working unchanged.
- [x] 5.2 Teach the harness to score a section-level expectation: whether the retrieved fragment
      came from the expected section, reported separately from page-level recall so the two are not
      conflated.
- [x] 5.3 Add queries whose answer lives in one section of a long page, with the expected section
      named. These measure the heading context that 002's chunker exists to preserve and that has
      never been scored.
- [x] 5.4 Add tag-filtered cases that exercise `search_knowledge`'s filter, including one where the
      filter must lift a page that would otherwise rank below the cut.
- [x] 5.5 Verify the harness still runs, and the existing 28 queries still score, with the new
      fields absent.

### Notes on sections 3, 4 and 5

- **The ranking parameters are reported unconditionally**, unlike the index counts, which are
  omitted when semantic search is off. They are configuration of the running process, not a
  measurement of an index that may not exist.
- **Section 4 was implemented as a JOIN, not a copy.** See 4.3 — no duplication, no staleness, no
  re-index.
- **Search results now carry their heading path too.** `retrieval-ranking` requires a result to say
  where in the page it came from, and hybrid hits did not. Fixing it was needed to score section
  recall at all, and it closes a fifth spec gap this change did not set out to.
- **The corpus has no usable tags**, so the loader writes one per page naming the dump it came
  from. It writes straight to `page_tags` rather than into the markdown: touching the body would
  change the embedded text and every previous run would stop being comparable over a tag. The
  provenance is a real fact about each page; only where it is stored is synthetic.
- **Filter cases live in their own file and their own row**, for the same reason: adding them to
  the main 28 would move the headline metrics and break comparability with all four earlier runs.

**Finding, recorded and not acted on:** section recall is **0.38** over the eight queries that
declare an expected heading — the right page is retrieved but the wrong section of it in five cases
out of eight. This is the first time the number has existed, and 6.2 forbids tuning against a
metric this change introduced. It belongs to its own change, with its own before-and-after.

## 6. Verification

- [x] 6.1 Run the harness against `2026-09-04-baseline-002-final.json`: recall@1 and MRR at or
      above it, zero-result rate no worse, latency reported. Commit the result.
- [x] 6.2 Do not re-tune `RRF_K`, `RRF_VECTOR_WEIGHT` or `SEARCH_MIN_SCORE` in this change. If the
      new section-level cases say a constant is wrong, record it as a finding for its own change —
      tuning against a metric this change invented would make the benchmark meaningless.
- [x] 6.3 Confirm the four live specs this change exists to satisfy now hold: `retrieval-ranking`
      on deduplication, budget, fallback text and configuration visibility; `chunking` on
      frontmatter; `retrieval-evaluation` on query coverage.
- [x] 6.4 Confirm nothing in the MCP tool surface or the frontend changed except the two new
      informational rows.
- [x] 6.5 Run the Python gate: `uv run ruff check . && uv run ruff format --check . && uv run
      pyright app tests && uv run pytest`.
- [x] 6.6 Run the frontend gate if the settings section changed: `cd frontend && npm run check`.
