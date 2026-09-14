# Contributing to doction

Thanks for looking. doction is deliberately small: a markdown wiki that stores plain
files, answers over REST and MCP, and has no LLM inside it. The fastest way to get a
change merged is to keep it in that shape.

## Before you write code

**Behaviour is specified before it is written.** doction uses OpenSpec: a non-trivial change
starts as a proposal, grows a spec delta and a design, and only then a task list. A pull
request with code and no proposal is the wrong shape for this repository.
[`openspec/README.md`](openspec/README.md) explains the two directories and how to read them;
[`AGENTS.md`](AGENTS.md) is the short orientation.

Read the archive for the area you are touching before proposing. The notes at the end of an
archived `tasks.md` record what diverged from the plan and why, which is the part no commit
message carries.

- **Open an issue first for anything non-trivial.** A bug fix or a typo needs no
  ceremony. A new endpoint, a new dependency, or a new page in the UI does — it is
  cheaper to disagree about scope in an issue than in a diff. What is already identified and
  not yet done is in [`ROADMAP.md`](ROADMAP.md).
- **Read the design doc.** `DESIGN.md` describes the visual system as *implemented*: every
  token in it was read out of `app/static/style.css`. When the document and the code
  disagree, the document is the defect.
- **Dependencies are a liability.** A pull request that adds one has to say what it
  replaced and why the standard library or the existing stack could not do it. doction has
  no ORM, no MCP SDK, no NetworkX, and no CDN on purpose.

## Setting up

You need Docker (the test suite starts its own Postgres) and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --dev
cd frontend && npm install && cd ..

cp .env.example .env      # edit POSTGRES_PASSWORD and SECRET_KEY
make dev                  # backend on :8000
make frontend             # Vite dev server, proxies /api to :8000
```

Every command below also has a `make` target; read the `Makefile` for the full list.

## The check gate

A change is done when this passes. Nothing else counts as done.

```bash
make check
```

That target runs, in this order:

```bash
uv run ruff check .              # lint
uv run ruff format --check .     # formatting (drop --check to apply)
uv run pyright app tests         # types — pyright, not mypy
uv run pytest                    # backend tests
cd frontend && npm run check     # eslint + prettier + build + no-remote-asset check
make license                     # the licence agrees everywhere it is declared
make changelog                   # the declared version has a CHANGELOG entry
make docs-reachable              # no tracked document points at an untracked file
make docs                        # the documentation site builds with no broken link
openspec validate --all --strict # the spec suite in openspec/
```

`make docs` needs the documentation toolchain, which is not installed by default because the
Docker test stage would pick it up. Get it once with `uv sync --group docs`, and use
`make docs-serve` to preview the site locally.

The frontend unit tests are **not** in that target. Run them yourself when you touch
anything under `frontend/src/`:

```bash
cd frontend && npm run test      # vitest
```

Two things trip people up:

- **`uv run pytest` needs no setup beyond Docker.** With `TEST_DATABASE_URL` unset,
  `tests/conftest.py` starts a throwaway `doction-test-pg` container with its datadir in
  tmpfs. It is unrelated to your dev Postgres. Clean up with
  `docker rm -f doction-test-pg`.
- **Any change under `frontend/` needs a build before it shows up in the app** —
  `npm run build`, or `make build-web`. That includes `app/static/style.css`, which is
  linked with a content hash that only changes on build. Measuring a CSS change against a
  running dev server without rebuilding describes the *previous* stylesheet.

## What a good pull request looks like

- **One concern per PR.** A refactor bundled with a fix is two PRs.
- **Tests for the behaviour you changed**, covering the happy path and the failure you
  care about. Overmocking is worse than no test; the suite talks to a real Postgres for a
  reason.
- **No unrelated reformatting.** `ruff format` decides formatting; do not hand-tune.
- **Comments explain WHY, never WHAT.** A comment restating the line above it will be
  asked to go.
- **Docs move with the code.** If you change behaviour, update the README, `docs/`, or
  `DESIGN.md` in the same PR. A README that describes last month's behaviour is a bug.
- **English in the repo.** Code, comments, docstrings, commit messages, and docs are in
  English regardless of the language the discussion happens in. Some existing comments are
  in Spanish; new ones should not be.

## Commit messages

Conventional-commit prefixes, imperative mood, lowercase subject:

```
fix(search): fold accents before stemming so `renovacion` matches `Renovación`
feat(mcp): add list_children for the v2 page tree
docs(readme): regenerate screenshots against the React SPA
chore(deps): bump onnxruntime to 1.20
```

Prefixes in use: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`.

## Releasing

