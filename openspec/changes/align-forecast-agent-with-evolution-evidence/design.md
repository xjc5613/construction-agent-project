## Context

Chapter 4 produces a bounded evolution-evidence packet rather than an unrestricted retrieval corpus. Its primary objects are the nine identified themes `T01`–`T09`; the six potential technologies `C01`–`C06` retain candidate status. The packet combines theme meaning, selected stage-specific network trajectories, static theme relations and cooperation interpretations, source locations, optional representative patents, and qualifications about IPC-to-theme mappings. Empty or unavailable fields mean that the current packet has not supplied or verified that record; they do not prove the underlying research was not performed and do not automatically create a data-completion obligation.

Chapter 5 uses that packet to produce conditional development judgments through five research responsibilities: evolution analysis, development-proposition generation, reverse review, engineering review, and synthesis/adjudication. The unit of review is an atomic proposition, not a complete theme narrative. Agent agreement is a process observation, not evidence strength or event probability.

The repository already has valuable foundations: research contract v3 fixes the 2010–2014, 2015–2019, and 2020–2025 windows and the 2025-10-01 cutoff; deterministic network and model services are separated from LLM interpretation; evidence snapshots, prompt/model manifests, persistent graph checkpoints, human review interrupts, publication gates, and export provenance exist.

The current runnable architecture nevertheless differs from Chapter 5 in material ways:

| Current design | Chapter 5 requirement | Consequence |
|---|---|---|
| Ranks future IPC fusions before synthesizing one technology concept | Starts with fixed `T01`–`T09` and separately retained `C01`–`C06` | The workflow can redefine the research objects instead of preserving Chapter 4 continuity |
| Freezes patent/paper IDs and IPC codes as a mostly flat context | Needs typed Q/N/H/M evidence, source locations, mapping qualification, missingness, and claim boundaries | A valid citation ID can still be irrelevant to the proposition it is used to support |
| Generates theme-level forecast and scenario objects | Requires stable atomic propositions with object, type, period, evidence, assumptions, conditions, competing explanations, and gaps | Reviews cannot precisely target or version a disputed inference |
| One scientific critic reviews the synthesized concept before future forecasts | Reverse review and engineering review independently inspect each future proposition and its original evidence | Forecast claims and implementation conditions escape the intended competitive review |
| Blocking correction expects an unregistered generic correction handler | Affected propositions are locally revised and re-reviewed with bounded iterations | Blocking findings currently do not form a complete repair-and-closure loop |
| Runtime advances through a static ordered loop despite compiling a graph | Conditional branches, parallel reviews, per-claim loops, and independent terminal states are required | One failure or revision is handled at job/theme granularity rather than claim granularity |
| Validator checks evidence-ID membership, IPC/year scope, and prohibited wording | Deterministic numeric fidelity and semantic support/inference-boundary checks are also required | Structural validity can be mistaken for evidentiary validity |
| Legacy path requests 0–100 model confidence and mandatory TRL | Support level is categorical and distinct from event probability; TRL needs external maturity evidence | Model self-assessment can overstate certainty and unsupported maturity |
| Cross-theme synthesis can use forecast summaries without complete adjudicated roadmap inputs | Synthesis must carry prerequisites, retained objections, and full accepted proposition/roadmap records | Global conclusions can hide unresolved local limitations |

The primary users are the thesis researcher assembling Chapter 4 evidence, reviewers assessing Chapter 5 method execution, and later readers tracing a development judgment to its source and review history.

## Goals / Non-Goals

**Goals:**

- Represent the user-defined bounded evidence packet faithfully without requiring a complete knowledge graph.
- Preserve Chapter 4 object identity, evidence type, source location, mapping confidence, unknowns, and inference boundaries in a frozen version.
- Make atomic propositions and their review/version history the central state of the Chapter 5 workflow.
- Implement the five research responsibilities with independent reverse and engineering review and evidence-based adjudication.
- Use deterministic checks for identity and numeric fidelity, and explicit semantic review for support and inference boundaries.
- Make revision local, bounded, rechecked, and auditable; allow unaffected propositions to complete.
- Build roadmaps and cross-theme synthesis only from adjudicated propositions while retaining prerequisites and unresolved objections.
- Keep evidence support, calibrated model probability, model agreement, and engineering maturity as separate concepts.
- Preserve completed legacy results and retain IPC-fusion discovery as an optional, separately labeled mode.
- Provide an empirical evaluation path that does not claim multi-agent superiority before controlled results exist.

