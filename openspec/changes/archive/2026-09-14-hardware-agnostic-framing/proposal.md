## Why

Three active specs (`client-resilience`, `visual-language`, `retrieval-ranking`) justify
a requirement by naming "Raspberry Pi" specifically, as if that device were doction's
intended identity. doction is self-hosted and hardware-agnostic — the Pi is one real
deployment, not the product's purpose. The rationale prose should name the actual
constraint each requirement protects (modest resident memory, no public route, running
behind a VPN) instead of a specific device, so the requirement reads the same regardless
of what hardware a given deployment runs on.

## What Changes

- Reword the rationale sentence in three places to describe the underlying constraint
  (self-hosted on modest hardware, often with no public route / behind a VPN) instead of
  naming a specific device:
  - `openspec/specs/client-resilience/spec.md` — `## Purpose`
  - `openspec/specs/visual-language/spec.md` — rationale under "The visual language costs
    nothing at runtime"
  - `openspec/specs/retrieval-ranking/spec.md` — rationale under "doction retrieves and
    never generates"
- No requirement's SHALL/MUST text changes, no scenario changes, no behavior changes.
  This is a wording-only pass over rationale prose that sits outside the normative
  statements.

## Capabilities

This change touches no requirement's behavior — only the rationale prose that explains an
already-existing requirement. `skip_specs: true` is set in `.openspec.yaml` accordingly;
no delta spec is included, and the wording is applied directly to the three files listed
above as this change's task.

### New Capabilities

(none)

### Modified Capabilities

(none — no requirement text changes; see Why)

## Impact

- Docs-only: three files under `openspec/specs/`. No code, no tests, no CI, no runtime
  behavior. `openspec validate --all --strict` (part of `make check`) must still pass
  after the edit.
