## 1. The licence itself

- [x] 1.1 Replace `LICENSE` with the verbatim FSF text of the GNU Affero General Public
      License version 3. Verify by comparing the sha256 of the written file against the
      canonical AGPL-3.0 text, not by reading it.
- [x] 1.2 Set `license = "AGPL-3.0-only"` in `pyproject.toml` (keeping `license-files`) and
      `"license": "AGPL-3.0-only"` in `frontend/package.json`. Verify `uv lock --check`
      passes and `prettier --check` accepts the JSON.
- [x] 1.3 Update the README badge and licence section, and `CONTRIBUTING.md`, to AGPL-3.0-only.
      The licence section must state the three operator cases from the spec requirement
      "An operator knows what running doction obliges". Verify by reading the rendered
      section and confirming all three cases appear.
- [x] 1.4 Add the 0.31.5 entry to `CHANGELOG.md` naming AGPL-3.0-only as effective from that
      version and stating that the MIT grant through 0.31.3 and the GPL-3.0 grant at 0.31.4
      are not withdrawn. Verify the entry names both previous licences.
- [x] 1.5 Bump the version in `pyproject.toml` only, and run `uv lock`. Verify
      `python -c "from app.version import VERSION; print(VERSION)"` reports the new version
      and that `app/mcp.py` `SERVER_INFO` follows.

### Notes on section 1

<!-- Record what actually happened here, including anything that diverged from the plan. -->

## 2. The consistency check

- [x] 2.1 Write `scripts/check_license.py` reading the licence from `pyproject.toml` as the
      single authored source and asserting `LICENSE`, `frontend/package.json`, the README
      badge, the README licence section and `CONTRIBUTING.md` all agree. Verify it exits
      non-zero when any one of them is edited to disagree.
- [x] 2.2 Extend it to read the published repository description and report a mismatch,
      degrading to a loud skip when the API is unreachable or unauthenticated. Verify both
      paths: a mismatch fails, and no network produces a skip that is visible in the output
      rather than silent.
- [x] 2.3 Wire it into `make check` and into the Dockerfile `test` stage so CI runs it.
      Verify `make check` fails on a deliberately broken declaration and passes once
      restored.
- [x] 2.4 Add a test asserting the check catches a disagreeing declaration, so the check
      itself is covered rather than trusted. Verify `uv run pytest` includes it.

### Notes on section 2

- **The check runs in CI as a step, not inside the Dockerfile.** 2.3 said to put it in the
  `test` stage. That stage copies only `app`, `tests` and `scripts`, so the check's other
  four files would have had to be copied in too, and then a README typo would invalidate the
  layer and re-run 293 tests against an embedded Postgres to verify a string comparison. It
  runs before the docker build instead, on the runner's Python, since it only uses stdlib.
  `make license` keeps the local gate and CI on the same command. design.md records the
  reasoning.
- **The remote half compares loosely on purpose.** The description check does not demand an
  exact phrasing; it fails when the description names a *different* licence family. Requiring
  an exact string would have forced the description into a template, and the actual bug was a
  stale name, not a missing one.
- **The API response is cached.** After updating the description via the API, the public
  unauthenticated endpoint served the old value for a short while. Nothing was done about it:
  the check is not a gate on the description being freshly written, and a stale read resolves
  itself. Worth knowing if it ever reports a mismatch that looks wrong.

## 3. The source offer

- [x] 3.1 Add `SOURCE_URL` to the environment set, defaulting to this project's repository,
      and report it with the licence identifier from `GET /api/system`. Verify
      `curl -s $DOCTION/api/system | jq '{license, source_url}'` returns both, and that
      setting the variable changes the reported value.
- [x] 3.2 Surface licence and source in the Settings System section, as a reachable link.
      Verify by loading Settings in a browser against a running instance and following the
      link.
- [x] 3.3 Document `SOURCE_URL` in `README.md`, `.env.example`, `compose.yaml` and
      `docs/configuration.md`, including that an operator running a modified instance is
      expected to point it at their own source. Verify the compose file forwards it, since a
      variable documented but not forwarded does nothing.
- [x] 3.4 Add a test that `GET /api/system` reports the configured source URL and the
      licence. Verify `uv run pytest` includes it.

### Notes on section 3

- **`LICENSE_ID` went into `app/version.py`, not `main.py`.** That module already reads
  `pyproject.toml` and exists precisely so a project fact lives in one place, so the licence
  reads from the same file the consistency check treats as authoritative. `_read_version()`
  became `_read(key, fallback)` to serve both.
- **3.2 was not verified in a browser.** The Chrome extension disconnected partway through,
  so the visual check could not be run. Everything else was: the built bundle contains the
  block, both i18n catalogs serve the four new labels over `/api/i18n`, and `/api/system`
  reports the licence and the configured source. The render itself is unverified and worth a
  glance next time Settings is open.
- **The licence rows render conditionally on `report.license`.** An older bundle against a
  newer server, or the reverse, simply omits the block instead of rendering empty rows.

## 4. Close out

- [x] 4.1 Run the whole gate: `make check` plus `cd frontend && npm run test`. Verify ruff,
      ruff format, pyright, pytest, the frontend gate, the licence check and
      `openspec validate --all --strict` all pass.
- [x] 4.2 Update the GitHub repository description, which still says "MIT licensed", and
      confirm the consistency check from 2.2 now reports agreement. This is a manual step
      because a commit cannot reach platform metadata.
- [ ] 4.3 Tag the release and confirm the published image reports the new version via the
      MCP `initialize` response.

### Notes on section 4

- **4.2 was not manual.** The task assumed platform metadata needs a human because a commit
  cannot reach it, but `gh api -X PATCH` can, so it was done here and the check now reports
  agreement. It was done out of order, during section 2, because the check could not be
  verified green until the description was fixed.
