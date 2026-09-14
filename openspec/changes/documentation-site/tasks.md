## 1. The documentation that does not exist

- [ ] 1.1 Write the page on writing pages: creating one, the page tree and subpages, moving and
      renaming, what git history gives you, and deletion. Verify every claim against the running
      application rather than against the code, and that the page names the raw markdown endpoint
      a reader would reach for next.
- [ ] 1.2 Write the page on linking: `[[target]]`, `[[target|label]]`, how a target resolves to a
      slug, and that an unresolved link is stored rather than discarded because a broken link is
      information. Verify the documented target limits against `meta.extract_links`, including
      that a target cannot contain `[`, and say why rather than presenting it as arbitrary.
- [ ] 1.3 Write the page on tags and the metadata block. It MUST state that the block is not
      YAML: `key: value` and inline `tags: [a, b]` take effect and a block list is silently
      ignored. Verify by running both spellings through `meta.extract_tags` and reporting what
      each returns, and cover that a tag must start with a letter, is lowercased, and is ignored
      inside code fences and inline code.
- [ ] 1.4 Write the page on search: the three modes, that `keyword` is the default and the sidebar
      uses `hybrid`, and that there is no query syntax. It MUST state what happens to the four
      constructions a user will try — `OR`, a quoted phrase, a stopword-only query, and a bare
      term that prefix-matches. Verify each against a running instance and quote the compiled
      query for `OR`.
- [ ] 1.5 Write the page on the graph: what `GET /api/graph` returns, what the view draws, and
      that it is trimmed above `GRAPH_NODE_LIMIT` by PageRank. Verify the node limit and the
      trimming behaviour against `graph.workspace_graph`, and link the roadmap entry for the
      layout defect rather than describing the view as finished.
- [ ] 1.6 Add the new pages to `docs/README.md`'s index with what each answers, in the table's
      existing shape. Verify `uv run python -m scripts.check_docs_reachable` still passes and that
      the count of examined references went up.

### Notes on section 1

## 2. The behaviour gate

- [ ] 2.1 Add tests asserting the four documented search behaviours as they are today: `OR`
      compiles to a conjunction, a stopword-only query is empty, a term prefix-matches, and a
      quoted phrase is not a phrase search. Each test names the page that documents it in its
      failure message. Verify each test fails when its assertion is inverted.
- [ ] 2.2 Add tests asserting the documented metadata and tag behaviours: block-list metadata
      yields no tags, inline-list does, a tag must start with a letter, tags are lowercased, and
      code spans are excluded. Same naming requirement. Verify by inverting each assertion.
- [ ] 2.3 Confirm these tests run in the Docker `test` stage, which copies only `app/`, `tests/`,
      `scripts/` and `pyproject.toml`. Anything reading a documentation file must skip rather than
      fail there. Verify in the stripped stage **before** pushing: this has broken three changes.

### Notes on section 2

## 3. The reference and the served schema

- [ ] 3.1 Pass the application version to `FastAPI(...)` from `app.version`. Verify
      `/openapi.json` declares the same version `/health` reports, and add a test asserting the
      two agree so the default cannot come back.
- [ ] 3.2 Add tags to the 59 operations by area, written on each decorator. Verify
      `app.openapi()` reports no untagged operation, and that the tag set is the intended one
      rather than whatever the routes happened to produce.
- [ ] 3.3 Translate the 21 Spanish route docstrings to English, changing nothing but the prose.
      Verify the operation count with a description is unchanged and that no non-docstring line
      was touched.
- [ ] 3.4 Write the REST reference page covering all 59 operations, grouped by the tags from 3.2,
      with the endpoint list in one fenced block, one operation per line, method first. Verify it
      covers every operation the schema reports.
- [ ] 3.5 Add the coverage test: parse the fenced block and compare it as a set against
      `app.openapi()`, failing in both directions. Verify it fails when an operation is removed
      from the page and when a route is added without an entry, and that it asserts a plausible
      minimum count so it cannot pass by parsing nothing.
- [ ] 3.6 Document that `/docs`, `/redoc` and `/openapi.json` are served publicly with no
      authentication, and that the interactive pages fetch assets from a CDN so they do not work
      on an instance with no outbound network. Verify the claim against the running instance
      rather than asserting it.

### Notes on section 3

## 4. The published site

- [ ] 4.1 Add MkDocs to its own `docs` dependency group, not `dev`. Verify `uv sync --frozen`
      installs nothing new, so the Docker `test` stage is untouched, and that
      `uv sync --group docs` gets the toolchain.
- [ ] 4.2 Write the MkDocs configuration with a nav that includes the five root documents from
      where they are, so the escaping relative links resolve without being rewritten and stay
      inside the reachability gate. Verify a strict build passes and that all five links resolve
      in the built site.
- [ ] 4.3 Prove the gate bites: break one internal link, confirm the strict build fails, restore
      it. A build that has never failed is not known to be strict.
- [ ] 4.4 Add the strict build to `make check` and to `ci.yaml` beside the licence, changelog and
      reachability checks, and add a `make` target for it. Verify `make check` runs it and fails
      on a broken link.
- [ ] 4.5 Add the Pages deployment workflow on pushes to `main`, with `pages: write` and
      `id-token: write` only. Verify the permission block grants nothing else, and state in the
      task notes that it cannot succeed until Pages is enabled on the repository.
- [ ] 4.6 Once Pages is enabled, verify the published site serves the new pages and that the five
      root documents resolve there. If it is not enabled, record that and leave the task open
      rather than marking it done.

### Notes on section 4

## 5. Close out

- [ ] 5.1 Run the whole gate: `make check` plus `cd frontend && npm run test`. Verify ruff, ruff
      format, pyright, pytest, the licence, changelog, reachability and site checks and
      `openspec validate --all --strict` all pass.
- [ ] 5.2 Add the deferred items to `ROADMAP.md`: response models across the 59 handlers, and the
      Community phase. Verify each names where it was identified, as the `contribution`
      capability requires.
- [ ] 5.3 Bump the version in `pyproject.toml` and release. `publish` runs on every push to
      `main` and republishes an unbumped version tag, and this change alters `app/` and
      `scripts/`, so it needs a version of its own. Verify the release workflow created the
      GitHub Release and that the CHANGELOG entry exists, since a version tag without one fails
      CI.

### Notes on section 5
