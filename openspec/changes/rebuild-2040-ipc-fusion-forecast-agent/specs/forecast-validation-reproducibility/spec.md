## ADDED Requirements

### Requirement: Rolling-origin historical evaluation
The system SHALL evaluate fusion models with time-ordered folds that prevent future observations from influencing training, feature generation, calibration, threshold selection, or model selection.

#### Scenario: Evaluate the first broad transition
- **WHEN** the system evaluates predictions from the 2010-2014 observation window into 2015-2019
- **THEN** all model inputs and selections are derived only from information available through 2014 and outcomes are measured only in the configured future window

#### Scenario: Add annual rolling folds
- **WHEN** annual or rolling-window data provide additional valid cutoffs
- **THEN** the system evaluates those folds separately and aggregates them without replacing the three source-study reporting periods

### Requirement: Mandatory scientific baselines
The system SHALL compare the selected model with at least a prevalence or random baseline, common-neighbors ranking, Adamic-Adar ranking, and logistic regression using a declared minimal feature set.

#### Scenario: Candidate model does not improve baselines
- **WHEN** the selected model fails the configured improvement criterion against mandatory baselines
- **THEN** the run is marked validation-limited and cannot claim superior predictive performance

### Requirement: Ranking and probability metrics
The system SHALL report ranking metrics and, when probabilities are published, discrimination and calibration metrics appropriate to the frozen candidate universe and class balance.

#### Scenario: Complete a calibrated model evaluation
- **WHEN** a calibrated model has sufficient positive and negative outcomes
- **THEN** the result reports Precision@K, Recall@K, Hit Rate@K, MAP or NDCG, PR-AUC where defined, Brier score, expected calibration error, support counts, and bootstrap confidence intervals

#### Scenario: Metric cannot be estimated
- **WHEN** a fold lacks sufficient events for a requested metric or confidence interval
- **THEN** the system reports the metric as not estimable with the reason rather than returning zero or a fabricated value

### Requirement: Ablation and sensitivity analysis
The system SHALL evaluate the stability of conclusions across feature-family ablations and configured sensitivities for period cutoff, candidate definition, edge threshold, negative sampling, IPC normalization, and 2025 completeness.

#### Scenario: Compare complete-year and partial-2025 results
- **WHEN** 2025 coverage is marked incomplete
- **THEN** the validation bundle includes results excluding 2025 and results using the observed portion of 2025, and flags candidates whose rank or probability is unstable

#### Scenario: Remove paper-derived features
- **WHEN** the paper-signal ablation is executed
- **THEN** the system records metric changes and candidate-rank changes without mutating the primary model run

### Requirement: Publication readiness gate
The system SHALL compute publication readiness from frozen evidence, validation, calibration, stability, citation, and review criteria and SHALL not equate an override with passing those criteria.

#### Scenario: All publication criteria pass
- **WHEN** the model, evidence, sensitivity, output-schema, citation, and human-review gates all pass
- **THEN** the forecast is marked publication-ready with the exact gate results and manifest identifiers

#### Scenario: Researcher overrides an unmet gate
- **WHEN** an authorized researcher supplies a reason to continue despite an unmet gate
- **THEN** the run remains visibly evidence-limited or validation-limited, stores the reason and reviewer, and propagates the limitation to every result and export

### Requirement: Reproducible run manifest
The system SHALL create an immutable manifest containing contract and schema versions, source checksums, coverage, mappings, algorithms, feature definitions, candidate rules, seeds, dependencies, model and calibration artifacts, prompts, model-provider settings, reviews, and output checksums.

#### Scenario: Reproduce a deterministic run
- **WHEN** an operator reruns a manifest against the same supported environment and source artifacts
- **THEN** deterministic network, feature, model, chart-data, and manifest checksums match or the system reports a field-level reproducibility difference

#### Scenario: Export a research package
- **WHEN** a publication-ready forecast is exported
- **THEN** the package contains a machine-readable manifest and sufficient intermediate structured data to audit each published table and figure

### Requirement: No mock evidence in research results
The system MUST keep synthetic fixtures, mock forecasts, and simulated outcomes separate from empirical project results and MUST label every synthetic artifact.

#### Scenario: Run automated tests with fixtures
- **WHEN** a test uses generated historical data
- **THEN** outputs remain in the test scope, carry a synthetic marker, and cannot be selected as a project validation run or publication metric

