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
- [x] 1.4 Measure the cross-page collision property directly: two identically worded sections in
      two different pages, and whether a query matching one ranks the other equally. This is what
      002 added the page title to protect, and dropping the title from the embedding puts it at
      risk. Add it as a test, not only as an eval case.
- [x] 1.5 Record all three runs in `evals/results/`, each labelled with its packing variant, so the
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
- [x] 2.4 Ship the tiebreak only if it earns its place. Measure it separately from the packing
      change so the two contributions are attributable, exactly as 002 separated the chunker from
      the fusion.
- [x] 2.5 Verify sibling sections are meaningfully apart under the shipped configuration: report
      the average and maximum cosine between sections of one page, against today's 0.685 and 0.943.

## 3. Benchmark and gate

- [x] 3.1 Extend the section-level query set beyond eight. A 0.65 target over eight queries moves
      in steps of 0.125, so a single query decides whether this change passes. Add cases across the
      existing query classes, with their expected headings verified against the corpus.
- [x] 3.2 Run the final configuration against `evals/results/2026-09-04-003-final.json` and commit
      the result labelled with its variant.
- [ ] 3.3 **Gate — FAILS on the honest set, see below.** section recall at or above 0.65, up from 0.38.
- [ ] 3.4 **Gate:** page recall@1 no more than 0.02 below today — 0.68 hybrid, 0.71 semantic — and
      MRR held at 0.75 / 0.77. A change that finds the right section by losing the right page is
      not an improvement.
- [x] 3.5 **Gate:** zero-result rate no worse than 0.00, and latency reported.
- [x] 3.6 Do not re-tune `RRF_K`, `RRF_VECTOR_WEIGHT` or `SEARCH_MIN_SCORE`. If the new numbers say
      a constant is wrong, that is a finding for its own change.
- [x] 3.7 Bump `meta.CHUNKER_ID`. The embedded text changes, so every stored vector is stale, and
      this is the case the mechanism exists for. Verify search keeps working mid-reindex and that a
      converged deployment re-queues nothing.

### Not archived: the change violates its own spec delta

Task 4.1 asked for tests of the two `chunking` properties. Written, and one of them fails
outright: two identically worded sections in two different pages now produce **the same vector**,
cosine 1.0000. With `# Section\n\nbody` packing their embedded text is byte-identical, so nothing
tells them apart. That is the property 002 put the page title in the embedding to protect, and
removing the title is exactly what raised section recall.

It is recorded as a strict xfail so the suite stays honest and flips the moment someone fixes it.

Archiving would promote a `chunking` delta stating a property the code demonstrably breaks. Held
for a decision instead.

### Final state, and two gates that do not close

The section-level query set went from 8 to **19**, and that changes the verdict. The 0.75 reported
mid-change was measured on the original eight, which turned out to be a favourable sample. Measured
like for like on all nineteen, packing variant A scores 0.32 and the shipped variant B scores 0.42.
The harness agrees: its `rag` row reads 0.42 over the same nineteen.

| | before | after |
|---|---|---|
| section recall, 8 queries | 0.38 | 0.75 |
| section recall, 19 queries | 0.32 | **0.42** |
| hybrid recall@1 / MRR | 0.68 / 0.75 | 0.68 / 0.75 |
| rag recall@1 / MRR | — | **0.68 / 0.77** |
| semantic recall@1 | 0.71 | 0.64 |
| hybrid+tags recall@1 | 1.00 | 0.60 |

**3.3 fails.** Section recall is 0.42 against a 0.65 gate. It improves — 0.32 → 0.42, a third
better — but it does not reach what this change set out to reach. The 0.75 that looked like a pass
was eight queries moving in steps of 0.125, which is exactly the risk task 3.1 was written to catch,
and catching it is what widening the set was for.

**3.4 fails on `semantic`** (0.71 → 0.64, gate allowed 0.02) and is met on `hybrid` and on the new
`rag` row. See the decision recorded in the proposal: the pure vector mode is accepted as weaker
because nothing uses it.

**`hybrid+tags` at 0.60 is not fixed by pre-filtering.** Both channels now filter inside their own
extraction — the lexical in SQL, the vector before scoring — which is the correct shape and is what
fusion by position requires. It does not move the number. A read-only diagnostic says why: for
these queries the vector list is already entirely within the filtered set, so pre- and
post-filtering are equivalent, and the page that loses is one the lexical channel ranks first and
the weakened vector channel ranks second. `RRF_VECTOR_WEIGHT = 2.0` was calibrated in 002 against a
vector channel that had page context in its embedding. This change removed that context and did not
re-calibrate, because 3.6 forbids it.

**That prohibition is now the open question.** It exists so a change cannot tune against a metric it
invented. But a constant whose input distribution changed is stale rather than merely untuned, and
re-sweeping the weight is the obvious first move for whatever follows this change. It should be its
own change, with the sweep committed, exactly as 002 did.

### Where the change landed after the rag_context refactor

`rag_context` now selects pages through the fused ordering and sections by cosine with the heading
tiebreak. The harness gained a `rag` row, because `semantic` and `hybrid` measure
`embeddings.search` and no change inside `rag_context` can move them — without the row the effect
would be invisible.

| | recall@1 | MRR | section | p50 |
|---|---|---|---|---|
| semantic | 0.71 → 0.64 | 0.77 → 0.73 | 0.38 → **0.75** | 14 → 17 ms |
| hybrid | 0.68 → **0.68** | 0.75 → **0.75** | 0.38 → **0.75** | 17 → 20 ms |
| hybrid+tags | 1.00 → 0.60 | 1.00 → 0.75 | — | 22 → 25 ms |
| **rag** (new row) | **0.68** | **0.77** | **0.75** | 60 ms |

**What recovered.** Assembled context — the thing an agent actually receives — now matches hybrid
on page recall, beats every other row on MRR at 0.77, misses one query out of 28 where the vector
channel missed four, and keeps section recall at 0.75. That was the point of the option.

**What did not, and cannot from here.** `semantic` and `hybrid+tags` are unmoved, because they
measure `embeddings.search`. Nothing in this refactor touches that path. Two consequences remain
open and are not fixed by this change:

- `search(mode="semantic")` is now the weaker mode: 0.64 against hybrid's 0.68. It is an
  explicitly-named API mode a caller opts into, and no doction surface uses it — the sidebar, the
  REST default and every MCP tool use hybrid or `rag`.
- `hybrid+tags` at 0.60 is the real open regression. Filtering to one dump leaves the lexical half
  with fewer hits to carry the fused order, so the weakened vector channel shows through. It is
  measured by the filter cases and not addressed here.

**Latency.** The first version of the refactor called `_hybrid`, which loaded the vectors and
encoded the query a second time: 187 ms. Doing the vector work once and fusing inline took it to
60 ms. A second pass was needed after that, because bounding `pool` by pages rather than by
candidates left ~150 fragments for a deduplication that compares each against every kept one — 418
ms. Bounded by candidates, 60 ms. Three times hybrid's cost, for a call that assembles context
rather than ranking a keystroke.

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
- [x] 4.2 Confirm `retrieval-ranking`, `retrieval-evaluation`, `mcp-tools` and `search` are
      untouched.
- [x] 4.3 Confirm the stored heading path and the chunk boundaries are unchanged — only the string
      handed to the encoder moved.
- [x] 4.4 Run the Python gate: `uv run ruff check . && uv run ruff format --check . && uv run
      pyright app tests && uv run pytest`.
