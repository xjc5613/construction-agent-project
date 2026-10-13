## Context

The repository is a local single-user FastAPI, SQLite, and React research workbench. Earlier changes introduced a technology taxonomy, staged datasets, project-isolated materials and topics, evidence packages, immutable job snapshots, readiness gates, multi-round LLM runners, and result assets. Those foundations remain useful, but the current forecast path still has four structural gaps.

First, the implementation uses `2010-2015`, `2016-2020`, and `2021-2026` with a 2026 baseline, while the supplied Chapter 4 study uses `2010-2014`, `2015-2019`, and `2020-2025`, with data collected through October 1, 2025 and explicitly noted as incomplete for that year. Second, annual aggregate IPC metrics and a small fusion table cannot always reconstruct the patent-level co-occurrence graph used by the study. Third, current stage analysis describes trend direction but does not train and calibrate a future-edge model. Fourth, the forecast service invokes module-level prompt runners under a process lock; context and stage analysis are not consistently available before Round 1, and checkpoints represent UI job steps rather than resumable graph state.

The primary stakeholder is an intelligent-construction researcher who needs a defensible forecast of IPC combinations and resulting technology themes through 2040. Secondary stakeholders are research reviewers who need to reproduce the analysis, domain experts who review candidates, and readers who consume publication figures and roadmaps. The system remains locally deployable and must preserve historical snapshots and user-imported files.

## Goals / Non-Goals

**Goals:**

- Reproduce the Chapter 4 historical period contract while retaining annual or rolling-window observations for model training and sensitivity analysis.
- Separate observed data, deterministic inference, calibrated prediction, agent interpretation, and human judgment in storage, APIs, user interface, and exports.
- Reconstruct annual and stage IPC networks from auditable source records and generate explainable future fusion candidates without temporal leakage.
- Validate candidate ranking and probability calibration against historical transitions before allowing a forecast to be published.
- Replace script-style LLM sequencing with a persistent LangGraph workflow whose state, prompts, model calls, reviews, retries, and outputs are inspectable.
- Use LLMs only for bounded semantic tasks and enforce typed, evidence-linked outputs with deterministic validators.
- Present the research as one readiness-driven project workflow and produce accessible, publication-grade figures and per-theme roadmaps.
- Preserve local SQLite deployment, existing immutable results, and compatibility access to legacy jobs.

**Non-Goals:**

- Claiming causal relationships from IPC co-occurrence or paper-topic correlation.
- Allowing an LLM to calculate network statistics, invent source records, or assign forecast probabilities.
- Treating a three-snapshot deep graph model as inherently superior to interpretable baselines.
- Automatically purchasing, scraping, or bypassing access controls for patent or academic databases.
- Replacing the technology taxonomy with an ontology or external graph database in this change.
- Building multi-tenant access control, distributed workers, or a cloud-only deployment.
- Automatically publishing a forecast without explicit researcher review.

## Decisions

### 1. Introduce research contract version 3 aligned to the source study

All new projects use baseline year 2025, forecast nodes 2030/2035/2040 up to the selected target, and reporting periods:

```text
stage_1 = 2010-2014
stage_2 = 2015-2019
stage_3 = 2020-2025
```

The period codes are stored independently from display labels and are frozen in each job snapshot. Internal annual networks and configurable trailing windows may be calculated, but all paper-facing stage summaries use the three source-study windows. Coverage metadata records the observation cutoff and completeness for every year and source; 2025 is never silently treated as complete.

Legacy contract versions remain readable. They cannot be selected for a new v3 project, merged into a v3 model run, or relabeled as v3 results.

Alternative considered: retain the existing periods to avoid migration. Rejected because it prevents direct reproduction of Chapter 4 and moves the observation boundary into an unobserved year.

### 2. Store reconstructable patent-to-IPC incidence as the canonical network source

The schema adds canonical entities conceptually equivalent to:

```text
patents
├── patent_id, dataset_id, publication_number, title, abstract,
│   application_year, applicant_type, legal_status, source_file_id, source_row

patent_ipcs
├── patent_id, ipc_code_raw, ipc_code_normalized, ipc_level,
│   ipc_edition, mapping_status

ipc_edges_yearly
├── edge_id, network_run_id, year, ipc1, ipc2, cooccurrence_count,
│   association_strength, jaccard, pmi, supporting_patent_count

papers
├── existing fields + paper_type, source_database, publication_date,
│   citation_count_observed_at

data_coverage / ipc_code_mappings / network_runs / model_runs
```

`patent_ipcs` is authoritative when available. A reviewed annual edge file is accepted as a reduced-data fallback only if it contains raw co-occurrence counts, denominators, normalization metadata, and source provenance. Manually entered probability values are stored as researcher hypotheses, never as model predictions.

