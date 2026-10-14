## ADDED Requirements

### Requirement: Deterministic reference validation
The system SHALL verify that every object ID, evidence ID, stage, IPC code, date, and source locator used by a claim belongs to the frozen packet and research contract.

#### Scenario: Citation exists outside the packet
- **WHEN** an agent cites a real repository patent that is not part of the frozen packet
- **THEN** reference validation rejects the citation for that run

### Requirement: Numeric fidelity validation
The system SHALL compare copied numeric claims, units, stages, directions, and object identifiers against structured frozen records. It SHALL NOT rely on an LLM to approve exact numeric equality.

#### Scenario: Degree and betweenness directions are conflated
- **WHEN** a claim says all B33Y-070 indicators increased although degree centrality declined and betweenness increased
- **THEN** numeric validation emits a blocking finding identifying the mismatched metrics and stages

#### Scenario: Numeric source is prose-only
- **WHEN** a claim contains a number for which the packet has no structured authoritative value
- **THEN** the system marks the value unverified and requires removal, structured source addition, or explicit qualification

### Requirement: Inference-boundary validation
The system SHALL identify unsupported transitions between evidence and conclusion, including IPC node to complete theme, centrality to engineering performance, static relation to dynamic change, patent activity to maturity, domain lifecycle to individual technology lifecycle, and target scenario to observed fact.

#### Scenario: IPC metric becomes a theme growth rate
- **WHEN** B25J-011 degree centrality is described as the growth rate of the robot-cluster-coordination theme
- **THEN** the validator emits a blocking object-and-measure boundary finding

#### Scenario: Functional mapping is stated as verified membership
- **WHEN** a node-theme relation is marked `functional_only` but a claim states that all node patents belong to the theme
- **THEN** the validator requires the statement to be qualified or supported by the optional document mapping attachment

### Requirement: Semantic citation support review
The system SHALL distinguish citation existence from semantic support and SHALL record whether a source supports the whole claim, only a premise or fragment, contradicts it, or is indeterminate.

#### Scenario: Valid source supports only the premise
- **WHEN** a network record supports increased association range but not improved construction efficiency
- **THEN** semantic review marks partial support and targets the unsupported performance clause

### Requirement: Evidence support levels
The system SHALL assign only `direct_support`, `conditional_support`, `exploratory_scenario`, or `insufficient_evidence`, with a reason tied to evidence, inference distance, conditions, counter-information, and unresolved gaps.

#### Scenario: Future route has historical basis and unverified conditions
- **WHEN** a proposition extends an observed network trajectory into a future engineering capability with explicit interface and safety conditions
- **THEN** its maximum support is conditional unless independent future-capability evidence warrants a different classification

### Requirement: Confidence concepts remain separated
The system SHALL NOT convert agent agreement, text similarity, self-rated confidence, evidence support level, or optional TRL into event probability. Calibrated probability SHALL be displayed only with its deterministic model run, event definition, support, and calibration status.

#### Scenario: Agent outputs converge
- **WHEN** repeated role runs produce similar wording
- **THEN** the system may record a stability diagnostic but does not increase evidence support or publish a probability

### Requirement: Typed validation findings and closure
Every validation or review finding SHALL contain a stable ID, check kind, claim/version target, severity, evidence references, message, remediation, status, and closure reference. A wording change alone SHALL NOT close a factual finding unless the changed proposition resolves the cited issue.

#### Scenario: Revision only paraphrases the same unsupported inference
- **WHEN** a revised claim changes wording but retains the same unsupported causal conclusion
- **THEN** the original finding remains open

