## Why

The research workflow currently exposes contradictory evidence readiness signals, permits duplicate or insufficiently reviewed forecast starts, and loses task and page state after refresh. Resource lifecycle gaps, unguarded destructive actions, inaccessible controls, and missing end-to-end coverage make the workbench unsafe for repeatable long-running research.

## What Changes

- Make the backend the single source of truth for workflow readiness, evidence quality requirements, progress, and forecast-start eligibility.
- Recalculate evidence quality after review changes and require either sufficient evidence or an explicit, reasoned override before a forecast can start.
- Add forecast cost disclosure, confirmation, idempotent submission, active-job duplicate prevention, history, recovery, cooperative cancellation, and retry.
- Complete project, material, and dataset lifecycle operations with reference-aware archive, deprecate, restore, and narrowly scoped deletion rules.
- Replace implicit legacy dataset classification with a dedicated review dialog that shows before/after values and requires explicit confirmation.
- Guard topic deletion, archive, merge, taxonomy archive, and taxonomy moves; make technology edits follow one draft-and-save interaction model.
- Add URL-addressable pages carrying project and job identifiers, project switching, refresh/result recovery, and unsaved-change protection.
- Replace hard-coded dashboard progress and baseline text with backend-derived workflow summaries based on the selected project.
- Make layouts responsive down to 390px, raise minimum readable text sizes and contrast, and add semantic tables, accessible controls, dialogs, live notifications, and chart alternatives.
- Standardize write-operation validation, loading, duplicate-submit protection, error reporting, and success feedback.
- Introduce backend contract tests and Playwright end-to-end, responsive, recovery, and accessibility coverage.

## Capabilities

### New Capabilities

- `workflow-readiness-gating`: Canonical evidence requirements, score semantics, project progress, disabled reasons, override policy, and atomic forecast-start eligibility.
- `resource-lifecycle-governance`: Reference-aware editing, archive/deprecation, restore and deletion behavior for projects, materials, datasets, topics, and taxonomy data, including safe legacy classification.
- `forecast-job-operations`: Persistent project job history, result recovery, idempotent starts, active-job exclusion, cancellation, retry, and restart reconciliation.
- `recoverable-workbench-navigation`: URL-addressable project workflow pages, project switching, browser navigation, refresh restoration, and unsaved-change protection.
- `safe-accessible-workbench`: Confirmation and feedback conventions, responsive layouts, readable presentation, accessible semantics and interactions, chart alternatives, and UI test requirements.

### Modified Capabilities

None. Existing capability specifications have not yet been archived into `openspec/specs`; this change introduces explicit hardening contracts without mutating completed change artifacts.

## Impact

- Backend: FastAPI project, library, technology, evidence, and forecast APIs; SQLite schema and migrations; job storage and runner coordination; shared validation and readiness services.
- Frontend: application routing and state restoration, project context, dashboard, library, materials, topics, technology, evidence, forecast, results, shared form/dialog/table/notification components, charts, and responsive styles.
- Data: additive lifecycle, job lineage, idempotency, cancellation, and readiness fields plus migration/reconciliation for existing 2025 legacy projects and on-disk jobs.
- Dependencies: React Router and Playwright tooling; no external database or distributed queue is introduced.
- Compatibility: existing completed snapshots remain immutable and readable; legacy projects retain their recorded baseline instead of being relabeled as 2026.
