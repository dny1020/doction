## Purpose

Defines what doction's search must find: which queries retrieve which pages across the
keyword, semantic and hybrid modes, so that retrieval quality does not depend on whether a
page is written in English or Spanish, nor on whether the person searching typed the
accents.

## Requirements

### Requirement: Keyword search ignores diacritics

Keyword search SHALL match query terms to page titles and content independently of
diacritical marks, in both directions. A query written without accents MUST find content
written with them, and a query written with accents MUST find content written without them.
This applies to page search and to OCR-indexed upload text alike.

#### Scenario: Unaccented query finds accented content

- **WHEN** a workspace contains the page `RPI-Operaciones / Renovación TLS con Certbot` and
  the user searches for `renovacion`
- **THEN** that page is returned as the first result
- **AND** the result is the page itself, not another page that merely mentions its slug

#### Scenario: Accented query finds unaccented content

- **WHEN** a page's body spells a term without its accent, as in `contenedor caido`, and the
  user searches for `caído`
- **THEN** that page is returned among the results

#### Scenario: Diacritic folding does not merge unrelated terms

- **WHEN** the user searches for a term whose only accented neighbour is a different word
- **THEN** results do not include pages that match solely through that unrelated word

### Requirement: A query built from a page's own words retrieves that page

For a query composed of terms that appear in a page's title or body, ignoring diacritics,
hybrid search SHALL return that page and rank it first. Hybrid search MUST NOT return an
empty result set for such a query.

#### Scenario: Spanish title terms, typed without accents

- **WHEN** the user searches the sidebar for `renovacion tls`
- **THEN** the result list is not empty
- **AND** `RPI-Operaciones / Renovación TLS con Certbot` is the first result

#### Scenario: The score floor does not suppress a correct match

- **WHEN** a query's only correct match would score below the minimum score applied to the
  hybrid result list
- **THEN** the page is still returned, because the keyword half of hybrid search retrieves
  it independently of that score

### Requirement: English retrieval does not regress

Queries that succeed today SHALL continue to succeed after the retrieval configuration
changes. English technical vocabulary — the terms that discriminate between pages in this
corpus — MUST retain its current ranking behaviour.

#### Scenario: English technical term

- **WHEN** the user searches for `certbot`, `fstab` or `nginx`
- **THEN** the pages documenting those topics are returned, ranked as they are today or
  better

#### Scenario: Natural-language English question

- **WHEN** the user asks `how do I renew the TLS certificate` through semantic search
- **THEN** `RPI-Operaciones / Renovación TLS con Certbot` is the first result

### Requirement: Stored embeddings are never compared across encoder models

Semantic search SHALL only compare vectors produced by the same encoder. When the configured
encoder changes, previously stored vectors MUST NOT contribute to results, and the affected
pages MUST be re-embedded before their content is searchable by meaning again.

#### Scenario: Encoder is replaced on an existing deployment

- **WHEN** the server starts with a different embedding model than the one that produced the
  vectors already stored for a workspace
- **THEN** those pages are queued for re-embedding
- **AND** no result is ranked using a mixture of vectors from two different models

#### Scenario: Semantic search while a reindex is in progress

- **WHEN** some pages have been re-embedded with the new model and others have not
- **THEN** search still returns results and does not error
- **AND** pages not yet re-embedded are retrievable by keyword search in the meantime

### Requirement: The retrieval configuration upgrade reaches existing databases

Applying this change to a deployment that already holds data SHALL bring that database to
the new search configuration without manual SQL, without data loss, and without a separate
migration step in the deploy procedure. Running it more than once MUST be safe.

#### Scenario: Upgrading a populated database

- **WHEN** the server starts against a database whose search index was built with the
  previous configuration
- **THEN** the index is rebuilt to the new configuration during startup
- **AND** every existing page remains present and searchable afterwards

#### Scenario: Restarting an already-upgraded database

- **WHEN** the server starts again against a database that is already on the new
  configuration
- **THEN** no rebuild is performed and startup is unaffected

#### Scenario: Fresh database

- **WHEN** the server initialises an empty database
- **THEN** it is created directly with the new configuration and no upgrade step runs
