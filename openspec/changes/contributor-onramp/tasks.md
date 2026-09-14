## 1. Orientation that ships

- [x] 1.1 Write `AGENTS.md`. Original content limited to what nothing else states: work is
      proposed before it is written, `openspec/specs/` holds the behaviour contracts,
      `openspec/changes/archive/` holds the reasoning behind past decisions. Everything else
      is a pointer to the document that owns it — README, `CONTRIBUTING.md`, `DESIGN.md`,
      `docs/`. Verify it is tracked by git and that it restates nothing from `CLAUDE.md`.
- [x] 1.2 Write `openspec/README.md` explaining the two directories and how to read a
      capability versus an archived change. Verify a reader can tell, from it alone, where
      current behaviour is specified and where a past decision's reasoning lives.
- [x] 1.3 Point `CONTRIBUTING.md` at the workflow it currently never names, and the README at
      the orientation file. Verify `CONTRIBUTING.md` says proposals precede code, which today
      it does not.

### Notes on section 1

- **`openspec/README.md` turned out to be the substance, not the footnote.** Writing it
  surfaced that the two directories answer different questions, and that the notes at the end
  of an archived `tasks.md` are where a decision's reasoning actually lives — which is the
  thing a newcomer would never guess. Several examples are named there specifically because
  they look arbitrary in the code: the English stemmer, the disabled reranker, a wikilink
  target excluding `[`.
- `AGENTS.md` names two habits beyond the workflow — measure rather than assert, and record
  what diverged — because both are load-bearing here and neither is stated anywhere else.

## 2. The discoverability check

- [x] 2.1 Write a script that, for each tracked markdown file, finds references to
      repository-relative paths and fails when a referenced path is untracked or gitignored.
      Scope it to repository paths only: no URLs, no anchors, so the gate needs no network.
      Verify it passes on the tree today and fails when a tracked document is made to
      reference `CLAUDE.md`.
- [x] 2.2 Wire it into `make check` and as a CI step beside the licence and changelog checks,
      for the same reason: it reads repository files, not the built image. Verify `make check`
      fails on a deliberately broken reference and passes once restored.
- [x] 2.3 Add tests covering both directions. Verify `uv run pytest` includes them, and that
      they skip rather than fail where the tracked docs are absent — the Docker `test` stage
      copies only four things, which has broken two changes in a row.

### Notes on section 2

- **The check caught its own motivating case on the first run**, before it was even wired in:
  `AGENTS.md`, `openspec/README.md` and `ROADMAP.md` were referenced from tracked documents
  while still untracked or nonexistent. That is exactly the failure it exists to prevent.
- `openspec/changes/archive/` is excluded from the scan. Those are historical records, and a
  reference that was valid when written should not break the gate because a file moved later.
- **I broke the gate by linting the wrong scope, twice.** After writing each new script I ran
  `ruff check` on just that file, so an E501 in the one written before it reached the Docker
  stage, and later a `B007` reached `make check`. Worse, I read ruff's trailing "No fixes
  available" line as success when it was the tail of a failure. Exit codes from here on, not
  message tails.
- The stripped-tree verification was run **before** pushing this time, unlike the previous two
  changes: 315 passed, 20 skipped.

## 3. The identified work becomes visible

- [x] 3.1 Write `ROADMAP.md` from the nine identified items, in priority order, **with no
      dates**, marking which are enterable work and which are decisions for the maintainer.
      The items: the graph force layout is unreadable; search snippets leak raw markdown;
      `Delete` is the only page action outside the overflow menu; the seeded pages describe a
      retired Gitea runner and SQLite; comments are mixed Spanish and English against the
      project's own convention; five tests still perform requests inside `assert`;
      `knowledge-graph` carries a `TBD` Purpose; OpenSSF Scorecard is unblocked and not
      enabled; two secret-scanning settings are off. Verify every item names where it was
      identified.
- [x] 3.2 Record in `CONTRIBUTING.md` that an item deferred by a change reaches the roadmap
      rather than staying in that change's notes. Verify the text says where, not just that.
- [x] 3.3 File issues for the enterable subset only, each referencing its roadmap entry
      rather than restating it, and labelled so a newcomer can find them. Verify the labels
      applied are ones that already exist.

### Notes on section 3

- **Five of nine items became issues; four did not, and the split matters.** The four are
  decisions — enabling Scorecard, the two secret-scanning settings, the image size, the
  language convention — and filing them as issues would have presented a choice the
  maintainer has to make as work a stranger could pick up. The roadmap marks them
  **decision** for that reason.
- Every issue links to its roadmap entry rather than restating it, and each carries a hint
  that is only obvious from having read the code: that `meta.strip_code()` is probably the
  wrong tool for the snippet work, that the highlighter's control characters must survive any
  stripping, that `d3-force` is bundled and the graph route is code-split.

## 4. Licence provenance

- [x] 4.1 Write a `pull_request` check asserting every commit carries a `Signed-off-by`
      matching its author. A script rather than a third-party action, matching the release
      workflow's use of `gh`. Its failure message must include the exact remedy, amend
      command included: a provenance check that blocks a real contribution without saying how
      to fix it costs more than it protects.
- [x] 4.2 **Verify it against a constructed commit, both ways.** It will not fire on ordinary
      work, since every commit in this repository's history is a direct push to `main`, so a
      green CI proves nothing about it. Confirm a signed-off commit passes and an unsigned
      one fails with the remedy in the message.
- [x] 4.3 Add the sign-off requirement to `CONTRIBUTING.md`, with `git commit -s`, and state
      the consequence: sign-off transfers no copyright, so the project cannot be relicensed
      without every contributor's permission. Verify that consequence is written down rather
      than implied.

### Notes on section 4

- **The check requires the sign-off to match the commit *author*.** A trailer naming someone
  else certifies nothing about the person who wrote the change, so a mismatched signature
  fails with both addresses named.
- **Verified against constructed commits in a throwaway repository, and that was necessary.**
  The first push after adding it showed `signoff` as *skipped*, since it is a push and not a
  pull request. A green CI proves nothing about this check, which is the whole reason task 4.2
  demanded a constructed test.

## 5. Close out

- [x] 5.1 Run the whole gate: `make check` plus `cd frontend && npm run test`. Verify ruff,
      ruff format, pyright, pytest, the frontend gate, the licence, changelog and
      discoverability checks and `openspec validate --all --strict` all pass.
- [x] 5.2 Verify the requirement from a clean clone rather than from the working tree: clone
      the repository to a temporary directory and confirm the orientation is present and
      points at nothing missing. The working tree contains files a clone does not.
- [x] 5.3 Release. No application code changed, so this can ride with the next version rather
      than needing one of its own — unlike the security fix that preceded it.

### Notes on section 5

- **5.3 was wrong about how this project releases.** It said a documentation-only change could
  "ride with the next version". It cannot: `publish` runs on every push to `main` and tags the
  image with the version in `pyproject.toml`, so the first push republished 0.31.7 with
  different content — `scripts/` is copied into the runtime stage. The version was bumped to
  0.31.8 instead.
- **That exposed a contradiction between two capabilities written in this session.**
  `release-integrity` requires a published version identifier to be stable; the requirement is
  worded about git tags, so republishing an image tag satisfies the letter and not the purpose.
  The root fix — `publish` refusing when the declared version already exists in the registry —
  is recorded in the roadmap as a decision rather than absorbed into this change.
- 5.2 was verified from an actual `git clone`, not the working tree: the orientation is
  present, `CLAUDE.md` is absent, and the check passes from inside the clone.
