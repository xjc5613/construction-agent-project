## Context

The workbench is a single-user local research application built with FastAPI, SQLite, file-backed forecast artifacts, and a React single-page frontend. Two completed changes introduced project isolation, evidence packages, technology taxonomy, staged datasets, and cumulative forecasts, but the control plane remains split across frontend memory, persisted SQLite rows, and per-job JSON files.

Evidence quality currently has independent score and sufficiency algorithms. Evidence exclusions do not recalculate the stored quality object, frontend eligibility is inferred from topic status, and forecast creation does not reserve an active-job slot or accept an idempotency key. A process-global runner lock serializes execution, but queued jobs can be submitted repeatedly and there is no history, cancellation, retry, or restart reconciliation.

Projects, materials, and datasets have partial lifecycle APIs; risky taxonomy and topic operations are immediate. Frontend navigation is an in-memory page key, so project and result context disappears on reload. Existing layouts force a desktop minimum width and use small, low-contrast text and non-semantic interactive structures.

The primary stakeholder is a researcher who needs reproducible evidence-bound predictions and must be able to understand why an action is blocked, recover completed work, and avoid accidental or duplicate model runs. The implementation must preserve local deployment, existing 2025 legacy projects, completed evidence snapshots, and existing result artifacts.

## Goals / Non-Goals

**Goals:**

- Establish one backend-owned readiness contract for evidence quality, workflow progress, gate reasons, and forecast eligibility.
- Make forecast submission atomic, idempotent, recoverable, cancellable at safe boundaries, and retryable with lineage.
- Complete resource lifecycle operations without invalidating frozen evidence or historical forecast results.
- Make legacy classification and other consequential mutations explicit and reviewable.
- Make page, project, job, and result state addressable and recoverable from URLs.
- Provide consistent mutation feedback, validation, responsive behavior, and accessible semantics.
- Cover critical contracts and complete workflows with automated backend and browser tests.

**Non-Goals:**

- Introducing a distributed queue, external database, multi-user authorization, or collaborative editing.
- Cancelling an in-flight external model HTTP request; cancellation is cooperative between durable forecast stages.
- Rewriting completed evidence snapshots or recalculating historical forecast outputs.
- Guaranteeing full feature parity on very small screens for dense visualizations; summaries and data alternatives remain available.
- Reporting exact monetary cost when provider pricing and token usage are unavailable. The confirmation displays a deterministic workload estimate and any configured pricing estimate.

## Decisions

### 1. A canonical readiness service owns quality and workflow decisions

Add a backend service that returns a versioned `WorkflowReadiness` representation for a project and, where relevant, each selected topic:

```json
{
  "contract_version": 1,
  "project_id": "project_...",
  "progress_percent": 64,
  "current_stage": "evidence_review",
  "requirements": [
    {
      "id": "paper_count",
      "label": "相关论文",
      "actual": 1,
      "required": 2,
      "passed": false,
      "blocking": true,
      "remediation": "补充论文数据或调整检索范围"
    }
  ],
  "evidence": {
    "score": 75,
    "sufficient": false,
    "state": "override_required"
  },
  "forecast": {
    "can_start": false,
    "can_override": true,
    "blocking_reasons": [],
    "override_reasons": ["至少2篇相关论文"],
    "active_job_id": null
  }
}
```

The evidence score is computed from the same normalized requirements that determine sufficiency. Each requirement contributes its configured weight only when passed, and the score reaches 100 only when every blocking evidence requirement passes. Historical-period coverage is part of this requirement set for non-legacy projects. Legacy projects use their recorded contract and visibly identify unavailable requirements rather than being relabeled.

Quality is evaluated from non-excluded items at read and start time. Stored package quality is treated as an auditable retrieval-time observation, not as authority after review mutations. Evidence item mutation returns updated readiness so the frontend cannot retain a stale gate.

Project progress is a weighted state summary derived from actual resources: scope, material readiness, confirmed topic associations, per-topic evidence readiness, and terminal/active job state. It is not inferred solely from project existence or a mutable status string.

Alternative considered: keep the score informational and gate separately. Rejected because users reasonably interpret 100 as complete and every consumer would still need to reconcile two contracts.

### 2. Forecast creation is a database reservation followed by artifact initialization

SQLite becomes authoritative for forecast job identity, project association, status, idempotency, lineage, cancellation request, timestamps, and snapshot checksum. Per-job files remain authoritative for immutable snapshots and generated artifacts.

Forecast creation executes as follows:

