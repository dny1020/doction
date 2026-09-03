## Purpose

Defines how doction combines its two ways of finding a page into one ordering, and what the
assembled context handed to an agent must contain. The `search` capability governs what search
finds; this one governs the order it comes back in and how it is packed.

## ADDED Requirements

### Requirement: Lexical and vector results are fused by rank, not by score

Hybrid retrieval SHALL combine the lexical and the vector result lists using their positions
rather than their raw scores. A cosine similarity and a text-search rank have no common unit, so
any constant added to one to account for the other is arbitrary at some point in the list.

Each retriever MUST produce its own ranked list independently, and the fused order MUST be
derivable from those two orderings alone.

#### Scenario: A page found by both retrievers

- **WHEN** a page appears in both the lexical and the vector list
- **THEN** it ranks above a page that appears high in only one of them

#### Scenario: An exact term that the vectors miss

- **WHEN** a query names an exact identifier — a command, an endpoint, an error string — that
  lexical search matches and vector search does not
- **THEN** that page still appears in the fused list, at a rank reflecting its lexical position

#### Scenario: A paraphrase that the words miss

- **WHEN** a query shares no words with the page that answers it
- **THEN** that page still appears, at a rank reflecting its vector position

#### Scenario: One retriever returns nothing

- **WHEN** lexical search returns no rows, or the workspace has no vectors yet
- **THEN** the fused list is the other retriever's list, in its own order

#### Scenario: No score arithmetic across scales

- **WHEN** the fused ordering is computed
- **THEN** no lexical score is added to, subtracted from, or compared against a vector score

#### Scenario: Fusion is deterministic

- **WHEN** the same query runs twice against unchanged data
- **THEN** the order is identical, ties included

### Requirement: A result explains why it was retrieved

Every result SHALL say which retriever or retrievers produced it and where it came from in the
page. An agent choosing between two fragments, and a person debugging a bad answer, both need to
distinguish an exact match from a semantic neighbour.

#### Scenario: Provenance on every hit

- **WHEN** a search returns results
- **THEN** each one names its page, its heading path, and which retrievers found it

#### Scenario: Rank is inspectable

- **WHEN** a result was produced by fusion
- **THEN** its position in each contributing list is available, so the ordering can be checked
  rather than trusted

### Requirement: Assembled context is deduplicated and bounded

The context assembled for an agent SHALL NOT contain the same passage twice, and SHALL be bounded
by a size budget rather than a fixed number of fragments. Two overlapping windows from one page
spend an agent's budget twice on one sentence.

Fragments MUST be returned whole. Truncating one mid-sentence to fit the budget produces a
fragment that reads as though the document says something it does not.

#### Scenario: Overlapping fragments from one page

- **WHEN** two retrieved fragments from the same page share most of their text
- **THEN** the assembled context contains one of them, not both

#### Scenario: Several distinct sections of one page

- **WHEN** two fragments come from the same page but different sections
- **THEN** both may appear, because they answer different parts of the question

#### Scenario: The budget is reached

- **WHEN** adding the next fragment would exceed the budget
- **THEN** it is left out entirely rather than cut short
- **AND** the response says the context was truncated

#### Scenario: Every fragment keeps its provenance

- **WHEN** assembled context is returned
- **THEN** each fragment carries its page, its heading path and its score

#### Scenario: Vector search unavailable

- **WHEN** semantic search is disabled or the workspace is not yet indexed
- **THEN** context is still assembled from lexical results
- **AND** the fragments are page text, not the short highlighted extracts used to rank results

### Requirement: doction retrieves and never generates

No part of the retrieval path SHALL call a language model, and doction SHALL NOT return prose it
composed itself. It returns passages that exist in the corpus, with provenance. Synthesis is the
connected agent's job.

This is the product's architecture, not a temporary limitation: the boundary is what lets doction
run on a Raspberry Pi, stay auditable, and answer with text that can be traced to a page.

#### Scenario: Assembled context is quoted, not written

- **WHEN** an agent requests context for a query
- **THEN** every fragment returned appears verbatim in a stored page
- **AND** no sentence in the response was composed by doction

#### Scenario: No model in the query path

- **WHEN** a query is served
- **THEN** the only model involved is the local embedding encoder, and no text-generating model is
  loaded, called, or configured

#### Scenario: An empty result is reported as empty

- **WHEN** nothing in the workspace matches
- **THEN** the response says so
- **AND** it does not offer a composed answer in place of the missing passages

### Requirement: Ranking configuration is deployment state, not per-query input

The parameters that shape the ordering SHALL be properties of the running deployment, readable
through the existing system report, and MUST NOT be settable per request. A caller that can retune
the ranking per query makes every measurement meaningless.

#### Scenario: Reading the configuration

- **WHEN** an authenticated client reads the system report
- **THEN** it can tell which retrieval mode and which ranking parameters the server is running

#### Scenario: A request cannot retune the ranking

- **WHEN** a search request supplies ranking parameters
- **THEN** they are ignored, and the deployment's configuration is used
