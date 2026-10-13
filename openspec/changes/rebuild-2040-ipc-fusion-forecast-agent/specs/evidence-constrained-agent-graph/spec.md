## ADDED Requirements

### Requirement: Persistent typed forecast graph
The system SHALL execute version 3 forecasts as a typed LangGraph state graph with persistent checkpoints, explicit nodes and conditional edges, and a stable job/thread identity.

#### Scenario: Start a forecast graph
- **WHEN** a researcher starts an eligible version 3 forecast
- **THEN** the system creates a thread, initial typed state, checkpoint record, graph version, and job event stream before executing the first node

#### Scenario: Inspect graph progress
- **WHEN** a forecast is running or paused
- **THEN** the job API exposes completed, active, pending, interrupted, failed, and skipped nodes from persisted graph state rather than inferred frontend status

### Requirement: Deterministic and semantic node boundary
The system SHALL execute data validation, snapshotting, network construction, feature extraction, model training, probability calibration, citations, numeric checks, and publication gates as deterministic services, while limiting LLM nodes to evidence analysis, concept synthesis, scientific criticism, and scenario-roadmap narration.

#### Scenario: Semantic node requests a network metric
- **WHEN** an agent needs a centrality, edge weight, probability, or validation metric
- **THEN** it receives the frozen deterministic value by reference and cannot calculate or persist a replacement value

### Requirement: Versioned structured model output
Every LLM node SHALL use a versioned Pydantic or JSON Schema contract through LangChain structured output and SHALL reject unvalidated free-form payloads from the scientific result path.

#### Scenario: Provider supports native structured output
- **WHEN** the configured model provider supports strict schema output
- **THEN** the node uses the provider-supported structured strategy and validates the returned object again against the local schema

#### Scenario: Output violates its schema
- **WHEN** an LLM omits a required evidence ID or returns an invalid IPC code, year, probability, or enum
- **THEN** the graph records validation errors, performs only the configured bounded correction attempts, and then fails or pauses visibly

### Requirement: Evidence-linked claims and numeric integrity
The system SHALL require evidence identifiers for every core semantic claim and SHALL verify all numeric claims, IPC codes, dates, and source references against the frozen state before accepting agent output.

#### Scenario: Agent invents a source
- **WHEN** an agent references a patent, paper, IPC, dataset, or network result absent from the snapshot
- **THEN** the validator rejects the claim and records the nonexistent reference

#### Scenario: Agent overstates a prediction
- **WHEN** an agent describes an association as causal or a validation-limited result as certain
- **THEN** the scientific critic or deterministic language policy returns a finding requiring correction or explicit limitation

### Requirement: Human review interrupts
The graph SHALL pause with a durable checkpoint for researcher review of fusion candidates, technology themes, and final publication, and SHALL support approve, edit where allowed, and reject-with-reason decisions.

#### Scenario: Review fusion candidates
- **WHEN** deterministic fusion ranking completes
- **THEN** the graph pauses before theme synthesis and presents candidate evidence, model quality, limitations, and permitted review actions

#### Scenario: Resume after review
- **WHEN** a researcher submits a valid review decision
- **THEN** the system stores the pre-review value, decision, edits, reason, reviewer, and timestamp and resumes from the interrupted checkpoint without repeating completed scientific runs

### Requirement: Recoverable idempotent execution
The system SHALL make graph nodes idempotent, checkpoint scientific artifact references, and resume after process failure without duplicating completed side effects or silently changing inputs.

#### Scenario: Process stops after model calibration
- **WHEN** the service restarts after a calibrated model artifact and checkpoint were committed
- **THEN** the job resumes from the next incomplete node using the same snapshot and model run rather than retraining or changing candidates

#### Scenario: Snapshot changed before resume
- **WHEN** referenced inputs no longer match their frozen checksums
- **THEN** resume is blocked with a reproducibility error and remediation rather than continuing on different data

### Requirement: Parallel bounded topic workers
The system SHALL support graph-managed parallel evidence and per-topic forecast workers with isolated typed inputs and deterministic aggregation.

#### Scenario: Forecast multiple reviewed themes
- **WHEN** several themes are approved for forecasting
- **THEN** each worker receives only its theme, approved candidate pairs, evidence references, target nodes, and shared contract, and aggregation preserves a result or explicit failure for every theme

### Requirement: Job-scoped configuration and cancellation
The system SHALL provide graph nodes with job-scoped dependencies and output locations, SHALL not mutate module-level runner settings, and SHALL checkpoint cancellation at safe node boundaries.

#### Scenario: Two projects use different model settings
- **WHEN** two jobs run with different approved provider or prompt configurations
- **THEN** each graph resolves only its job-scoped settings and artifacts without a global configuration lock or cross-job output collision

#### Scenario: Cancel a running graph
- **WHEN** a researcher requests cancellation
- **THEN** the graph completes or safely aborts the active idempotent operation, records a cancelled checkpoint, and leaves prior artifacts auditable

### Requirement: Complete graph audit trace
The system SHALL record node inputs by reference, output checksums, prompt and model manifests, token and latency metadata where available, validation findings, retries, human decisions, exceptions, and state transitions.

#### Scenario: Audit a technology statement
- **WHEN** a reviewer selects a statement in a completed forecast
- **THEN** the system resolves the statement to the generating node, validated structured output, prompt/model version, evidence IDs, deterministic inputs, and review history

