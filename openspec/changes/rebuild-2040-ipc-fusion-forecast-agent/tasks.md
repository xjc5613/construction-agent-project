## 1. Baseline Inventory and Contract Foundations

- [x] 1.1 Add a read-only pre-change inventory command for databases, datasets, source files, periods, mapping states, projects, jobs, snapshots, and result assets.
- [x] 1.2 Add fixtures that represent the current 2026-baseline contract, mapped and unmapped datasets, partial results, and completed legacy snapshots.
- [x] 1.3 Define versioned constants and schemas for research contract v3 with baseline 2025, periods 2010-2014/2015-2019/2020-2025, and target nodes 2030/2035/2040.
- [x] 1.4 Add compatibility readers that resolve periods, baseline, and target nodes from each snapshot's stored contract version instead of current defaults.
- [x] 1.5 Add validation that prevents new v3 projects from selecting a 2026 baseline or legacy period codes.
- [x] 1.6 Add unit and API contract tests for v3 project creation, cumulative forecast nodes, and legacy result rendering.

## 2. Evidence and Provenance Database Schema

- [x] 2.1 Add additive schema migrations for canonical patents with publication number, text, year, applicant type, legal status, and source provenance.
- [x] 2.2 Add patent-to-IPC assignment tables preserving raw code, normalized code, analysis level, IPC edition, and mapping status.
- [x] 2.3 Add temporal coverage tables for source cutoff, expected and observed coverage, completeness, and researcher notes by dataset and year.
- [x] 2.4 Extend paper records with controlled paper type, source database, publication date, citation count, and citation observation date.
- [x] 2.5 Add versioned IPC code-mapping tables and repository operations without overwriting raw source codes.
- [x] 2.6 Add network run, network node, annual edge, reporting-period edge, node-transition, and community-membership tables with checksums and algorithm metadata.
- [x] 2.7 Add feature run, model run, candidate pair, prediction, calibration, fold metric, ablation, sensitivity, and publication-gate tables.
- [x] 2.8 Add graph thread/checkpoint references, node-event, human-review, prompt manifest, model manifest, and export manifest tables.
- [x] 2.9 Add indexes and uniqueness constraints for temporal queries, patent/IPC provenance, candidate lookups, checkpoints, and immutable run identity.
- [x] 2.10 Add migration and repository tests covering transactions, duplicate records, immutable artifacts, and legacy schema upgrades.

## 3. Patent, IPC Edge, Paper, and Coverage Ingestion

- [x] 3.1 Define staging schemas and field mapping for patent records with multiple IPC assignments per patent.
- [x] 3.2 Implement IPC parsing, raw-value retention, main-group normalization, edition capture, and unresolved-code reporting.
- [x] 3.3 Implement duplicate patent and duplicate patent-IPC detection with explicit preview counts and deterministic commit behavior.
- [x] 3.4 Implement patent-level import preview showing normalized assignments, invalid codes, pair counts, year coverage, and source rows.
- [x] 3.5 Define and implement the reviewed reduced annual-edge import contract with support counts, denominators, formulas, and provenance.
- [x] 3.6 Reject or quarantine probability-only pair inputs as researcher hypotheses so they cannot populate model-prediction fields.
- [x] 3.7 Add controlled paper-type vocabulary, mapping preview, explicit `other` review, and paper-type coverage summaries.
- [x] 3.8 Add source cutoff and completeness controls to import preview and require a cutoff for partial 2025 data.
- [x] 3.9 Implement transactional commit and rollback for patent, patent-IPC, reduced-edge, paper, mapping, and coverage imports.
- [x] 3.10 Add import API and repository tests for valid files, malformed rows, mixed IPC formats, partial years, unknown paper types, and source traceability.

## 4. Temporal Scope, Eligibility, and Snapshotting

- [x] 4.1 Update dataset period validation and splitting to use v3 reporting periods while preserving legacy period handling by contract version.
- [x] 4.2 Extend dataset eligibility to report canonical patent-incidence, reduced-edge, paper-type, mapping, and coverage grades.
- [x] 4.3 Add completeness-aware period summaries with included-year and complete-year denominators.
- [x] 4.4 Extend project research design with research question, paper types, IPC analysis level, candidate target, cutoff assumptions, and advanced parameters.
- [x] 4.5 Version research-design changes and mark dependent network, model, graph, and export artifacts stale without deleting them.
- [x] 4.6 Freeze v3 snapshots containing design version, eligible data, source checksums, record IDs, coverage, mappings, and contract metadata.
- [x] 4.7 Add tri-state scoping tests proving empty eligible evidence never falls back to unscoped library records.
- [x] 4.8 Add compatibility tests proving later remapping or republication does not change frozen jobs.

