## Context

See `proposal.md` — Why. Three properties of the current system shape everything below.

**The search index is a generated column.** `pages.search_vector` and
`upload_texts.search_vector` are `GENERATED ALWAYS AS (…) STORED`, with the text-search
configuration hardcoded as `'english'`. Postgres maintains them without triggers, which is
why the project has no trigger machinery — a property worth keeping.

**There is no migration ladder, by design.** `init_db()` is a list of
`CREATE TABLE IF NOT EXISTS` statements (`CLAUDE.md` states this explicitly). It is
idempotent, and it silently ignores tables that already exist — so a changed column
definition never reaches an existing database.

**The query side inherits its configuration implicitly.** The index is built with an
explicit `to_tsvector('english', …)`, but `search_pages()` calls `to_tsquery(%s)` with no
configuration, falling back to `default_text_search_config`. They agree today only because
`postgres:16-alpine` defaults to `pg_catalog.english`. That is a coincidence, not a
contract.

## Goals / Non-Goals

**Goals:**

- One named text-search configuration, defined in one place, that both the index and the
  query use explicitly — so the two can never drift again.
- A schema that *converges* to the desired shape on startup, keeping the no-ladder property
  rather than breaking it.
- A measurement that is auditable after the fact: the numbers that justified each constant
  are committed next to the constants.
- Semantic search that cannot silently compare vectors from two different models.

**Non-Goals:**

- A permanent evaluation suite or a CI quality gate. This harness runs when someone touches
  a retrieval knob and is otherwise dormant.
- Retrieval performance. At 43 pages the full-corpus scan moves ~250 KB per query.
- The suggestion layer's thresholds (`LINK_THRESHOLD`, `DUP_THRESHOLD`) — different tasks,
  different ground truth, measured separately if ever.
- Language detection per page. The corpus is bilingual within single documents (Spanish prose
  around English technical nouns); routing a page to one stemmer or the other would be a
  worse model of the data than picking one configuration for everything.

## Decisions

### Use a custom text-search configuration, not `unaccent()` inline

The obvious fix — `to_tsvector('english', unaccent(title))` — **does not work in a generated
column.** `unaccent(text)` is declared `STABLE`, not `IMMUTABLE`, because its behaviour
depends on a dictionary that can be redefined. Postgres rejects non-immutable expressions in
generated columns and in index definitions. The two common workarounds are an `IMMUTABLE`
wrapper function around `unaccent` (which lies to the planner) or a custom configuration.

We take the configuration. `CREATE EXTENSION unaccent`, then a configuration — call it
`doction` — whose word mappings chain `unaccent` ahead of the stemmer. `to_tsvector(regconfig,
text)` with an explicit configuration *is* `IMMUTABLE`, so the generated column stays valid
and the GIN index stays usable.

This also gives us one lever: the stemmer inside `doction` is a single line, so switching
between `english_stem` and `spanish_stem` after measurement changes one definition rather
than four call sites.

Alternative rejected: `to_tsvector('spanish', …)` alone. Spanish snowball folds accents as a
side effect of stemming, so it would fix the reported defect — but it silently applies
Spanish stemming rules to the English technical vocabulary that actually discriminates
between these pages, and drops Spanish stopwords while keeping English ones. Whether that is
a net win is exactly what the harness measures; it should be a measured choice of stemmer
inside one configuration, not a different mechanism.

### Name the configuration on the query side too

`search_pages()` moves from `to_tsquery(%s)` to `to_tsquery('doction', %s)`, and `ts_rank`
and `ts_headline` take the same configuration. This closes the implicit dependency on
`default_text_search_config` described in Context. Without it, an index built with `doction`
and a query parsed with `english` would fold accents on one side only — a worse failure than
today's, because it would look like it works.

### Converge the schema on startup instead of adding migrations

`init_db()` gains one step that reads the current generation expression of each
`search_vector` column from the catalog, compares it to the expression the code wants, and
rebuilds the column only when they differ:

