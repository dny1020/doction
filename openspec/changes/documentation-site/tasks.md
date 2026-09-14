## 1. The documentation that does not exist

- [x] 1.1 Write the page on writing pages: creating one, the page tree and subpages, moving and
      renaming, what git history gives you, and deletion. Verify every claim against the running
      application rather than against the code, and that the page names the raw markdown endpoint
      a reader would reach for next.
- [x] 1.2 Write the page on linking: `[[target]]`, `[[target|label]]`, how a target resolves to a
      slug, and that an unresolved link is stored rather than discarded because a broken link is
      information. Verify the documented target limits against `meta.extract_links`, including
      that a target cannot contain `[`, and say why rather than presenting it as arbitrary.
- [x] 1.3 Write the page on tags and the metadata block. It MUST state that the block is not
      YAML: `key: value` and inline `tags: [a, b]` take effect and a block list is silently
      ignored. Verify by running both spellings through `meta.extract_tags` and reporting what
      each returns, and cover that a tag must start with a letter, is lowercased, and is ignored
      inside code fences and inline code.
- [x] 1.4 Write the page on search: the three modes, that `keyword` is the default and the sidebar
      uses `hybrid`, and that there is no query syntax. It MUST state what happens to the four
      constructions a user will try — `OR`, a quoted phrase, a stopword-only query, and a bare
      term that prefix-matches. Verify each against a running instance and quote the compiled
      query for `OR`.
- [x] 1.5 Write the page on the graph: what `GET /api/graph` returns, what the view draws, and
      that it is trimmed above `GRAPH_NODE_LIMIT` by PageRank. Verify the node limit and the
      trimming behaviour against `graph.workspace_graph`, and link the roadmap entry for the
      layout defect rather than describing the view as finished.
- [x] 1.6 Add the new pages to `docs/README.md`'s index with what each answers, in the table's
      existing shape. Verify `uv run python -m scripts.check_docs_reachable` still passes and that
      the count of examined references went up.

### Notes on section 1

- **The live instance was the right call and it corrected the plan twice.** Deleting a page is
  recoverable: there is a trash with restore and purge, which no document mentioned and which
  changes what 1.1 had to say about deletion. A workspace also exports as a zip of markdown, which
  is the answer to "how do I leave" and was likewise undocumented.
- **A wikilink target can be a page title**, because the target is slugified before lookup, and it
  also resolves through the aliases a rename leaves behind. Both measured end to end rather than
  read out of the code.
- **The broken link heals by itself.** A page linking to a slug that did not exist had its edge
  resolved when that page was later created, with no second save of the linking page. That makes
  linking ahead of writing a reasonable habit, and it is the most useful thing on the linking page.
- `hybrid` is reciprocal rank fusion with a weighted vector list, not "lexical hits then semantic
  ones" as the project's own private notes still say. The page documents what the code does.
- Searching with `mode=semantic` on an instance with the flag off returns keyword results rather
  than an error. Measured: all three modes returned the same five pages. Documented as deliberate
  degradation, with a pointer to `/api/system` for finding out which mode is really available.

## 2. The behaviour gate

- [x] 2.1 Add tests asserting the four documented search behaviours as they are today: `OR`
      compiles to a conjunction, a stopword-only query is empty, a term prefix-matches, and a
      quoted phrase is not a phrase search. Each test names the page that documents it in its
      failure message. Verify each test fails when its assertion is inverted.
- [x] 2.2 Add tests asserting the documented metadata and tag behaviours: block-list metadata
      yields no tags, inline-list does, a tag must start with a letter, tags are lowercased, and
      code spans are excluded. Same naming requirement. Verify by inverting each assertion.
- [x] 2.3 Confirm these tests run in the Docker `test` stage, which copies only `app/`, `tests/`,
      `scripts/` and `pyproject.toml`. Anything reading a documentation file must skip rather than
      fail there. Verify in the stripped stage **before** pushing: this has broken three changes.

### Notes on section 2

- **Every one of the 17 assertions was inverted and confirmed to fail.** A test that asserts
  current behaviour can pass vacuously, so the inversion is the only thing that proves it is
  load-bearing. None still passed when denied.
- The tests read no documentation, only code, so they need no skip and run in the stripped stage
  like any other test. Only the reference-coverage tests in section 3 read a file from `docs/`.

## 3. The reference and the served schema

- [x] 3.1 Pass the application version to `FastAPI(...)` from `app.version`. Verify
      `/openapi.json` declares the same version `/health` reports, and add a test asserting the
      two agree so the default cannot come back.
- [x] 3.2 Add tags to the 59 operations by area, written on each decorator. Verify
      `app.openapi()` reports no untagged operation, and that the tag set is the intended one
      rather than whatever the routes happened to produce.
- [x] 3.3 Translate the 21 Spanish route docstrings to English, changing nothing but the prose.
      Verify the operation count with a description is unchanged and that no non-docstring line
      was touched.
- [x] 3.4 Write the REST reference page covering all 59 operations, grouped by the tags from 3.2,
      with the endpoint list in one fenced block, one operation per line, method first. Verify it
      covers every operation the schema reports.
- [x] 3.5 Add the coverage test: parse the fenced block and compare it as a set against
      `app.openapi()`, failing in both directions. Verify it fails when an operation is removed
      from the page and when a route is added without an entry, and that it asserts a plausible
      minimum count so it cannot pass by parsing nothing.
- [x] 3.6 Document that `/docs`, `/redoc` and `/openapi.json` are served publicly with no
      authentication, and that the interactive pages fetch assets from a CDN so they do not work
      on an instance with no outbound network. Verify the claim against the running instance
      rather than asserting it.

### Notes on section 3