1. Recompute readiness for the submitted topic IDs.
2. Validate override selection and a trimmed reason when readiness is overrideable but insufficient.
3. In one transaction, resolve the idempotency key and reserve the project's active-job slot.
4. Write the evidence snapshot and initial job file using the reserved job ID.
5. Persist the snapshot checksum and enqueue the local worker thread.

The database adds a unique idempotency key and a partial unique index allowing at most one `queued`, `running`, or `cancelling` job per project. Repeating the same key and equivalent payload returns the original job. Reusing the key for a different payload is a conflict. A different key while a project has an active job returns the active job identifier and a user-readable conflict.

If artifact initialization fails, the reservation is marked failed with a structured error; it is not silently deleted. This preserves auditability and releases the active-job uniqueness constraint.

Alternative considered: frontend-only button disabling. Rejected because refreshes, multiple tabs, retries, and direct API clients bypass it.

### 3. Job history and recovery use explicit state transitions

The supported state machine is:

```text
queued -> running -> completed | partial_failed | failed
   |         |
   +------> cancelling -> cancelled

failed | partial_failed | cancelled -> retry (new job with parent_job_id)
```

Cancellation sets `cancel_requested_at` and `cancelling`; the runner checks before starting each expensive stage and before asset/report generation. It records `cancelled` at the next safe boundary without deleting partial artifacts. Completed and already failed jobs reject cancellation.

Retry creates a new job with a new idempotency key and `parent_job_id`; it revalidates current project readiness and creates a new snapshot. It never edits or resumes the old snapshot. The UI explains when current evidence differs from the original job.

On application startup, queued jobs with complete initialization can be enqueued. Jobs left in `running` or `cancelling` from a prior process are marked failed with `worker_interrupted` and remain retryable. Automatic resumption of an interrupted model stage is avoided because the external call may already have incurred cost.

List and detail APIs join SQLite metadata with file-backed progress/results. Missing or corrupt artifact files produce an explicit degraded record instead of omitting the job.

### 4. Lifecycle policy is reference-aware and favors reversible transitions

Resources receive explicit lifecycle metadata and endpoints:

- Projects: edit name/description, archive, restore. A project with any forecast job is not hard-deleted.
- Materials: edit text metadata/content and soft-delete while no frozen snapshot references the material. Referenced materials can be hidden from future extraction but their stored content remains available to historical snapshots.
- Datasets: draft, published, deprecated, failed. Deprecation removes the dataset from new retrieval while preserving references. Hard deletion is limited to drafts with no committed records, evidence items, stage analyses, or snapshots.
- Topics: existing soft deletion/archive/merge remains, but APIs return impact summaries and require confirmation tokens for consequential transitions.
- Taxonomy: archive/move operations return reference impact; referenced nodes archive rather than hard-delete. Moves remain stable-ID changes and are committed with the rest of the edit draft.

Lifecycle services validate transitions and references in transactions. The frontend never decides whether hard deletion is safe.

Alternative considered: expose hard delete for every resource with a confirmation dialog. Rejected because confirmation cannot protect reproducibility when snapshots or evidence cite the resource.

### 5. Consequential changes use preview-and-confirm contracts

Archive, deletion, merge, taxonomy move, legacy classification, and forecast start use a two-step interaction. A preview computes affected references, before/after values, warnings, and a short-lived confirmation token bound to the payload. Commit endpoints validate the token and payload before applying the mutation.

Legacy dataset classification has independent dialog state initialized from the selected dataset, not from the create-dataset form. It displays the old and proposed technology path, historical period, and kind. The commit validates that the selected node is active and level 3 and that the period, kind, and version conform to backend validators.

Forecast confirmation shows topic count, target nodes, enabled enhancements, workload/cost estimate, evidence-limited status, and override reason. The start button remains disabled until the confirmation is accepted.

For low-impact edits such as project description changes, a normal validated save is sufficient; no preview token is required.

### 6. Shared validation and mutation envelopes standardize write behavior

Pydantic models and repository invariants share named validators for dataset versions, project fields, lifecycle states, technology associations, and override reasons. Dataset versions use a documented conservative pattern such as alphanumeric segments separated by `.`, `-`, or `_`; punctuation-only values are rejected.

All write APIs return either the updated resource/readiness or a consistent error body containing a stable code, user message, field errors, and optional remediation. Frontend mutation helpers provide pending state, duplicate-click suppression, success notification, inline field errors, and caught failure reporting. Page effects also handle failures and cancellation to prevent unhandled promises and stale state updates.

### 7. React Router owns recoverable application context

Introduce route patterns such as:

```text
/
/technologies
/library
/projects
/projects/:projectId/materials
/projects/:projectId/topics
/projects/:projectId/evidence
/projects/:projectId/forecast
/projects/:projectId/jobs
/projects/:projectId/jobs/:jobId/results
```

