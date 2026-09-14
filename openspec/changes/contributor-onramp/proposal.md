## Why

The repository ships 112 OpenSpec files — 19 capabilities and every archived change with
its proposal, design, tasks and the notes recording what actually happened — and **nothing
that travels in a clone explains what they are**. `CONTRIBUTING.md` mentions `openspec`
once, as a command inside the quality gate. The README and `docs/` do not mention it at all.
There is no index in `openspec/`.

So the most valuable orientation material in this project is invisible to whoever arrives.
Someone who reads `CONTRIBUTING.md`, learns the gate and the commit convention, and then
opens a pull request with code and no proposal has done exactly the wrong thing for this
repository, and nothing told them otherwise.

The maintainer's own working context lives in `CLAUDE.md`, which is deliberately gitignored.
That is the right policy and it leaves a gap: a project whose stated thesis is a wiki for
humans **and AI agents**, with a 27-tool MCP surface, hands an agent that clones it no
orientation at all.

**Identified work is recorded where nobody can read it.** There are zero `TODO` comments in
the project's own code, zero open issues, and no active changes, which reads as "no backlog".
There is one: nine concrete items were identified during review and deliberately deferred,
and they live in review notes and archived task files rather than anywhere a person can
find them. Among them: the graph view's force layout is unreadable, search snippets leak
raw markdown, `Delete` is the only page action not hidden behind a menu, the seeded pages
describe a Gitea runner and SQLite that were both retired, five tests still perform requests
inside `assert`, and the `knowledge-graph` capability still carries a `TBD` Purpose.

**Licence provenance is cheap now and expensive later.** `CONTRIBUTING.md` says opening a
pull request means agreeing the work ships under AGPL-3.0-only, which is a claim with no
record behind it. Asking contributor number one for a sign-off is trivial; reconstructing it
for contributor twenty is not possible.

Two things this change does **not** claim. It will not attract contributors: the binding
constraint on a repository with one star and no forks is that nobody arrives, not that
arrivals bounce off a missing label. And a Developer Certificate of Origin check will not
fire for a long time, because every commit in this project's history is a direct push to
`main` and such a check runs on pull requests. Both are worth doing anyway, for the same
reason the licence-consistency check was: the cost of adding them later is much higher than
the cost of adding them now.

## What Changes

- **`AGENTS.md` ships**, and is a map rather than a copy. Its only original content is what
  nothing currently says: that work is proposed before it is written, that `openspec/specs/`
  holds the behaviour contracts, and that `openspec/changes/archive/` is where the reason
  for a past decision lives. Everything else points at what already ships — the README for
  the tour, `CONTRIBUTING.md` for the gate, `DESIGN.md` for the visual system. Copying
  `CLAUDE.md` into it would put one truth in two files, which is the failure this session
  has already chased three times.
- **`openspec/` gets an index** explaining the two directories and how to read a capability
  versus an archived change.
- **The deferred work becomes visible**: an inventory of what is identified and not done, in
  priority order and **without dates**, plus GitHub issues for the items that are genuinely
  enterable.
- **A Developer Certificate of Origin is required and documented**, with its consequence
  stated: sign-off transfers no copyright, so the project cannot be relicensed without every
  contributor's permission. That follows from choosing AGPL-3.0-only over a dual licence and
  is recorded rather than discovered later.

## Capabilities

### New Capabilities

- `contribution`: what the repository owes whoever arrives wanting to change it — that its
  own way of working is discoverable from a clone, that work already identified is visible
  rather than private, and that every contribution carries a record of the terms it was
  offered under.

### Modified Capabilities

None. `licensing` covers the licence the project is under; this covers the terms a
*contribution* arrives under, which is a different fact about a different party.

## Impact

| Area | Change |
| --- | --- |
| `AGENTS.md` | new, shipped, thin |
| `openspec/README.md` | new index |
| `ROADMAP.md` | the inventory of identified, undone work |
| `CONTRIBUTING.md` | sign-off requirement, and a pointer to the workflow it never named |
| `.github/` | a DCO check on pull requests |

Outside the working tree: the issues themselves, and enabling the sign-off requirement where
that is a repository setting rather than a workflow.

No application code changes. Nothing about the running product is different after this.