- **`POST /api/uploads` was tagged wrong at first** and the generated grouping is what showed it.
  It is registered on the app with a full path rather than on the prefixed router, so a rule
  keyed on the router's relative path put it under `app`. Retagged to `uploads`.
- **The coverage test's own parser was broken, and its minimum-count guard caught it.** An
  expression pairing a fence with a fence matched from the *closing* fence of an earlier `bash`
  block, capturing prose instead of the endpoint list, so the documented set was empty. The first
  rewrite was still wrong: skipping a language-tagged block means its closing fence is
  indistinguishable from a bare opening one. The working version tracks fence state and bareness
  separately. The guard that made this visible rather than silent is the reason it exists.
- **The stripped Docker build is where an E501 surfaced, again.** The whole-project ruff run
  catches it; I ran the build first. Lint the whole tree before the expensive step, not after.
- Only docstrings, decorators and the FastAPI constructor changed in `app/`. Verified by filtering
  the diff: every non-decorator line is a docstring line.
- `/docs` and `/redoc` pull Swagger UI and ReDoc from `cdn.jsdelivr.net`, confirmed by reading the
  served HTML, and all three documentation routes answer 200 with no credential on both the live
  instance and a local one.

## 4. The published site

- [x] 4.1 Add MkDocs to its own `docs` dependency group, not `dev`. Verify `uv sync --frozen`
      installs nothing new, so the Docker `test` stage is untouched, and that
      `uv sync --group docs` gets the toolchain.
- [x] 4.2 Write the MkDocs configuration with a nav that includes the five root documents from
      where they are, so the escaping relative links resolve without being rewritten and stay
      inside the reachability gate. Verify a strict build passes and that all five links resolve
      in the built site.
- [x] 4.3 Prove the gate bites: break one internal link, confirm the strict build fails, restore
      it. A build that has never failed is not known to be strict.
- [x] 4.4 Add the strict build to `make check` and to `ci.yaml` beside the licence, changelog and
      reachability checks, and add a `make` target for it. Verify `make check` runs it and fails
      on a broken link.
- [x] 4.5 Add the Pages deployment workflow on pushes to `main`, with `pages: write` and
      `id-token: write` only. Verify the permission block grants nothing else, and state in the
      task notes that it cannot succeed until Pages is enabled on the repository.
- [ ] 4.6 Once Pages is enabled, verify the published site serves the new pages and that the five
      root documents resolve there. If it is not enabled, record that and leave the task open
      rather than marking it done.

### Notes on section 4

- **The design said five root documents; the real number is nine plus `LICENSE`.** The five were
  the links *out of* `docs/`. Once a root document is in the site, its own links have to resolve
  too: the README reaches `ROADMAP.md`, `AGENTS.md`, `openspec/README.md` and `LICENSE`, and
  `CONTRIBUTING.md` adds `CODE_OF_CONDUCT.md`. The strict build found each one, which is the
  gate doing its job before it was even wired in.
- **MkDocs cannot include a file from above its `docs_dir`, and the alternatives were worse.**
  Pointing `docs_dir` at the repository root fails because `site_dir` may not sit inside it, and
  it would drag every markdown file in the repository into the site. A plugin would be another
  dependency. So `scripts/build_docs.py` stages a tree shaped the way the relative links already
  assume, and the staged copies are build output that is gitignored, never a second committed
  copy. This diverges from the design's wording, which assumed a nav could reference the files
  where they are.
- **The strict build was proven to fail before being trusted.** One link changed to a
  nonexistent target aborted the build with the warning named; restored, it passes.
- **The docs build is its own CI job, not a step in `test`.** The design put it beside the
  licence and changelog checks, which run on the runner's stdlib Python. This one needs mkdocs
  from the `docs` group, and installing a documentation toolchain inside the job whose purpose is
  an image build is the wrong shape. Same workflow, separate job.
- `uv sync --frozen` installs 45 packages and mkdocs is not among them, so the Docker `test`
  stage is untouched, which was the whole point of the separate group.
- **4.6 cannot be done yet.** The Pages API still answers 404 for this repository, so the
  deployment workflow has nothing to publish to. It is written and pinned; enabling Pages is a
  repository setting.

## 5. Close out

- [x] 5.1 Run the whole gate: `make check` plus `cd frontend && npm run test`. Verify ruff, ruff
      format, pyright, pytest, the licence, changelog, reachability and site checks and
      `openspec validate --all --strict` all pass.
- [x] 5.2 Add the deferred items to `ROADMAP.md`: response models across the 59 handlers, and the
      Community phase. Verify each names where it was identified, as the `contribution`
      capability requires.
- [ ] 5.3 Bump the version in `pyproject.toml` and release. `publish` runs on every push to
      `main` and republishes an unbumped version tag, and this change alters `app/` and
      `scripts/`, so it needs a version of its own. Verify the release workflow created the
      GitHub Release and that the CHANGELOG entry exists, since a version tag without one fails
      CI.

### Notes on section 5

- **The stripped stage was verified before pushing, and the arithmetic checks out.** It reports
  334 passed and 23 skipped, against 315 and 20 before this change. The 19 extra passes are the
  new tests that read only code; the 3 extra skips are exactly the reference-coverage tests that
  read `docs/api.md`, which the stage does not copy. Locally the same suite is 356 passed and 1
  skipped.
- **The roadmap gained two entries rather than one.** Response models across the 59 handlers was
  the expected deferral. Pages not being enabled is the second, and it is a decision rather than
  enterable work, since it is a repository setting.
- **5.3 is committed but not pushed, deliberately.** Pushing triggers `pages.yaml`, which cannot
  succeed until Pages is enabled on the repository, so the first push would put a red run on
  `main` for a reason that is a settings change rather than a defect. Enabling Pages first makes
  the same push green.
