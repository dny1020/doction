## Context

See proposal.md — Why. The requirements are in `specs/contribution/spec.md`.

Three existing facts constrain the approach. `openspec/` is tracked, 112 files of it, so the
decision record already ships and only needs explaining. `CLAUDE.md` and `.claude/` are
gitignored by deliberate policy, and `AGENTS.md` is not, so a shipped orientation file does
not require changing that policy. And this project already has a precedent for enforcing a
promise about the repository mechanically rather than by review: `scripts/check_license.py`
runs in the gate and in CI.

## Goals / Non-Goals

**Goals**

- Someone who clones the repository learns that work is proposed before it is written.
- Deferred work stops living only in review notes.
- Licence provenance is recorded from the first outside contribution.

**Non-Goals**

- Attracting contributors. Stated in the proposal, repeated here because it is the thing
  most likely to be read into this change.
- A CLA or any copyright assignment. Decided when AGPL-3.0-only was chosen over a dual
  licence.
- A general documentation link checker. The narrow check below is not that.
- Filing issues for all nine deferred items. Some are decisions for the maintainer, not
  entry points for a stranger.

## Decisions

### `AGENTS.md`, not a committed `CLAUDE.md`

The maintainer's policy is that `CLAUDE.md` is never committed, and that policy is right:
it holds their own working context. `AGENTS.md` is a separate, tool-neutral convention and
is not gitignored, so the project's conventions can ship without the maintainer's notes
shipping with them.

The two are different documents with different audiences, which is why this is not a
workaround. `CLAUDE.md` says how *this maintainer* works on doction. `AGENTS.md` says how
doction is worked on.

*Alternative considered:* un-ignoring `CLAUDE.md`. Rejected — it would publish the
maintainer's private context to satisfy a need that a separate file meets better.

### The orientation file is a map, and its thinness is a review property rather than a check

Its original content is limited to the workflow nothing else states: propose before writing,
`openspec/specs/` for contracts, `openspec/changes/archive/` for reasons. Everything else is
a pointer — README for the tour, `CONTRIBUTING.md` for the gate and commit style,
`DESIGN.md` for the visual system, `docs/` for operations.

**This is deliberately not mechanically enforced, and that is worth stating rather than
hiding.** Whether a sentence duplicates an authoritative source or usefully summarises it is
a judgement, and a check that counted lines or forbade keywords would enforce the wrong
thing. The spec expresses it as a review scenario for that reason. The mechanical half of
the requirement is the part that can be checked: that orientation reaches a reader from
tracked files only.

### The check asserts that tracked documentation does not point at untracked files

A script in the shape of `check_license.py`: for each tracked markdown file, find references
to repository paths and fail when a referenced path is untracked or gitignored.

This is the mechanical half of "discoverable from a clone". It catches the specific failure
this change exists to fix — a document telling a reader to consult something that is not in
their clone — and it would have caught it today, since `CONTRIBUTING.md` and the README
currently reference nothing untracked but nothing stopped them from doing so.

Its scope is narrow on purpose: references to paths inside the repository, not URLs, not
anchors, not external links. A full link checker needs network access, which the gate must
not require, and would fail for reasons that have nothing to do with this requirement.

### The DCO check is a script, not a third-party action

Verifying that each commit in a pull request carries a `Signed-off-by` matching its author
is a short script. `release.yaml` already uses `gh` rather than an action for the same kind
of reason, and every third-party action in this repository has to be pinned to a commit SHA
and then maintained.

It runs on `pull_request` only. It will not fire for a long time: every commit in this
project's history is a direct push to `main`. That is not an argument against having it —
the requirement exists to be earlier than the first contribution — but it does mean the
check must be verified deliberately, against a constructed commit, rather than assumed to
work because CI is green.

*Alternative considered:* the GitHub DCO App. Rejected as a third-party integration with
repository write access, for a check that is twenty lines.

### `ROADMAP.md` is the inventory; issues point at it

One authoritative list, in priority order, with no dates. Issues are filed only for items
that a stranger could actually pick up, and they reference the roadmap entry rather than
restating it.

The alternative — issues as the only record — was considered and rejected for a specific
reason: several of the nine deferred items are decisions for the maintainer rather than
tasks, and an issue tracker misrepresents a decision as available work. The roadmap can hold
both kinds and say which is which.

No dates, per the requirement. The three preceding changes each declined to put a schedule
in a spec for the same reason: a single-maintainer promise about timing is a document that
becomes false without anyone editing it.

## Risks / Trade-offs

**`AGENTS.md` drifts into a second `CLAUDE.md`** → It starts thin and the requirement names
duplication as the defect. The realistic failure is gradual accretion, which review catches
only if the reviewer knows the file's purpose; that purpose is stated in the file itself.

**The path check produces false failures on prose** → It looks for path-shaped references
and only fails when the target is both repository-relative and untracked. A word that merely
looks like a path but names nothing will not resolve to an untracked file.

**The DCO check blocks a first-time contributor over a formality** → The failure message has
to say exactly how to fix it, including the `git commit -s` amend command. A provenance check
that stops a genuine contribution without explaining the remedy costs more than it protects.

**The roadmap becomes stale in a different way** → It commits to no dates, so it can only be
wrong by omission. Items reaching it from a change's deferred notes is the habit that keeps
it current, and that is stated in the requirement rather than left to memory.

## Migration Plan

1. `AGENTS.md` and the `openspec/` index. These are the substance: orientation that ships.
2. The path check, wired into the gate and CI beside the licence and changelog checks.
3. `ROADMAP.md`, from the nine identified items.
4. The DCO check, `CONTRIBUTING.md`'s sign-off section, and the relicensing consequence.
5. Issues for the enterable subset.

Rollback is `git revert`. Nothing here affects the running application, the image or the API.

## Open Questions

None. Which of the nine items become issues is a judgement to make while writing the
roadmap, not a question that changes the specs or the approach.
