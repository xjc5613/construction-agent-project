## ADDED Requirements

### Requirement: Atomic versioned development propositions
The system SHALL make an atomic `DevelopmentClaim` the unit of generation, review, revision, adjudication, and reporting. Each claim SHALL include stable identity, version lineage, object IDs, claim type, target period, statement, evidence IDs, reasoning bridge, assumptions, enabling conditions, validation requirements, competing explanations, uncertainty sources, support level, unresolved gaps, and status.

#### Scenario: Compound statement is split
- **WHEN** a generated sentence combines an observed centrality change, a causal explanation, and a 2035 capability assertion
- **THEN** the system requires separately reviewable propositions or rejects the compound claim for correction

#### Scenario: Claim is revised
- **WHEN** an accepted review finding requires a narrower statement
- **THEN** the system appends a new immutable claim version with the parent version and change reason preserved

### Requirement: Four proposition types
Every claim SHALL be classified as `historical_observation`, `conditional_extrapolation`, `target_scenario`, or `insufficient_evidence`, and its wording and required fields SHALL conform to that type.

#### Scenario: Future capability lacks observational support
- **WHEN** a capability is a desired 2040 combination rather than a measured result
- **THEN** it is classified as a target scenario with conditions and is not rendered as a historical observation

### Requirement: Five bounded research responsibilities
The thesis workflow SHALL implement evolution analysis, proposition generation, reverse review, engineering review, and adjudication as distinct roles with typed inputs, outputs, and authority limits.

#### Scenario: Evolution analyst encounters a missing value
- **WHEN** a topic has no verified stage-specific topic frequency
- **THEN** the evolution analyst records the missingness and does not calculate, infer, or substitute that frequency

#### Scenario: Proposition generator uses original evidence
- **WHEN** propositions are generated for a theme
- **THEN** the generator receives both the evolution summary and the relevant original frozen evidence records rather than relying only on an agent-produced summary

### Requirement: Independent competitive and engineering review
The system SHALL run reverse review and engineering review independently against the same claim version and relevant original evidence. Each finding SHALL identify the claim/version, category, severity, evidence basis, issue, and requested remediation.

#### Scenario: Reviews legitimately disagree
- **WHEN** the reverse reviewer accepts the historical premise but the engineering reviewer finds missing interface and safety conditions
- **THEN** both findings are preserved for adjudication and neither overwrites the other

### Requirement: Evidence-based adjudication
The adjudicator SHALL decide `accept`, `revise`, `downgrade`, or `defer` by resolving findings against the original evidence and claim conditions. It SHALL NOT use role vote counts or wording convergence to determine support.

#### Scenario: Multiple roles agree on an unsupported claim
- **WHEN** all model roles repeat a claim whose source does not semantically support it
- **THEN** adjudication does not raise its support level and requires revision, downgrade, or deferral

### Requirement: Bounded local revision and rereview
Only affected claims SHALL be revised. Revised claim versions SHALL repeat structural, reference, numeric, reverse, and engineering checks required by the original findings. Revision and resource limits SHALL be frozen before execution.

#### Scenario: One claim exhausts revisions
- **WHEN** a blocking conflict remains after the configured limit
- **THEN** that claim terminates as `revision_exhausted` or `deferred`, retains the unresolved finding, and unrelated claims continue

#### Scenario: Local revision resolves a finding
- **WHEN** a claim removes an unsupported timing assertion and the corresponding rereview confirms the change
- **THEN** the system closes that finding with links to the old and new claim versions

### Requirement: Conditional roadmap from adjudicated claims
Theme roadmaps SHALL be built only from accepted or explicitly downgraded claim versions. Each milestone SHALL contain its period, capability scope, prerequisites, entry conditions, validation indicators, scenario assumptions, evidence IDs, and retained objections.

#### Scenario: Prerequisite ordering is invalid
- **WHEN** a 2030 milestone depends on a capability first scheduled for 2035
- **THEN** the roadmap fails dependency validation or is returned for correction

#### Scenario: TRL lacks maturity evidence
- **WHEN** no test, demonstration, or deployment source supports a TRL assignment
- **THEN** the milestone omits TRL and reports capability and validation criteria instead

### Requirement: Complete cross-theme synthesis
Cross-theme synthesis SHALL consume complete adjudicated propositions, roadmap milestones, prerequisites, and unresolved findings. It SHALL label whether each proposed relationship derives from a network observation, static semantic relation, reviewed model artifact, or engineering-functional hypothesis.

#### Scenario: Cross-theme relation is only functional
- **WHEN** two themes have an engineering dependency but no corresponding network or clustering record
- **THEN** the synthesis retains the relationship as an engineering-functional hypothesis rather than inventing a statistical association

### Requirement: Per-claim and job termination reporting
The system SHALL distinguish normal completion, insufficient evidence, revision exhaustion, execution failure, cancellation, and human deferral at claim and job-summary levels.

#### Scenario: Mixed outcome job completes
- **WHEN** some claims are accepted, one is deferred for insufficient evidence, and one agent call fails after retries
- **THEN** the result reports all outcomes and coverage counts instead of displaying only successful claims or failing the entire job silently

### Requirement: Human review changes create traceable versions
Human edits at evidence, claim, or publication gates SHALL record reviewer, reason, before value, after value, and resulting version or decision. An unattached `after` payload SHALL NOT be treated as having changed the authoritative claim.

#### Scenario: Researcher narrows a claim
- **WHEN** a researcher edits a claim during the claim-review interrupt
- **THEN** a new claim version becomes authoritative and the stored review links both versions and the reason

