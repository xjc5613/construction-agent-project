## 1. Migration and Compatibility Foundations

- [x] 1.1 Add a pre-migration inventory command that reports taxonomy states, mapped/unmapped datasets, paper and IPC record counts, projects, evidence packages, jobs, and artifact paths.
- [x] 1.2 Add additive SQLite migrations and indexes needed for technology-scoped paper/IPC pagination, import disposition queries, and effective-status lookups.
- [x] 1.3 Add a legacy dataset migration report that classifies every non-mapped dataset as requiring mapping or splitting without changing its records or source files.
- [x] 1.4 Add migration fixtures covering the current archived-parent hierarchy, empty mapped dataset, unbound paper data, unbound IPC data, legacy projects, and historical results.
- [x] 1.5 Document database backup, migration preview, apply, rollback, and post-migration verification commands.

## 2. Effective Technology Catalog

- [x] 2.1 Extend taxonomy repository queries with recursive effective activation based on each node and all ancestors.
- [x] 2.2 Update technology trees, descendants, selectors, project scopes, and dataset validation to use effective activation.
- [x] 2.3 Extend technology lifecycle preview to list affected descendants, references, and inherited-state impact.
- [x] 2.4 Require explicit confirmation when deactivating a node with active descendants while preserving descendant own statuses.
- [x] 2.5 Add a technology summary API returning path, effective state, child count, active dataset count, paper count, IPC record count, and project references.
- [x] 2.6 Add repository and API tests for inactive parents, explicitly inactive children, restoration, selectors, references, and historical snapshot access.

## 3. Canonical Dataset Eligibility

- [x] 3.1 Implement a shared eligibility resolver for project roots, topic technology associations, effective technology states, dataset lifecycle, mapping, publication, committed records, and periods.
- [x] 3.2 Return eligible and excluded technology/dataset IDs, exclusion reasons, per-period record coverage, provenance metadata, and a deterministic scope checksum.
- [x] 3.3 Change paper, IPC metric, and IPC fusion repository filters so `None` means intentional administrative scope and an empty ID collection returns no rows.
- [x] 3.4 Validate that topic technology associations are effective level-three descendants of the project root and reject out-of-scope associations.
- [x] 3.5 Remove automatic fallback assignment to the first project technology when topic extraction finds no meaningful match.
- [x] 3.6 Use the eligibility resolver for stage dataset summaries attached during topic extraction.
- [x] 3.7 Use the eligibility resolver for project coverage and count valid committed records instead of dataset containers.
- [x] 3.8 Use the eligibility resolver for stage-analysis inputs and preserve exclusion reasons when required periods have no records.
- [x] 3.9 Use the eligibility resolver in evidence retrieval, reject foreign requested dataset IDs, and remove all-dataset fallback behavior.
- [x] 3.10 Store eligible/selected datasets, technology paths, versions, filters, and scope checksum in new evidence packages and forecast snapshots.
- [x] 3.11 Add contract tests for empty eligible sets, unbound legacy records, foreign IDs, empty published datasets, mapped records, cross-scope topics, and immutable legacy results.

## 4. Technology-Bound Data APIs and Import

- [x] 4.1 Add shared pagination response schemas and bounded filter validation for library record endpoints.
- [x] 4.2 Extend the paper list endpoint with technology scope, period, year, dataset, lifecycle/status, text query, and pagination filters.
- [x] 4.3 Include paper technology path, dataset version, source file, parse status, and provenance in list/detail responses without returning full chunks in list rows.
- [x] 4.4 Extend the IPC metric list endpoint with technology scope, period, year range, IPC code, dataset, lifecycle/status, and pagination filters.
- [x] 4.5 Include IPC technology path, dataset version, source file, source row, patent count, growth, and centrality provenance in list responses.
- [x] 4.6 Add technology-scoped source-file and import-history listing with eligibility and remediation reasons.
- [x] 4.7 Implement guided import staging that accepts technology, public kind, files, and optional advanced version metadata without a pre-created dataset ID.
- [x] 4.8 Infer historical periods from staged records and generate a reviewed split plan for files spanning multiple supported periods.
- [x] 4.9 Generate valid unique date-and-sequence dataset versions when no advanced version is supplied.
- [x] 4.10 Implement transactional guided-import commit that creates or resolves draft datasets, writes records and provenance, and returns publication readiness.
- [x] 4.11 Keep publication explicit and validate mapped technology, periods, committed records, component requirements, and duplicate version identity before publishing.
- [x] 4.12 Update legacy mapping/splitting endpoints to preserve original records and make mapped outputs eligible only after all publication rules pass.
- [x] 4.13 Add API tests for unqueried record browsing, filters, pagination, provenance, single-period imports, split imports, duplicate versions, publication, and quarantine.

## 5. Readiness V2 and Workflow Contracts

