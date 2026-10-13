## 1. Database and Migration Foundations

- [x] 1.1 Add an additive SQLite migration for project/material/dataset lifecycle metadata and allowed lifecycle states without changing completed snapshots.
- [x] 1.2 Extend `forecast_jobs` with request checksum, unique idempotency key, parent job ID, progress/stage metadata, cancellation timestamps, terminal timestamps, structured error fields, and artifact health.
- [x] 1.3 Add and test the partial unique index that permits only one queued, running, or cancelling job per project.
- [x] 1.4 Add repository queries for resource reference impact, active jobs, job lineage, list/detail history, and safe lifecycle transitions.
- [x] 1.5 Implement a migration/reconciliation command that backs up the database, imports existing job directories, preserves completed results, and marks abandoned running jobs as interrupted failures.
- [x] 1.6 Add migration tests covering the current 2025 legacy projects, unmapped datasets, completed artifacts, and safe repeat execution.

## 2. Canonical Validation and Readiness

- [x] 2.1 Create shared backend validators for dataset versions, project metadata, lifecycle states, technology associations, confirmation tokens, and trimmed override reasons.
- [x] 2.2 Implement the canonical evidence requirement evaluator using only included items and incorporating IPC presence, year coverage, papers, paper fragments, and non-legacy historical periods.
- [x] 2.3 Derive score, sufficiency, requirement messages, remediation, and overrideability from the same weighted requirement collection so 100 always means sufficient.
- [x] 2.4 Implement project workflow progress and current-stage derivation from scope, materials, confirmed topics, per-topic readiness, and active/terminal jobs.
- [x] 2.5 Add versioned project/topic readiness response schemas and read endpoints, including active job and disabled-action reasons.
- [x] 2.6 Return recomputed package and project readiness after evidence exclusion or restoration and prevent mutation of frozen historical snapshots.
- [x] 2.7 Replace forecast-start gate calculations with the canonical readiness service and distinguish structural blockers from reasoned evidence overrides.
- [x] 2.8 Add backend tests for score/sufficiency equivalence, historical coverage, exclusion/restoration, multi-topic aggregation, legacy behavior, and strict/override gates.

## 3. Confirmation and Lifecycle APIs

- [x] 3.1 Implement a short-lived payload-bound confirmation preview/token service with expiry, mismatch, replay, and structured error handling.
- [x] 3.2 Add project edit, archive, restore, impact preview, and reference-safe transition endpoints.
- [x] 3.3 Add material edit, deactivate/restore, impact preview, and frozen-reference protection endpoints.
- [x] 3.4 Add dataset deprecate/restore and narrowly scoped draft deletion endpoints with committed-record, evidence, analysis, and snapshot reference checks.
- [x] 3.5 Add topic delete/archive/merge impact previews and require confirmation tokens while preserving existing soft-delete and snapshot behavior.
- [x] 3.6 Add transactional taxonomy edit support that commits parent move with other draft fields and records a unified change log entry.
- [x] 3.7 Add taxonomy archive/move/delete impact previews and confirmation enforcement with stable-ID and reference protections.
- [x] 3.8 Add legacy classification preview/commit APIs that return before/after technology paths, period and kind and validate active level-three selection.
- [x] 3.9 Standardize mutation success bodies and error envelopes across project, material, dataset, topic, technology, evidence, and classification writes.
- [x] 3.10 Add lifecycle and confirmation contract tests, including punctuation-only dataset version rejection and confirmation payload mismatch.

## 4. Forecast Job Control Plane

- [x] 4.1 Implement forecast start preview with topics, target nodes, enabled enhancements, workload estimate, optional configured price estimate, readiness, and override disclosure.
- [x] 4.2 Refactor forecast creation to recompute readiness, validate confirmation, reserve the job transactionally, and initialize immutable files using the reserved ID.
- [x] 4.3 Implement idempotent replay, conflicting-key rejection, and active-project-job conflict responses that identify the existing job.
- [x] 4.4 Persist runner stage/progress/status changes in SQLite and reconcile them with file-backed job progress and artifacts.
- [x] 4.5 Add project job list/detail endpoints that expose lineage, options, evidence limits, timestamps, errors, result availability, and degraded artifact health.
- [x] 4.6 Add cooperative cancellation endpoints and runner checks before every expensive round, roadmap, report, and asset boundary while retaining partial artifacts.
- [x] 4.7 Add retry preview and commit endpoints that revalidate readiness, identify snapshot differences, and create a new child job without editing the parent.
- [x] 4.8 Implement startup reconciliation that safely re-enqueues configured fully initialized queued jobs and marks prior running/cancelling jobs as `worker_interrupted` failures.
- [x] 4.9 Expand API/job/result schemas and project status derivation for `cancelling` and `cancelled` without breaking historical status reads.
- [x] 4.10 Add deterministic job tests for duplicate clicks, parallel requests, artifact initialization failure, history degradation, cancellation boundaries, retry lineage, and restart reconciliation.

## 5. Routing and Recoverable Frontend State