## 5. Deterministic Dynamic IPC Network Service

- [x] 5.1 Create a framework-independent network module with versioned parameter and result schemas.
- [x] 5.2 Build annual IPC co-occurrence graphs from canonical patent-to-IPC assignments with one contribution per normalized patent pair.
- [x] 5.3 Build the three reporting-period networks from frozen annual observations and the selected completeness policy.
- [x] 5.4 Support reviewed reduced-edge evidence while enforcing its available measures and lower provenance grade.
- [x] 5.5 Calculate raw support, association strength, Jaccard or PMI, and documented denominators for every eligible edge.
- [x] 5.6 Calculate degree, betweenness, closeness, eccentricity, and eigenvector centrality with explicit undefined-state handling.
- [x] 5.7 Implement versioned community detection with a frozen seed and stable community identifiers across comparable observations.
- [x] 5.8 Derive node first appearance, persistence, centrality trajectories, community movement, and peripheral-to-core transitions.
- [x] 5.9 Store supporting patent IDs and source provenance for observed edges and expose paginated edge evidence queries.
- [x] 5.10 Generate deterministic shared layout coordinates for comparable figures separately from model features.
- [x] 5.11 Add checksum-based network caching and idempotency so identical inputs reproduce identical run IDs and measures.
- [x] 5.12 Add golden-data tests reproducing known Chapter 4 sample pairs and centrality values within documented numerical tolerance where source data are available.
- [x] 5.13 Add network tests for duplicate IPCs, isolated nodes, disconnected components, missing years, reduced-edge data, and deterministic reruns.

## 6. Fusion Candidate and Temporal Feature Pipeline

- [x] 6.1 Define versioned candidate universes and separate target schemas for first edge emergence and significant edge strengthening.
- [x] 6.2 Implement configurable minimum support, edge threshold, forecast horizon, pair eligibility, exclusions, and negative-sampling policies.
- [x] 6.3 Build time-cutoff enforcement that rejects any feature or mapping observed after a training or prediction cutoff.
- [x] 6.4 Implement topology features including common neighbors, Adamic-Adar, resource allocation, preferential attachment, and community distance.
- [x] 6.5 Implement temporal node and edge trajectory features using only pre-cutoff observations.
- [x] 6.6 Implement patent-text and paper-signal feature adapters with source timestamps and feature lineage.
- [x] 6.7 Implement taxonomy and cross-domain distance features using the frozen technology and IPC mapping snapshots.
- [x] 6.8 Persist feature definitions, values, missing-value transformations, cutoff, source run IDs, and checksums.
- [x] 6.9 Add leakage tests that introduce known future-only records and prove they cannot affect historical features.
- [x] 6.10 Add candidate and feature APIs that expose definitions and provenance without returning unbounded source text.

## 7. Fusion Models, Calibration, and Explanation

- [x] 7.1 Implement deterministic random/prevalence, common-neighbors, and Adamic-Adar baseline rankers.
- [x] 7.2 Implement a minimal-feature logistic regression baseline with reproducible preprocessing and seeds.
- [x] 7.3 Implement the primary interpretable tabular model interface and a tree-based candidate behind the same versioned contract.
- [x] 7.4 Add time-ordered model selection that never evaluates or tunes on the final prediction horizon.
- [x] 7.5 Implement held-out probability calibration with explicit support checks and uncalibrated-score fallback.
- [x] 7.6 Implement bootstrap or repeated-resampling prediction intervals and persist the resampling configuration.
- [x] 7.7 Generate per-candidate feature contributions compatible with the selected model and link them to feature provenance.
- [x] 7.8 Persist authoritative rank, probability status, calibrated probability, interval, model limitations, and evidence grade.
- [x] 7.9 Enforce database and service guards preventing manual or LLM values from writing authoritative probability fields.
- [x] 7.10 Add deterministic training, calibration, ranking, guardrail, and explanation tests.

## 8. Historical Validation and Reproducibility

