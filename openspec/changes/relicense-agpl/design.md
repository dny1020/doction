## Context

See proposal.md — Why. The requirements are in `specs/licensing/spec.md`.

Two constraints shape the approach. The licence is declared in seven places, one of which
(the GitHub repository description) is not in the working tree and cannot be changed by a
commit. And `GET /api/system` already exists and already reports version, database
reachability and retrieval flags, so the source-offer requirement has somewhere to live
rather than needing a new surface.

## Goals / Non-Goals

**Goals**

- The licence value exists in as few authored places as possible, and disagreement between
  the remaining ones fails a check.
- The network-use obligation is discharged by the software, configurable per deployment.

**Non-Goals**

- Per-file licence headers. The AGPL recommends them and does not require them; adding a
  notice to roughly 50 source files is churn that no check would ever verify.
- Retroactive relicensing of published releases. Out of scope by requirement.
- A CLA, contributor copyright assignment, or dual licensing. Unrelated decision.

## Decisions

### The declaration set is checked by a script in the existing gate, not by review

The failure this prevents already happened: the repository description said "MIT licensed"
two releases after MIT was gone, and no human noticed across several reviews. So the check
has to be mechanical.

A small script reads the licence from `pyproject.toml` — the single authored source, since
`app/version.py` already establishes that file as the one place a project fact lives — and
asserts every other declaration matches. It runs inside `make check`, next to the existing
`check-local-assets.js`, which is the same shape of check: a promise the project makes,
enforced against the tree rather than documented.

**In CI it runs as a step in the `test` job, before the docker build, and not inside the
Dockerfile.** This departs from where `check-local-assets.js` lives and the reason is
measured rather than stylistic. That check sits in the `web` stage, which builds in seconds.
The `test` stage runs the full Python suite against an embedded Postgres and takes about
four minutes. It copies only `app`, `tests` and `scripts`, so putting the licence check
there would mean copying `LICENSE`, `README.md`, `CONTRIBUTING.md` and
`frontend/package.json` into that stage as well — and every typo in the README would then
invalidate the layer and re-run 293 tests to verify a string comparison that takes under a
second.

The project's rule is that the gate is one self-contained build. The rule exists so the
local gate and CI cannot diverge, and `make license` keeps that property: the same command
runs in both places. What is given up is running it inside the image, which buys nothing
here because the check inspects repository files rather than the built artifact.

*Alternative considered:* a pre-commit hook. Rejected because it runs on the author's
machine only, and the stale description survived precisely because nobody ran anything.

*Alternative considered:* generating the README badge and the licence section from
`pyproject.toml` at build time. Rejected as heavier than the problem: the README is authored
prose, and templating it to remove one line of duplication trades a check for a build step.

### The repository description is verified, not written, by the check

A commit cannot change platform metadata. The check therefore reads the published
description over the API and reports a mismatch rather than fixing it, and it treats an
unreachable API as a skip rather than a failure so the gate still works offline.

This keeps the offline guarantee the project already holds: `make check` must pass on a
machine with no route out, which is why the network half degrades to a skip instead of an
error.

*Alternative considered:* leaving platform metadata out of the checked set entirely.
Rejected because that is the declaration that was wrong, and excluding it would make the
check pass on exactly the case that motivated it.

### The source location is configuration, defaulting to upstream

`SOURCE_URL` joins the existing environment-variable set, defaults to this project's
repository, and is reported by `GET /api/system` alongside the licence identifier. The
frontend reads it from the status surface it already fetches.

Making it configurable is not a nicety. An operator who modifies doction owes their users
their own source; an instance that can only ever point upstream would let a modified
deployment believe it is compliant while it is not.

*Alternative considered:* deriving it from the git remote at build time. Rejected because
the built image is what gets deployed, and the person deploying it is not the person who
built it. Configuration belongs to whoever runs the instance.

*Alternative considered:* a static footer link in the HTML. Rejected because the value has
to reach the client at runtime to be operator-configurable, and `/api/system` is already the
path that carries runtime facts to the interface.

### Where the link appears

Settings, beside the existing system information, rather than a persistent footer. The
information is consulted deliberately and rarely; putting it in every view costs chrome on
every screen to serve an occasional question. The existing System section already answers
"what is this instance", which is the same question.

## Risks / Trade-offs

**The consistency check becomes the thing that breaks releases** → It asserts equality
between strings that only change during a deliberate relicence. The cost of a false failure
is one line; the cost of the failure it catches is legal ambiguity about the terms.

**The description check needs a token with repository read access in CI** → It degrades to a
skip without one, so CI keeps working and the check simply stops covering that one
declaration. Recorded rather than solved: a skip that nobody notices is the same failure
mode this change exists to close, so the check reports loudly when it skips.

**`SOURCE_URL` pointing somewhere wrong is worse than no link** → An operator who sets it to
an unrelated repository produces a confidently incorrect compliance claim. The software
cannot verify that a URL serves the corresponding source, so this stays the operator's
responsibility and the documentation says so plainly.

**AGPL narrows who will adopt doction** → Intended. Some organisations will not deploy AGPL
software. That is the cost of the property being bought, and the proposal accepts it.

## Migration Plan

1. Licence text, declarations and documentation, in one commit. At this point the licence is
   AGPL-3.0-only and internally consistent.
2. The consistency check, wired into `make check`. It must pass against step 1, which is what
   proves step 1 was complete.
3. `SOURCE_URL`, the `/api/system` field, and the Settings surface.
4. The repository description, by hand, because nothing else can.

Rollback is `git revert` plus restoring the description. Nothing in the database, the image
or the API contract changes in a way that outlives a revert; the added `/api/system` field is
additive and an older client ignores it.

## Open Questions

None. The one question that would have changed the specs — whether the obligation is
discharged by the software or left to documentation — was settled before this document was
written, and the spec carries the answer.
