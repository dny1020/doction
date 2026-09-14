# OpenSpec in this repository

Two directories, holding two different things. Confusing them is the usual mistake.

```
openspec/
├── specs/                  what the software must do, as it stands today
│   └── <capability>/
│       └── spec.md         Purpose + Requirements + Scenarios
│
└── changes/
    ├── <active-change>/    work in flight
    └── archive/            every change that landed, with its reasoning
        └── YYYY-MM-DD-<name>/
            ├── proposal.md why, and what changes
            ├── design.md   how, and what was rejected
            ├── specs/      the delta this change applied
            └── tasks.md    the work, and notes on what diverged
```

## Reading a capability

`specs/<capability>/spec.md` is the current contract. It answers "what must be true", never
"how is it built" — if an implementation could change without changing the spec, it does not
belong there.

Each file opens with a `## Purpose` saying what the capability is for, then `## Requirements`.
A requirement is a normative statement with SHALL or MUST, followed by `#### Scenario:`
blocks in WHEN/THEN form. Every scenario is a potential test.

There are two kinds of capability here. Most describe the product: `search`,
`markdown-rendering`, `navigation`, `mcp-tools`. A few describe how the project is conducted:
`licensing`, `release-integrity`, `vulnerability-triage`, `contribution`. They live together
on purpose — the precedent is `self-hosting`, which has always held a promise verified
mechanically rather than merely intended.

`openspec validate --all --strict` runs inside `make check`, so a malformed or contradictory
spec fails the gate.

## Reading an archived change

This is where the reasoning lives, and it is the part no commit message carries.

- **`proposal.md`** — why the change was needed, stated as a concrete failure rather than an
  aspiration.
- **`design.md`** — the technical decisions, each with the alternatives that were rejected
  and why. When you wonder why something is not done the obvious way, look here first.
- **`tasks.md`** — the work, and at the end of each section a **Notes** block recording what
  actually happened. Read these. They hold the corrections: measurements that contradicted an
  assumption, a plan that was wrong, a task that turned out to need something nobody
  foresaw.

A few examples of what is only recorded there: why the text-search configuration chains
`unaccent` ahead of an English stemmer, why the cross-encoder reranker ships disabled despite
being implemented, why a version tag cannot be moved even forward, why the licence check runs
as a CI step rather than inside the Docker build.

## Proposing a change

The workflow is driven by the `openspec` CLI. In outline: scaffold the change, write the
proposal, then the spec delta, then the design, then the tasks — each artifact building on
the last. Implement against the task list, recording what diverged. Sync the delta into
`specs/` and archive the change when it is done.

```bash
openspec new change "<name>"          # scaffold; never create the directory by hand
openspec status --change "<name>"     # what to write next
openspec validate "<name>" --strict   # before asking anyone to read it
openspec list                         # what is in flight
```

Every change either declares at least one capability it adds or modifies, or explicitly opts
out of specs for work that changes no behaviour. Do not invent a requirement to satisfy the
validator.

## Why a spec rather than an issue

An issue records that something should happen. A spec records what must remain true
afterwards, in a form that a test can check and a future change has to respect. The
distinction matters most for the things that are easy to lose: this repository's specs are
why "the queue has no untriaged alert" and "a published version tag cannot move" are
enforceable statements rather than intentions someone had once.