- [x] 8.1 Replace empirical use of mock backtesting with a rolling-origin validation service while retaining synthetic data only in isolated tests.
- [x] 8.2 Implement broad transition folds for 2010-2014 to 2015-2019 and pre-2020 observations to 2020-2025 outcomes.
- [x] 8.3 Add valid annual or rolling-window folds without changing the paper-facing reporting periods.
- [x] 8.4 Calculate Precision@K, Recall@K, Hit Rate@K, MAP or NDCG, PR-AUC where defined, Brier score, and expected calibration error.
- [x] 8.5 Implement bootstrap confidence intervals and explicit not-estimable results for insufficient folds or events.
- [x] 8.6 Compare every selected model with all mandatory baselines and record the model-selection criterion.
- [x] 8.7 Implement feature-family ablations for topology, temporal, patent text, paper signal, and taxonomy features.
- [x] 8.8 Implement sensitivity runs for candidate definition, thresholds, negative sampling, IPC normalization, and inclusion versus exclusion of partial 2025.
- [x] 8.9 Mark candidates unstable when rank, probability, or selection changes beyond configured sensitivity limits.
- [x] 8.10 Implement publication gates for evidence, validation, calibration, stability, schema, citation, asset, and human-review criteria.
- [x] 8.11 Implement reasoned expert override without changing failed gate states and propagate limitations to all downstream contracts.
- [x] 8.12 Generate immutable run manifests with environment, dependency, seed, source, algorithm, model, prompt, review, and output checksums.
- [x] 8.13 Add a manifest rerun/diff command that verifies deterministic artifacts and reports field-level differences.
- [x] 8.14 Add validation tests for fold leakage, class imbalance, missing metrics, baseline failure, unstable candidates, overrides, and reproducible reruns.

## 9. LangChain Schemas and Model Adapters

- [x] 9.1 Add supported LangChain and LangGraph dependencies with locked compatible versions and startup version diagnostics.
- [x] 9.2 Define versioned Pydantic schemas for evidence analysis, technology concepts, critic findings, theme forecasts, scenarios, milestones, and dossiers.
- [x] 9.3 Implement a provider-neutral LangChain chat-model factory using job-scoped configuration and secret-safe diagnostics.
- [x] 9.4 Implement structured-output selection with provider-native schema output where supported and a validated tool strategy fallback.
- [x] 9.5 Convert prompt files into versioned ChatPromptTemplate definitions with checksums, declared role, language, input schema, and output schema.
- [x] 9.6 Implement numeric, IPC, year, enum, and evidence-ID validators against frozen deterministic artifacts.
- [x] 9.7 Implement scientific-language validation for causal overstatement, hidden certainty, missing limitations, and unsupported confidence wording.
- [x] 9.8 Implement bounded schema-correction prompts that receive validation errors and stop after the configured retry limit.
- [x] 9.9 Add model-adapter tests for structured success, malformed outputs, invented sources, probability overwrite attempts, provider failure, and retry exhaustion.

## 10. Persistent Evidence-Constrained LangGraph

- [x] 10.1 Define the versioned `ForecastState`, reducer semantics, job runtime context, and stable artifact-reference types.
- [x] 10.2 Implement a persistent local checkpointer adapter and thread lifecycle with transaction and restart tests.
- [x] 10.3 Implement deterministic graph nodes for scope validation, snapshot freezing, network construction, validation/model runs, candidate ranking, citation validation, publication gates, and asset generation.
- [x] 10.4 Implement bounded evidence analyst, technology concept synthesizer, scientific critic, topic forecaster, and scenario-roadmap nodes.
- [x] 10.5 Implement patent and paper analysis fan-out with deterministic aggregation and per-worker failure records.
- [x] 10.6 Implement per-theme forecast fan-out so every reviewed theme produces either a typed result or an explicit failure.
- [x] 10.7 Implement conditional critic and schema-correction loops with hard iteration limits and visible terminal failure.
- [x] 10.8 Implement durable interrupts for fusion review, theme review, and publication review with approve/edit/reject policies.
- [x] 10.9 Persist pre-review and post-review values, reviewer, timestamp, decision, and reason without mutating model outputs.
- [x] 10.10 Map graph node and interrupt events to job progress, streaming updates, audit history, and readiness state.
- [x] 10.11 Make all scientific side effects content-addressed and idempotent so resume skips matching completed outputs.
- [x] 10.12 Implement safe cancellation and explicit resume/abandon actions at graph node boundaries.
- [x] 10.13 Replace process-global output-path and feature-flag mutation with job-scoped dependency injection for the v3 path.
- [x] 10.14 Remove the single global forecast lock from v3 execution while retaining bounded scientific compute concurrency.
- [x] 10.15 Add graph tests for normal completion, parallel partial failure, interrupt/resume, process restart, checksum mismatch, cancellation, retry limits, and cross-job isolation.