- [x] 5.1 Extend readiness schemas with versioned project steps, visibility, availability, routes, blocking reasons, remediation, and recommended action.
- [x] 5.2 Derive project overview, materials, topics/evidence, forecast, and results step states from scope, eligible coverage, materials, topics, evidence, and jobs.
- [x] 5.3 Keep project lifecycle separate from derived workflow stage and retain `projects.status` only as a compatibility projection.
- [x] 5.4 Return technology-scoped data gaps and filtered import/mapping routes in project overview readiness.
- [x] 5.5 Refresh readiness after material, topic, evidence, dataset publication, lifecycle, and job mutations that can change workflow availability.
- [x] 5.6 Add readiness tests for new projects, missing coverage, materials without topics, unassigned topics, evidence gaps, active jobs, completed jobs, archived projects, and legacy projects.

## 6. Global and Project Navigation

- [x] 6.1 Update frontend types and API adapters for effective technology state, paginated records, eligibility summaries, and readiness v2.
- [x] 6.2 Split the application shell into global navigation and conditional project workspace navigation.
- [x] 6.3 Hide materials, topics/evidence, forecast, and results/history navigation when no valid project context is loaded.
- [x] 6.4 Add `/projects/:projectId/overview` and route project creation/entry to the overview instead of directly to materials.
- [x] 6.5 Build a shared project route guard that handles missing projects, archived write routes, unavailable future steps, refresh, and browser history.
- [x] 6.6 Preserve compatibility redirects from existing topics, evidence, jobs, and result deep links to their consolidated project destinations.
- [x] 6.7 Add a project overview page showing scope, baseline, target, forecast nodes, eligible data coverage, workflow progress, and one recommended next action.
- [x] 6.8 Update project selection to show active projects by default and provide a separate historical/archived view.

## 7. Technology and Basic Data Interfaces

- [x] 7.1 Refactor technology management around the hierarchy, effective status, child counts, and concise data coverage.
- [x] 7.2 Move stable IDs, slugs, versions, relations, reference impact, and change logs into an advanced governance panel.
- [x] 7.3 Move descriptions, keywords, and aliases into an advanced matching-settings editor while preserving their topic-matching behavior.
- [x] 7.4 Replace the basic data landing page with a technology tree/filter and summary for the selected technology scope.
- [x] 7.5 Add paper, IPC indicator, source file, import history, and coverage tabs backed by paginated APIs.
- [x] 7.6 Add paper and IPC detail views with dataset, technology, source-file, and parse provenance.
- [x] 7.7 Label IPC rows as aggregate IPC/patent-indicator data and avoid individual-patent terminology unsupported by the schema.
- [x] 7.8 Build the guided import wizard for technology/type selection, upload, preview, period split, generated versions, commit, and explicit publication.
- [x] 7.9 Add administrative filters and remediation actions for draft, failed, deprecated, unmapped, quarantined, and split-required imports.
- [x] 7.10 Add frontend tests for catalog simplification, inherited inactivity, direct record browsing, pagination, empty states, import preview/split, publication, and legacy mapping.

## 8. Consolidated Project Forecasting Experience

- [x] 8.1 Combine topic calibration and evidence review into one route with separate internal calibration and evidence stages.
- [x] 8.2 Restrict topic technology selectors to effective level-three technologies within the active project scope.
- [x] 8.3 Display eligible dataset coverage and missing-data remediation per topic before evidence retrieval.
- [x] 8.4 Remove the unrestricted all-library dataset selector and replace it with optional narrowing over eligible versions only.
- [x] 8.5 Drive forecast availability and disabled explanations exclusively from readiness v2 while retaining backend start validation.
- [x] 8.6 Combine job progress, task history, retry/cancel controls, result selection, artifact health, and result detail under results/history.
- [x] 8.7 Hide results/history navigation until at least one project job exists while preserving direct historical result links.
- [x] 8.8 Enforce read-only project workflow behavior for archived projects without changing completed results or job snapshots.
- [x] 8.9 Update dashboard and materials actions to link into the project overview and technology-filtered remediation flow.

## 9. End-to-End Verification and Documentation

- [x] 9.1 Add Playwright coverage for global-only navigation, project entry, step gating, direct unavailable routes, refresh, back/forward, and archived historical results.
- [x] 9.2 Add a provider-free end-to-end journey from technology-bound import through project overview, materials, topics/evidence, forecast, and results/history.
- [x] 9.3 Add a regression journey proving an empty eligible dataset set cannot retrieve records from unrelated or unbound datasets.
- [x] 9.4 Add responsive and keyboard checks for the technology tree, data tabs, import wizard, project step navigation, combined topics/evidence, and results/history.
- [x] 9.5 Update README and data-import, taxonomy, workflow, migration, and evidence-scope documentation to match the simplified user flow.
- [x] 9.6 Run backend tests, frontend build, Playwright suites, OpenSpec validation, and a migration dry run against a copied current database.
