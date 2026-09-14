## 1. Orientation that ships

- [ ] 1.1 Write `AGENTS.md`. Original content limited to what nothing else states: work is
      proposed before it is written, `openspec/specs/` holds the behaviour contracts,
      `openspec/changes/archive/` holds the reasoning behind past decisions. Everything else
      is a pointer to the document that owns it — README, `CONTRIBUTING.md`, `DESIGN.md`,
      `docs/`. Verify it is tracked by git and that it restates nothing from `CLAUDE.md`.
- [ ] 1.2 Write `openspec/README.md` explaining the two directories and how to read a
      capability versus an archived change. Verify a reader can tell, from it alone, where
      current behaviour is specified and where a past decision's reasoning lives.
- [ ] 1.3 Point `CONTRIBUTING.md` at the workflow it currently never names, and the README at
      the orientation file. Verify `CONTRIBUTING.md` says proposals precede code, which today
      it does not.

### Notes on section 1

<!-- Record what actually happened here, including anything that diverged from the plan. -->

## 2. The discoverability check

- [ ] 2.1 Write a script that, for each tracked markdown file, finds references to
      repository-relative paths and fails when a referenced path is untracked or gitignored.
      Scope it to repository paths only: no URLs, no anchors, so the gate needs no network.
      Verify it passes on the tree today and fails when a tracked document is made to
      reference `CLAUDE.md`.
- [ ] 2.2 Wire it into `make check` and as a CI step beside the licence and changelog checks,
      for the same reason: it reads repository files, not the built image. Verify `make check`
      fails on a deliberately broken reference and passes once restored.
- [ ] 2.3 Add tests covering both directions. Verify `uv run pytest` includes them, and that
      they skip rather than fail where the tracked docs are absent — the Docker `test` stage
      copies only four things, which has broken two changes in a row.

### Notes on section 2

<!-- Record what actually happened here, including anything that diverged from the plan. -->

## 3. The identified work becomes visible

- [ ] 3.1 Write `ROADMAP.md` from the nine identified items, in priority order, **with no
      dates**, marking which are enterable work and which are decisions for the maintainer.
      The items: the graph force layout is unreadable; search snippets leak raw markdown;
      `Delete` is the only page action outside the overflow menu; the seeded pages describe a
      retired Gitea runner and SQLite; comments are mixed Spanish and English against the
      project's own convention; five tests still perform requests inside `assert`;
      `knowledge-graph` carries a `TBD` Purpose; OpenSSF Scorecard is unblocked and not
      enabled; two secret-scanning settings are off. Verify every item names where it was
      identified.
- [ ] 3.2 Record in `CONTRIBUTING.md` that an item deferred by a change reaches the roadmap
      rather than staying in that change's notes. Verify the text says where, not just that.
- [ ] 3.3 File issues for the enterable subset only, each referencing its roadmap entry
      rather than restating it, and labelled so a newcomer can find them. Verify the labels
      applied are ones that already exist.

### Notes on section 3

<!-- Record what actually happened here, including anything that diverged from the plan. -->

## 4. Licence provenance

- [ ] 4.1 Write a `pull_request` check asserting every commit carries a `Signed-off-by`
      matching its author. A script rather than a third-party action, matching the release
      workflow's use of `gh`. Its failure message must include the exact remedy, amend
      command included: a provenance check that blocks a real contribution without saying how
      to fix it costs more than it protects.
- [ ] 4.2 **Verify it against a constructed commit, both ways.** It will not fire on ordinary
      work, since every commit in this repository's history is a direct push to `main`, so a
      green CI proves nothing about it. Confirm a signed-off commit passes and an unsigned
      one fails with the remedy in the message.
- [ ] 4.3 Add the sign-off requirement to `CONTRIBUTING.md`, with `git commit -s`, and state
      the consequence: sign-off transfers no copyright, so the project cannot be relicensed
      without every contributor's permission. Verify that consequence is written down rather
      than implied.

### Notes on section 4

<!-- Record what actually happened here, including anything that diverged from the plan. -->

## 5. Close out

- [ ] 5.1 Run the whole gate: `make check` plus `cd frontend && npm run test`. Verify ruff,
      ruff format, pyright, pytest, the frontend gate, the licence, changelog and
      discoverability checks and `openspec validate --all --strict` all pass.
- [ ] 5.2 Verify the requirement from a clean clone rather than from the working tree: clone
      the repository to a temporary directory and confirm the orientation is present and
      points at nothing missing. The working tree contains files a clone does not.
- [ ] 5.3 Release. No application code changed, so this can ride with the next version rather
      than needing one of its own — unlike the security fix that preceded it.

### Notes on section 5

<!-- Record what actually happened here, including anything that diverged from the plan. -->