## 11. Version 3 APIs and Readiness

- [x] 11.1 Add research-design create, version, confirm, and stale-artifact APIs with versioned request and response schemas.
- [x] 11.2 Add data-quality APIs for coverage, paper types, IPC mappings, reconstruction grade, invalid records, and partial-year warnings.
- [x] 11.3 Add network-run APIs for start/status, period summaries, nodes, edges, trajectories, communities, and source evidence.
- [x] 11.4 Add validation/model-run APIs for folds, baselines, metrics, calibration, ablations, sensitivities, gates, and manifests.
- [x] 11.5 Add fusion-candidate APIs with emergence/strengthening separation, explanation, stability, evidence, pagination, and review actions.
- [x] 11.6 Add technology-theme proposal, critic, merge/edit/reject, confirm, and provenance APIs.
- [x] 11.7 Add graph start, status, event stream, interrupt decision, cancel, resume, and abandon APIs.
- [x] 11.8 Add dossier, roadmap, chart-data, provenance, manifest, export, and asset-regeneration APIs.
- [x] 11.9 Implement readiness contract v3 for the six research steps, blocking reasons, remediation, checkpoint state, and recommended action.
- [x] 11.10 Add authorization-independent integrity validation so direct API calls cannot bypass snapshots, model authority, reviews, or publication gates.
- [x] 11.11 Add API contract tests for happy paths, invalid transitions, deep-link recovery data, pagination, immutable runs, and legacy compatibility.

## 12. Project Shell and Research Workflow Frontend

- [x] 12.1 Add frontend types and API clients for v3 contracts, network/model results, graph state, reviews, dossiers, and manifests.
- [x] 12.2 Replace v3 project navigation with research design, data quality, network evolution, fusion forecast, technology themes, and roadmap/report steps.
- [x] 12.3 Retain global taxonomy, evidence library, and project navigation outside the project workflow.
- [x] 12.4 Consume readiness v3 for step visibility, route guards, blockers, remediation, graph checkpoint, and one recommended next action.
- [x] 12.5 Add a persistent project scope bar showing contract, cutoff, completeness, technology scope, baseline, and target nodes.
- [x] 12.6 Add observed/derived/predicted/agent-generated/human-reviewed status components using redundant non-color encodings.
- [x] 12.7 Add researcher and advanced view modes that do not change frozen run state.
- [x] 12.8 Add legacy route adapters and read-only legacy project labels without implying v3 gate completion.
- [x] 12.9 Preserve unsaved-change protection, refresh recovery, error boundaries, loading states, and responsive shell behavior.
- [x] 12.10 Add routing and shell tests for new, blocked, interrupted, completed, archived, and legacy projects.

## 13. Research Step Pages and Review Interaction

- [x] 13.1 Build the research-design page with source-study defaults, assumptions, version history, confirm action, and stale-impact preview.
- [x] 13.2 Build the data-quality page with coverage calendar, reconstruction grade, paper types, mapping issues, duplicates, invalid rows, and remediation links.
- [x] 13.3 Build the network-evolution page with linked annual/reporting views, stable selection, node trajectories, community changes, thresholds, and provenance drawer.
- [x] 13.4 Build the fusion-forecast page with separate emergence/strengthening rankings, calibrated status, intervals, feature contributions, stability, and evidence.
- [x] 13.5 Add fusion approve/edit-metadata/reject review controls that preserve authoritative model rank and probability.
- [x] 13.6 Build the technology-themes page connecting approved IPC pairs, semantic clusters, patent/paper evidence, agent proposals, critic findings, and review history.
- [x] 13.7 Add theme rename, merge, edit, reject, and confirm flows with evidence and schema revalidation.
- [x] 13.8 Build the graph execution panel with live node state, interrupts, retries, cancellation, resume, and audit detail.
- [x] 13.9 Build the roadmap/report page with theme dossiers, scenario comparison, publication gates, limitations, exports, and asset regeneration.
- [x] 13.10 Implement end-to-end provenance drill-down from a milestone to theme, IPC pairs, feature explanation, networks, sources, graph node, and reviews.
- [x] 13.11 Add accessible tables and CSV downloads for every scientific visualization.
- [x] 13.12 Add component and Playwright tests for all review decisions, blocked actions, advanced views, provenance paths, and keyboard interaction.