- [x] 5.1 Add React Router and define dashboard, technology, library, project workflow, job history, and job result routes with project/job identifiers.
- [x] 5.2 Replace `App.tsx` page-key state with route-aware project and job loaders plus explicit loading, not-found, archived, and degraded states.
- [x] 5.3 Restore queued/running polling and completed/partial result, chart, topic, and asset loading from a direct job URL after refresh.
- [x] 5.4 Add a project-scoped job history page with status, timestamps, evidence limitation, parent/retry links, reopen-result, cancel, and retry actions.
- [x] 5.5 Add an accessible current-project switcher that preserves equivalent workflow routes where valid and shows recorded baseline/target context.
- [x] 5.6 Replace dashboard hard-coded completion and baseline values with backend readiness and selected-project facts, keeping 2026 labeled only as a new-project default.
- [x] 5.7 Implement a shared dirty-form registry with guarded route/project navigation and `beforeunload`, then integrate technology, materials, imports, evidence configuration, and forecast options.
- [x] 5.8 Add compatibility redirects from prior root navigation behavior and verify browser back, forward, copied links, unknown IDs, and archived result routes.

## 6. Shared Mutation and Safety Components

- [x] 6.1 Extend the frontend API client with structured errors, request cancellation, field errors, and a mutation helper that suppresses duplicate submissions.
- [x] 6.2 Add shared pending button, inline validation, disabled-reason, success/error notification, and retryable load-error components.
- [x] 6.3 Replace the current modal with an accessible dialog supporting title association, initial focus, focus containment, Escape, pending protection, and focus restoration.
- [x] 6.4 Build reusable impact/confirmation and forecast-start confirmation dialogs that consume backend previews and payload-bound tokens.
- [x] 6.5 Migrate project, material, dataset, topic, taxonomy, evidence, and forecast writes to consistent pending, success, caught error, and confirmation flows.
- [x] 6.6 Make technology parent changes local draft state until the unified save action commits them.
- [x] 6.7 Replace legacy classification reuse of create-form defaults with independent dialog state and explicit before/after confirmation.
- [x] 6.8 Replace blur-saved `contentEditable` topic names with labeled edit, save, and cancel controls and add accessible names to row selection controls.
- [x] 6.9 Add explicit no-results states for IPC and paper queries and filtered technology searches, distinct from uninitialized empty collections.

## 7. Responsive Layout and Accessibility

- [x] 7.1 Introduce readable typography and contrast tokens, remove 7–10px supporting text usage, and document the minimum text hierarchy.
- [x] 7.2 Remove global body minimum widths and implement collapsible navigation, stacked forms/metrics, wrapped actions, and locally constrained dense content at 390px and 1024px.
- [x] 7.3 Convert project, material, dataset, topic, evidence, task, and result grids to semantic tables or responsive semantic card/table components with captions and headers.
- [x] 7.4 Keep enhancement checkboxes in the accessibility tree with native keyboard behavior and visible focus while retaining the switch appearance.
- [x] 7.5 Add `aria-current` to navigation, appropriate live regions to notifications, `aria-describedby` disabled explanations, and visible focus styles across controls.
- [x] 7.6 Add generated text summaries and semantic data alternatives for every forecast chart and verify dynamic target-year rendering.
- [x] 7.7 Audit all workflow pages at 390px and 1024px for document overflow, overlapping controls, truncated essential labels, keyboard order, and contrast regressions.

## 8. End-to-End Verification and Documentation

- [x] 8.1 Add Playwright configuration, deterministic seeded API fixtures or mocked runner mode, browser install instructions, and test scripts without invoking paid providers.
- [x] 8.2 Add an end-to-end happy path from project creation through materials, topics, evidence, confirmed forecast start, completion, and result reopening.
- [x] 8.3 Add end-to-end gate tests for insufficient evidence, required override reason, evidence exclusion recalculation, confirmation disclosure, and duplicate-click prevention.
- [x] 8.4 Add end-to-end history tests for refresh/deep links, queued/running recovery, completed results, cancellation, retry lineage, and missing artifact messaging.
- [x] 8.5 Add end-to-end safety tests for topic/taxonomy/resource confirmations, independent legacy classification, unified taxonomy save, malformed versions, and dirty navigation.
- [x] 8.6 Add keyboard and accessibility assertions for navigation, checkboxes, named row controls, dialogs, live notifications, semantic tables, chart alternatives, and focus restoration.
- [x] 8.7 Add 390px and 1024px responsive tests that assert no document-level horizontal overflow and capture traces/screenshots on failure.
- [x] 8.8 Run backend, TypeScript build, and Playwright suites; fix regressions while preserving existing legacy API and completed-result compatibility tests.
- [x] 8.9 Update README and workbench documentation with lifecycle states, readiness semantics, override audit behavior, task recovery/cancellation/retry, routes, migration, rollback, and test commands.
- [x] 8.10 Execute the migration against a copy of current local data and record verification that both 2025 legacy projects, unmapped datasets, and all existing result artifacts remain readable.