**Non-Goals:**

- Building an exhaustive graph of every patent field, all 926 document mappings, and all external papers.
- Re-running BERTopic or Chapter 4 network analysis merely because a traceability attachment is not currently available.
- Treating every empty evidence-packet field as mandatory remediation.
- Replacing real domain experts with an engineering-review prompt.
- Assigning event probabilities from LLM confidence, role agreement, or categorical support levels.
- Automatically merging predicted IPC-fusion concepts into the nine thesis themes.
- Rewriting completed legacy job artifacts or removing their compatibility readers.

## Decisions

### 1. Use a bounded evidence packet with typed evidence records and optional traceability attachments

The packet will have a version, checksum, research contract, object registry, evidence records, attachments, source registry, and validation summary. The object registry contains `T01`–`T09` and may contain `C01`–`C06`. Evidence records use stable IDs and one of these kinds:

- `theme_fact` for Q records;
- `network_observation` for stage/IPC N records;
- `semantic_relation` for H records;
- `method_metric` for M records;
- `engineering_source` for selectively added external evidence;
- `derived_model_evidence` for reviewed deterministic IPC-fusion outputs.

Each record stores applicable object IDs, stage, statement, structured values where present, source locator, relation/mapping basis, limitations, `supports`, and `does_not_support`. Unknown fields remain null with an optional availability note; zero is never used to represent unknown.

The reported 926-document mapping may be attached as rows containing patent/document ID, year, IPC codes, and topic ID. The packet records whether that attachment is supplied and verified for the run. Its absence results in a mapping qualification, not a claim that the mapping work never occurred.

Alternative considered: pass only theme summaries. Rejected because it makes Chapter 5 depend mainly on model prior knowledge. Alternative considered: ingest every raw field and external publication. Rejected because it exceeds the thesis requirement, increases context noise, and turns a traceability problem into an unnecessary knowledge-platform project.

### 2. Keep thesis forecasting and IPC-fusion discovery as separate modes

`thesis_evolution_forecast` uses the frozen Chapter 4 packet and cannot create, delete, merge, or rename thesis objects. `ipc_fusion_discovery` retains deterministic candidate ranking and optional concept synthesis. A reviewed discovery artifact may be imported as `derived_model_evidence` with an explicit object mapping and source/model provenance.

The modes may share storage, deterministic services, checkpoints, and export infrastructure, but they have different entry contracts and output semantics.

Alternative considered: force the current IPC-fusion candidate into every thesis run. Rejected because Chapter 5 evaluates the nine identified themes and conditional paths, not only novel IPC edges.

### 3. Make an atomic, versioned development proposition the unit of work

`DevelopmentClaim` will include:

```text
claim_id, version, parent_version_id
object_ids, claim_type, target_period, scenario
statement, evidence_ids, reasoning_bridge
assumptions, enabling_conditions, validation_requirements
competing_explanations, uncertainty_sources
support_level, unresolved_gaps, status, change_reason
```

`claim_type` is one of `historical_observation`, `conditional_extrapolation`, `target_scenario`, or `insufficient_evidence`. `support_level` is one of `direct_support`, `conditional_support`, `exploratory_scenario`, or `insufficient_evidence`. Support level is not a probability.

Claims containing separable observation, cause, future capability, and timing statements must be split. A revision appends a new immutable version and never overwrites the reviewed version.

Alternative considered: keep one forecast object per theme. Rejected because a single valid historical clause can conceal an unsupported causal or timing clause, and reviewers cannot close findings independently.

### 4. Implement five bounded responsibilities around claims

The roles and authority boundaries are:

