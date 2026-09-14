## Why

doction publishes a multi-arch image on every push to `main`, and someone who pulls it
cannot tell what changed, what is inside it, or whether the version they asked for is the
version they got.

**40 tags, zero releases.** The tags exist and the image is published, but nothing on the
repository says what a version contains. `CHANGELOG.md` has the content; it is simply not
attached to anything a person lands on when they look up `v0.31.5`.

**The version identifier is not trustworthy.** Nothing prevents a `v*` tag from being moved
or deleted, so `v0.31.4` today and `v0.31.4` next month need not be the same commit. The
tag list already carries the evidence: there is a tag literally named `rm`, pointing at an
ordinary commit, which is a mistyped `git tag` nobody noticed. A release automation that
acted on "every tag" would have published a release for it.

**Nobody can enumerate what is in the image.** The published image carries no SBOM, so a
downstream operator asking "does this contain the package in today's advisory" has to
unpack layers and guess. Trivy scans the image in CI, but that result is ours, not theirs.

**Provenance exists and nobody knew.** `docker/build-push-action` emits SLSA provenance by
default, so the image already proves which CI run built it. It is at `mode=min`, which
records the builder and the two base images but not the build steps or the source
materials. The gap is not "no provenance", it is "provenance that stops short".

**A release can fail for no reason and there is no recovery.** The 0.31.4 publish failed
with HTTP 429 from Hugging Face while downloading the embedding model. The download is
pinned by revision and verified by sha256, so this was purely availability: the bytes were
correct and unavailable for a moment. There is no retry, so a rate limit on a third-party
host is enough to stop a release, and the multi-arch build fetches the same model twice,
which makes hitting the limit likelier.

## What Changes

- Pushing a `vX.Y.Z` tag publishes a GitHub Release whose notes are the matching
  `CHANGELOG.md` section. Automation acts only on tags matching the version pattern, so a
  stray tag like `rm` is ignored by construction rather than by luck.
- **A version with no `CHANGELOG.md` entry fails the gate.** The check runs against the
  version in `pyproject.toml`, so a version bump cannot be merged without its entry, and
  the tag therefore cannot exist for a version nobody described.
- Releases start at 0.31.5 and are not backfilled. `CHANGELOG.md` was reconstructed at
  0.31.3 and deliberately groups history into ranges, so 30 of the 40 tags have no
  per-version entry. Writing 30 sets of notes from grouped entries would be inventing them.
- The published image carries an SBOM, and its provenance moves to `mode=max`.
- The model downloads retry on transient upstream failures.
- A ruleset prevents `v*` tags from being moved or deleted. It does **not** yet require that
  only CI create them: the last three releases were tagged by hand and that stays possible.

## Capabilities

### New Capabilities

- `release-integrity`: what a published release guarantees about itself — that its notes
  exist and come from one source, that its version identifier is stable, that its contents
  and origin can be enumerated by someone who did not build it, and that a transient
  upstream failure does not decide whether it ships.

### Modified Capabilities

None. `self-hosting` covers what a *running* deployment guarantees, which is a different
object: this change is about the published artifact and the process that produces it.

## Impact

| Area | Change |
| --- | --- |
| `.github/workflows/` | a release workflow on version tags; SBOM and provenance flags on the publish build |
| `Dockerfile` | retry flags on the four model downloads |
| `scripts/` | a check that the declared version has a changelog entry, and the notes extractor the release uses |
| `Makefile` | the changelog check joins the gate |
| `CONTRIBUTING.md`, `docs/operations.md` | the release procedure gains a step it no longer has to remember |

Outside the working tree: the tag ruleset, which a commit cannot create.

Out of scope, decided deliberately: triaging the 21 open code-scanning alerts, and OpenSSF
Scorecard. Scorecard publishes its findings into code scanning, so enabling it before that
queue is triaged would add noise to the signal this project is trying to recover. It waits
for its own change.
