<!--
Keep it short. One concern per pull request; a refactor bundled with a fix is two.
-->

## What this changes

<!-- One or two sentences. What behaviour is different after this merges? -->

## Why

<!-- The problem being solved. Link the issue if there is one: Closes #123 -->

## How to verify

<!-- The commands or clicks a reviewer runs to see it work. -->

```bash

```

## Checklist

- [ ] `make check` passes locally (ruff, ruff format, pyright, pytest, `npm run check`)
- [ ] `cd frontend && npm run test` passes, if this touches `frontend/src/`
- [ ] Tests cover the changed behaviour, happy path and the failure mode that matters
- [ ] Docs move with the code: README, `docs/`, or `DESIGN.md` updated if behaviour changed
- [ ] `npm run build` was run, if this touches `frontend/` or `app/static/style.css`
- [ ] No new runtime dependency, or the description says what it replaced and why
- [ ] Comments explain WHY, not WHAT; new comments are in English

## Notes for the reviewer

<!-- Anything you are unsure about, deliberately left out, or want pushed back on. -->
