## Purpose

Defines the measurement discipline that gates changes to retrieval quality. doction's retrieval
constants already cite the runs that justify them; this makes that practice a requirement rather
than a habit, so a change that feels better but measures worse cannot ship on the feeling.

## ADDED Requirements

### Requirement: A baseline is recorded before the logic changes

Before any change to chunking or ranking, the harness SHALL be run against the unchanged code and
its output committed. A baseline taken after the fact is a description of the new behaviour, not a
comparison.

The recorded run MUST state the corpus size, the query count, the model, and the score for every
retrieval variant, so a later reader can tell whether two runs are comparable at all.

#### Scenario: Establishing the baseline

- **WHEN** work begins on a change that affects retrieval
- **THEN** a run of the current code is recorded under the results directory before the first
  logic change

#### Scenario: A run identifies its conditions

- **WHEN** a result file is read later
- **THEN** it names the corpus size, the query count, the embedding model and the variant scored

#### Scenario: Runs over different corpora are not compared

- **WHEN** two runs used corpora of different sizes
- **THEN** they are not presented as a before-and-after of the same measurement

### Requirement: A retrieval change must not lose ground

A change to the chunker, the ranking, or the assembled context SHALL hold or improve recall@1 and
MRR against the baseline, on the same corpus and the same query set. A change that trades one of
them for the other MUST say so explicitly and justify the trade with the numbers.

Latency is part of the result. A change that improves ranking while multiplying response time is a
regression unless the trade is stated and accepted — the reranker is the worked example: +0.01 MRR,
−0.04 recall@1, 29× the median latency, and it stays off.

#### Scenario: An improvement

- **WHEN** a ranking change is proposed
- **THEN** a run shows recall@1 and MRR at or above the baseline before it is merged

#### Scenario: A regression

- **WHEN** a run shows either metric below the baseline
- **THEN** the change does not ship in that form

#### Scenario: A deliberate trade

- **WHEN** a change raises one metric and lowers another
- **THEN** both numbers are recorded, and the reason for accepting the trade is written down with
  them

#### Scenario: Latency counts

- **WHEN** a change alters median or tail latency materially
- **THEN** that is reported alongside the quality metrics and weighed against them

#### Scenario: The zero-result rate is reported

- **WHEN** a run is recorded
- **THEN** it includes how often a query returned nothing, because a ranking that orders well and
  finds nothing is not an improvement

### Requirement: The query set covers what the tools promise

The evaluation query set SHALL include queries of each kind the tool surface claims to serve, and
each query MUST name the pages that should be retrieved. A capability that is asserted in a tool
description and absent from the query set is unmeasured.

Coverage MUST include, at minimum: exact identifiers such as commands and endpoints, natural
language questions, paraphrases sharing no vocabulary with their target, queries written without
the accents of the indexed text, and queries whose answer lives in a subsection rather than at the
top of a page.

#### Scenario: A new capability arrives with its queries

- **WHEN** a change adds or changes a retrieval capability
- **THEN** the query set gains cases that exercise it, with their expected pages

#### Scenario: Section-level retrieval is measured

- **WHEN** chunking changes to preserve heading context
- **THEN** the query set contains queries whose answer is in one section of a long page, and the
  expected result names that section

#### Scenario: The corpus stays private

- **WHEN** the query set and results are committed
- **THEN** the corpus they ran against is not, and the harness continues to take its path from the
  environment

### Requirement: The harness stays outside the test suite

Retrieval quality SHALL be measured by a harness run deliberately, not by the automated test
suite. A quality number that can fail a build is a build that gets ignored, and the corpus it
needs is not in the repository.

Correctness, in contrast, stays in the suite: that a filter filters, that fusion is deterministic,
that a code block is not split, are behaviours and belong in tests.

#### Scenario: The suite does not score quality

- **WHEN** the automated tests run
- **THEN** no test asserts a recall or MRR threshold

#### Scenario: The suite runs without the corpus

- **WHEN** the tests run on a machine that has no evaluation corpus
- **THEN** they pass

#### Scenario: Behaviour is still tested

- **WHEN** ranking or chunking behaviour changes
- **THEN** tests cover the behaviour — filters, determinism, block integrity, deduplication —
  independently of the quality run
