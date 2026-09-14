# Working on doction

Orientation for anyone changing this repository, human or agent. It is deliberately short
and mostly signposts: each subject below is owned by a document that already explains it,
and repeating that explanation here would put one truth in two places. That failure has
already cost this project three corrections — a licence declared in seven places with one
left behind, a published description contradicting the licence, release notes that would
have been written twice — so this file points rather than restates.

## The one thing nothing else tells you

**Behaviour is specified before it is written.** doction uses [OpenSpec](openspec/README.md):
a change starts as a proposal, grows a spec delta and a design, and only then a task list
that gets implemented. Opening a pull request with code and no proposal is the wrong shape
for this repository, and it is the mistake this file exists to prevent.

Two directories carry that:

| Where | What it holds |
| --- | --- |
| `openspec/specs/` | the behaviour contracts as they stand today, one per capability |
| `openspec/changes/archive/` | every past change, with the reasoning and what actually happened |

Before proposing something, **read the archive for the area you are touching**. The notes in
an archived `tasks.md` record what diverged from the plan and why, which is the part no
commit message carries. Several decisions that look arbitrary in the code are explained
there and nowhere else — why the text-search stemmer is English, why the reranker ships
disabled, why a wikilink target excludes `[`.

`openspec/README.md` explains how to read both directories.

## Everything else is already written down

| Subject | Read |
| --- | --- |
| What doction is, and its REST and MCP surfaces | [`README.md`](README.md) |
| Setup, the quality gate, commit style, releasing | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| What is identified and not yet done | [`ROADMAP.md`](ROADMAP.md) |
| The visual system, as implemented | [`DESIGN.md`](DESIGN.md) |
| Installing, configuring and operating a deployment | [`docs/`](docs/README.md) |
| The security model and how to report a problem | [`SECURITY.md`](SECURITY.md) |
| What changed in each release | [`CHANGELOG.md`](CHANGELOG.md) |

A change is done when `make check` passes. `CONTRIBUTING.md` says what that runs and in what
order; do not take a shorter path and report the work as finished.

## Two habits that matter more than they look

**Measure rather than assert.** Where this project makes a claim about performance or
quality, the claim came from a measurement and the measurement is recorded. The retrieval
constants cite runs in `evals/results/`. The wikilink pattern cites a before-and-after. If
you change something whose value was established by measurement, re-measure; do not reason
about it.

**Record what diverged.** When implementation departs from the plan — and it usually does —
write why in the change's `tasks.md` notes. That record is the most useful thing in this
repository for whoever comes next, including you in six months.
