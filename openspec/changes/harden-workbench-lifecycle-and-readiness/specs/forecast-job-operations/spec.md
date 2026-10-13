## ADDED Requirements

### Requirement: Forecast submission is idempotent and project-exclusive
The system SHALL require or generate an idempotency key for forecast creation and SHALL atomically permit at most one active queued, running, or cancelling task per project.

#### Scenario: Duplicate submission uses the same key
- **WHEN** an equivalent forecast request is repeated with the same idempotency key
- **THEN** the original task is returned and no additional task or model work is created

#### Scenario: Same key is reused for different input
- **WHEN** an idempotency key is reused with a different topic, option, or override payload
- **THEN** the request is rejected as an idempotency conflict

#### Scenario: Another active project task exists
- **WHEN** a new key is submitted while the project has a queued, running, or cancelling task
- **THEN** creation is rejected with the active task identifier and the existing task remains unchanged

### Requirement: Start confirmation discloses workload and evidence limitations
The system SHALL present a start preview containing selected topic count, target nodes, enabled enhancements, deterministic workload estimate, configured cost estimate when available, and any evidence override before accepting confirmation.

#### Scenario: Enhanced task is previewed
- **WHEN** an operator requests a preview with self-consistency or multi-agent options
- **THEN** the preview shows the additional expected model work relative to the default configuration

#### Scenario: Evidence-limited task is previewed
- **WHEN** the task requires an evidence override
- **THEN** the confirmation prominently shows missing requirements and the reason that will be frozen into the task

### Requirement: Persistent task history and result recovery
The system SHALL list forecast jobs by project and expose durable status, progress, timestamps, options, lineage, evidence limitation, errors, and result availability. A known job URL SHALL restore its status or results after refresh.

#### Scenario: User refreshes a completed result URL
- **WHEN** a completed job result route is loaded directly
- **THEN** the system reloads job metadata, results, charts, topics, and available assets from persistent storage

#### Scenario: Job artifacts are missing
- **WHEN** job metadata exists but one or more artifact files are missing or corrupt
- **THEN** history shows a degraded job with explicit missing-artifact details instead of hiding it

### Requirement: Cooperative cancellation preserves audit data
The system SHALL accept cancellation for queued or running jobs, stop at the next safe stage boundary, preserve existing snapshots and partial artifacts, and reach a terminal cancelled state.

#### Scenario: Queued job is cancelled
- **WHEN** cancellation is confirmed before execution begins
- **THEN** the job becomes cancelled without running a model stage

#### Scenario: Running job is cancelled
- **WHEN** cancellation is requested during an external stage
- **THEN** the job becomes cancelling, completes or abandons the current safe unit, skips later stages, and becomes cancelled

#### Scenario: Completed job cancellation is requested
- **WHEN** cancellation is requested for a terminal job
- **THEN** the request is rejected without changing the result

### Requirement: Retry creates immutable lineage
The system SHALL retry a failed, partial, or cancelled task by creating a new task linked to its parent and by revalidating current readiness into a new immutable snapshot.

#### Scenario: Failed task is retried
- **WHEN** an operator confirms retry and current readiness permits it
- **THEN** a new job with `parent_job_id` is created while the original job and artifacts remain unchanged

#### Scenario: Evidence changed before retry
- **WHEN** current evidence differs from the parent snapshot
- **THEN** the retry preview identifies the difference and the new task freezes the current evidence only after confirmation

### Requirement: Startup reconciliation avoids duplicate paid work
The system SHALL reconcile non-terminal jobs on application startup. Fully initialized queued jobs MAY be re-enqueued according to configuration, while previously running or cancelling jobs SHALL become interrupted failures eligible for explicit retry.

#### Scenario: Service restarts during a running stage
- **WHEN** startup finds a job recorded as running from an earlier process
- **THEN** it is marked failed with a worker-interrupted error and is not automatically rerun

