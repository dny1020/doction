## Purpose

Defines what a running doction deployment reports about itself: its version, whether its
database is reachable, and which optional retrieval features are active — so that the mode a
server is running in can be read rather than inferred from the shape of search results.

## ADDED Requirements

### Requirement: The deployment reports its own configuration

An authenticated client SHALL be able to read the running deployment's version, database
reachability, and whether each optional retrieval feature is enabled. The report MUST reflect
the running process rather than any stored preference.

#### Scenario: Reading the report

- **WHEN** an authenticated client requests the system report
- **THEN** it receives the running version, the database state, and a flag for each of
  semantic search, reranking and upload OCR

#### Scenario: Optional features are off

- **WHEN** the deployment runs with semantic search disabled
- **THEN** the report says semantic search is disabled
- **AND** requesting the report does not load the embedding model

#### Scenario: Unauthenticated request

- **WHEN** an unauthenticated client requests the system report
- **THEN** it is refused, in the same way as any other authenticated endpoint

### Requirement: The report is read-only

The system report SHALL expose no way to change what it reports. Retrieval configuration is a
property of the deployment, set where the deployment is configured.

#### Scenario: No write path

- **WHEN** a client attempts to modify any value in the system report
- **THEN** the request is rejected as an unsupported operation

### Requirement: Semantic index state is visible when semantic search is on

When semantic search is enabled, the report SHALL say which embedding model produced the
stored vectors and how much of the active workspace is indexed, so that a workspace still
being embedded is distinguishable from one whose search is simply performing poorly.

#### Scenario: Indexing in progress

- **WHEN** semantic search is enabled and some pages in the active workspace are not yet
  embedded
- **THEN** the report gives both the number of indexed pages and the number still pending

#### Scenario: Fully indexed

- **WHEN** every page in the active workspace is embedded
- **THEN** the report shows no pending pages

#### Scenario: Semantic search disabled

- **WHEN** semantic search is disabled
- **THEN** the report omits index counts rather than reporting zero, which would be
  indistinguishable from an unindexed workspace

### Requirement: The report is presented in settings

The settings area SHALL present the system report in a section of its own, marked as
informational rather than editable.

#### Scenario: Viewing system information

- **WHEN** a person opens the system section
- **THEN** they see the version, database state, retrieval configuration and index state
- **AND** none of these are presented as editable controls

#### Scenario: The report cannot be retrieved

- **WHEN** the system report cannot be loaded
- **THEN** the section says so, and the rest of the settings area continues to work
