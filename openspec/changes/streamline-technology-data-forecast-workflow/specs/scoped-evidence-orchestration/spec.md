## ADDED Requirements

### Requirement: Canonical eligible dataset set
For each confirmed project topic, the backend SHALL derive one canonical eligible dataset set from active mapped level-three technology associations that are descendants of the project's selected technology root. Only active published dataset versions bound to those technologies SHALL be included.

#### Scenario: Derive topic datasets
- **WHEN** a confirmed topic is associated with BIM and robotics technologies inside the project scope
- **THEN** the eligible set contains only active published mapped datasets bound to those associated technologies

#### Scenario: Topic references an out-of-scope technology
- **WHEN** a topic association identifies a technology outside the project's selected root
- **THEN** confirmation and evidence retrieval are rejected with a technology-scope validation error

### Requirement: No unscoped retrieval fallback
The system MUST return an empty eligible set and explicit remediation when no qualifying dataset exists. It MUST NOT interpret an empty eligible set as permission to search every published dataset.

#### Scenario: Technology has no datasets
- **WHEN** a confirmed topic's associated technologies have no eligible dataset versions
- **THEN** retrieval returns no library IPC or paper evidence and readiness identifies the missing technology-bound data

#### Scenario: Unbound legacy data exists
- **WHEN** the library contains published legacy paper or IPC records without a validated technology binding
- **THEN** those records do not appear in the new topic's evidence package

### Requirement: Advanced retrieval can only narrow scope
Advanced retrieval options SHALL allow users to narrow the canonical eligible set by dataset version, period, year range, or relevance. A client-supplied dataset ID MUST be rejected when it is not a member of the canonical eligible set.

#### Scenario: Select an eligible dataset version
- **WHEN** a user chooses one version from the topic's eligible dataset list
- **THEN** retrieval uses that subset and records the selection in the evidence query

#### Scenario: Submit a foreign dataset ID
- **WHEN** a client submits a dataset bound to an unrelated or out-of-scope technology
- **THEN** the API rejects the request and does not create an evidence package

### Requirement: Shared scope across analysis and readiness
Topic extraction, stage analysis, evidence retrieval, coverage calculations, and readiness SHALL use the same effective technology and dataset eligibility rules. Coverage MUST be based on eligible records rather than the mere existence of published dataset containers.

#### Scenario: Empty published dataset exists
- **WHEN** a technology has a published dataset version with no valid committed paper or IPC records
- **THEN** coverage and readiness do not count that version as satisfying evidence requirements

#### Scenario: Data becomes eligible
- **WHEN** valid records are committed and the mapped dataset is published
- **THEN** coverage, stage analysis inputs, evidence eligibility, and readiness reflect the data consistently

### Requirement: Scope-aware topic extraction
Research-material topic extraction SHALL match candidates only to active level-three technologies within the project scope and SHALL attach only eligible stage dataset summaries. A fallback technology association MUST NOT be silently assigned when no meaningful match exists.

#### Scenario: Material matches no scoped technology
- **WHEN** extraction cannot find a meaningful technology match in the project scope
- **THEN** the candidate remains explicitly unassigned and requires user calibration before evidence retrieval

#### Scenario: Material matches multiple scoped technologies
- **WHEN** extraction finds meaningful signals for several in-scope technologies
- **THEN** the candidate records those associations, their relevance, and one proposed primary technology for review

### Requirement: Evidence and forecast snapshot reproducibility
Every evidence package and forecast job SHALL record the project root, topic technology associations, eligible and selected dataset IDs, technology paths, taxonomy version, dataset versions, filters, and content checksums used for the run.

#### Scenario: Start a forecast
- **WHEN** a forecast job is confirmed
- **THEN** the immutable snapshot contains the resolved technology and dataset scope in addition to the selected evidence items

#### Scenario: Catalog changes after completion
- **WHEN** technologies are renamed, moved, or deactivated after a job completes
- **THEN** historical results continue to display the frozen technology paths and dataset versions from the job snapshot

### Requirement: Legacy result compatibility
The stricter scope rules SHALL apply to new retrieval and forecast operations without rewriting completed evidence packages, forecast snapshots, or results from legacy projects.

#### Scenario: Open a pre-migration result
- **WHEN** a user opens a completed result created before strict technology scoping
- **THEN** the system renders its original snapshot and identifies it as a legacy scope contract without recalculating its evidence
