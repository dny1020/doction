## 1. One parser, and the gate that uses it

- [x] 1.1 Write `scripts/changelog.py <version>` printing that version's `CHANGELOG.md`
      section to stdout, exiting non-zero when there is none. It must skip `## Unreleased`,
      stop at the next `## ` heading, and **not** match a range heading such as
      `## 0.28.0 – 0.30.0` as any single version. Verify it prints the 0.31.5 section, fails
      for a version that does not exist, and fails for `0.29.0`, which only appears inside a
      range.
- [x] 1.2 Add a gate check asserting the version declared in `pyproject.toml` has a section.
      Verify it passes today, and fails when the declared version is temporarily changed to
      one with no entry.
- [x] 1.3 Wire it into `make check` and as a CI step next to the licence check, for the same
      reason: it reads repository files, not the built image. Verify `make check` fails on a
      version with no entry and passes once restored.
- [x] 1.4 Add tests for the parser covering the three cases in 1.1 plus the range-heading
      rejection. Verify `uv run pytest` includes them.

### Notes on section 1

- **The gate uses `--check`, not a separate flag for the declared version.** The first cut
  had `--declared` printing the section, which meant the Makefile had to extract the version
  itself to print a confirmation, and the shell quoting for that broke. `--check` now reads
  the declared version and prints its own one-line confirmation, so the caller needs to know
  nothing. The bare form still prints the section for the release workflow.
- **Two tests read the real CHANGELOG.md and are skipped in the Docker `test` stage — and CI
  found that, again.** The module docstring originally asserted the opposite, that the file
  is "present wherever pytest runs". It is not: that stage copies only app/, tests/, scripts/
  and pyproject.toml, exactly as with the licence tests one change earlier. Only the two
  file-reading cases skip; the four parametrised ones build their own changelog in a
  temporary tree and keep running in CI, so the parser's rules stay covered where it
  matters. Verified in the stripped stage *before* pushing this time.

## 2. Retries on the model downloads

- [x] 2.1 Add `--retry 5 --retry-delay 5` to the four `curl -fsSL` model fetches in the
      Dockerfile, without `--retry-all-errors` so a 404 still fails promptly. Verify
      `docker build --target runtime` still succeeds and the images still pass their
      sha256 checks.
- [x] 2.2 Verify the retry actually engages on a 429 rather than trusting the flag: time a
      `curl -fsSL --retry` against a host returning 429 and confirm the elapsed time shows
      the retries, and that the final exit status is still a failure.

### Notes on section 2

<!-- Record what actually happened here, including anything that diverged from the plan. -->

## 3. SBOM and fuller provenance

- [ ] 3.1 Add `sbom: true` and `provenance: mode=max` to the publish build. Verify by
      pushing and then reading the published image: `docker buildx imagetools inspect
      --format '{{json .SBOM}}'` must be non-empty, and provenance must carry build steps
      and resolved dependencies rather than only the builder.
- [ ] 3.2 **Inspect a real published attestation for credential-shaped content** before
      calling this done. Verify no token, password or registry credential appears in either
      attestation. A reasoned argument that none were passed is not the verification.
- [x] 3.3 Document in `docs/operations.md` how an operator reads the SBOM and the provenance
      of an image they pulled, since the point of both is that someone who did not build it
      can use them. Verify the documented commands by running them against a published tag.

### Notes on section 3

<!-- Record what actually happened here, including anything that diverged from the plan. -->

## 4. The release workflow

- [x] 4.1 Add a workflow triggered on `push: tags: v*` that extracts notes with
      `scripts/changelog.py` and publishes a GitHub Release for that version. It holds
      `contents: write` and nothing else, and it must not build or push an image. Verify the
      job definition grants no other permission.
- [x] 4.2 Verify it ignores a tag that is not a version: the trigger pattern must not match
      a tag such as `rm`. Confirm by inspecting the pattern and, if cheap, by pushing and
      deleting a throwaway non-version tag before the ruleset in section 5 exists.
- [ ] 4.3 Publish the release for the existing `v0.31.5` tag, since 0.31.5 is where releases
      start and its tag already exists. Verify the release appears with the 0.31.5 changelog
      section as its body.
- [x] 4.4 Record the release step in `CONTRIBUTING.md` and `docs/operations.md`, replacing
      "tag the commit" with what now happens automatically. Verify the documented procedure
      matches the workflow's trigger.

### Notes on section 4

<!-- Record what actually happened here, including anything that diverged from the plan. -->

## 5. The version identifier becomes stable

- [x] 5.1 Delete the stray `rm` tag, locally and on the remote. Do this **before** the
      ruleset exists. Verify `git ls-remote --tags` no longer lists it.
- [ ] 5.2 Create a ruleset targeting `refs/tags/v*` that blocks deletion and
      non-fast-forward, with no creation restriction. Verify by attempting to delete and to
      move a published version tag: both must be refused, and creating a new one must still
      work.
- [ ] 5.3 Record in `CONTRIBUTING.md` that a published version tag cannot be moved or
      deleted, and what to do instead when a release is wrong: publish the next version.
      Verify the text names the ruleset so someone hitting the refusal knows why.

### Notes on section 5

<!-- Record what actually happened here, including anything that diverged from the plan. -->

## 6. Close out

- [ ] 6.1 Run the whole gate: `make check` plus `cd frontend && npm run test`. Verify ruff,
      ruff format, pyright, pytest, the frontend gate, the licence check, the changelog check
      and `openspec validate --all --strict` all pass.
- [ ] 6.2 Confirm the end state against the capability: the 0.31.5 release exists with notes
      from the changelog, its image reports a non-empty SBOM and `mode=max` provenance, the
      `v*` tags refuse to move, and `rm` is gone.

### Notes on section 6

<!-- Record what actually happened here, including anything that diverged from the plan. -->
