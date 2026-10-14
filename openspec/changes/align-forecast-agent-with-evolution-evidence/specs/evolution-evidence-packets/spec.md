## ADDED Requirements

### Requirement: Bounded Chapter 4 evidence packet
The system SHALL represent a Chapter 4 evolution-evidence packet containing the stable thesis objects, their technical meaning, selected dynamic evidence needed to support judgments, theme relations or cooperation interpretations, source locations, mapping qualifications, limitations, and explicit unknowns. The system SHALL NOT require every raw IPC field, every patent, or an external paper for every theme.

#### Scenario: Sufficient bounded context is frozen
- **WHEN** a researcher provides the nine theme definitions, selected network trajectories, applicable relations, and source locations
- **THEN** the system freezes a valid packet without requiring unrelated raw network rows or a complete external literature collection

#### Scenario: Missing optional content is not promoted to a task
- **WHEN** an optional representative patent or independent lifecycle field is empty
- **THEN** the system records it as unavailable or unknown and does not treat the value as zero, fabricate content, or automatically block the packet

### Requirement: Stable thesis object identities
The system SHALL preserve `T01`–`T09` as the primary forecast objects and SHALL preserve supplied `C01`–`C06` records as candidates rather than silently merging, renaming, or promoting them.

#### Scenario: Candidate remains a candidate
- **WHEN** a `C03` record is functionally related to `T03`
- **THEN** the frozen packet retains both IDs, the relation basis, and `C03` candidate status

### Requirement: Typed evidence and inference boundaries
Each packet record SHALL declare an evidence kind, applicable object IDs, source locator, structured value and stage where applicable, mapping or relation basis, limitations, supported uses, and unsupported extrapolations.

#### Scenario: Network observation records its boundary
- **WHEN** `N1-B25J011`, `N2-B25J011`, and `N3-B25J011` contain the reported degree-centrality values
- **THEN** the records can support an observation about the IPC node's expanding direct association range and explicitly cannot by themselves support a robot-cluster productivity or theme growth-rate claim

#### Scenario: Static relation remains static
- **WHEN** an H record originates from a heat map or hierarchical clustering result
- **THEN** it is labeled as a static semantic relation and cannot be represented as measured dynamic fusion speed

### Requirement: Qualified IPC-patent-topic traceability
The system SHALL support an optional mapping attachment containing patent or document ID, year, IPC codes, and topic ID. It SHALL distinguish supplied-and-verified, supplied-unverified, reported-but-not-supplied, and unavailable mapping states.

#### Scenario: Reported mapping table is not currently supplied
- **WHEN** the thesis reports that 926 documents were mapped but the row-level table is not included in the current packet
- **THEN** the system records `reported_but_not_supplied` and does not state that the mapping research was not performed

#### Scenario: Mapping table is supplied later
- **WHEN** the researcher attaches and validates document-to-topic rows
- **THEN** the system creates a new packet version, content-addresses the attachment, and makes row-level traceability available without changing prior frozen runs

### Requirement: Source provenance and packet immutability
Every evidence record SHALL resolve to a source registry entry with a table, figure, paragraph, file, or structured-artifact locator. Starting a thesis forecast SHALL freeze the packet version, checksum, contract version, cutoff, and attachment checksums.

#### Scenario: Source trace from a claim
- **WHEN** a result references `N3-B33Y070`
- **THEN** a reviewer can trace it through the frozen packet to the exact Chapter 4 source location and packet version

#### Scenario: Evidence is updated after a run
- **WHEN** a source locator or mapping attachment is corrected after a forecast starts
- **THEN** the system creates a new packet version and the existing job continues to resolve the original version

### Requirement: Thesis and discovery evidence separation
The system SHALL keep deterministic IPC-fusion discovery output separate from Chapter 4 evidence. A discovery result MAY enter a thesis packet only as reviewed `derived_model_evidence` with model provenance and an explicit object mapping.

#### Scenario: Unreviewed fusion candidate exists
- **WHEN** an IPC-fusion model ranks a new pair that has not been mapped and reviewed
- **THEN** it is excluded from the thesis packet and cannot create or rename a thesis theme