Maintainer task, recorded here so the process is not folklore.

1. Bump the version in **`pyproject.toml` only**. `app/version.py` reads it at import, so
   `/health`, the MCP `initialize` response, and the image tag all follow.
2. Add the entry to `CHANGELOG.md`, under a `## X.Y.Z` heading. **This is not optional and
   not a courtesy**: `make check` fails when the declared version has no section, because
   release notes are taken from that file rather than written again somewhere else. The
   check runs here rather than at tag time, where it would be too late — the tag would
   already exist, and a published tag cannot be deleted.
3. Merge to `main`. CI runs the gate inside `docker build --target test`, then publishes
   `ghcr.io/dny1020/doction:{version}` and `:latest` for amd64 and arm64, each carrying an
   SBOM and SLSA provenance.
4. Tag the commit `vX.Y.Z` and push the tag. Pushing it publishes the GitHub Release
   automatically, with that version's changelog section as the body. Nothing else to do.

**A published version tag cannot be moved or deleted.** The "Protect version tags" ruleset
refuses deletion and *any* update to a `v*` tag, forward moves included — a tag is not a
branch, so there is no such thing as a legitimate fast-forward for a version. A version is a
promise that a name refers to one commit, and everything else, the notes and the provenance
and the image contents, describes whatever that name resolves to.

If a release turns out wrong, **publish the next version**. Do not repoint the tag. The
ruleset has no bypass actor, so repairing a tag means deliberately disabling it first, which
is the friction it is meant to have.

Only tags matching `vX.Y.Z` trigger a release, so an experimental or mistyped tag is ignored
rather than published.

Deploying is manual and separate — see `docs/operations.md`.

### When a change defers something

Write it into [`ROADMAP.md`](ROADMAP.md), not only into the change's `tasks.md` notes. An
item that exists solely in an archived change is an item nobody will find: the notes explain
what happened, the roadmap says what is still pending. Say where the item was identified, so
the next reader can follow the reasoning rather than rebuild it.

## Code scanning alerts

CodeQL and Trivy report into the repository's Security tab. **An alert has two possible
outcomes: fixed, or dismissed with a reason that says what makes it not apply.** Leaving one
open and unexamined is not one of them, and neither is dismissing one with the words "false
positive" and nothing else.

The reason is the point. Whoever dismisses an alert will not remember the argument in six
months, and the next person needs enough to disagree with. Write what specifically makes it
inapplicable — the sanitiser the analyser did not see, the validation that happens earlier,
the reason a value cannot hold the character the rule is worried about.

If you cannot state a specific reason, the alert is not a false positive. Say so and leave it
open rather than dismissing it.

This is not bureaucracy. This queue once sat unread for weeks with a genuine quadratic
denial-of-service in it, hidden among twenty findings that were not real. The cost of an
unread queue is not untidiness; it is that a real finding becomes indistinguishable from
noise.

## Reporting bugs and asking for features

Use the issue templates. A bug report without the version from `/health` and a
reproduction usually cannot be acted on.

Security problems do **not** go in issues — see [SECURITY.md](SECURITY.md).

## Code of conduct

Participating means agreeing to the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

Contributions are accepted under the
[GNU Affero General Public License v3.0 only](LICENSE), the same terms as the rest of the
project.

### Sign your commits

**Every commit in a pull request must carry a `Signed-off-by` trailer.** Add it with `-s`:

```bash
git commit -s -m "fix(search): ..."
git commit --amend -s --no-edit     # fixing the last one
git rebase --signoff main           # fixing a whole branch
```

The trailer is a [Developer Certificate of Origin](https://developercertificate.org/): it
certifies that you wrote the change or have the right to submit it, and that you offer it
under this project's licence. A note in a contributing guide saying that opening a pull
request implies agreement asserts your consent without evidencing it; a trailer on the
commit is a record that survives whatever this document happened to say at the time. CI
checks it and the failure message tells you the exact command.

**Sign-off transfers no copyright, and that has a consequence worth knowing.** You keep
ownership of what you write, which means **doction cannot be relicensed without the
permission of everyone who has contributed**. That follows from choosing AGPL-3.0-only over
a dual licence, and it is deliberate rather than an oversight.

The project was MIT through 0.31.3, GPL-3.0-only at 0.31.4, and is AGPL-3.0-only from
0.31.5.

If you add a dependency, establish its licence is compatible **before** the change lands —
a dependency cannot be removed from a release that has already shipped. Permissive licences
(MIT, BSD, ISC, Apache-2.0) and LGPL are compatible; GPL-2.0-only is not. Say which licence
it carries in the pull request description, not just which package it is.