```
  read pg_attrdef / pg_get_expr for pages.search_vector
      ├─ matches desired expression → do nothing
      └─ differs or column absent   → ALTER TABLE DROP COLUMN search_vector,
                                      ADD COLUMN … GENERATED ALWAYS AS (…) STORED,
                                      recreate the GIN index
```

This keeps the project's actual invariant — *the schema converges to what the code declares,
from any prior state* — rather than the weaker one it currently relies on, which is *nothing
ever changes*. It is idempotent, it needs no version table, and it makes rollback safe in
both directions: an older image started against an upgraded database converges the column
back on its own.

Alternative rejected: a migration tool (Alembic or hand-rolled). It would buy ordered,
irreversible history that this schema does not need, and it would contradict a documented
design property for a single column definition.

Alternative rejected: a documented manual `ALTER` on the Pi. Deploys there are already manual
with no rollback; adding a hand-run SQL step to that procedure is how a database drifts from
its code.

Dropping a generated column drops its index, so the GIN index must be recreated in the same
step. At 43 pages this is instantaneous; on a large table it is a rewrite, which is worth
knowing but is not this deployment's problem.

### Filter chunks by model, and reindex when the model changes

`page_chunks.model` is already written on every insert (`store_page_chunks`) and read
nowhere. Two changes make it load-bearing:

1. `workspace_chunk_vectors()` filters to the current encoder's name, so a half-reindexed
   workspace never blends two embedding spaces in one cosine comparison.
2. The enrichment worker marks pages dirty on its first pass when their stored chunks carry a
   different model name, so an encoder swap self-heals without an operator step.

Reading the expected model name must not load the ONNX session — `name` is a class attribute
on both encoders, so the current name is derivable from the environment flags alone.

This is required whether or not the multilingual encoder is adopted: without it, adopting it
later is a silent-corruption change rather than a configuration change.

### Extract the hybrid merge out of the route

The hybrid mode's merge logic sits inline in the `/api/search` handler
(`app/main.py:576-602`). The harness needs to evaluate exactly what users get, and the
alternatives are reimplementing the merge (which would then be the thing under test rather
than the real code) or driving a `TestClient` per query (which measures HTTP overhead
alongside retrieval).

Moving those lines into a function alongside `semantic_search` is a small refactor that the
project's own guidance already asks for — *API should not contain business rules* — and it
makes the eval measure the shipped code path.

### The harness is a script, not a test

`evals/` at the repo root, run on demand, printing a table to stdout:

```
  config           recall@1   MRR    zero-results   p50     p95
  ────────────────────────────────────────────────────────────────
  fts-english          …       …          …          …       …
  fts-spanish          …       …          …          …       …
  fts-unaccent         …       …          …          …       …
  semantic             …       …          …          …       …
  hybrid               …       …          …          …       …
  hybrid+rerank        …       …          …          …       …
```

- **Corpus**: a local dump of `{DATA}/pages/`, which is already plain markdown in a git repo,
  read from a path in `EVAL_CORPUS`. Not committed — the wiki is private and the repository
  is public. The consequence, accepted: the run is reproducible for its owner and not for a
  stranger. Acceptable for a one-off; it would not be for a CI gate.
- **Queries and results**: committed as JSON. Not YAML — PyYAML is not a dependency of this
  project and a one-off harness is not a reason to make it one.
- **Model**: the real ONNX encoder from `models/` via `MODEL_DIR`, with `EMBED_STUB` unset.
  The existing `test_real_onnx_embedder_similarity` already establishes this env-gated
  escape hatch from the stub; this is the same idea at corpus scale.
- **Counterfactual configurations** are evaluated by computing the alternative `tsvector`
  inline in the harness's own SQL. The experiment never modifies `SCHEMA_STATEMENTS`, so a
  failed run cannot leave the schema in an experimental state.
- **Reuse**: `embeddings.drain_pending()` (documented as "útil en tests/CLI"),
  `semantic_search(min_score=, keyword_boost=)` whose knobs are already parameters, and the
  ephemeral-Postgres approach from `tests/conftest.py`.

### Metrics: recall@1, MRR, zero-result rate

