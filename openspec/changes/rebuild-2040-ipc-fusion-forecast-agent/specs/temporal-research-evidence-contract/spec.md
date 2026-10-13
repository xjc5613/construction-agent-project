## ADDED Requirements

### Requirement: Source-study temporal contract
The system SHALL use research contract version 3 for new projects, with baseline year 2025, reporting periods 2010-2014, 2015-2019, and 2020-2025, and cumulative forecast nodes 2030, 2035, and 2040 up to the selected target year.

#### Scenario: Create a 2040 research project
- **WHEN** a researcher creates a version 3 project with target year 2040
- **THEN** the system stores baseline year 2025, all three source-study reporting periods, and forecast nodes 2030, 2035, and 2040

#### Scenario: Reject an incompatible new period contract
- **WHEN** a client attempts to create a version 3 project using the legacy 2021-2026 period or a 2026 baseline
- **THEN** the system rejects the request with the supported research contract and migration guidance

### Requirement: Explicit temporal coverage and cutoff
The system SHALL store the observation cutoff, expected coverage, observed coverage, and completeness state for every imported source and year, and SHALL propagate incomplete-year status into analyses, forecasts, visualizations, and exports.

#### Scenario: Import partial 2025 patent data
- **WHEN** a patent dataset is observed only through October 1, 2025
- **THEN** the system marks 2025 as partial, records the cutoff date, and prevents any output from describing 2025 as a complete year

#### Scenario: Aggregate a period containing an incomplete year
- **WHEN** the 2020-2025 reporting period includes a partial 2025 observation
- **THEN** the period summary exposes the partial-year warning and both included-year and complete-year denominators used by each metric

### Requirement: Reconstructable patent and IPC evidence
The system SHALL support canonical patent records and patent-to-IPC assignments sufficient to reconstruct co-occurrence networks, preserving raw IPC codes, normalized IPC codes, source record identifiers, source rows, and dataset versions.

#### Scenario: Import patent-level IPC assignments
- **WHEN** a staged file contains a patent identifier and two or more IPC codes
- **THEN** the import preview shows the normalized patent and IPC assignments, duplicate handling, invalid codes, analysis level, and resulting candidate pairs before commit

#### Scenario: Trace a network edge to source patents
- **WHEN** a researcher opens an observed IPC edge
- **THEN** the system lists the supporting patent identifiers and their source dataset, file, and row provenance

### Requirement: Reviewed reduced-edge fallback
The system SHALL accept annual IPC edge data without patent-level records only under a reduced-evidence contract containing raw support counts, denominators, normalization metadata, source provenance, and an explicit researcher review.

#### Scenario: Commit a valid reduced-edge dataset
- **WHEN** an annual edge file satisfies the reduced-evidence schema and the researcher approves its limitations
- **THEN** the system imports it with a reduced-evidence grade and permits only analyses supported by its fields

#### Scenario: Reject probability-only fusion input
- **WHEN** a file contains IPC pairs and claimed probabilities but no derivation, support counts, denominators, or source provenance
- **THEN** the system stores it only as a researcher hypothesis or rejects it as model evidence and never treats the values as calibrated predictions

### Requirement: Paper type and bibliographic provenance
The system SHALL store a controlled paper type, source database, publication date or year, authorship metadata, citation observation date where applicable, source file, and import provenance for each paper.

#### Scenario: Import mixed paper types
- **WHEN** a paper metadata file contains journal, conference, thesis, standard, or report records
- **THEN** the system validates each type against the configured vocabulary and exposes type-level coverage in the import preview and data-quality summary

#### Scenario: Unknown paper type
- **WHEN** a paper record contains a value outside the controlled vocabulary
- **THEN** the record is held for mapping or assigned an explicit reviewed `other` value rather than silently coerced

### Requirement: Versioned IPC normalization
The system SHALL preserve raw IPC codes and apply a versioned, auditable mapping to the configured analysis level without overwriting source values.

#### Scenario: Normalize an IPC main group
- **WHEN** an imported IPC code contains subgroup detail and the project uses main-group analysis
- **THEN** the system stores both raw and normalized codes and records the mapping rule and IPC edition

#### Scenario: Unresolved historical IPC mapping
- **WHEN** an IPC code cannot be mapped unambiguously across editions
- **THEN** the system marks the assignment unresolved, excludes it from canonical network construction by default, and exposes remediation

### Requirement: Immutable research snapshots and legacy compatibility
The system SHALL freeze contract version, eligible datasets, source checksums, coverage, IPC mappings, and record identifiers for each new forecast while retaining read-only access to historical jobs under their original contracts.

#### Scenario: Source data changes after forecast start
- **WHEN** a dataset is republished or remapped after a forecast snapshot is frozen
- **THEN** the running and completed forecast continues to resolve its original snapshot and reports the original checksums

#### Scenario: Open a legacy 2026-baseline result
- **WHEN** a user opens an existing legacy job
- **THEN** the system renders its original baseline and periods with a legacy-contract label and does not relabel it as a version 3 forecast

