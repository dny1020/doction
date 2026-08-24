## 1. Make the shipped code path measurable

- [x] 1.1 Extract the hybrid merge from the `/api/search` handler (`app/main.py:576-602`) into
      a function next to `semantic_search`, and verify `uv run pytest tests/test_semantic.py
      tests/test_spa_api.py` passes unchanged — the endpoint's responses must be identical.
- [x] 1.2 Add `evals/` with a corpus loader that reads a markdown dump from `EVAL_CORPUS`
      (the layout of `{DATA}/pages/`) into a throwaway Postgres via `db.init_db()` and
      `db.create_page`, and verify it reports the expected page count against a local dump.
- [x] 1.3 Wire the real encoder into the harness (`MODEL_DIR` set, `EMBED_STUB` unset) and
      drive indexing with `embeddings.drain_pending()`; verify every loaded page has chunks
      and that a known English query returns its page at rank 1.

## 2. Query set

- [x] 2.1 Write `evals/queries.json`: ~25 entries, each with the query, its failure class
      (A unaccented-Spanish, B Spanish-paraphrase, C cross-lingual, D English-control,
      E conceptual) and the slug(s) that count as correct. Verify every referenced slug
      exists in the corpus — a typo in a label silently becomes a permanent miss.
- [x] 2.2 Include the reproduction from `proposal.md` as an explicit class-A row
      (`renovacion` → `rpi-operaciones-renovacion-tls-con-certbot`) and confirm it fails
      against today's configuration, so the harness is known to detect the defect it exists
      to measure.

## 3. Harness

- [x] 3.1 Implement the six configurations — `fts-english`, `fts-spanish`, `fts-unaccent`,
      `semantic`, `hybrid`, `hybrid+rerank` — with the FTS counterfactuals computed inline in
      the harness's own SQL. Verify `SCHEMA_STATEMENTS` is untouched by a run (diff the
      generated column definition before and after).
- [x] 3.2 Implement recall@1, MRR, zero-result rate and p50/p95 latency, and verify the
      metrics on a hand-checkable subset of three queries whose correct ranks you computed by
      hand.
- [x] 3.3 Print the comparison table to stdout and write the same numbers to
      `evals/results/<date>.json`; verify a second run on the same corpus reproduces the
      table (the encoder is deterministic, so it must).
- [x] 3.4 Run the harness against the real corpus and commit the results file. This is the
      artifact the remaining decisions cite.

## 4. Text-search configuration

- [x] 4.1 Add `CREATE EXTENSION IF NOT EXISTS unaccent` and an idempotent `doction` text
      search configuration chaining `unaccent` before the stemmer, with the stemmer chosen by
      the §3.4 results. Verify it is safe to run twice against the same database.
- [x] 4.2 Handle the extension being refused for the application role: log and fall back to a
      stemmer-only configuration rather than failing startup, and verify by running
      `init_db()` as a role without create-extension rights.
- [x] 4.3 Point both `search_vector` generated columns (`app/db.py:226-229`, `:342-344`) at
      the `doction` configuration, and name it explicitly in `to_tsquery`, `ts_rank` and
      `ts_headline` in `search_pages()` — verify the index and the query use the same
      configuration by searching an accented term and its unaccented spelling.

## 5. Convergent schema upgrade

- [x] 5.1 Add a startup step to `init_db()` that compares each `search_vector` column's stored
      generation expression against the one the code declares, and rebuilds the column and its
      GIN index only when they differ. Verify with a test that starts against a database built
      from the old definition and asserts the column is rebuilt and every page survives.
- [x] 5.2 Verify idempotence and rollback: starting twice performs one rebuild, and starting
      the previous definition against an upgraded database converges it back with no manual
      SQL.

## 6. Encoder-model safety

- [x] 6.1 Filter `workspace_chunk_vectors()` to the current encoder's name so a partially
      reindexed workspace cannot blend two embedding spaces; verify with a test that inserts
      chunks under two model names and asserts only the current model's chunks are scored.
- [x] 6.2 Derive the current model name without constructing the ONNX session (both encoders
      expose `name` as a class attribute) and verify no model file is opened when
      `SEMANTIC_SEARCH` is off.
- [x] 6.3 Have the enrichment worker mark pages dirty on its first pass when their stored
      chunks carry a different model name; verify a test where the model name changes and the
      pages are re-embedded without an operator step.

## 7. Settle the constants

- [x] 7.1 For each of `SEARCH_MIN_SCORE`, `KEYWORD_BOOST` and `RERANK_CANDIDATES`, either
      change the value or keep it — and in both cases replace the comment with the measured
      figures from §3.4. Verify no constant in `app/embeddings.py` is still justified by a
      hand-waved comment.
- [x] 7.2 Decide `RERANK` on the measured MRR and latency delta. If it does not earn its
      ~23 MB of image and ~80-100 MB of RAM, record that in `CLAUDE.md` next to the flag so
      the finding is not rediscovered later.

## 8. Conditional: multilingual encoder — measured and rejected

Class C recovered on its own once the keyword path was fixed (0.40 → 0.67 MRR), so the
stated condition did not fire. Class B stayed weak (0.44), so the encoder was measured
anyway rather than assumed either way. It made things **worse**; the English model stays.

- [x] 8.1 Downloaded `Xenova/paraphrase-multilingual-MiniLM-L12-v2` (rev
      `2c4055b12046f11709e9df2c122e59ffbdc2f900`, 118 MB model + 17 MB tokenizer) and ran the
      harness against it. **Not** pinned into the Dockerfile — see 8.2.
- [x] 8.2 Re-ran the harness (`evals/results/2026-08-24-minilm-multilingual.json`). Class B
      *fell* 0.44 → 0.30 and class E collapsed 0.57 → 0.15; class C gained +0.03, inside the
      noise. Overall hybrid MRR 0.72 → 0.63, recall@1 0.61 → 0.50. Decision: keep
      `all-MiniLM-L6-v2`. The only gain was zero-result rate (0.04 → 0.00) — it retrieves
      something more often but ranks it worse.
- [x] 8.3 Not applicable: the encoder was not adopted and `RERANK` stays off, so the 768 MB
      budget is unchanged from today's measured-good configuration.

## 9. Verification and documentation

- [x] 9.1 Reproduce the original defect end to end: `renovacion` returns
      `RPI-Operaciones / Renovación TLS con Certbot` at rank 1 in both keyword and hybrid
      search, and the sidebar renders a non-empty list.
- [x] 9.2 Add regression tests for the spec's scenarios — diacritic folding both directions,
      English control queries, partial-reindex behaviour — using the stub encoder so they run
      in CI.
- [x] 9.3 Run the full gate: `uv run ruff check . && uv run ruff format --check . && uv run
      pyright app tests && uv run pytest`.
- [x] 9.4 Update `CLAUDE.md`: the text-search configuration, the convergent-schema step (it
      qualifies the documented "no migration ladder" property), and the `evals/` harness with
      how to run it.
