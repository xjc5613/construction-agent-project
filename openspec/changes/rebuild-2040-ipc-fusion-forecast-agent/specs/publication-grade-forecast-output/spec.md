## ADDED Requirements

### Requirement: Structured per-theme forecast dossier
The system SHALL produce a versioned dossier for every approved technology theme containing its fused IPCs, canonical IPC names, target type, authoritative model rank and probability status, interval, evidence chain, technology definition, use cases, maturity, bottlenecks, dependencies, scenarios, milestones, measurable indicators, uncertainty, limitations, falsification signals, and review state.

#### Scenario: Generate a complete theme dossier
- **WHEN** a reviewed theme completes agent synthesis and deterministic validation
- **THEN** every required dossier field is present or explicitly marked not estimable, and every core claim resolves to approved evidence

#### Scenario: Probability is unavailable
- **WHEN** the selected fusion model has only an uncalibrated score
- **THEN** the dossier omits calibrated probability, labels the score correctly, and cannot be marked publication-ready

### Requirement: Three-node scenario roadmap
The system SHALL generate cumulative 2030, 2035, and 2040 roadmap nodes up to the project target, with baseline, accelerated, and constrained scenarios, explicit dependencies, TRL progression, quantitative indicators, decision points, and uncertainty ranges.

#### Scenario: Build a 2040 roadmap
- **WHEN** a theme is forecast to 2040
- **THEN** its roadmap contains coherent 2030, 2035, and 2040 capabilities whose dependencies and TRL changes are validated against the theme state

#### Scenario: Forecast only to 2035
- **WHEN** the project target is 2035
- **THEN** the roadmap contains 2030 and 2035 nodes and no generated 2040 claims

### Requirement: Observed, derived, predicted, and interpreted status
Every result and visualization SHALL distinguish observed source data, deterministic derived measures, calibrated or uncalibrated predictions, agent interpretations, and human-reviewed decisions.

#### Scenario: Render a predicted network edge
- **WHEN** a future IPC fusion is shown alongside historical edges
- **THEN** the predicted edge uses a distinct dashed style and prediction label while observed edges use solid styling and source support

### Requirement: Required scientific figure families
The system SHALL generate structured data and renderers for fixed-layout network small multiples, IPC transition trajectories, ranked fusion candidates, community evolution, patent-paper evidence convergence, model backtest and calibration, and dependency-aware theme roadmaps.

#### Scenario: Compare reporting-period networks
- **WHEN** the three reporting networks are rendered together
- **THEN** shared nodes retain positions and community colors, panel scales and filters are disclosed, and each panel shows its sample size and completeness status

#### Scenario: Render calibration evidence
- **WHEN** a forecast publishes calibrated probabilities
- **THEN** the export includes reliability/calibration evidence and the held-out support used to justify probability interpretation

### Requirement: Publication figure metadata and formats
Every static scientific figure SHALL include or accompany a title, numbered caption, legend, sample size, observation cutoff, uncertainty encoding, source note, data checksum, algorithm or model version, and accessibility description, and SHALL be exportable as SVG or PDF plus a 600-DPI PNG.

#### Scenario: Export a network figure
- **WHEN** a researcher requests a publication export
- **THEN** the system creates the required vector and high-resolution raster formats from the frozen chart-data contract and records their checksums in the export manifest

### Requirement: Accessible interactive and tabular views
Interactive figures SHALL provide keyboard operation, text alternatives, non-color encodings, and a downloadable and screen-readable table containing the plotted values and statuses.

#### Scenario: Open the tabular alternative
- **WHEN** a user requests the data behind a fusion chart
- **THEN** the system displays the same ranked pairs, values, intervals, statuses, and evidence links used by the chart

### Requirement: Reproducible report and research bundle
The system SHALL generate a report and research bundle from immutable structured results rather than scraping rendered UI or free-form model text.

#### Scenario: Export a publication-ready project
- **WHEN** all publication gates pass and the researcher approves publication
- **THEN** the bundle contains the report, structured dossiers, chart data, figures, validation results, manifest, source bibliography, limitations, and review log with matching checksums

#### Scenario: Regenerate failed assets
- **WHEN** a static asset failed but structured forecast results remain valid
- **THEN** the system can regenerate only the affected assets from their frozen inputs without rerunning the forecast model or agents

### Requirement: Scientific language and uncertainty integrity
The report SHALL avoid causal or certainty claims unsupported by the analysis and SHALL present limitations, unstable candidates, incomplete coverage, evidence conflicts, and overrides near the affected conclusions.

#### Scenario: Candidate is unstable under sensitivity analysis
- **WHEN** a candidate changes materially across declared sensitivity runs
- **THEN** its dossier, chart, roadmap, and report use an instability marker and explain the affected assumptions