1. `evolution_analyst`: converts evidence records into sourced observations and explicit missingness; cannot calculate or alter network metrics.
2. `proposition_generator`: proposes atomic development claims from original evidence plus the evolution summary; cannot add historical facts.
3. `reverse_reviewer`: finds alternative explanations, time leakage, scope shifts, and observation-to-causality/maturity overreach.
4. `engineering_reviewer`: identifies task, interface, environment, safety, reliability, authorization, and validation conditions; it is a model role, not an expert endorsement.
5. `adjudicator`: decides `accept`, `revise`, `downgrade`, or `defer` by resolving findings against evidence, never by majority vote.

Reverse and engineering review execute in parallel from the same claim version and relevant original evidence. Neither sees the other's draft. The adjudicator receives both complete findings.

Alternative considered: keep a generic scientific critic. Rejected because evidence competition and engineering feasibility are different responsibilities and can legitimately reach different conclusions.

### 5. Let LangGraph own branching, local revision, and per-claim termination

The thesis graph is:

```text
freeze_packet -> validate_packet -> evidence_review_interrupt
  -> map evolution_analysis over objects
  -> generate_claims -> structural_and_numeric_validation
  -> fan out each claim to reverse_review + engineering_review
  -> adjudicate
      accept/downgrade -> roadmap eligibility
      revise -> revise_claim -> revalidate -> rereview affected claim
      defer -> terminal claim state
  -> build_topic_roadmaps
  -> cross_theme_synthesis
  -> semantic_and_citation_validation
  -> claim_review_interrupt
  -> publication_gate -> publication_review_interrupt -> complete
```

Revision limits are fixed in the run manifest. Exhaustion changes only the affected claim to `revision_exhausted` or `deferred`; it does not force acceptance and does not fail unrelated claims. Normal completion, insufficient evidence, revision exhaustion, and execution failure are reported separately.

The existing repository remains the durable system of record, but the compiled graph's conditional edges and map/reduce execution replace the static `ORDER` loop for thesis jobs.

### 6. Split deterministic validation from semantic support review

Four validation components will be composed:

- `ReferenceValidator`: evidence/object IDs, packet membership, stage, date, and source existence;
- `NumericClaimValidator`: exact numeric claims and units against structured N/M/source records;
- `InferenceBoundaryValidator`: known invalid transitions such as IPC node to whole theme, centrality to performance, static relation to dynamic acceleration, patent attention to maturity, and target scenario to observed fact;
- `SemanticSupportReviewer`: whether the cited source supports the specific proposition or only a premise/fragment.

Validators return typed findings with check kind, target claim/version, severity, evidence references, and remediation. “Valid reference” and “semantically supported” remain separate results.

Alternative considered: use one LLM critic for all validation. Rejected because exact membership and numeric equality are deterministic and should not consume model judgment, while semantic support cannot be reduced to JSON-schema validity.

### 7. Separate support level, probability, agreement, and TRL

New thesis outputs do not contain a free 0–100 confidence score. They carry categorical evidence support with a reason. Any calibrated probability comes only from an identified deterministic model run and remains attached to its IPC candidate, not copied into a development claim unless the claim explicitly concerns that modeled event.

Agent agreement may be recorded as diagnostic process metadata but never raises support level. TRL is nullable and may be emitted only with maturity evidence IDs and a stated scale; otherwise the roadmap uses capability descriptions and validation criteria.

### 8. Build roadmaps from adjudicated claims, not from fresh unconstrained generation

For each theme, roadmap milestones reference accepted or downgraded claim versions and include target interval, prerequisite capabilities, entry conditions, validation indicators, scenario assumptions, retained objections, and evidence IDs. A later milestone must not depend on a capability scheduled after it.

Cross-theme synthesis receives complete eligible propositions and roadmaps, not shortened forecast summaries. It labels each relationship as network observation, static semantic relation, reviewed model evidence, or engineering-functional hypothesis.

### 9. Persist the full claim-review trace additively

Additive entities will store evidence packet versions/records, claim identities/versions, review findings, adjudications, and claim terminal states. Existing graph events and human reviews will reference these stable IDs. Human edits create a new claim version and reason rather than only storing an unattached `after_json`.

