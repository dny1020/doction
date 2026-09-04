## MODIFIED Requirements

### Requirement: Every chunk carries the path that locates it

A chunk SHALL carry enough context to be read on its own: the workspace, the page, and the chain
of headings above it. That path MUST be stored with the chunk, so a fragment returned by search
identifies its origin without a second lookup.

The text handed to the encoder SHALL satisfy two properties at once. The specification names the
properties and not the packing that achieves them, because they pull in opposite directions and
which packing satisfies both is a measured question:

- **Sections of different pages must not collide.** A query that identifies one page MUST NOT
  rank a different page's identically worded section equally. The requirement is on the result,
  not on the vector: with the same text there is nothing *in the section* to tell them apart, and
  demanding different vectors forces shared page context into the embedding — the very thing the
  second property forbids.
- **Sections of the same page must stay apart.** Sibling sections MUST remain distinguishable from
  each other. Text that every section of a page shares carries no information about which of them
  answers a question, and enough of it turns siblings into one vector with different labels. This
  wants shared page context out.

The measurement that settles it is section recall, reported separately from page recall.

#### Scenario: A nested section

- **WHEN** a chunk comes from a section under a subsection under a top-level heading
- **THEN** its path names the page and all three headings in document order

#### Scenario: Retrieval returns the path

- **WHEN** a search result is returned for that chunk
- **THEN** the path is part of the result, not something the caller has to reconstruct

#### Scenario: The path is embedded with the text

- **WHEN** two pages contain an identically worded section, and a query names one of those pages
- **THEN** that page ranks first, and the other page's identical section does not displace it

#### Scenario: Sibling sections stay apart

- **WHEN** one page contains several sections that answer different questions
- **THEN** a query answered by one of them retrieves that one rather than a sibling
- **AND** their vectors are not near-identical to each other

#### Scenario: Frontmatter is available without polluting the prose

- **WHEN** a page declares a `type` or tags in its frontmatter
- **THEN** those are retrievable alongside the chunk
- **AND** the raw frontmatter block is not embedded as if it were prose
