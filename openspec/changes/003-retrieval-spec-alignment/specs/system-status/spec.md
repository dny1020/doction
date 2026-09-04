## MODIFIED Requirements

### Requirement: The deployment reports its own configuration

An authenticated client SHALL be able to read the running deployment's version, database
reachability, whether each optional retrieval feature is enabled, and the parameters that shape
the ranking. The report MUST reflect the running process rather than any stored preference.

The ranking parameters belong here because they decide the order of every hybrid result: two
deployments on the same version can rank differently, and without this neither can say so. They
are reported for the same reason the retrieval flags are — so the mode a server is running in can
be read rather than inferred from the shape of its results.

#### Scenario: Reading the report

- **WHEN** an authenticated client requests the system report
- **THEN** it receives the running version, the database state, and a flag for each of
  semantic search, reranking and upload OCR

#### Scenario: Ranking parameters are reported

- **WHEN** an authenticated client requests the system report
- **THEN** it receives the constants that determine the fused ordering and the score floor
  applied to the vector list

#### Scenario: Optional features are off

- **WHEN** the deployment runs with semantic search disabled
- **THEN** the report says semantic search is disabled
- **AND** requesting the report does not load the embedding model

#### Scenario: Unauthenticated request

- **WHEN** an unauthenticated client requests the system report
- **THEN** it is refused, in the same way as any other authenticated endpoint
