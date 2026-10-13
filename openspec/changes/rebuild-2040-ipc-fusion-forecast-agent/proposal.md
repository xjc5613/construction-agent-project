## Why

The current workbench can collect evidence and run multi-round prompts, but it does not yet implement a reproducible scientific forecast from the 2010-2025 patent IPC co-occurrence network and paper corpus to calibrated future IPC fusion candidates. Its historical periods differ from the source research, the available data model cannot fully reconstruct patent-level networks, and the model workflow is a script-style prompt pipeline rather than a persistent, inspectable orchestration graph.

This change turns the project into an evidence-grounded 2040 intelligent-construction forecasting system in which deterministic network and validation methods produce candidate forecasts, constrained agents explain and synthesize those results, and researchers can audit every result from source record to publication figure.

## What Changes

- Align the research contract with the source study: historical windows `2010-2014`, `2015-2019`, and `2020-2025`; baseline year 2025; forecast nodes 2030, 2035, and 2040; explicit treatment of incomplete 2025 coverage.
- Add patent-to-IPC incidence and annual IPC edge data, paper type metadata, IPC version mappings, coverage metadata, and immutable model-run provenance so dynamic networks can be reconstructed and audited.
- Build annual and stage-level IPC co-occurrence networks with normalized edge weights, node/community evolution, edge-emergence definitions, and reproducible feature extraction.
- Add an interpretable future IPC fusion ranking model, probability calibration, rolling-origin backtesting, baseline comparisons, ablation tests, sensitivity analysis, and confidence intervals.
- Replace direct prompt-runner sequencing with a LangGraph state graph using LangChain model adapters, versioned prompt templates, Pydantic structured outputs, persistent checkpoints, bounded retries, conditional validation loops, and human review interrupts.
- Restrict LLM agents to evidence analysis, technology concept synthesis, scenario construction, roadmap writing, and scientific criticism; deterministic code remains authoritative for statistics, network measures, probabilities, citations, and quality gates.
- Redesign the project workspace around the research lifecycle: research design, data quality, network evolution, fusion prediction, technology-theme forecasting, and roadmap/report publication.
- Produce per-theme forecast dossiers and publication-grade scientific visuals that distinguish observed facts from predicted edges and expose evidence, uncertainty, model version, data cutoff, and review status.
- **BREAKING**: Replace the current `2010_2015`/`2016_2020`/`2021_2026` public period contract and 2026 baseline with the source-study-aligned period contract and 2025 baseline for new projects and forecasts. Historical job snapshots remain readable under their original contract version.
- **BREAKING**: New forecasts may not treat manually entered fusion probabilities or LLM-generated scores as model probabilities; only calibrated deterministic fusion-model outputs can populate probability fields.

## Capabilities

### New Capabilities

- `temporal-research-evidence-contract`: Source-study-aligned historical periods, patent/IPC and paper schemas, data coverage, IPC normalization, provenance, immutable snapshots, and legacy compatibility.
- `dynamic-ipc-fusion-forecasting`: Reconstructable annual/stage networks, normalized topology, candidate-edge definitions, feature generation, calibrated IPC fusion ranking, and explainable candidate results.
- `forecast-validation-reproducibility`: Rolling-origin backtests, leakage prevention, baselines, probability calibration, ablation and sensitivity tests, confidence intervals, run manifests, and reproducibility gates.
- `evidence-constrained-agent-graph`: Persistent LangGraph orchestration, LangChain structured model nodes, human review interrupts, deterministic validation, bounded agent roles, and recoverable execution.
- `scientific-forecast-workbench`: Research-lifecycle navigation, readiness gates, data-quality and network exploration, fusion review, topic forecasting, provenance drill-down, and advanced research controls.
- `publication-grade-forecast-output`: Structured technology forecast dossiers, scenario roadmaps, evidence-linked conclusions, uncertainty-aware figures, accessible interactive charts, and reproducible report exports.

### Modified Capabilities

None. The repository has no archived baseline specifications under `openspec/specs`; this change establishes the consolidated behavior as new capability specifications while preserving compatible access to historical snapshots.

## Impact

- Database schema and migrations for patents, patent IPC assignments, annual fusion edges, paper types, data coverage, IPC mappings, network/model runs, checkpoints, reviews, and export manifests.
- Ingestion, validation, stage analysis, network analysis, forecasting, evidence retrieval, job lifecycle, result, chart, and export APIs.
- Replacement or compatibility adaptation of `src/llm_orchestrator`, prompt builders, parsers, process-global runner configuration, mock backtesting, and report generation.
- React routing, readiness contracts, project pages, research visualizations, result provenance views, and publication controls.
- New LangChain/LangGraph dependencies plus deterministic scientific-computing dependencies selected during implementation; local SQLite deployment remains the default.
- Existing datasets require a dry-run migration and mapping report. Existing jobs and result artifacts remain immutable and readable under their frozen contract versions.
