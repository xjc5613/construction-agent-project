## Context

The application is a local single-user FastAPI, SQLite, and React workbench. Three completed changes added a technology taxonomy, staged datasets, project-isolated materials and topics, evidence packages, forecast jobs, readiness, and recoverable routes. The resulting features are individually capable but are exposed as peer navigation modules, so users see project-only pages before entering a project and must understand internal dataset containers before importing or browsing evidence.

The intended data chain already exists in the schema: projects select a level-one technology, topics associate level-three technologies, and datasets bind to level-three technologies. The enforcement is incomplete. Evidence retrieval derives dataset IDs from topic technologies, but an empty list is subsequently treated as no filter; paper and IPC repository queries also accept no technology constraint. Current legacy data demonstrates the impact: most paper and IPC records are in published `needs_mapping` datasets, while the only mapped technology dataset is empty.

The change must preserve immutable evidence and job snapshots, legacy 2025 projects, file-backed results, local deployment, and the existing data model where IPC rows are annual indicators rather than individual patent documents.

## Goals / Non-Goals

**Goals:**

- Present a clear global workspace and reveal project workflow navigation only after a project is entered.
- Make one backend readiness contract authoritative for project steps, route availability, prerequisites, and the recommended next action.
- Let users browse paper and IPC indicator records directly by technology and import data without manually creating a dataset container first.
- Enforce one shared definition of eligible technology-bound data across import publication, coverage, topic extraction, stage analysis, evidence retrieval, readiness, and forecast snapshots.
- Keep lifecycle, audit, relation, and versioning capabilities for reproducibility while moving them out of the primary researcher flow.
- Quarantine or map existing unbound data without rewriting completed evidence packages or results.

**Non-Goals:**

- Adding individual patent-document storage, patent titles, applicants, claims, or application-number search.
- Removing dataset versions, source files, checksums, audit logs, or immutable snapshots from the backend.
- Replacing SQLite, introducing a distributed queue, or adding multi-user permissions.
- Automatically guessing technology mappings for legacy datasets without review.
- Recomputing completed forecasts under the new scope rules.

## Decisions

### 1. Split the shell into global and project workspaces

Global routes remain `/`, `/technologies`, `/library`, and `/projects`. Project routes remain addressable under `/projects/:projectId`, but the project shell presents:

```text
overview -> materials -> topics-and-evidence -> forecast -> results
```

The global shell does not render project navigation when no valid project is loaded. Entering a project first routes to its overview, not directly to materials. Topic calibration and evidence review become internal stages of one page; job history and result detail become views of one results module. Existing deep links receive redirects or compatibility route components so bookmarks are recoverable.

Alternative considered: keep all navigation items disabled. Rejected because disabled modules still imply that they are global peers and reproduce the current visual confusion.

### 2. Extend readiness to a versioned workflow-step contract

Readiness contract version 2 adds:

```json
{
  "steps": [
    {
      "id": "materials",
      "state": "available",
      "visible": true,
      "route": "/projects/{id}/materials",
      "blocking_reasons": [],
      "remediation": []
    }
  ],
  "recommended_action": {
    "step_id": "materials",
    "label": "添加研究材料",
    "route": "/projects/{id}/materials"
  }
}
```

Step state is derived from project scope, eligible data coverage, active materials, confirmed topic associations, evidence packages, and forecast jobs. The mutable `projects.status` column remains a compatibility projection during migration but no longer decides navigation or eligibility. `lifecycle_status` continues to mean only active or archived.

Frontend route guards consume this contract. Backend mutation and forecast endpoints retain their own structural validation; route guards are navigation behavior, not security.

Alternative considered: infer steps from frontend collections. Rejected because refreshes, direct API clients, exclusions, and job reconciliation would produce divergent state.

### 3. Introduce a shared eligibility resolver

A backend service resolves:

```text
project root
  -> effective active descendant level-three technologies
  -> confirmed topic technology associations
  -> active + mapped + published datasets
  -> type-specific committed valid records
  -> optional user narrowing
```

The resolver returns eligible technology IDs, dataset IDs, excluded candidates with reasons, coverage by period/type, and a deterministic scope checksum. It is used by project coverage, topic extraction, stage analysis, evidence retrieval, readiness, and forecast snapshot creation.

An empty resolved dataset set is an explicit empty set, never an omitted filter. Repository methods receive dataset IDs as a tri-state contract: `None` means an intentionally unscoped administrative query, while an empty collection means return no rows. Project services never pass `None`.

Client-provided dataset IDs are intersected with the eligible set only after validating that every requested ID is eligible; foreign IDs produce a validation error rather than being silently ignored.

Alternative considered: add technology filters independently to each query. Rejected because separate filters would drift and would not solve consistent coverage/readiness semantics.

### 4. Count eligible records, not dataset containers

A dataset version satisfies coverage only when it is active, mapped, published, and has at least one committed valid record of the required public type. Integrated datasets satisfy each channel according to their committed components and records.

Coverage responses include record counts, dataset counts, periods, technology paths, and exclusion reasons. Empty published datasets therefore remain visible administratively but do not satisfy readiness.

Alternative considered: retain container-based coverage and add a warning. Rejected because readiness would still claim evidence exists when retrieval returns nothing.

### 5. Keep datasets as internal reproducibility units