## 14. Scientific Visualization and Publication Assets

- [x] 14.1 Define a versioned shared chart-data contract used by interactive and static renderers.
- [x] 14.2 Establish a color-vision-safe visual token system, Chinese/Latin typography, symbol and line-style semantics, captions, and figure numbering.
- [x] 14.3 Implement fixed-layout annual and three-period network small multiples with stable node positions and community colors.
- [x] 14.4 Implement IPC centrality and peripheral-to-core transition trajectory figures.
- [x] 14.5 Implement ranked fusion candidate and fusion matrix figures with intervals, calibrated status, and stability markers.
- [x] 14.6 Implement community evolution figures without implying that alluvial flow represents patent or IPC causality.
- [x] 14.7 Implement patent-paper convergence and conflict matrix figures linked to evidence counts and direction labels.
- [x] 14.8 Implement baseline comparison, ranking performance, reliability/calibration, ablation, and sensitivity figures.
- [x] 14.9 Implement dependency-aware baseline/accelerated/constrained roadmap swimlanes with TRL and uncertainty bands.
- [x] 14.10 Ensure observed edges are solid and predicted edges dashed in every combined historical/future visualization.
- [x] 14.11 Generate SVG or PDF and 600-DPI PNG assets with caption, sample size, cutoff, checksum, version, source note, legend, and accessibility description.
- [x] 14.12 Remove decorative radar and donut charts as primary scientific evidence while retaining compatibility rendering for legacy results.
- [x] 14.13 Add deterministic visual-data tests, image smoke tests, grayscale/color-vision checks, label-overlap checks, and representative visual regression baselines.

## 15. Forecast Dossiers, Reports, and Research Bundles

- [x] 15.1 Implement the versioned per-theme dossier assembler from validated model, evidence, agent, review, and roadmap artifacts.
- [x] 15.2 Enforce required dossier fields and explicit not-estimable states for unavailable probabilities, intervals, maturity, or indicators.
- [x] 15.3 Implement cumulative 2030/2035/2040 roadmap validation for dependencies, target boundaries, TRL progression, scenarios, and indicators.
- [x] 15.4 Propagate partial 2025 coverage, validation limits, unstable candidates, evidence conflicts, and overrides adjacent to affected claims.
- [x] 15.5 Generate the final report solely from immutable structured artifacts and normalized bibliography records.
- [x] 15.6 Generate a research bundle containing report, dossiers, chart data, vector/raster figures, validation artifacts, manifest, bibliography, limitations, and review log.
- [x] 15.7 Record output checksums and dependencies in the export manifest and provide manifest-level integrity verification.
- [x] 15.8 Implement targeted asset regeneration from frozen structured inputs without rerunning models or agents.
- [x] 15.9 Add dossier, roadmap, citation, report, manifest, export, and asset-regeneration tests.

## 16. Migration, Verification, and Operational Documentation

- [x] 16.1 Implement a dry-run migration classifier for mapped, needs patent-IPC reconstruction, reduced-edge-only, needs period split, and quarantined legacy datasets.
- [x] 16.2 Require explicit review before migrating any dataset or project into contract v3 and preserve the original version and files.
- [x] 16.3 Add a shadow-run comparison command for selected legacy prompt workflows and v3 graph workflows without asserting scientific equivalence.
- [x] 16.4 Verify that v3 Round 1-equivalent theme forecasting receives frozen stage analysis, model candidates, evidence, and target contract before its first model call.
- [x] 16.5 Add database backup, dry-run, apply, verification, export-preservation, and rollback documentation and scripts.
- [x] 16.6 Document input templates for patent incidence, reduced annual edges, papers, IPC mappings, and temporal coverage.
- [x] 16.7 Document the scientific methodology, target definitions, leakage controls, metrics, calibration, sensitivity analysis, agent boundary, and interpretation limits.
- [x] 16.8 Document local model/provider configuration, prompt versioning, graph checkpoints, cancellation, resume, and troubleshooting.
- [x] 16.9 Run the full backend unit and integration suite, migration fixtures, manifest reproducibility checks, and legacy compatibility tests.
- [x] 16.10 Run frontend type checks, production build, component tests, Playwright workflows, accessibility checks, and visual regressions.
- [x] 16.11 Run a clean end-to-end empirical fixture from import through publication review and verify every result can be traced to source evidence.
- [x] 16.12 Validate `rebuild-2040-ipc-fusion-forecast-agent` with strict OpenSpec validation and resolve every reported issue.
