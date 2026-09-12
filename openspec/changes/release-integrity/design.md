## Context

See proposal.md — Why. The requirements are in `specs/release-integrity/spec.md`.

Three facts about the current setup shape everything below.

`publish` runs on push to `main`, takes the version from `pyproject.toml`, and pushes the
image. Tags are created by hand afterwards, so at publish time the tag does not exist yet
and at tag time the image already does. The two events are separate and stay separate.

`docker/build-push-action` already emits SLSA provenance at `mode=min`. The image carries
two attestation manifests today that nobody added on purpose. So this is a change to an
existing mechanism's detail level, not a new mechanism.

The model downloads are pinned by revision and verified by sha256. Availability is the only
thing that can go wrong with them.

## Goals / Non-Goals

**Goals**

- One parser for what a version changed, used by both the gate and the release.
- A stranger can enumerate an image's contents and trace its origin.
- A rate limit cannot decide whether a release ships.

**Non-Goals**

- Backfilling releases for the 30 tags with no per-version changelog entry.
- Requiring that tags be created by CI. Out of scope by decision; tagging by hand stays.
- Signing images or tags. A separate concern, and pinning the identifier is the prerequisite
  this change delivers.
- Triaging code-scanning alerts, and OpenSSF Scorecard.

## Decisions

### The changelog check runs against `pyproject.toml` in the gate, not against the tag

Checking at tag time is checking too late. By then the tag exists, the version is public,
and the only remedy is deleting a tag — which the same change is about to forbid.

So the gate asserts that the version currently declared in `pyproject.toml` has a section
in `CHANGELOG.md`. A version bump cannot be merged without its entry, which means a tag can
never name an undescribed version. The release workflow then re-reads the same section to
produce notes, and fails if it is missing, but by construction it never will be.

This mirrors the licence check from the previous change: `pyproject.toml` is the single
authored source for a project fact, and the gate compares everything else against it.

*Alternative considered:* generating the changelog entry from commit messages at tag time.
Rejected. The existing entries explain *why* a change was made, which a commit subject line
does not carry, and the ones written recently are the most useful thing in the repository
for someone deciding whether to upgrade.

### One script prints a version's notes; the gate runs it and throws the output away

`scripts/changelog.py <version>` prints that version's section to stdout and exits non-zero
when there is none. The gate calls it with the declared version and ignores stdout; the
release workflow calls it with the tag's version and captures stdout as the notes.

Two callers, one parser. A separate "does it exist" check would be a second implementation
of the same heading-matching rule, and the two would eventually disagree about a heading
format.

The parser must skip `## Unreleased`, which sits above the versions, and must stop at the
next `## ` heading. Range headings like `## 0.28.0 – 0.30.0` are deliberately *not* matched
as any single version: they describe history, and treating them as a match would let a new
release inherit notes about three old ones.

### The release is its own workflow, triggered on `push: tags: v*`

It cannot live in `publish`, which is triggered by a push to `main` when no tag exists.

The workflow needs `contents: write` to create a release, which is a permission the current
workflows do not hold. It is scoped to that one job and nothing else in the repository gains
it. The job does not build or push anything: the image for that version was already
published when the version merged, so a release job that rebuilt it could produce a
*different* image under the same name.

*Alternative considered:* creating the release from the tag automatically inside `publish`,
by having `publish` also push the tag. Rejected. That would make every push to `main` a
release, removing the deliberate human step between "this is merged" and "this is
released".

### `mode=max` and SBOM are flags, and the disclosure question is answered by inspection

`provenance: mode=max` and `sbom: true` on the publish build. Nothing else is required.

`mode=max` records build arguments, so the disclosure question is real. The Dockerfile's
eight `ARG`s are model repositories, revisions and checksums — all values already in the
repository. The registry credential reaches `docker/login-action`, not the build, so it is
not a build argument at all.

That reasoning is why it is *expected* to be safe. It is not why it will be *considered*
safe: the attestation of a real published image gets inspected for credential-shaped
content before this is called done. A reasoned argument about what buildkit records is
weaker than reading what it actually recorded.

### Retries use curl's transient-error set, not `--retry-all-errors`

`--retry 5 --retry-delay 5` on the existing `curl -fsSL`. Measured rather than assumed:
with `--retry 3 --retry-delay 2`, a 429 takes six seconds instead of returning immediately,
which is three retries happening. 429 is already in curl's transient set, so nothing more
is needed.

`--retry-all-errors` is deliberately omitted. It would also retry a 404, turning a wrong
URL or a renamed model revision into a slow failure instead of an immediate one. The
requirement says a genuinely wrong download must fail promptly, and this is how.

The multi-arch build fetches each model once per architecture, which doubles the requests
and makes the limit likelier. Retrying is the fix chosen here; caching the model in the
build is a larger change and not attempted.

### The tag ruleset forbids changing tags, not creating them

A ruleset targeting `refs/tags/v*` with deletion and non-fast-forward blocked. No creation
restriction and no required checks, because a tag is pushed after CI has already run on the
commit it points at.

The stray `rm` tag gets deleted as part of this work. It is not covered by a `v*` rule, and
leaving a mistyped tag in a repository that is about to promise its tags are stable would
undercut the promise on the first `git tag --list`.

## Risks / Trade-offs

**A release now depends on a changelog heading format** → The parser is the only thing that
knows the format, and the gate exercises it on every run against the real file, so a format
change fails immediately and locally rather than at tag time.

**`contents: write` is a real widening** → Scoped to the release job. It creates releases
and nothing else; it does not build, push, or touch the registry.

**`mode=max` attestations are larger and more revealing** → Larger is immaterial at this
scale. More revealing is the point, and the inspection step is what turns that from a hope
into a check.

**Retries hide a persistent upstream problem as slowness** → Five retries at five seconds
is a bounded 25 seconds. A model host that is down stays a build failure; what changes is
that a momentary limit no longer is one.

**Tag protection removes the escape hatch** → Deleting a bad tag becomes an admin action
rather than a `git push --delete`. That is the intended cost: the previous change already
established that a published identifier which can be repointed is worse than an ugly one
that cannot.

## Migration Plan

1. The changelog parser and the gate check. It must pass against 0.31.5, which is what
   proves the parser matches the real file.
2. Retries on the model downloads.
3. SBOM and `mode=max`, then inspect a published attestation.
4. The release workflow. First exercise is the next version tag.
5. The tag ruleset, and delete the `rm` tag. Order matters: deleting it after the ruleset
   exists is harder than before.

Rollback is `git revert` for everything in the tree. A published release can be deleted; a
published attestation cannot be removed from an image already pulled, which is another
reason step 3's inspection happens before anything depends on it.

## Open Questions

None.