Loaders or route effects fetch project and job state from identifiers. The selected project is therefore derived from the URL; optional local storage only remembers a convenience default and is never authoritative. Browser back/forward and direct links restore the correct page. An unknown or archived project displays a recoverable error with a route back to project selection.

A project switcher navigates explicitly and checks a shared dirty-form registry. Materials, technology edits, import mappings, evidence configuration, and forecast configuration register dirty state. Navigation, project switching, and `beforeunload` prompt when state would be lost. Successful save/reset clears the registration.

Alternative considered: persist all component state to local storage. Rejected because it creates stale drafts and does not make pages shareable or server-verifiable.

### 8. Accessibility and responsive behavior are component-level contracts

Shared components provide semantic tables with captions/headers, accessible empty states, button disabled explanations, live notifications, and dialogs with `role="dialog"`, accessible names, initial focus, focus containment, Escape handling, and focus restoration. Native checkboxes remain in the accessibility tree using visually-hidden styling rather than `display:none`. Inline topic editing becomes a labeled input with explicit save/cancel.

The global body minimum width is removed. At narrow widths the navigation collapses, forms and metric grids stack, action groups wrap, and dense tables use either a card presentation or a locally scrollable semantic table. No page may create document-level horizontal overflow at 390px. Core and secondary text have minimum size/contrast tokens appropriate for sustained use.

Charts include a concise generated text summary and an accessible data table or downloadable equivalent representing the same essential values.

Disabled actions expose their reason adjacent to the control and through `aria-describedby`; a disabled button is not the only indication of an unmet prerequisite.

### 9. Verification combines contract tests and Playwright journeys

Backend tests cover score/sufficiency equivalence, recalculation after exclusions, override rules, atomic idempotency, active-job uniqueness, cancellation boundaries, retry lineage, startup reconciliation, lifecycle reference protection, classification validation, and migration of existing data.

Playwright covers the complete project journey, blocked and overridden forecast starts, duplicate clicks, refresh and deep-link recovery, task history/result reopening, cancellation/retry, destructive confirmation, dirty navigation, empty search states, keyboard-only dialog/control operation, accessible names/live regions, and 390px/1024px layouts.

Tests use deterministic mocked runners and seeded evidence; they do not invoke paid model providers.

## Risks / Trade-offs

- [Existing package scores change after migration] → Keep retrieval-time quality for audit, expose the new contract version, and recompute operational readiness without rewriting completed snapshots.
- [SQLite and job files become temporarily inconsistent] → Reserve identity in SQLite first, record initialization failure, reconcile files on startup, and surface degraded history records.
- [Cancellation is not immediate during an external request] → Label cancellation as cooperative and check at every durable stage boundary.
- [A single active job per project limits deliberate parallel experiments] → Require separate projects for parallel runs; this matches project-scoped evidence and prevents accidental cost duplication.
- [Confirmation tokens add API complexity] → Restrict them to consequential operations and centralize token generation/validation.
- [Responsive conversion can reduce dense-table scan efficiency] → Preserve semantic desktop tables and switch to cards or local scrolling only at constrained widths.
- [Dirty-form interception can become noisy] → Register only user-modified values, clear on successful mutations, and allow explicit discard.
- [New routing dependency touches most pages] → Migrate routes incrementally behind a shared project loader and retain redirects from the root in-memory entry behavior.

## Migration Plan

1. Add additive schema migrations for lifecycle timestamps/statuses, job idempotency and lineage, cancellation fields, structured errors, and indexes. Back up the SQLite file before migration.
2. Reconcile current forecast job directories into SQLite. Preserve completed artifacts; classify incomplete running jobs as interrupted/failed and retryable.
3. Add readiness and lifecycle APIs while retaining existing endpoints as compatibility adapters with deprecation headers.
4. Move forecast start to reservation/idempotency flow and update the runner for cancellation and status reconciliation.
5. Introduce routing, server restoration, shared mutation/dialog/form primitives, then migrate pages one workflow stage at a time.
6. Apply responsive and accessibility changes and add browser tests before removing compatibility navigation.
7. Rollback by deploying the prior application against the backed-up database. Additive columns remain harmless; do not roll back after new lifecycle states have been relied upon without first mapping them to legacy states.

## Open Questions

- Whether configured model pricing is sufficiently reliable to show currency; otherwise the first implementation will display estimated model-call and sampling counts only.
- Whether interrupted queued jobs should auto-start on boot by default or require explicit local configuration; the safe default is to resume only fully initialized queued jobs and never resume running stages.

