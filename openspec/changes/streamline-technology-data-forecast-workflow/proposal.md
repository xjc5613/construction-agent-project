## Why

The workbench exposes taxonomy governance, dataset versioning, project setup, materials, topics, evidence, jobs, and results as peer modules even when no project is active. This makes the forecasting path difficult to understand, while the current evidence retrieval behavior can fall back to unrelated published data when a technology has no bound dataset, weakening the core promise that analysis is scoped to selected technologies.

## What Changes

- Separate the application into a small global workspace and a project-scoped forecasting workspace. Project-only modules are hidden until a project is selected and entered.
- Replace the permanent project module list with a readiness-driven workflow that exposes project overview, research materials, topics and evidence, forecast execution, and results/history at the appropriate time.
- Simplify technology management around the hierarchy and data coverage. Stable IDs, slugs, taxonomy versions, lifecycle history, and cross-domain relations move out of the primary researcher interface.
- Keep reversible technology deactivation for historical references, but present it as a secondary governance action and prevent ambiguous parent/child activation states.
- Make the basic data center technology-first: users select a technology and directly browse imported paper records, IPC indicator records, source files, coverage, and import status.
- Replace the create-dataset-first interaction with an import flow that selects technology and data type, previews records, validates/splits historical periods, creates the underlying dataset version, and publishes it.
- Automatically select evidence datasets from confirmed topic technology associations and the project scope. Advanced retrieval settings may narrow this set but may not expand beyond it.
- **BREAKING**: evidence retrieval no longer falls back to all published datasets when a technology has no eligible dataset, and explicitly supplied dataset IDs outside the project/topic technology scope are rejected.
- Migrate or explicitly quarantine legacy unbound datasets so their paper and IPC records cannot silently enter new technology-scoped forecasts.
- Preserve existing immutable job snapshots and completed results without rewriting historical technology or dataset references.

## Capabilities

### New Capabilities

- `technology-catalog-experience`: Simplified taxonomy browsing and editing, secondary lifecycle governance, effective parent/child activation, and technology data coverage visibility.
- `technology-bound-data-explorer`: Technology-first paper and IPC record browsing, guided import, generated dataset versions, period validation, and legacy mapping visibility.
- `progressive-project-workflow`: Global/project navigation separation, readiness-driven step availability, project overview, route guards, and consolidated results/history.
- `scoped-evidence-orchestration`: Strict project/topic technology scoping for dataset selection, evidence retrieval, stage analysis, readiness, and forecast snapshots.

### Modified Capabilities

None. The repository currently has no archived baseline capabilities under `openspec/specs`; the new capability specs consolidate and refine behavior from the completed but unarchived changes.

## Impact

- Frontend routing, application shell, dashboard, technology, library, projects, materials, topics, evidence, forecast, job history, and result pages.
- Technology, library, project, readiness, retrieval, stage-analysis, and forecast APIs and services.
- SQLite queries and additive migrations for effective taxonomy state, legacy dataset disposition, record-list filtering, and import metadata where required.
- Existing imported data requires a reviewed mapping or quarantine pass; current job snapshots and result artifacts remain read-only and compatible.
- Backend contract tests and Playwright journeys must be updated for navigation visibility, route gating, scoped retrieval, direct record browsing, imports, and historical result recovery.
