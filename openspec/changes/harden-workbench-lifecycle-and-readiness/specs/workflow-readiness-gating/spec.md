## ADDED Requirements

### Requirement: Canonical readiness contract
The system SHALL compute evidence quality, workflow progress, current stage, unmet prerequisites, disabled reasons, and forecast eligibility in a versioned backend readiness contract. Frontend clients SHALL render these values without independently redefining their business rules.

#### Scenario: Project readiness is requested
- **WHEN** a client requests readiness for a project
- **THEN** the response includes contract version, derived progress, current stage, requirement results, forecast eligibility, and remediation messages

#### Scenario: Dashboard progress reflects resources
- **WHEN** a project has materials but no confirmed topics or evidence packages
- **THEN** progress reflects the completed material stage and incomplete later stages rather than a hard-coded value based on project existence

### Requirement: Score and sufficiency use the same requirements
The system SHALL derive evidence score and sufficiency from the same set of weighted, blocking requirements, including IPC presence, year coverage, paper count, paper fragments, and required historical periods. A score of 100 SHALL mean every blocking requirement passes.

#### Scenario: Counts are high but a historical period is missing
- **WHEN** evidence counts would otherwise reach the maximum score but a required historical period is absent
- **THEN** sufficiency is false and the score is less than 100 with the missing period identified

#### Scenario: All evidence requirements pass
- **WHEN** every blocking requirement passes for every selected topic
- **THEN** evidence sufficiency is true and the evidence score is 100

### Requirement: Review changes immediately affect readiness
The system SHALL evaluate operational evidence quality from currently included evidence items and SHALL return refreshed readiness after an item is excluded or restored.

#### Scenario: Required papers are excluded
- **WHEN** an operator excludes evidence so that included paper count falls below the threshold
- **THEN** the topic becomes insufficient and forecast eligibility is recalculated immediately

#### Scenario: Evidence is restored
- **WHEN** an excluded item is restored and all thresholds pass again
- **THEN** readiness becomes sufficient without requiring a new retrieval

### Requirement: Strict or reasoned forecast gate
The system SHALL allow forecast creation only when all submitted topics are confirmed, have valid technology associations and evidence packages, and either pass readiness or are covered by an explicit override with a non-empty reason. Non-overrideable structural failures SHALL always block creation.

#### Scenario: Sufficient evidence starts normally
- **WHEN** all selected topics pass readiness and no active job exists
- **THEN** forecast start is eligible without an override

#### Scenario: Insufficient evidence without override
- **WHEN** one or more evidence requirements fail and no override is supplied
- **THEN** the start request is rejected with per-topic missing requirements and remediation

#### Scenario: Insufficient evidence with reasoned override
- **WHEN** only overrideable evidence requirements fail and the operator confirms an override with a trimmed reason
- **THEN** the task can start and its snapshot and result are marked evidence-limited with that reason

#### Scenario: Topic is not confirmed
- **WHEN** a submitted topic still requires review or has no valid primary technology
- **THEN** the start request is rejected even if an evidence override is supplied

### Requirement: Disabled actions explain prerequisites
The system SHALL provide a visible and programmatically associated explanation for workflow actions that are unavailable.

#### Scenario: Forecast action is disabled
- **WHEN** forecast start is unavailable because evidence has not been retrieved
- **THEN** the interface identifies the affected topics and explains that evidence retrieval is required

