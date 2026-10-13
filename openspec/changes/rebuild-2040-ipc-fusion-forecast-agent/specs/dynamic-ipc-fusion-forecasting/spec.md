## ADDED Requirements

### Requirement: Deterministic annual and reporting-period network construction
The system SHALL deterministically build versioned annual IPC co-occurrence networks and the three research-contract reporting networks from the frozen patent-to-IPC incidence or reviewed reduced-edge evidence.

#### Scenario: Rebuild an identical network
- **WHEN** the same normalized evidence snapshot, parameters, algorithm version, and seed are processed twice
- **THEN** the resulting network identifiers, node and edge measures, checksums, and candidate universe are identical

#### Scenario: Count one patent contribution per pair
- **WHEN** a patent repeats the same normalized IPC assignment in its source data
- **THEN** the patent contributes at most one support count to that IPC pair for the relevant network observation

### Requirement: Multiple normalized edge measures
The system SHALL retain raw co-occurrence support and calculate configured normalized edge measures, including at least association strength and one of Jaccard or pointwise mutual information, using recorded formulas and denominators.

#### Scenario: Inspect an observed edge weight
- **WHEN** a researcher opens an IPC edge for a year or reporting period
- **THEN** the system shows raw support, normalized measures, denominators, formula version, and input network run

### Requirement: Longitudinal node and community analysis
The system SHALL calculate versioned node measures and longitudinal changes, including degree, betweenness, closeness where defined, eccentricity where defined, community membership, first appearance, persistence, and movement between peripheral and core positions.

#### Scenario: Identify a node transition
- **WHEN** an IPC node crosses the configured peripheral/core criterion between observations
- **THEN** the system records the transition, the metric values before and after, the threshold definition, and its sensitivity status

#### Scenario: Metric is undefined
- **WHEN** a centrality or distance measure is mathematically undefined for a disconnected component
- **THEN** the system stores an explicit undefined state and does not substitute zero without a declared transformation

### Requirement: Explicit candidate and target definitions
The system SHALL version and freeze the eligible IPC pair universe, edge-emergence target, edge-strengthening target, forecast horizon, minimum support, exclusion rules, and negative sampling policy for every model run.

#### Scenario: Generate edge-emergence candidates
- **WHEN** a model run targets first appearance after a historical cutoff
- **THEN** only eligible pairs absent under the frozen pre-cutoff target definition enter the emergence candidate universe

#### Scenario: Separate strengthening from emergence
- **WHEN** an IPC pair already satisfies the observed-edge definition before cutoff
- **THEN** it is excluded from the emergence target and may enter a separately labeled strengthening model

### Requirement: Leakage-safe temporal features
The system SHALL compute each training or prediction feature using only evidence available at or before that observation's cutoff and SHALL retain feature lineage to source network, patent, and paper artifacts.

#### Scenario: Build a historical fold
- **WHEN** features are generated for a 2019 cutoff
- **THEN** no 2020 or later patent, paper, citation observation, network measure, topic assignment, or mapping update is included

#### Scenario: Inspect a candidate feature
- **WHEN** a researcher expands a predicted IPC pair
- **THEN** the system shows the feature value, definition, observation window, source run, and whether the feature is topological, temporal, textual, bibliographic, or taxonomic

### Requirement: Interpretable fusion ranking and calibrated probability
The system SHALL rank eligible IPC pairs using a versioned deterministic model and SHALL publish a probability only when it has been calibrated on held-out historical outcomes.

#### Scenario: Publish a calibrated candidate
- **WHEN** the selected model passes the configured calibration and validation gates
- **THEN** each candidate result includes rank, calibrated probability, interval or resampling distribution, model version, feature contributions, evidence grade, and limitations

#### Scenario: Model is not calibrated
- **WHEN** a model produces a score but lacks a valid held-out calibration result
- **THEN** the system labels the value as an uncalibrated score and prevents it from populating any probability field or publication-ready output

### Requirement: Model probability authority
The system MUST NOT allow manual input, prompt text, LLM output, self-consistency agreement, or agent voting to overwrite deterministic fusion ranks or calibrated probability fields.

#### Scenario: Agent proposes a different probability
- **WHEN** an agent output contains a probability that differs from the selected model result
- **THEN** deterministic validation rejects the field, preserves the authoritative model value, and records the agent validation error

### Requirement: Evidence-backed candidate explanations
The system SHALL expose why each pair was ranked, including feature contributions, historical network trajectory, supporting patents and papers, semantic relationship, uncertainty sources, and alternative explanations.

#### Scenario: Review a high-ranked cross-domain pair
- **WHEN** a researcher opens a high-ranked IPC pair from different technology domains
- **THEN** the candidate view provides its model contributions, historical evidence, text evidence, domain mapping, counter-evidence, and data limitations without asserting causality