IPC codes are normalized to the selected analysis level, initially the IPC main group used in Chapter 4. The raw code and mapping edition are retained so normalization can be re-run.

Alternative considered: continue using only `ipc_metrics` and `ipc_fusions`. Rejected because derived aggregates cannot prove which patents created an edge or reproduce alternative edge-weight definitions.

### 3. Separate network construction from fusion prediction

A deterministic network service constructs one undirected IPC co-occurrence graph per year and three reporting graphs. Each patent contributes at most once to a normalized IPC pair in a given run. The service records node and edge counts, isolated-node handling, normalization formula, thresholds, community algorithm, random seed, and input checksum.

It calculates at least degree, betweenness, closeness, eccentricity where defined, eigenvector centrality where stable, community membership, and edge weight. It also derives longitudinal changes, first appearance, persistence, community movement, and edge-strength trajectories. Fixed-layout coordinates for comparison figures are derived once per network family and are not part of the scientific model.

Fusion prediction operates only on versioned network outputs. A candidate is either an absent edge eligible to emerge or an existing weak edge eligible to strengthen; the exact target rule, horizon, minimum support, and negative sampling policy are explicit parameters frozen with the run.

Alternative considered: ask the LLM to infer promising pairs directly from network summaries. Rejected because the resulting score would not be calibrated, reproducible, or backtestable.

### 4. Use an interpretable, benchmarked ranking model before optional advanced models

The primary model is a supervised and calibrated tabular ranker/classifier using leakage-safe features such as normalized historical edge trajectories, common neighbors, Adamic-Adar, resource allocation, preferential attachment, node centrality levels and slopes, community distance, patent text similarity, paper-topic similarity, paper growth signals, and cross-domain distance.

Logistic regression and topology-only heuristics are mandatory baselines. A tree-based model may become the primary model when it improves predefined validation metrics and its feature contributions can be exposed. Temporal embeddings or graph neural networks may be evaluated as experimental comparators only when annual-window sample size and holdout design are adequate; they do not replace baseline reporting.

Predicted probability is populated only after calibration on held-out historical transitions. Outputs include calibrated probability, rank, interval or resampling distribution, feature contributions, supporting source IDs, and model limitations.

Alternative considered: use only centrality thresholds. Rejected because node importance does not directly estimate edge emergence and a mean threshold is sensitive to network size and skew.

### 5. Make historical validation an execution gate, not an appendix

The validation service performs rolling-origin evaluation using only information available at each cutoff. At minimum it evaluates a 2010-2014 to 2015-2019 transition and a pre-2020 to 2020-2025 transition; annual or rolling-window observations add folds without changing the reporting periods.

Runs report Precision@K, Recall@K, Hit Rate@K, MAP or NDCG, PR-AUC where defined, Brier score, expected calibration error, and bootstrap confidence intervals. They also compare mandatory baselines, run feature-family ablations, and execute sensitivity tests for candidate thresholds, negative sampling, IPC normalization, and inclusion versus exclusion of incomplete 2025 data.

A forecast can be explored with an insufficient model, but it cannot be marked publication-ready unless configured minimum evidence, backtest, and calibration gates pass or a documented expert override is stored and visibly propagated. Mock backtests are retained only as test fixtures and never shown as empirical results.

Alternative considered: retain current self-consistency similarity as the primary confidence measure. Rejected because agreement among generated texts is not empirical forecast accuracy or probability calibration.

### 6. Implement a typed LangGraph state machine around deterministic and agent nodes

The new graph state contains stable identifiers and references instead of duplicating uncontrolled text:

```text
ForecastState
├── contract, project_id, job_id, thread_id
├── dataset_snapshot, coverage_assessment
├── network_run_ids, validation_run_id, model_run_id
├── fusion_candidates, reviewed_candidate_ids
├── evidence_package_ids, topic_candidates, reviewed_topic_ids
├── theme_forecasts, critic_findings, roadmaps
├── validation_errors, review_decisions, warnings
└── prompt_manifest, model_manifest, export_manifest
```

The graph nodes are:

```text
validate_research_scope
  -> freeze_dataset_snapshot
  -> build_dynamic_networks
  -> backtest_and_calibrate_model
  -> rank_future_ipc_fusions
  -> review_fusion_candidates [interrupt]
  -> parallel patent/paper evidence analysis
  -> synthesize_technology_concepts
  -> scientific_critic -> revise or continue
  -> review_topics [interrupt]
  -> parallel_topic_forecasters
  -> synthesize_scenario_roadmaps
  -> validate_citations_and_schemas
  -> render_publication_assets
  -> publication_review [interrupt]
  -> complete
```