Not recall@5. On a 43-page corpus the top 5 is 12% of everything, so recall@5 saturates and
cannot discriminate between configurations. Zero-result rate is included because an empty
sidebar is the failure the user actually reported. Latency is included because on a Pi a
small quality gain bought with doubled latency is a loss.

The query set is stratified by failure hypothesis rather than sampled for realism: unaccented
Spanish, Spanish paraphrase, cross-lingual, English control, and conceptual queries with no
lexical overlap. With ~25 queries only large differences are meaningful — see Risks.

## Risks / Trade-offs

- **`CREATE EXTENSION unaccent` may be refused for the application's database role** →
  `unaccent` is a trusted extension from PostgreSQL 13 onward, so a database owner can create
  it without superuser. If it still fails, the startup step logs and falls back to a
  configuration built on `spanish_stem` alone, which folds accents through the stemmer. Search
  degrades to today's behaviour rather than the server failing to boot.
- **Rebuilding a generated column rewrites the table** → instantaneous at this scale; the
  convergence check ensures it happens once per definition change, not on every startup.
- **A Spanish stemmer would apply to English content, and vice versa** → this is precisely
  what the English control class in the query set measures. Whichever stemmer wins, the
  control class must not regress; if both regress something, the configuration keeps
  `english_stem` and takes only the accent folding.
- **~25 queries is low statistical power** → roughly ±9pp on a proportion. The harness settles
  "does this fail" and "is the reranker worth 100 MB", not "is this 3% better". Act only on
  large deltas and record the numbers rather than the conclusions.
- **The multilingual encoder costs ~120-135 MB and ~2× inference inside `mem_limit: 768m`** →
  gated on evidence, and if adopted must be measured with `RERANK=1` also enabled, since that
  is the configuration most likely to hit the limit.
- **The eval corpus is private, so the numbers cannot be independently reproduced** →
  accepted for a one-off tuning exercise; the committed results and query set at least make
  the reasoning auditable.
- **Fixing keyword search may make the semantic half look unnecessary** → that is a legitimate
  outcome, not a failure. If `fts+unaccent` closes the gap on its own, the honest conclusion
  is recorded and `SEMANTIC_SEARCH` stops being the answer to a problem configuration created.

## Migration Plan

1. Deploy the image. On startup `init_db()` creates the extension and configuration if
   absent, then converges both `search_vector` columns and their GIN indexes.
2. If the encoder is unchanged, no reindex occurs and stored vectors remain valid.
3. If the encoder is replaced, the worker marks every page dirty on its first pass and
   re-embeds in the background. Keyword search covers the gap while that runs, and
   model-filtered chunk reads keep partial state from producing blended results.
4. **Rollback**: revert to the previous image. The convergence check rebuilds the columns back
   to the earlier definition on startup — no manual SQL, and nothing to undo by hand. This is
   the practical benefit of converging over laddering, and it matters here because the Pi's
   deploy is manual and has no rollback procedure today.
5. Verification is the reproduction from `proposal.md`: `renovacion` must return
   `RPI-Operaciones / Renovación TLS con Certbot` at rank 1 in both keyword and hybrid search.

## Open Questions

Both were answered by the harness during implementation; recorded here so the reasoning
survives the change.

- **Which stemmer goes inside the `doction` configuration?** → `english_stem`. Accent
  folding was the whole defect; the stemmer was not. `spanish_stem` scores **0.00 MRR** on
  class C (English queries against Spanish pages) because it mangles English words, in
  exchange for +0.09 on the English control class. `unaccent + english_stem` took class A
  from 0.14 to 0.76 MRR while leaving C and D intact.
- **Is `paraphrase-multilingual-MiniLM-L12-v2` adopted?** → No, and the measurement is the
  reason rather than the cost. It is *worse* on the class it was meant to fix: Spanish
  paraphrase fell 0.44 → 0.30 and conceptual queries collapsed 0.57 → 0.15, for +0.03 on
  cross-lingual (noise). Overall hybrid MRR 0.72 → 0.63, recall@1 0.61 → 0.50. It does
  reduce the zero-result rate to 0.00 — it finds something more often, but ranks it worse.
  135 MB instead of 23 MB for a net loss.
