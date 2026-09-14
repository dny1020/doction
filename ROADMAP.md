# Roadmap

What has been identified and is not done. **No dates.** A single-maintainer project that
promises a schedule publishes a document that is wrong within weeks; one that lists what is
pending stays true until the work is done.

Every entry says where it was identified, so the reasoning can be found rather than
reconstructed. Entries marked **open** are work someone could pick up; entries marked
**decision** need the maintainer to choose a direction first, and are listed so nobody
mistakes them for available tasks.

When a change defers something deliberately, the item belongs here rather than only in that
change's notes. That is a requirement of the `contribution` capability, not a habit.

---

## Product defects

### The graph view is unreadable — **open**

`/w/<ws>/graph` renders, but the force layout collapses every node into the centre with
labels overlapping, leaving most of the canvas empty. On a 15-page workspace the labels are
already illegible. Needs the repulsion strength and link distance tuned, and probably a
label-collision strategy.

*Identified during the five-phase maturity review; the reason no graph screenshot is in the
README.*

### Search snippets leak raw markdown — **open**

Results show table pipes, `##`, `[[…]]` and even mermaid syntax inside the excerpt, because
snippets are extracted from the stored markdown without stripping syntax. Ranking is
unaffected; it is presentation. Note that `meta.strip_code()` already exists for a related
purpose and may be the wrong tool here, since the goal is readable prose rather than tag
removal.

*Identified during the five-phase maturity review.*

### `Delete` is the only page action outside the overflow menu — **open**

Edit, New subpage and History live behind the `…` menu while the destructive action sits
alone and prominent in red. The hierarchy is inverted: the primary action is hidden and the
irreversible one is the easiest to hit.

*Identified during the five-phase maturity review.*

### The seeded pages describe retired infrastructure — **open**

`app/seed.py` ships three pages to every new user. One is a runbook describing a Gitea
runner and an SQLite database on a mounted volume; Gitea was retired and the database is
PostgreSQL. It is the first thing a new user reads, and it is wrong.

*Identified during the five-phase maturity review.*

---

## Consistency

### Comments are mixed Spanish and English — **decision**

`CONTRIBUTING.md` states that code, comments and docs are English regardless of the
conversation's language. Much of `app/`, the workflows, `compose.yaml` and the `Makefile` are
in Spanish, including comments added recently. Either the convention changes or the codebase
converges on it; what is not defensible is the current state, where the stated rule and the
code disagree.

*Identified during the five-phase maturity review, and repeatedly since.*

### The `knowledge-graph` capability has a `TBD` Purpose — **open**

`openspec/specs/knowledge-graph/spec.md` opens with the placeholder the archive process
leaves when a delta carried no Purpose. Every other capability describes what it is for. A
good first task: read the capability's requirements and write the two sentences.

*Identified while syncing the `licensing` capability.*

---

## Security and supply chain

### OpenSSF Scorecard is unblocked and not enabled — **decision**

It was deliberately deferred until the code scanning queue reached zero, because Scorecard
publishes its findings as SARIF into that same queue and would have been indistinguishable
from the backlog. The queue is now at zero, so the precondition is met. Enabling it will
produce new findings, each of which then needs a decision under the `vulnerability-triage`
capability.

*Deferred by `2026-09-14-vulnerability-triage`; the reason is in `SECURITY.md`.*

### Two secret-scanning settings are off — **decision**

`secret_scanning_non_provider_patterns` and `secret_scanning_validity_checks` are disabled.
The second is the more useful: it reports whether a leaked credential is still live. Both are
repository settings rather than anything a commit can change.

*Identified in the installation health review.*

### `publish` republishes an existing version tag — **decision**

`publish` runs on every push to `main` and tags the image with the version in
`pyproject.toml`. A push that does not bump the version therefore republishes that tag with
different content: 0.31.4 was published three times and 0.31.7 twice. The
`release-integrity` capability requires that a published version identifier be stable, and
that requirement is written about git tags, so the letter is satisfied while the purpose is
not.

The root fix is for `publish` to refuse when the declared version already exists in the
registry, which turns "forgot to bump" into a failed build rather than a silently
overwritten release. Until then the workaround is bumping the version for any change that
alters the image, which is what 0.31.8 did.

*Identified during the five-phase maturity review and again while implementing
`contributor-onramp`, where it forced a version bump for a documentation-only change.*

### The runtime image carries 75 MB of superseded files — **decision**

Applying Debian security updates in the runtime stage grew the image from 666 MB to 741 MB,
because Docker layers are additive: the upgraded packages are written above while the
originals remain below. The alternative with no size cost is waiting for `python:3.14-slim`
to be rebuilt with those updates, which has no timeline. Revisit when the base image moves.

*Recorded in the notes of `2026-09-14-vulnerability-triage`.*

---

## Project maturity

Two phases of the open-source maturity plan remain. Neither is started.

**Documentation.** A published documentation site, end-user documentation, and an API
reference generated from the OpenAPI schema the application already serves. The existing
`docs/` is operator-facing: it covers installing and running doction, and nothing explains
how to *use* the wiki — writing a page, wikilinks, tags, frontmatter, search syntax, the
graph. That is the real gap.

**Community.** GitHub Sponsors, a public demo instance, and using Discussions. A demo needs
`DISABLE_REGISTRATION=1` and a seeded read-only account, since sign-up is open by default.
Most of this is account-level setup the maintainer has to do rather than work in the
repository.

*From the five-phase maturity review. The first three phases landed as `licensing`,
`release-integrity` and `vulnerability-triage`.*
