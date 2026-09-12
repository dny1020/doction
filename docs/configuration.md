# Configuration

Everything is an environment variable. There is no config file and no settings UI, so a
running instance is fully described by its environment plus its two volumes.

## Required in production

Both have defaults that let the server boot, which is convenient in development and wrong
everywhere else.

| Variable | What it does |
| --- | --- |
| `SECRET_KEY` | Signs session cookies and JWTs. Anyone who knows the key can mint a valid session for any user. Generate with `openssl rand -hex 32`. |
| `DATABASE_URL` | Postgres connection string. Defaults to `postgresql://doction:doction@postgres:5432/doction`, which is the Compose service name — outside Compose it will not resolve. |

The two interact, and the interaction is deliberate. With `SECURE_COOKIES` off, an unset
or placeholder `SECRET_KEY` falls back to a development key and logs a warning, so a local
checkout just runs. With `SECURE_COOKIES=1` — the signal that you are behind TLS, in
production — the server **refuses to start** on an unset key. The placeholders shipped in
`.env.example` (`change-me`, `changeme`, `dev-secret-key`) count as unset, so copying the
example file and forgetting to edit it fails loudly instead of signing tokens with a key
that is public on GitHub.

## Strongly recommended

| Variable | Default | What it does |
| --- | --- | --- |
| `SECURE_COOKIES` | off | Set to `1` when a TLS-terminating proxy is in front. Marks the session cookie `Secure`, so it is never sent over plain HTTP. Leaving it off on a public instance means the session cookie travels in the clear on any accidental HTTP request. |
| `DISABLE_REGISTRATION` | off | Set to `1` to close public sign-up. **Registration is open by default**: on a reachable instance, anyone who finds the URL can create an account. With the flag set, the first user can still register — so a fresh instance is never locked out — and everyone after that has to be added as a workspace member by an owner. |

## Licence compliance

| Variable | Default | What it does |
| --- | --- | --- |
| `SOURCE_URL` | this project's repository | Where this instance's source lives. Reported by `GET /api/system` and shown to signed-in users in Settings. |

doction is AGPL-3.0-only, and that licence attaches its obligation to *network use* rather
than to handing out copies. An operator who modified doction and lets other people use it
owes those users the modified source. The software surfaces the offer so it does not depend
on the operator remembering.

Three cases, which is the whole of it:

| What you are doing | What you set |
| --- | --- |
| Running a published release, unmodified | Nothing. The default points at upstream, which is the source you are running. |
| Modified, instance private to you or your team | Nothing. No obligation is triggered. |
| Modified, other people use it over a network | `SOURCE_URL` must point at *your* source. |

Leaving the default on a modified instance is worse than leaving it empty: the instance
then makes a confident claim that the code it is running is at a URL where it is not. The
software cannot verify that a URL serves the corresponding source, so that part stays the
operator's responsibility.

## Storage

| Variable | Default | What it does |
| --- | --- | --- |
| `DATA_DIR` | `/data` | The git repo of markdown pages (`{DATA_DIR}/pages/`) and uploaded files. This is half your backup; the database is the other half. Unrelated to `DATABASE_URL`. |
| `LOG_DIR` | `/logs` | Directory for the rotated log file. Logs also go to stdout. Diagnostic only — not part of a backup. |
| `MODEL_DIR` | the models baked into the image | Where the ONNX embedding and reranker models live. Override only if you are mounting your own. |

Mount `DATA_DIR` and `LOG_DIR` as separate volumes. Sharing one means log rotation and
page history compete for the same space, and a full disk then loses writes to pages.

## Logging

| Variable | Default | What it does |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | Root logger level: `DEBUG`, `INFO`, `WARNING`, `ERROR`. `DEBUG` is the right setting when reporting a bug. |

The root logger is configured at import time, before any logger exists, because uvicorn
only configures its own `uvicorn.*` loggers. Without that, every `app.*` line would be
dropped — which is why `LOG_LEVEL` reaches application logs and not just access logs.

## Search

doction always has full-text search: a generated `tsvector` column with a GIN index,
maintained by Postgres itself. Semantic search is layered on top and opt-in.

| Variable | Default | What it does |
| --- | --- | --- |
| `SEMANTIC_SEARCH` | off | `1` enables local embeddings: the `sgrep` and `rag` MCP tools, and `mode=semantic` / `mode=hybrid` on `/api/search`. A MiniLM int8 ONNX model (~23 MB) ships in the image and loads lazily. A background worker embeds pages without blocking requests. With the flag off, semantic modes degrade to full-text search rather than erroring. |
| `RERANK` | off | `1` re-scores the top 20 semantic hits with a local cross-encoder. Requires `SEMANTIC_SEARCH=1`. **Leave it off.** |

### Why the reranker ships off

Measured against a real wiki, not guessed. The numbers live in `evals/results/`.

| Metric | Semantic | With reranker |
| --- | --- | --- |
| MRR | 0.72 | 0.73 |
| recall@1 | 0.61 | 0.57 |
| median latency | 12 ms | 350 ms |

It buys 0.01 MRR, *loses* recall@1, and costs 29× the latency. Budget 80–100 MB of extra
RAM if you enable it anyway.

### Why the stemmer is English

Search runs on a Postgres text-search configuration named `doction`: `unaccent` chained
ahead of `english_stem`. Accent folding is the point — `to_tsvector('english',
'Renovación')` indexes the accented token, so a search for `renovacion` used to miss the
page entirely.

The English stemmer is a measurement, not an assumption: `spanish_stem` scored 0.00 MRR
on English queries against Spanish pages. A multilingual encoder was measured too and
rejected — six times the size, and *worse* on Spanish paraphrase (0.30 vs 0.44) and on
conceptual queries (0.15 vs 0.57).

If the database role lacks permission to `CREATE EXTENSION unaccent`, the server logs it
and falls back to the stemmer alone rather than refusing to boot. You lose accent folding
and nothing else.

## OCR of uploads

| Variable | Default | What it does |
| --- | --- | --- |
| `OCR_UPLOADS` | off | `1` runs the `tesseract` binary over uploaded images and indexes the extracted text, so a pasted screenshot becomes searchable. Runs as a background task; a failure never breaks the upload. |
| `OCR_LANGS` | `eng+spa` | tesseract language packs. Only packs present in the image work. |

## Rarely needed

| Variable | Default | What it does |
| --- | --- | --- |
| `DOCTION_APP_PATH` | `/app` | Base path where the single-page app is served. Changing it also changes the router basename the bundle was built with, so it only works if you rebuild the frontend to match. |
| `TEST_DATABASE_URL` | unset | Test-suite only. Unset, `tests/conftest.py` starts a throwaway Postgres container with its datadir in tmpfs. CI sets it instead. Never set this in production. |

## A worked example

Minimum viable production environment, for a single-user instance behind nginx:

```bash
SECRET_KEY=$(openssl rand -hex 32)
DATABASE_URL=postgresql://doction:<generated>@postgres:5432/doction
SECURE_COOKIES=1
DISABLE_REGISTRATION=1
SEMANTIC_SEARCH=1
LOG_LEVEL=INFO
```

`.env.example` in the repo root is the annotated starting point.

## Verifying what is actually live

The environment you *set* and the configuration the process *has* are different things.
Ask the process:

```bash
curl -s $DOCTION/health | jq
# {"status":"ok","db":"ok","version":"0.31.3"}
```

`GET /api/system` (authenticated) reports which optional features resolved as enabled,
which is the honest answer to "did `SEMANTIC_SEARCH=1` actually take effect".
