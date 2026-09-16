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

---

## Documentation

### The API reference describes no response shapes — **open**

Every route handler returns `Response` or `JSONResponse`, so FastAPI has nothing to infer an
output shape from: of 59 operations, one has a response schema for a 2xx. `/docs` therefore shows
request bodies and status codes but tells a client nothing about what comes back.

Fixing it means declaring Pydantic response models across all 59 handlers, which touches every
route and is why `documentation-site` left it out. That change made the reference complete in its
*coverage* of endpoints and correct in the version it declares, and a test now keeps it that way;
completing the *descriptions* is this entry.

*Deferred by `documentation-site`, where the measurement is recorded.*

### The docs site will not be served from GitHub Pages — **decision**

Enabling Pages was left open as a repository-setting decision (see the original note below);
the direction has since changed. Documentation and API exposure are planned to move to a
`doction.dev` domain once it is acquired, rather than to a `github.io` subdomain, so Pages will
not be enabled for this repository. The deployment workflow
(`.github/workflows/pages.yaml`) exists, is pinned, and takes only `pages: write` and
`id-token: write`, but it has nothing to publish to and is not going to get one, so its push
trigger is commented out and it now runs only on `workflow_dispatch`. It was failing on every
push that touched a path it watched (`docs/**`, `README.md`, `CHANGELOG.md`, and the other
root documents in its `nav`), on a decision rather than a defect. The path list is kept in the
file rather than deleted, so restoring the trigger is uncommenting it. `make docs` still builds
the site locally in strict mode; only the deployment step is affected.

*Original decision identified while implementing `documentation-site`; direction changed by
the maintainer once a `doction.dev` domain became the plan.*

---

## Project maturity

One phase of the open-source maturity plan remains.

**Community.** GitHub Sponsors, a public demo instance, and using Discussions. A demo needs
`DISABLE_REGISTRATION=1` and a seeded read-only account, since sign-up is open by default.
Most of this is account-level setup the maintainer has to do rather than work in the
repository.

*From the five-phase maturity review. The first four phases landed as `licensing`,
`release-integrity`, `vulnerability-triage` and `documentation-site`.*