LangGraph supplies conditional edges, map/reduce topic workers, durable checkpoints, streaming events, cancellation boundaries, and interrupt/resume semantics. LangChain supplies provider-neutral chat models, versioned chat prompt templates, tool bindings where required, and Pydantic structured output. The repository continues to own scientific services, schemas, storage, and job APIs; LangGraph does not become the source of scientific truth.

SQLite-backed checkpointing is preferred for the local deployment if the supported saver meets transaction and concurrency requirements. Otherwise graph checkpoints receive a dedicated SQLite adapter behind a repository interface. Nodes are idempotent and use content-addressed run IDs so resume does not duplicate scientific side effects.

Alternative considered: wrap the existing three runners in one sequential chain. Rejected because it would not provide human interrupts, conditional correction loops, per-topic fan-out, or reliable resume semantics.

### 7. Bound agent authority and validate every semantic output

Four semantic roles are used: evidence analyst, technology concept synthesizer, scenario/roadmap author, and scientific critic. They receive only approved evidence references and deterministic results. They cannot execute arbitrary SQL, edit datasets, alter probabilities, or publish results.

Every output conforms to a versioned Pydantic schema. Evidence-bearing claims require valid evidence IDs; numeric claims must resolve to frozen deterministic artifacts; IPC codes must resolve through the snapshot taxonomy/mapping; dates may not exceed the target; and confidence language is mapped from explicit evidence and model-quality fields. Invalid outputs enter a bounded correction loop and then fail visibly rather than being accepted through permissive parsing.

Prompts are versioned artifacts with checksum, role, schema version, language, and model parameters. Prompt text remains configurable but is not allowed to define hidden workflow state.

Alternative considered: retain regex extraction of JSON-like text. Rejected because silent coercion and partial parsing undermine auditability.

### 8. Organize the frontend around six research decisions

Global navigation retains the workbench, technology catalog, evidence library, and project list. Entering a project exposes one ordered workflow:

```text
research-design
-> data-quality
-> network-evolution
-> fusion-forecast
-> technology-themes
-> roadmap-report
```

Readiness version 3 is authoritative for visibility, availability, blocking reasons, remediation actions, active graph checkpoint, and recommended next action. Each page displays the frozen scope and distinguishes observed, derived, predicted, agent-generated, and human-reviewed information.

The default researcher view emphasizes decisions and evidence. An advanced view exposes mappings, graph parameters, feature definitions, model metrics, prompt/model manifests, checkpoint history, and downloadable intermediate artifacts. A user can drill from a technology claim to its predicted IPC pair, feature explanation, source patents/papers, network run, and dataset row.

Legacy routes redirect to the nearest v3 step for v3 projects and remain read-only for legacy projects.

Alternative considered: add network and model panels to the existing forecast page. Rejected because it would hide the main scientific decisions inside one dense execution page and preserve the misleading impression that the LLM is the forecast engine.

### 9. Treat publication figures as verified views of versioned data

Interactive charts consume structured chart data from the API; static renderers consume the same normalized data contract. Required figure families include fixed-layout network small multiples, node-transition trajectories, candidate fusion matrix or ranked plot, community evolution, patent/paper convergence matrix, calibration/backtest plots, and dependency-aware roadmap swimlanes.

Observed edges use solid styling and predicted edges use dashed styling. Color, symbol, and labels redundantly encode status so meaning survives grayscale and color-vision differences. Stable community colors and node positions are used across comparable periods. Hairball graphs, decorative radar charts, and donut charts are not used as primary evidence.

Each export includes title, caption, sample size, cutoff, uncertainty encoding, legend, data checksum, algorithm/model version, and source note. Static figures are exported as SVG or PDF plus 600-DPI PNG; interactive charts meet keyboard and screen-reader requirements and have a tabular alternative.

Alternative considered: continue generating charts independently from loosely structured roadmap text. Rejected because visual claims could drift from the result JSON and could not be reproduced exactly.

### 10. Replace process-global runner mutation with job-scoped dependencies

Graph nodes receive a job-scoped runtime context containing repositories, model adapters, output paths, cancellation token, and event writer. No node mutates module-level configuration or shared output directories. A persistent event stream maps graph node lifecycle to the job API and frontend progress display.

The local service may initially execute one scientific model-training node at a time to control memory, but independent project jobs and per-topic LLM workers are not serialized by a single global lock. Cancellation is checked before and after idempotent nodes and records a checkpoint that can be resumed or intentionally abandoned.

Alternative considered: keep `_RUN_LOCK` and only add graph-shaped status labels. Rejected because presentation-only graph state does not solve isolation, recovery, or concurrency.

### 11. Version every boundary and preserve legacy results

