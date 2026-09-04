## Purpose

Defines how a markdown page is divided for indexing, and what each piece has to carry so that a
fragment retrieved on its own still says where it came from. A chunk is the unit an agent
eventually reads; if it arrives without its heading, the agent is guessing.

## ADDED Requirements

### Requirement: Chunks follow the document's headings

A page SHALL be divided along its markdown heading structure rather than at fixed character
offsets. A heading MUST stay with the prose it introduces, and a section short enough to fit
whole MUST NOT be split.

A size ceiling still applies, because the encoder truncates. When a section exceeds it, the split
MUST fall on a paragraph boundary inside that section, and every resulting piece MUST keep the
section's heading path.

#### Scenario: A page of short sections

- **WHEN** a page has several sections, each shorter than the size ceiling
- **THEN** each section becomes one chunk
- **AND** no chunk contains text from two different sections

#### Scenario: A heading and its first paragraph

- **WHEN** a page is chunked
- **THEN** no chunk begins immediately after a heading with that heading in the previous chunk

#### Scenario: A section longer than the ceiling

- **WHEN** one section's text exceeds the size ceiling
- **THEN** it is split at a paragraph boundary within the section
- **AND** every piece carries the same heading path

#### Scenario: A page with no headings

- **WHEN** a page is a flat body of prose with no headings at all
- **THEN** it is still chunked at paragraph boundaries within the ceiling, and each chunk carries
  the page title as its path

#### Scenario: An empty page

- **WHEN** a page has a title and no body
- **THEN** it produces no chunks, and indexing it is not an error

### Requirement: Every chunk carries the path that locates it

A chunk SHALL carry enough context to be read on its own: the workspace, the page, and the chain
of headings above it. That path MUST be stored with the chunk, so a fragment returned by search
identifies its origin without a second lookup.

The path MUST be part of the text that is embedded. A section titled "Renewal" only means
something next to the page it sits in, and an encoder that never sees the page title cannot place
it.

#### Scenario: A nested section

- **WHEN** a chunk comes from a section under a subsection under a top-level heading
- **THEN** its path names the page and all three headings in document order

#### Scenario: Retrieval returns the path

- **WHEN** a search result is returned for that chunk
- **THEN** the path is part of the result, not something the caller has to reconstruct

#### Scenario: The path is embedded with the text

- **WHEN** two pages contain an identically worded section
- **THEN** their chunks do not produce identical vectors, because each embedding includes its own
  path

#### Scenario: Frontmatter is available without polluting the prose

- **WHEN** a page declares a `type` or tags in its frontmatter
- **THEN** those are retrievable alongside the chunk
- **AND** the raw frontmatter block is not embedded as if it were prose

### Requirement: Blocks that only make sense whole are never split

A fenced code block, a table, or a mermaid diagram SHALL be kept inside a single chunk. Splitting
one produces two fragments that are each wrong: half a function and an unclosed fence.

When such a block on its own exceeds the size ceiling, the ceiling yields. An over-long chunk is a
worse embedding; half a code block is a worse answer.

#### Scenario: A long code block

- **WHEN** a section contains a fenced code block longer than the size ceiling
- **THEN** that block is in exactly one chunk, whole, fences included

#### Scenario: A table split across the boundary

- **WHEN** a chunk boundary would fall inside a markdown table
- **THEN** the boundary moves so the table stays whole, header row included

#### Scenario: A mermaid diagram

- **WHEN** a page contains a mermaid block
- **THEN** it is in one chunk with its fence and its language tag intact

#### Scenario: Prose around a large block

- **WHEN** an over-long block sits between two paragraphs
- **THEN** the surrounding prose is chunked normally and is not dragged into the block's chunk

### Requirement: Re-chunking an existing deployment is automatic and safe

Changing how pages are chunked SHALL invalidate the stored chunks and re-index them without manual
SQL and without a separate deploy step. Search MUST keep working throughout.

#### Scenario: Upgrading a populated deployment

- **WHEN** the server starts with a chunker different from the one that produced the stored chunks
- **THEN** the affected pages are queued for re-indexing
- **AND** no result mixes chunks from two different chunkers

#### Scenario: Searching mid-reindex

- **WHEN** some pages have been re-chunked and others have not
- **THEN** search returns results and does not error
- **AND** pages not yet re-chunked are still retrievable by keyword search

#### Scenario: Restarting an already-converged deployment

- **WHEN** the server restarts and every page is already chunked by the current chunker
- **THEN** nothing is re-queued