The UI centers on technology records, but datasets remain the versioned ownership and provenance boundary. New paginated record APIs support technology scope, period, dataset, status, year, and query filters:

```text
GET /api/library/papers
GET /api/library/ipc/trends
GET /api/library/technologies/{nodeId}/summary
GET /api/library/imports
```

Existing paper and IPC endpoints are extended rather than duplicated. Their default administrative behavior remains available only when explicitly requested without project context. Responses include pagination and technology/dataset/source provenance.

The guided import endpoint accepts technology, public kind, files, and optional advanced version metadata. Staging infers record periods and proposes one or more dataset targets. Commit transactionally creates/resolves draft versions and writes records; publication remains explicit or can be included in the reviewed commit when all gates pass. Generated versions use a deterministic date-and-sequence format and still pass the existing validator.

Alternative considered: remove versioning and import directly into technology tables. Rejected because evidence snapshots require stable dataset versions and source provenance.

### 6. Use effective taxonomy activation

A node is effectively active only when it and every ancestor are active. Recursive taxonomy queries expose `effective_status` and all selectors and eligibility resolution use it. Deactivating a parent previews affected descendants and requires explicit cascade-impact confirmation, but descendant own statuses are not overwritten. Restoring the parent therefore restores descendants whose own status remained active, while explicitly inactive descendants remain inactive.

The primary technology page shows the hierarchy, effective state, and data coverage. Description, keywords, and aliases move to advanced editing. Relations, stable IDs, versions, references, and change history move to advanced governance but retain current APIs.

Alternative considered: write `archived` to every descendant. Rejected because it destroys the distinction between inherited and explicit deactivation and complicates correct restoration.

### 7. Quarantine legacy unbound data before strict retrieval

Eligibility requires `migration_status='mapped'`; current `legacy`, `needs_mapping`, and `needs_split` datasets are treated as quarantined regardless of publication status. A migration report lists record counts and suggested administrative actions but does not auto-assign technologies.

The mapping flow validates level-three effective activation, period boundaries, public type, and duplicate version identity. A cross-period legacy dataset remains `needs_split` until a reviewed split creates mapped period-specific versions. Original records and source files are preserved for audit.

Completed packages and job snapshots continue to resolve their recorded evidence IDs and dataset metadata even if those datasets are quarantined for new work.

### 8. Freeze resolved scope in new forecast snapshots

New evidence packages record resolver output and scope checksum in their query metadata. Forecast start recalculates readiness and freezes the project root, topic associations, eligible and selected datasets, technology paths, taxonomy versions, dataset versions, filters, evidence IDs, and checksums.

Historical snapshots retain their original contract version. Result rendering reads the frozen snapshot and does not apply current effective activation or mapping rules.

## Risks / Trade-offs

- [Strict scoping initially leaves new projects with little usable evidence] -> Surface exact missing technologies and periods, provide filtered import/mapping links, and migrate data before making strict retrieval the default.
- [Effective status changes current behavior for active children of an archived parent] -> Produce a migration report, show affected descendants in preview, and test selectors and snapshots against inherited inactivity.
- [A larger readiness contract increases API and UI coordination] -> Version the contract, keep a compatibility projection, and migrate route groups behind shared adapters.
- [Automatic period splitting can create several dataset versions from one file] -> Require a preview that shows target periods, record counts, and generated versions before commit.
- [Combining topics and evidence can create a dense page] -> Keep separate internal stages and topic-level panels while removing only the top-level navigation boundary.
- [Record browsing may be slow as imports grow] -> Add server-side pagination, indexed dataset/year/code filters, bounded text search, and avoid returning paper chunks in list responses.
- [Legacy mapping can assign a broad dataset to one technology incorrectly] -> Never auto-commit mappings; preserve quarantine and support reviewed splitting.

## Migration Plan

1. Back up `var/library/index/library.sqlite3` and inventory technology states, dataset mapping states, record counts, projects, packages, jobs, and file artifacts.
2. Add indexes or additive metadata required for paginated record queries and import disposition; do not remove existing columns or statuses.
3. Introduce the effective taxonomy query and shared eligibility resolver behind tests, then update coverage and readiness to consume it.
4. Mark all non-mapped datasets ineligible for new project retrieval and generate a migration report. Map or split reviewed legacy datasets before enabling strict retrieval in the UI.
5. Extend paper, IPC, import, coverage, and readiness APIs while retaining compatibility fields and old routes.
6. Add project overview and workspace routing, then migrate navigation, topics/evidence, forecast, and results/history page groups incrementally.
7. Enable strict evidence validation and scope snapshotting after the data explorer and remediation links are available.
8. Run backend contract tests and Playwright workflows covering empty data, mapped data, direct routes, archived projects, legacy results, import splitting, and foreign dataset rejection.
9. Roll back by restoring the database backup and prior application version. Additive indexes and metadata may remain, but do not roll back after new imports without first exporting or preserving their generated dataset versions.

## Open Questions

- Whether a guided import should publish automatically after a clean preview or retain an explicit publish confirmation; the conservative default is explicit publication.
- Whether the project overview should block material entry when historical coverage is incomplete or allow materials while marking later evidence/forecast steps incomplete; the recommended default is to allow materials and block only evidence sufficiency.
- Whether individual patent-document ingestion will be proposed separately; this change intentionally labels and lists the existing aggregate IPC indicator records.
