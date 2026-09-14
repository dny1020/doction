## Purpose

Defines what a published doction release guarantees about itself: that its notes exist and
come from a single source, that its version identifier is stable once published, that its
contents and its origin can be enumerated by someone who did not build it, and that a
transient failure on a third-party host does not decide whether it ships.

## ADDED Requirements

### Requirement: A published version is described

Every version that is published SHALL have release notes, and those notes MUST come from
`CHANGELOG.md` rather than being written again somewhere else.

A version with no entry in `CHANGELOG.md` MUST fail the quality gate. The check MUST run
against the version declared in `pyproject.toml`, so the failure happens when the version
bump is proposed and not after a tag exists: a tag naming a version nobody described cannot
be created if the version could not be merged.

Notes SHALL be derived, never transcribed. Two hand-maintained copies of what changed
diverge, and the one people read is the one nobody updates.

#### Scenario: A version bump arrives without an entry

- **WHEN** the version in `pyproject.toml` changes and `CHANGELOG.md` has no section for it
- **THEN** the gate fails, naming the version it could not find

#### Scenario: A version tag is pushed

- **WHEN** a tag naming a described version is pushed
- **THEN** a release is published whose notes are that version's `CHANGELOG.md` section

#### Scenario: History is not invented

- **WHEN** versions were released before this requirement existed and their changelog
  entries describe ranges rather than single versions
- **THEN** they are left without releases, because notes that do not exist are not written
  retroactively

### Requirement: Release automation acts only on version tags

Automation that publishes releases SHALL act only on tags matching the project's version
pattern, and MUST ignore every other tag.

A repository accumulates tags that are not versions, including mistakes: this one carries a
tag named `rm` from a mistyped command. Automation that treats every tag as a release turns
such a mistake into a published artifact, so the filter is a correctness requirement and
not a convenience.

#### Scenario: A tag that is not a version

- **WHEN** a tag that does not match the version pattern is pushed
- **THEN** no release is published and the automation reports nothing to do

### Requirement: A published version identifier is stable

Once a version tag exists, it SHALL NOT be moved to another commit or deleted.

A version is a promise that a name refers to a specific commit. If the name can be
repointed, every other guarantee in this capability is void: notes, provenance and
contents would all describe something the name no longer resolves to.

This does not require that tags be created by automation. Creating them by hand stays
permitted; what is forbidden is changing one after the fact.

#### Scenario: Someone tries to move a published tag

- **WHEN** a force-push or a delete targets an existing version tag
- **THEN** the operation is refused

#### Scenario: Tagging by hand

- **WHEN** a maintainer creates a new version tag from their own machine
- **THEN** it is accepted, because the restriction is on changing tags and not on making
  them

### Requirement: A published image can be inspected by someone who did not build it

Every published image SHALL carry an SBOM enumerating its contents, and provenance
describing how it was produced.

Provenance MUST record the build steps and the resolved source materials, not only the
builder's identity, so the question "was this built from the commit it claims" is
answerable from the artifact. A scan the project runs in its own CI does not satisfy this:
that result belongs to the project, and the requirement is about what a stranger can
establish independently.

Attestations MUST NOT contain credentials or other secrets. This SHALL be verified against
a real published attestation rather than assumed from the fact that none were passed
deliberately.

#### Scenario: An operator asks whether an advisory affects them

- **WHEN** someone with the published image needs to know whether it contains a given
  package and version
- **THEN** they can answer it from the image's SBOM, without unpacking layers or asking the
  maintainer

#### Scenario: Verifying an image came from this project

- **WHEN** someone inspects a published image's provenance
- **THEN** it names the build, its steps and its resolved inputs

#### Scenario: Attestations are checked for disclosure

- **WHEN** provenance is made more detailed
- **THEN** a published attestation is inspected for credentials before the change is
  considered done

### Requirement: A transient upstream failure does not stop a release

A build step that fetches from a third-party host SHALL retry a transient failure before
failing the build.

The failure that motivates this was HTTP 429 from a model host: the content was pinned by
revision and verified by checksum, so correctness was never in question and only
availability was. A release stopped by a momentary rate limit is a release stopped for no
reason.

Retrying MUST be limited to transient conditions. A genuinely wrong URL or a checksum
mismatch MUST still fail promptly, because retrying those only delays a failure that is not
going to resolve itself.

#### Scenario: The model host rate-limits the build

- **WHEN** a model download receives a transient error such as HTTP 429
- **THEN** the download is retried and the build continues

#### Scenario: A download is genuinely wrong

- **WHEN** a fetch fails because the resource does not exist, or its checksum does not match
- **THEN** the build fails without exhausting retries first
