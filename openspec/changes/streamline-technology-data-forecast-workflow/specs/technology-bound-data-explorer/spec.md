## ADDED Requirements

### Requirement: Technology-first basic data browsing
The basic data center SHALL require or derive a technology context and SHALL make imported records, not dataset containers, the primary browsing surface. Users MUST be able to switch between paper records, IPC indicator records, source files, imports, and coverage for the selected technology.

#### Scenario: Open a leaf technology data view
- **WHEN** a user selects a level-three technology in the basic data center
- **THEN** the system displays counts and tabs for its paper records, IPC indicator records, source files, imports, and historical-period coverage

#### Scenario: Open a parent technology data view
- **WHEN** a user selects a level-one or level-two technology
- **THEN** the system aggregates records from eligible descendant level-three technologies and retains each record's full technology path

### Requirement: Direct paper record list
The system SHALL provide a paginated paper list filterable by technology scope, historical period, year, dataset version, publication status, and text query. Each row MUST expose title, authors, year, keywords, source dataset, source file when available, and parse status.

#### Scenario: Browse imported papers without a query
- **WHEN** a user opens the paper tab for a technology
- **THEN** the system returns that technology scope's paper records without requiring the user to enter a search term

#### Scenario: Inspect a paper
- **WHEN** a user opens a paper record
- **THEN** the system displays its abstract, metadata, parsed fragments, source dataset version, and source file provenance

### Requirement: Direct IPC indicator record list
The system SHALL provide a paginated IPC record list filterable by technology scope, historical period, year range, IPC code, dataset version, and publication status. Each row MUST expose IPC code, year, patent count, growth rate, centrality values, source dataset, and source row when available.

#### Scenario: Browse imported IPC data
- **WHEN** a user opens the IPC tab for a technology
- **THEN** the system lists the imported IPC indicator rows without requiring an IPC code query

#### Scenario: Clarify record granularity
- **WHEN** the current storage contains aggregated IPC indicators rather than individual patent documents
- **THEN** the interface labels the rows as IPC or patent-indicator data and does not imply that patent title, applicant, or application-number records are available

### Requirement: Guided technology-bound import
The system SHALL provide one guided import flow that captures technology, public data type, files, and optional advanced version metadata. The system MUST stage and preview parsed records before commit and MUST create the underlying dataset container without requiring a separate create-dataset step.

#### Scenario: Import a paper file
- **WHEN** a user selects a technology and paper data type, uploads a supported file, reviews the preview, and confirms import
- **THEN** the system creates or resolves a draft dataset version, commits valid paper records, records source provenance, and offers publication

#### Scenario: Import IPC files
- **WHEN** a user selects a technology and IPC data type and uploads metric or fusion files
- **THEN** the system stores each file as an IPC component while presenting one public IPC dataset to the user

### Requirement: Automatic period and version handling
The system SHALL derive historical periods from record years when possible and SHALL generate a valid unique dataset version by default. Files spanning multiple supported periods MUST be split into period-specific dataset versions or require an explicit reviewed correction; out-of-range records MUST NOT be silently committed.

#### Scenario: Import records from one period
- **WHEN** all valid records fall within `2016-2020`
- **THEN** the system assigns the import to that historical period and generates a version unless the user supplied an advanced version value

#### Scenario: Import records across periods
- **WHEN** a file contains valid records from more than one supported historical period
- **THEN** the preview shows the split and the system creates separate period-specific dataset versions only after confirmation

### Requirement: Publication and retrieval eligibility
Only active, mapped, successfully parsed, published dataset versions SHALL be eligible for new stage analysis and evidence retrieval. Draft, failed, deprecated, unbound, or quarantined versions MUST remain visible in administrative filters but MUST be excluded from new forecasts.

#### Scenario: Publish a valid import
- **WHEN** a mapped draft dataset has committed valid records and passes its type-specific publication rules
- **THEN** the system publishes it and immediately includes it in technology coverage and eligible retrieval counts

#### Scenario: Browse an ineligible import
- **WHEN** a user enables administrative statuses
- **THEN** the system displays ineligible versions with a reason and remediation without treating their records as usable evidence

### Requirement: Explicit legacy data disposition
Every legacy dataset without a validated technology binding SHALL be marked as requiring mapping or quarantined. Legacy records MUST NOT participate in new technology-scoped retrieval until a maintainer reviews and commits their technology, period, and public type classification.

#### Scenario: Existing unbound records are migrated
- **WHEN** the migration encounters a published legacy dataset containing papers or IPC records without a technology node
- **THEN** the system preserves the records, marks the dataset quarantined or requiring mapping, and excludes it from new forecasts

#### Scenario: Complete legacy mapping
- **WHEN** a maintainer confirms a valid level-three technology, period, and public type for a legacy dataset
- **THEN** the system validates record years, marks the dataset mapped, and makes it eligible only if all publication rules pass
