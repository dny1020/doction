## ADDED Requirements

### Requirement: An agent can traverse the link graph in one call

The tool surface SHALL offer traversal of the wikilink graph from a starting page to a bounded
depth, returning each reachable page with its distance, the direction of the relationship, the
path that reached it, and whether the target exists. An agent deciding where to look next needs
the neighbourhood, not one hop at a time; without traversal it pays a round trip per edge and
cannot tell when it has left the neighbourhood.

Direction SHALL distinguish a mutual reference from a one-way one. Two pages that cite each other
are a different fact from one that only points at the other, and reporting a mutual edge under a
single direction erases it from the other.

Depth and result count SHALL both be capped, the caps SHALL be stated in the tool's description,
and a truncated result SHALL say that it was truncated. Traversal SHALL terminate on cycles,
self-links and unresolved targets.

Tools that traverse different relations SHALL say which relation they traverse. Neighbours by
shared tag and neighbours by link are different answers to different questions, and an agent
choosing between them reads only the descriptions.

#### Scenario: Exploring outward from a page

- **WHEN** an agent asks for a page's linked neighbourhood at a given depth
- **THEN** it receives each reachable page with its distance and the path that reached it

#### Scenario: Two pages that cite each other

- **WHEN** a neighbour both links to and is linked from the starting page
- **THEN** the relationship is reported as mutual, and the neighbour is still an answer to
  "what links here"

#### Scenario: A cycle in the graph

- **WHEN** pages link to each other in a loop
- **THEN** the traversal terminates and reports each page once

#### Scenario: The neighbourhood is larger than the cap

- **WHEN** the reachable set exceeds the result cap
- **THEN** the result is truncated and says so

#### Scenario: Telling the relational tools apart

- **WHEN** an agent reads the descriptions of the tools that return neighbours
- **THEN** each states whether it traverses links or shared tags
