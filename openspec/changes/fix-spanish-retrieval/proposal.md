## Why

doction's retrieval stack is configured for English end to end, and the wiki it serves is
written mostly in Spanish. Both `pages.search_vector` and `upload_texts.search_vector` are
built with `to_tsvector('english', …)`, and the semantic encoder is `all-MiniLM-L6-v2`, an
English-only model. The only component in the system that acknowledges Spanish is the OCR
language pack (`eng+spa`).

The result is reproducible on the live wiki today. Searching `renovación` finds
`RPI-Operaciones / Renovación TLS con Certbot` at rank 1. Searching `renovacion` — the same
word typed the way people actually type Spanish, and the way that page's own slug spells it —
does not find it at all:

- **FTS** returns `rpi-operaciones` instead, and only because that page happens to contain
  the literal string `[[rpi-operaciones-renovacion-tls-con-certbot]]` inside a wikilink. The
  correct page is invisible to the query, because `to_tsvector('english', 'Renovación')`
  indexes the accented token and the English stemmer has no reason to fold it.
- **sgrep** scores the whole workspace flat — 0.2846 / 0.2744 / 0.2700, correct page absent
  from the top 3 — because the English WordPiece vocabulary shreds `renovacion` into subword
  debris and the resulting vector carries no signal. Every hit sits below
  `SEARCH_MIN_SCORE = 0.35`, so the sidebar renders nothing.

Hybrid search exists on the premise that keyword and semantic retrieval cover each other's
gaps. On unaccented Spanish both halves fail simultaneously, for two unrelated reasons, and
the user gets an empty result list. The same query in English (`how do I renew the TLS
certificate`) scores 0.5369 at rank 1 with a clean gap to second place — the encoder is not
weak, it is being addressed in a language it does not know.

Every ranking constant in the stack (`SEARCH_MIN_SCORE`, `KEYWORD_BOOST`, `LINK_THRESHOLD`,
`DUP_THRESHOLD`, `RERANK_CANDIDATES`) is hand-tuned with no measurement behind it, and the
`RERANK=1` cross-encoder costs ~23 MB of image and ~80-100 MB of RAM inside a 768 MB
container with no evidence that it improves anything. There is no way to settle either
question — or to verify this fix — without a way to measure retrieval quality.

## What Changes

- **Accent-insensitive keyword search.** The `search_vector` generated columns stop being
  built with a hardcoded English configuration. Whether the fix is `unaccent`, the `spanish`
  text-search configuration, or both is decided by measurement, not assumption — the
  committed requirement is the behaviour, not the mechanism.
- **A one-off retrieval evaluation harness** under `evals/`, outside `pytest`. It loads a
  local corpus dump into a throwaway Postgres, indexes it with the real ONNX encoder, and
  prints one table comparing `fts-english` (today's baseline), `fts-spanish`,
  `fts+unaccent`, `semantic`, `hybrid` and `hybrid+rerank` on recall@1, MRR, zero-result
  rate and p50/p95 latency. Its purpose is to settle the configuration once; it is not
  infrastructure and does not gate CI.
- **A schema-change path that survives the no-migration design.** `init_db()` is
  `CREATE TABLE IF NOT EXISTS` by design, so a changed generated-column definition would
  never reach the existing database on the Pi. This change adds a guarded, idempotent
  upgrade for the `search_vector` columns.
- **Encoder-change invalidation.** `page_chunks.model` is written on every insert and read
  nowhere. Reindexing on a model change is added so that swapping encoders cannot silently
  mix vectors from two different embedding spaces in one cosine comparison.
- **Conditional: a multilingual encoder.** If the harness shows the fixed keyword path does
  not close the gap on Spanish paraphrase and cross-lingual queries,
  `paraphrase-multilingual-MiniLM-L12-v2` replaces the English model. This is deliberately
  gated on evidence: it costs ~120-135 MB instead of 23 MB and roughly 2× inference, inside
  a 768 MB limit that may also be hosting the reranker.
- **The measured constants are either kept with a recorded justification or changed.** No
  constant survives this change still labelled as a guess.

Not in scope: the frontend (no UI change), the suggestion/insights layer
(`LINK_THRESHOLD`, `DUP_THRESHOLD` are link- and duplicate-task knobs measured by a
different eval), and search performance — at 43 pages the full-corpus scan moves ~250 KB
per query and is not a problem worth solving.

## Capabilities

### New Capabilities

- `search`: language-correct retrieval behaviour — which queries must find which pages,
  independent of accents and of the language the page is written in. Covers the keyword
  (FTS), semantic and hybrid modes exposed by `GET /api/search` and MCP `sgrep`.

### Modified Capabilities

None. `app-shell` is unaffected; this change adds no UI.

## Impact

- **Schema**: `pages.search_vector` and `upload_texts.search_vector` definitions in
  `SCHEMA_STATEMENTS` (`app/db.py:226-229`, `app/db.py:342-344`); a new idempotent upgrade
  step in `init_db()`. Possibly `CREATE EXTENSION unaccent` (contrib ships in
  `postgres:16-alpine`).
- **Code**: `app/db.py` (schema, upgrade, `store_page_chunks`/reindex-on-model-change),
  `app/embeddings.py` (constants, and the model path if the encoder is replaced).
- **New**: `evals/` — harness plus a JSON query set. Queries and results are committed;
  the corpus is not (the wiki is private, the repo is public) and is read from a path given
  by an environment variable.
- **Dependencies**: none added. The harness uses `numpy` and the stdlib `json` module —
  notably not PyYAML, which is not a dependency of this project and must not become one.
- **Deployment**: existing databases need the guarded upgrade to run, and any encoder change
  forces a full reindex of `page_chunks`. Both must be safe on the Pi, where deploys are
  manual and there is no rollback.
- **Image size**: unchanged unless the multilingual encoder is adopted, in which case the
  image grows by ~100 MB and the runtime memory budget inside `mem_limit: 768m` must be
  re-checked against `RERANK=1`.
