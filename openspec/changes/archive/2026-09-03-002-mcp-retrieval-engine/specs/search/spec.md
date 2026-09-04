## MODIFIED Requirements

### Requirement: A query built from a page's own words retrieves that page

For a query composed of terms that appear in a page's title or body, ignoring diacritics,
hybrid search SHALL return that page and rank it first. Hybrid search MUST NOT return an
empty result set for such a query.

Hybrid search combines its two retrievers by rank, not by score: each produces its own ordered
list and the two orderings are fused. The guarantee above is therefore structural rather than
incidental — a page the keyword retriever ranks first cannot be displaced by a vector score,
because the two are never added together.

#### Scenario: Spanish title terms, typed without accents

- **WHEN** the user searches the sidebar for `renovacion tls`
- **THEN** the result list is not empty
- **AND** `RPI-Operaciones / Renovación TLS con Certbot` is the first result

#### Scenario: The score floor does not suppress a correct match

- **WHEN** a query's only correct match would score below the minimum score applied to the
  vector half of hybrid search
- **THEN** the page is still returned, because the keyword half retrieves it independently of
  that score, and fusion ranks it on its keyword position

#### Scenario: An exact identifier outranks a semantic neighbour

- **WHEN** a query names a command, an endpoint or an error string that appears verbatim in one
  page, and another page is merely about the same topic
- **THEN** the page containing the exact term is ranked first
