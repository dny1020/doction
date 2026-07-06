# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
simple incremental versioning (`pyproject.toml` ⇆ `SERVER_INFO` in `app/mcp.py`).

## [Unreleased]

### Added
- **Local ML round, no LLM and zero new Python dependencies** (`app/suggest.py`,
  `app/graph.py`, numpy over the existing embeddings/link graph):
  - Wikilink suggestions: `GET /api/pages/{slug}/suggest-links` + MCP `suggest_links`
    (cosine similarity between page vectors; literal title-mention fallback when
    semantic search is off).
  - Tag suggestions: `GET /api/pages/{slug}/suggest-tags` + MCP `suggest_tags`
    (TF-IDF vs the workspace corpus, boosting terms already used as tags).
  - Extractive summaries: `GET /api/pages/{slug}/summary` + MCP `summarize_page`
    (TextRank over sentence embeddings; leading-sentences fallback).
  - Workspace insights: `GET /api/insights` + MCP `workspace_insights` — PageRank
    central pages, orphans, hubs/authorities, broken wikilinks, near-duplicate pairs
    and k-means topic clusters. MCP tool count: 13 → 17.
- **OCR for uploads** (opt-in `OCR_UPLOADS=1`, `app/ocr.py`): the bundled tesseract
  binary indexes the text inside uploaded images into a new `upload_texts` table
  (generated tsvector + GIN). Surfaced via `GET /api/search?uploads=1` (opt-in param;
  the default response stays pages-only) and as `type: "upload"` items in MCP
  `search_pages`. Languages via `OCR_LANGS` (default `eng+spa`).
- **Cross-encoder reranker** (opt-in `RERANK=1`, requires `SEMANTIC_SEARCH=1`):
  ms-marco MiniLM int8 ONNX (~23 MB, baked into the image with pinned revision +
  SHA-256) re-scores the top-20 sgrep candidates; results gain `rerank_score` and
  `via: "semantic+rerank"` while keeping the bi-encoder `score` for explainability.

## [0.9] — 2026-06-15

### Added
- **Intelligence layer.** Markdown metadata is now parsed and indexed on every save:
  YAML frontmatter, `#tags`, and `[[wikilinks]]` (`app/meta.py` → `page_meta` / `page_tags`
  / `page_links` tables).
- **Local semantic search** (opt-in via `SEMANTIC_SEARCH=1`). ONNX MiniLM int8 model baked
  into the image; chunked page embeddings stored in SQLite; numpy cosine similarity blended
  with BM25. Fully offline, no API keys. An async background worker embeds pages without
  blocking the app, and everything degrades gracefully to FTS5 when disabled or unindexed.
- **New MCP tools** (now 12 total): `extract` (structured frontmatter/tag query),
  `list_backlinks`, `related_pages`, `sgrep` (semantic grep), and `rag` (retrieval pipe
  with provenance).
- **REST**: `GET /api/search?mode=semantic` for meaning-based search.

### Changed
- Embedding model is fetched at image build with a pinned revision and SHA-256 checksums
  for reproducibility.
- Bumped version to `0.9` in `pyproject.toml` and `app/mcp.py`.

## [0.8] — previous

- Native MCP server at `/api/mcp` (JSON-RPC 2.0, no SDK).
- Personal Access Tokens (PAT) for agents/MCP.
- GitHub Actions CI → GHCR with multi-arch images.
- Per-page git history, FTS5 full-text search, REST API.
