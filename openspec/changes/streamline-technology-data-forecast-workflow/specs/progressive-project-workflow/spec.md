## ADDED Requirements

### Requirement: Global and project workspace separation
The application SHALL expose only global modules when no project context is active. Project materials, topics and evidence, forecast execution, and results/history MUST be absent from the primary navigation until a project is selected and entered.

#### Scenario: Open the application without a project
- **WHEN** a user opens the dashboard, technology catalog, basic data center, or project list without a project ID
- **THEN** the primary navigation contains only the global workspace modules

#### Scenario: Enter a project
- **WHEN** a user chooses an active project and selects enter workflow
- **THEN** the application establishes URL-addressable project context and displays the project workspace navigation

### Requirement: Readiness-driven project workflow
The project workspace SHALL present the forecasting path as project overview, research materials, topics and evidence, forecast execution, and results/history. The backend readiness contract MUST provide each step's state, prerequisites, remediation, and target route.

#### Scenario: New project workflow
- **WHEN** a user enters a newly created project
- **THEN** project overview and research materials are available while later steps display their readiness state and unmet prerequisites

#### Scenario: Complete a workflow step
- **WHEN** a mutation satisfies the next step's prerequisites
- **THEN** refreshed readiness makes the next action available without relying on a separately maintained project status string

### Requirement: Project route guards
Project-scoped routes MUST validate project existence, lifecycle, and step readiness on direct navigation, refresh, and browser history traversal. Hiding navigation alone MUST NOT be treated as access control.

#### Scenario: Open a project route without project context
- **WHEN** a user directly requests a project-only route without a valid project ID
- **THEN** the application redirects to project selection with a clear explanation

#### Scenario: Open an unavailable future step
- **WHEN** a user directly requests a project step whose structural prerequisites are incomplete
- **THEN** the application shows the blocking prerequisites and a route to the current actionable step

#### Scenario: Open a historical result
- **WHEN** a user opens a valid completed job result for an archived or legacy project
- **THEN** the result remains readable even when editable workflow steps are unavailable

### Requirement: Project overview and data preflight
Every active project SHALL have an overview that displays selected technology scope, baseline, target year, cumulative forecast nodes, basic data coverage, current workflow step, and the single recommended next action.

#### Scenario: Project has incomplete historical data
- **WHEN** project scope lacks eligible data for one or more required historical periods
- **THEN** the overview identifies the missing periods and provides a technology-filtered entry to import or map basic data

#### Scenario: Project is ready for materials
- **WHEN** project scope is valid and no materials exist
- **THEN** the overview recommends adding research materials rather than exposing unrelated later actions

### Requirement: Consolidated topics and evidence workspace
Topic calibration and evidence review SHALL be presented as one project module with distinct internal stages. A user MUST be able to confirm topic names and technology associations, retrieve eligible evidence, review exclusions, and see per-topic readiness without switching between unrelated top-level modules.

#### Scenario: Calibrate an extracted topic
- **WHEN** a user confirms a topic name and one primary technology within project scope
- **THEN** the same workspace enables evidence retrieval for that topic

#### Scenario: Review retrieved evidence
- **WHEN** evidence retrieval completes
- **THEN** the workspace displays IPC, paper, material, and stage-analysis evidence with quality requirements and exclusion controls

### Requirement: Consolidated results and job history
Forecast progress, completed results, prior attempts, cancellation, retry, and artifact health SHALL be presented under one results/history module. The module MUST remain hidden or show no primary navigation entry until the project has at least one forecast job.

#### Scenario: First forecast starts
- **WHEN** the project creates its first forecast job
- **THEN** results/history becomes available and displays live progress for that job

#### Scenario: Open a prior attempt
- **WHEN** a project has multiple completed, failed, cancelled, or retried jobs
- **THEN** the user can select an attempt and inspect its immutable snapshot, status, results, and lineage from the same module

### Requirement: Separate workflow and lifecycle state
Project workflow stage SHALL be derived from current resources and jobs through readiness, while project lifecycle SHALL only represent whether the project is active or archived. Archiving MUST NOT overwrite workflow history or completed results.

#### Scenario: Archive a completed project
- **WHEN** a user archives a project with completed jobs
- **THEN** the project becomes read-only, disappears from active project selection, and retains its derived historical stage and results