Exports include the packet checksum, prompt/model manifests, claim lineage, findings, adjudications, unresolved gaps, per-state coverage, and validation results. Raw optional attachments can remain file-backed and content-addressed.

### 10. Evaluate workflow effects under controlled inputs and budgets

Evaluation conditions use the same frozen packet, object set, base-model version, target periods, and output contract. Required arms are:

- single-agent baseline;
- five-role workflow;
- budget-comparable single-agent staged reflection;
- predefined ablations of reverse review, engineering review, deterministic validation, and local rereview.

Metrics cover valid citation IDs, semantic support, unsupported extrapolation, condition completeness, finding resolution, output coverage, repeatability of substantive claims/evidence/conditions, calls, tokens, elapsed time, retries, and failures. Perturbation tests alter ordering, summary length, same-source duplication, or remove selected evidence in copied test packets. They never modify authentic evidence records.

Human evaluation hides workflow identity where practical. Results remain “not evaluated” until real outputs and annotations exist.

## Risks / Trade-offs

- [A bounded packet omits potentially relevant external evidence] → Mark packet scope and version prominently; add external evidence only when it supports a new bottleneck, performance, maturity, or breakthrough claim and preserve a new packet version.
- [Functional IPC-theme mappings may be mistaken for verified document membership] → Store mapping basis as a required enum and render it beside dependent claims.
- [Claim atomization can produce excessive records] → Split only independently verifiable observation, cause, capability, or timing clauses and group presentation by theme.
- [Semantic review can share the generator's model bias] → Preserve deterministic checks, independent role prompts, original evidence access, unresolved findings, and human evaluation; do not treat agreement as truth.
- [Local loops make graph state more complex] → Use immutable claim versions, stable IDs, fixed revision limits, idempotent nodes, and content-addressed outputs.
- [Legacy and thesis modes can confuse users] → Require an explicit mode on new jobs, label legacy results, and expose different readiness and output semantics.
- [Optional mapping attachments reduce uniformity across topics] → Report availability and verification status per object and reduce claim specificity rather than blocking every run.
- [Engineering review may sound authoritative] → Label it as model analysis and require evidence or explicit conditional reasoning; reserve expert validation as a separate human/source field.

## Migration Plan

1. Add additive tables and versioned schemas for evidence packets, evidence records, claim versions, findings, adjudications, and terminal states.
2. Add a packet importer/builder that can convert the current JSON draft and optional mapping table without treating null fields as zero or mandatory failures.
3. Seed the stable `T01`–`T09` and `C01`–`C06` object registry from the reviewed Chapter 4 packet; require user review before freezing the first version.
4. Implement deterministic packet and claim validators and contract tests before adding new agent prompts.
5. Add the five role prompts and structured contracts, then build the thesis LangGraph path behind an explicit `thesis_evolution_forecast` mode.
6. Run shadow jobs against fixed fixtures and verify claim lineage, independent reviews, local revision, partial completion, resume, and cancellation.
7. Add evidence/claim review and trace views, followed by roadmap and export changes.
8. Mark the current simple forecast route as legacy for new research runs while preserving its readers and historical artifacts.
9. Execute controlled evaluation runs only after prompts, budgets, revision limits, and annotation rules are preregistered in a run manifest.

Rollback disables creation of thesis-mode jobs and leaves additive tables intact. Existing legacy and IPC-fusion jobs continue to use their original contracts and artifacts. No rollback step deletes evidence packets or completed claim traces.

## Open Questions

- What exact JSON shape and source-location convention does the user's current Chapter 4 packet use, and should the importer accept both table/figure labels and paragraph anchors?
- Which representative patent fields can be distributed in thesis exports, and which should remain local traceability attachments?
- Should the first implementation require one human claim-review gate for the whole theme or allow independent approval per claim?
- What fixed revision and token budgets will be used in the thesis experiment?
- Which external engineering sources, if any, will be added before the first empirical Chapter 5 run?
