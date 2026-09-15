## 1. Reword rationale prose

- [x] 1.1 `openspec/specs/client-resilience/spec.md` — reword the `## Purpose` sentence
      naming "Raspberry Pi" to describe the constraint (self-hosted, often with no
      public route / behind a VPN) without naming a device, and verify
      `openspec validate client-resilience --strict` still passes
- [x] 1.2 `openspec/specs/visual-language/spec.md` — reword the rationale under "The
      visual language costs nothing at runtime" the same way, and verify
      `openspec validate visual-language --strict` still passes
- [x] 1.3 `openspec/specs/retrieval-ranking/spec.md` — reword the rationale under
      "doction retrieves and never generates" the same way, and verify
      `openspec validate retrieval-ranking --strict` still passes

## 2. Verify no behavior drift

- [x] 2.1 Diff each edited file and confirm no `SHALL`/`MUST` line or `#### Scenario:`
      block changed — only rationale prose
- [x] 2.2 Run `openspec validate --all --strict` and confirm the full spec set still
      passes

**Notes**: all three edits landed inside prose (a `## Purpose` paragraph and two
requirement-rationale sentences), never inside a `SHALL`/`MUST` line or `#### Scenario:`
block — confirmed by diff before running the final validate. Rewrapped affected lines to
match each file's existing ~96-100 char prose width; no other content touched.
