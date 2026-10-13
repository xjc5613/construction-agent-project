## ADDED Requirements

### Requirement: Six-step project research workflow
The system SHALL present version 3 projects as the ordered steps research design, data quality, network evolution, fusion forecast, technology themes, and roadmap/report, while keeping global taxonomy, evidence library, and project management outside the project workflow.

#### Scenario: Enter a version 3 project
- **WHEN** a researcher enters a version 3 project
- **THEN** the project shell shows the six research steps in order, current readiness, frozen scope summary, and one recommended next action

#### Scenario: Enter a legacy project
- **WHEN** a researcher enters a legacy project
- **THEN** the shell uses a read-only compatible workflow and does not imply that version 3 scientific gates were satisfied

### Requirement: Authoritative readiness and route guards
The backend SHALL provide a versioned readiness contract for each step containing visibility, state, blocking reasons, remediation, active graph checkpoint, and recommended action, and the frontend SHALL use that contract for navigation and direct-route recovery.

#### Scenario: Open fusion forecast before network validation
- **WHEN** a user directly navigates to fusion forecast without a valid network and backtest run
- **THEN** the page displays the blocking reasons and links to the required remediation rather than rendering an empty or runnable forecast form

### Requirement: Research design configuration
The research-design step SHALL expose contract version, research question, technology scope, source-study periods, cutoff and completeness assumptions, paper types, IPC analysis level, candidate target, target year, and saved advanced parameters before data are frozen.

#### Scenario: Confirm the research design
- **WHEN** all required fields are valid and the researcher confirms the design
- **THEN** the system versions the design and makes its assumptions visible on every downstream step

#### Scenario: Change design after analysis
- **WHEN** a researcher changes a network- or model-relevant design field after downstream runs exist
- **THEN** the system creates a new design version, marks affected runs stale, and preserves prior artifacts

### Requirement: Data-quality workspace
The data-quality step SHALL show record counts, year and source coverage, paper-type distribution, IPC mapping status, duplicates, invalid records, 2025 completeness, technology binding, and reduced-evidence limitations with actionable remediation.

#### Scenario: Data are insufficient for network reconstruction
- **WHEN** an eligible dataset lacks patent incidence and does not satisfy the reduced-edge contract
- **THEN** the workspace explains the missing fields, blocks canonical network construction, and offers a mapping or replacement import action

### Requirement: Comparable network evolution explorer
The network-evolution step SHALL provide linked annual and reporting-period views with stable filters, node positions and community colors, node/edge inspection, metric trajectories, transition classifications, and data/provenance details.

#### Scenario: Compare an IPC across three periods
- **WHEN** a researcher selects an IPC node
- **THEN** all period panels highlight the same IPC and show its observed measures, community, edge support, transition status, undefined metrics, and source evidence

### Requirement: Fusion candidate review workspace
The fusion-forecast step SHALL display ranked emergence and strengthening candidates separately with calibrated probability or uncalibrated score status, interval, feature explanation, validation metrics, stability, supporting and conflicting evidence, and review actions.

#### Scenario: Exclude a candidate
- **WHEN** a researcher rejects a ranked pair and supplies a reason
- **THEN** the system records the review without changing the model rank or probability and excludes the pair only from downstream reviewed-theme synthesis

### Requirement: Technology-theme calibration workspace
The technology-themes step SHALL show the relationship among approved IPC pairs, BERTopic or other semantic clusters, patent and paper evidence, agent-proposed names, concept definitions, critic findings, and researcher edits.

#### Scenario: Merge two proposed themes
- **WHEN** a researcher merges two semantically overlapping themes
- **THEN** the system preserves both original proposals, stores the merge rationale, combines only approved evidence references, and revalidates the resulting theme contract

### Requirement: Result provenance drill-down
The workbench SHALL allow navigation from a roadmap claim to the theme forecast, approved IPC pairs, model explanation, network history, supporting patents and papers, dataset records, and graph audit trace.

#### Scenario: Trace a 2040 milestone
- **WHEN** a reviewer selects a milestone in a roadmap
- **THEN** the interface reveals its scenario, dependencies, quantitative indicators, evidence IDs, generating graph node, uncertainty, and all upstream provenance links

### Requirement: Researcher and advanced views
The system SHALL provide a concise default researcher view and an advanced view that exposes data mappings, network parameters, feature definitions, fold metrics, calibration, sensitivity results, prompt/model manifests, checkpoint history, and intermediate downloads.

#### Scenario: Toggle advanced view
- **WHEN** a researcher enables advanced view
- **THEN** the current page reveals technical controls and provenance without changing the frozen run or hiding limitations

### Requirement: Accessible and resilient research interaction
The frontend SHALL provide keyboard-operable controls, non-color status cues, tabular alternatives for scientific charts, responsive layouts, loading and failure states, unsaved-change protection, and recovery for refresh and deep links.

#### Scenario: Inspect a chart without relying on color
- **WHEN** a user opens a network or roadmap visualization
- **THEN** observed/predicted and confidence states are also encoded by line style, symbol, label, or text and the same data are available in an accessible table

