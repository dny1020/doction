## Why

doction is a web application people run for other people. The licence it ships under does
not account for that.

0.31.4 relicensed the project from MIT to GPL-3.0-only. The GPL obliges whoever
*distributes* a copy to pass on the source; it says nothing about whoever *operates* the
software for third parties. For a library or a CLI those are close to the same act. For a
self-hosted wiki reached over HTTP they are not: the operator never hands anyone a copy, so
nothing is triggered. The README states the consequence plainly today, as a feature of the
licence rather than a gap: *"hosting it for other people is not distribution, so a private
instance stays private."*

That sentence describes exactly the case the AGPL exists for. Its section 13 requires an
operator who modifies the program and lets users interact with it over a network to offer
those users the corresponding source. Without it, doction can be forked, modified and sold
as a hosted service with no obligation to publish anything, which is the one outcome
copyleft was chosen to prevent.

The second reason is that the licence is declared in more places than anyone remembers.
`LICENSE`, `pyproject.toml`, `frontend/package.json`, the README badge, the README licence
section, `CONTRIBUTING.md`, and the GitHub repository description are seven independent
copies of one fact. The repository description still read *"MIT licensed"* two releases
after MIT was replaced, and nothing detected it, because nothing checks. A licence that is
inconsistently declared is worse than one that is merely permissive: it is unclear which
terms actually apply.

## What Changes

- **BREAKING** The licence becomes `AGPL-3.0-only`. `LICENSE` carries the verbatim GNU
  Affero General Public License version 3.
- Every declaration of the licence is brought to the same value, and the set of places that
  must agree is written down rather than remembered.
- The compatibility criterion a new dependency has to meet is stated, because AGPL-3.0
  narrows it: a dependency whose licence forbids the network-source obligation cannot be
  added. Notably this keeps Apache-2.0 acceptable and continues to exclude GPL-2.0-only.
- The obligations an operator actually takes on are documented, because the practical
  question a self-hoster asks is not which licence it is but whether running it commits
  them to anything. For an unmodified instance it does not.
- Releases up to and including 0.31.4 stay under their published terms. Relicensing is not
  retroactive and the proposal does not pretend it is.

## Capabilities

### New Capabilities

- `licensing`: what licence doction is under, where that fact is declared, which
  declarations must agree, what an operator is obliged to do, and what licence a new
  dependency may carry.

### Modified Capabilities

None. No existing capability describes the licence, the repository's published metadata, or
the dependency-admission criterion.

## Impact

Files that declare the licence and must end up consistent:

| File | What it declares |
| --- | --- |
| `LICENSE` | the licence text itself |
| `pyproject.toml` | `license` and `license-files` |
| `frontend/package.json` | `license` |
| `README.md` | the badge and the licence section |
| `CONTRIBUTING.md` | the terms a contribution is accepted under |
| `CHANGELOG.md` | the entry recording the change |

Outside the working tree, the GitHub repository description also states the licence and is
currently wrong. It cannot be changed by a commit, so it is a task, not a file edit.

No application code, API, endpoint or dependency version changes. The image, the database
schema and every runtime surface are untouched: this is a change to the terms doction is
offered under and to the places that record them.

One consequence worth stating because it is easy to miss: AGPL-3.0 and GPL-2.0-only remain
incompatible, so the dependency criterion does not loosen. What does change is that a
downstream operator modifying doction now owes source to its users, which is the entire
point.
