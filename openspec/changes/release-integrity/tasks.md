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

- [x] 3.1 Add `sbom: true` and `provenance: mode=max` to the publish build. Verify by
      pushing and then reading the published image: `docker buildx imagetools inspect
      --format '{{json .SBOM}}'` must be non-empty, and provenance must carry build steps
      and resolved dependencies rather than only the builder.
- [x] 3.2 **Inspect a real published attestation for credential-shaped content** before
      calling this done. Verify no token, password or registry credential appears in either
      attestation. A reasoned argument that none were passed is not the verification.
- [x] 3.3 Document in `docs/operations.md` how an operator reads the SBOM and the provenance
      of an image they pulled, since the point of both is that someone who did not build it
      can use them. Verify the documented commands by running them against a published tag.

### Notes on section 3

- **Provenance was already on.** `build-push-action` emits it by default at `mode=min`, so
  the two `unknown/unknown` manifests on the image predate this change. The work was raising
  the detail level, not adding the mechanism. `mode=max` took `resolvedDependencies` from 2
  to 3 and, more usefully, recorded the `RUN` commands — the retry flags added in section 2
  are visible in the published attestation.
- **SBOM: 1312 packages on amd64, 1314 on arm64, SPDX-2.3.**
- **3.2 found nothing, and was worth running anyway.** Both attestations were scanned for
  credential *shapes* rather than the word "token": GitHub token prefixes, PEM private keys,
  JWTs, basic-auth headers, credentials embedded in URLs, and docker config `auths` blocks.
  Zero matches across 219 KB of provenance and 18 MB of SBOM. The only occurrences of
  "token" are `tokenizer.json` and the `tokenizers` package.

## 4. The release workflow

- [x] 4.1 Add a workflow triggered on `push: tags: v*` that extracts notes with
      `scripts/changelog.py` and publishes a GitHub Release for that version. It holds
      `contents: write` and nothing else, and it must not build or push an image. Verify the
      job definition grants no other permission.
- [x] 4.2 Verify it ignores a tag that is not a version: the trigger pattern must not match
      a tag such as `rm`. Confirm by inspecting the pattern and, if cheap, by pushing and
      deleting a throwaway non-version tag before the ruleset in section 5 exists.
- [x] 4.3 Publish the release for the existing `v0.31.5` tag, since 0.31.5 is where releases
      start and its tag already exists. Verify the release appears with the 0.31.5 changelog
      section as its body.
- [x] 4.4 Record the release step in `CONTRIBUTING.md` and `docs/operations.md`, replacing
      "tag the commit" with what now happens automatically. Verify the documented procedure
      matches the workflow's trigger.

### Notes on section 4

- **`gh release create` instead of a third-party action.** One less SHA to pin, and the CLI
  is already on the runner.
- **4.3 was done by hand, deliberately.** The v0.31.5 tag already existed, so the workflow
  could not fire for it without deleting and re-pushing the tag — which this same change
  forbids. The release was created with the same notes the workflow would have used, from
  the same parser.
- **The workflow's first real run was v0.31.6, and it worked unattended.** Pushing the tag
  triggered it, the notes came out of the changelog, and the release appeared without
  anything else being done. That same push also confirmed tag *creation* is still permitted
  under the ruleset, which is why no throwaway tag was needed.

## 5. The version identifier becomes stable

- [x] 5.1 Delete the stray `rm` tag, locally and on the remote. Do this **before** the
      ruleset exists. Verify `git ls-remote --tags` no longer lists it.
- [x] 5.2 Create a ruleset targeting `refs/tags/v*` that blocks deletion and
      non-fast-forward, with no creation restriction. Verify by attempting to delete and to
      move a published version tag: both must be refused, and creating a new one must still
      work.
- [x] 5.3 Record in `CONTRIBUTING.md` that a published version tag cannot be moved or
      deleted, and what to do instead when a release is wrong: publish the next version.
      Verify the text names the ruleset so someone hitting the refusal knows why.

### Notes on section 5

- **`non_fast_forward` does not stop a version tag from moving, and the test proved it by
  breaking the tag.** The plan said "blocks deletion and non-fast-forward", which is what was
  built first. Deleting was refused; moving `v0.31.5` from `453942e` to a later commit was
  *accepted*, because a later commit on the same history is a fast-forward and that rule only
  blocks the other kind. A tag is not a branch: for a version, every move is wrong, forward
  included. The ruleset now also carries `update`, which blocks any change to the ref, and all
  three cases are refused.
- **The tag was restored exactly, not reconstructed.** The force-push replaced an annotated
  tag with a lightweight one, but the original tag object `015ec7a` was still in the local
  object store with its tagger, date and message, so `git update-ref` put it back byte for
  byte. Repairing required setting the ruleset to `disabled` for the duration, since it has
  no bypass actor — which is the intended posture: an admin escape hatch would have made the
  earlier delete test pass for the wrong reason.
- **Creation is not tested with a throwaway tag.** With `deletion` in force, a test tag could
  not be cleaned up afterwards. It is exercised by the next real release tag instead, which
  also gives the release workflow its first end-to-end run.

## 6. Close out

- [x] 6.1 Run the whole gate: `make check` plus `cd frontend && npm run test`. Verify ruff,
      ruff format, pyright, pytest, the frontend gate, the licence check, the changelog check
      and `openspec validate --all --strict` all pass.
- [x] 6.2 Confirm the end state against the capability: the 0.31.5 release exists with notes
      from the changelog, its image reports a non-empty SBOM and `mode=max` provenance, the
      `v*` tags refuse to move, and `rm` is gone.

### Notes on section 6

End state, verified against the published artefacts rather than the code that produces them:

| Claim | Evidence |
| --- | --- |
| Releases exist with notes from the changelog | 0.31.5 and 0.31.6, bodies match their sections |
| The image can be enumerated | SBOM 1312 packages on amd64, 1314 on arm64, SPDX-2.3 |
| Its origin can be traced | provenance at `mode=max`, records the `RUN` commands |
| No secrets leaked | zero credential shapes across 219 KB + 18 MB of attestations |
| Version tags are stable | move and delete both refused on 0.31.5 and 0.31.6 |
| Creating a tag still works | v0.31.6 pushed and accepted |
| The stray tag is gone | `rm` absent from the remote |

One thing this change did not fix and is worth knowing: the network dropped mid-run, and the
licence check degraded to a visible SKIP and passed, as designed. `uv lock` could not run at
all, which is expected — it needs an index. The gate's offline behaviour is therefore
partially confirmed by accident.
