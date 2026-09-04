## 1. Diagnosis: what the prefix costs

- [ ] 1.1 Move the throwaway diagnostic into `evals/` as a runnable comparison, so its numbers can
      be reproduced rather than quoted from a commit message. It compares packing variants over the
      queries that declare an expected heading and reports sibling similarity beside section recall.
- [ ] 1.2 Make the packing selectable at index time so the harness can run a variant end to end
      without editing source between runs. It is an experiment knob, not a deployment setting: it
      does not go in the system report and it has one committed default.
- [x] 1.3 Run all three variants through the **full** harness, not only the intra-page comparison.
      The isolated measurement says B reaches 0.75; what it cannot say is what B does to page
      ranking, which is the number that decides whether it ships.
- [ ] 1.4 Measure the cross-page collision property directly: two identically worded sections in
      two different pages, and whether a query matching one ranks the other equally. This is what
      002 added the page title to protect, and dropping the title from the embedding puts it at
      risk. Add it as a test, not only as an eval case.
- [ ] 1.5 Record all three runs in `evals/results/`, each labelled with its packing variant, so the
      comparison survives this change.

## 2. Granularity and tie-breaking

- [x] 2.1 Quantify what is left after the best packing wins: which queries still retrieve the wrong
      section, and whether the failure is a heading whose words overlap the query while its body
      does not. Both known cases — `where are the secrets stored` and `how do I update a docker
      image` — look like that; confirm before building for it.
- [x] 2.2 Evaluate a tiebreak: when a query's terms appear in a section's own heading, that section
      wins ties within its page. Applied inside one page only, so it changes which section is
      returned and not which page ranks first.
- [x] 2.3 Verify the tiebreak breaks ties and does not reorder pages: `retrieval-ranking` requires
      fusion by rank and forbids mixing score scales, and a tiebreak must do neither.
- [ ] 2.4 Ship the tiebreak only if it earns its place. Measure it separately from the packing
      change so the two contributions are attributable, exactly as 002 separated the chunker from
      the fusion.
- [ ] 2.5 Verify sibling sections are meaningfully apart under the shipped configuration: report
      the average and maximum cosine between sections of one page, against today's 0.685 and 0.943.

## 3. Benchmark and gate

- [ ] 3.1 Extend the section-level query set beyond eight. A 0.65 target over eight queries moves
      in steps of 0.125, so a single query decides whether this change passes. Add cases across the
      existing query classes, with their expected headings verified against the corpus.
- [ ] 3.2 Run the final configuration against `evals/results/2026-09-04-003-final.json` and commit
      the result labelled with its variant.
- [x] 3.3 **Gate:** section recall at or above 0.65, up from 0.38.
- [ ] 3.4 **Gate:** page recall@1 no more than 0.02 below today — 0.68 hybrid, 0.71 semantic — and
      MRR held at 0.75 / 0.77. A change that finds the right section by losing the right page is
      not an improvement.
- [ ] 3.5 **Gate:** zero-result rate no worse than 0.00, and latency reported.
- [ ] 3.6 Do not re-tune `RRF_K`, `RRF_VECTOR_WEIGHT` or `SEARCH_MIN_SCORE`. If the new numbers say
      a constant is wrong, that is a finding for its own change.
- [x] 3.7 Bump `meta.CHUNKER_ID`. The embedded text changes, so every stored vector is stale, and
      this is the case the mechanism exists for. Verify search keeps working mid-reindex and that a
      converged deployment re-queues nothing.

### Where fases 1 and 2 landed

Measured against `2026-09-04-003-final.json`, 43 pages, 28 queries:

| | recall@1 | MRR | section |
|---|---|---|---|
| semantic | 0.71 → **0.64** | 0.77 → **0.73** | 0.38 → **0.75** |
| hybrid | 0.68 → **0.68** | 0.75 → **0.75** | 0.38 → **0.75** |
| hybrid+tags | 1.00 → **0.60** | 1.00 → **0.75** | — |

- **3.3 passes.** Section recall 0.38 → 0.75, above the 0.65 gate.
- **3.4 fails.** Semantic page recall@1 drops 0.07, more than the 0.02 the gate allows, and MRR
  drops 0.04. Hybrid holds exactly.
- **The tag-filter row fell from 1.00 to 0.60**, which no gate covered and which is the sharpest
  regression of the three.

**Diagnosis.** Dropping the page title from the embedded text is what 002 warned about, and the
warning was right — for page ranking. Hybrid is unharmed because its lexical half matches page
titles through full-text search and compensates. The pure vector channel has nothing to compensate
with, and `hybrid+tags` falls hardest because filtering to one dump leaves fewer lexical hits to
carry it.

This matters more than the hybrid row suggests: `rag_context` ranks chunks by cosine alone, so the
context assembled for an agent follows `semantic`, not `hybrid`.

**The heading tiebreak works and is not the problem.** It changes which section represents a page
and leaves the page's score as its best cosine, so it cannot move page ranking by construction —
and measurement confirms it does not.

**A defect found on the way, in this change's own instrumentation.** The first version of the
tiebreak rebuilt the per-page entry when the representative section changed, losing the page's
maximum cosine with it. That inflated semantic recall@1 to 0.68 — apparently passing the gate. It
does not: fixed, the number is 0.64. Two harness bugs were also fixed: piping its output through
`head` killed it before it wrote its JSON, and the per-class table iterated a row that has no
per-query detail.

**Open question for 3.x, not decided here.** Three ways forward, none free: accept that `semantic`
is now the weaker mode and make `rag_context` select pages through the fused ordering; find a
packing that carries page signal without being shared across siblings; or accept the trade and
lower the page gate deliberately, with the reason recorded.

## 4. Verification

- [ ] 4.1 Confirm the `chunking` spec's two properties hold under the shipped packing: no cross-page
      collision, siblings apart. Both as tests.
- [ ] 4.2 Confirm `retrieval-ranking`, `retrieval-evaluation`, `mcp-tools` and `search` are
      untouched.
- [ ] 4.3 Confirm the stored heading path and the chunk boundaries are unchanged — only the string
      handed to the encoder moved.
- [ ] 4.4 Run the Python gate: `uv run ruff check . && uv run ruff format --check . && uv run
      pyright app tests && uv run pytest`.