Research contract, database schema, network algorithm, feature schema, model schema, agent output schema, prompt set, readiness API, chart data, and export manifest each have explicit versions. New v3 runs never rewrite completed legacy artifacts. Compatibility readers render historical v1/v2 snapshots with their original baseline and periods and label them as legacy.

Migration is additive until the v3 path passes acceptance tests. Legacy data receives a disposition of mapped, needs patent-IPC reconstruction, reduced-edge-only, needs period split, or quarantined. No automatic mapping is treated as reviewed.

Alternative considered: rewrite legacy periods and results into the new contract. Rejected because that would falsify the conditions under which earlier outputs were generated.

## Risks / Trade-offs

- [Patent-level IPC incidence may not be available for all imported data] -> Support a clearly labeled reduced-edge input contract, lower reproducibility grade, and block patent-level provenance claims.
- [Only two broad historical transitions provide weak supervised evidence] -> Train on annual or rolling windows, require simple baselines, report wide intervals, and prohibit unsupported deep-model superiority claims.
- [2025 is incomplete and may bias recent growth] -> Store coverage explicitly and require include/exclude sensitivity results before publication.
- [IPC editions and normalization can create false appearance or disappearance] -> Preserve raw codes, version mappings, mapping status, and normalization sensitivity results.
- [Negative sampling can inflate classification metrics] -> Freeze the candidate universe and sampling policy, report ranking metrics, and evaluate against all eligible pairs where feasible.
- [LangGraph adoption increases dependency and migration complexity] -> Keep scientific services framework-independent, introduce an adapter boundary, and migrate one vertical path before retiring runners.
- [Persistent checkpoints can replay side effects] -> Make nodes idempotent, content-address outputs, and separate computation from final publication writes.
- [Agent explanations can overstate correlation] -> Use typed claims, deterministic numeric validation, a scientific critic, prohibited-language checks, and visible limitations.
- [Human review can reduce reproducibility] -> Store every approval, edit, rejection, reason, reviewer identifier, and pre/post-review value in the immutable job trace.
- [Publication-quality rendering may fail independently of the forecast] -> Track result validity and asset health separately, retain structured data, and allow deterministic asset regeneration.
- [Six project steps can feel heavy for exploratory use] -> Provide concise default views, recommended actions, saved presets, and an explicitly labeled evidence-limited exploration path.

## Migration Plan

1. Freeze and inventory the current databases, raw files, dataset mappings, projects, jobs, and artifacts; produce a dry-run report without modifying records.
2. Add contract-version metadata and compatibility readers before changing period constants or routes.
3. Add patent, patent-IPC, coverage, IPC mapping, network run, model run, checkpoint, review, prompt manifest, and export manifest tables using additive migrations.
4. Add staging validators for patent-level incidence and reduced annual-edge imports. Classify all existing IPC datasets without guessing missing patent relationships.
5. Implement the v3 temporal contract and deterministic network builder behind new service and API versions; verify reproduction against the Chapter 4 sample metrics where source data permits.
6. Implement leakage-safe features, baselines, rolling-origin validation, calibration, sensitivity analysis, and publication gates before exposing future fusion probabilities.
7. Introduce LangChain model adapters and Pydantic outputs, then implement the LangGraph path with a persistent checkpointer and job event adapter. Run it in shadow mode against selected existing workflows.
8. Build readiness v3 and the six-step project workspace, retaining redirects and read-only legacy rendering.
9. Add the structured forecast dossier, interactive figures, static renderers, accessibility alternatives, and reproducible export bundle.
10. Migrate eligible projects by explicit user action, run backend, frontend, migration, reproducibility, visual-regression, and OpenSpec validation tests, then make v3 the new-project default.
11. Retire direct prompt runners from the v3 path only after result parity, failure recovery, cancellation, and snapshot compatibility tests pass. Keep legacy readers and export adapters.

Rollback restores the pre-migration database and application version as one backup set. Because migrations are additive, newly imported v3 files and generated artifacts are preserved separately before rollback. A v3 job is never resumed by a legacy runner.

## Open Questions

- Will the research dataset provide patent-level publication numbers and complete IPC lists, or only annual IPC node/edge tables for some periods?
- What controlled values does “paper type” require: journal article, conference paper, thesis, standard, report, or another project-specific classification?
- Should the primary positive label mean first edge appearance, statistically significant strengthening, or separate models for both outcomes?
- What publication gate thresholds should be fixed for Precision@K, calibration error, evidence volume, and bootstrap stability?
- Which model providers must the LangChain adapter support in the first implementation, and is fully offline inference required?
- Is expert review single-researcher approval sufficient, or must the system support two-reviewer agreement and record inter-rater reliability?
- Must the final report be DOCX in addition to HTML/PDF/data bundles, and which institutional thesis style governs its typography and captions?
