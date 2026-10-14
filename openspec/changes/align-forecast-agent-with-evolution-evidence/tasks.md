## 1. Versioned Data Contracts and Storage

- [x] 1.1 Add versioned Pydantic contracts for thesis objects, evidence packets, typed evidence records, source locators, mapping states, and optional traceability attachments.
- [x] 1.2 Add `DevelopmentClaim`, claim-version, review-finding, adjudication, roadmap-milestone, and per-claim terminal-state contracts with the enumerations defined in the specs.
- [x] 1.3 Add additive SQLite migrations for packet versions/records/sources/attachments, claim identities/versions, findings, adjudications, and claim states.
- [x] 1.4 Add repository methods that create immutable packet and claim versions, resolve lineage, and reject updates to frozen versions.
- [x] 1.5 Add indexes and uniqueness constraints for packet checksum, evidence ID within a packet, claim/version identity, finding targets, and idempotent adjudications.
- [x] 1.6 Add migration and repository tests proving that completed legacy jobs and existing research v3 artifacts remain readable and unchanged.

## 2. Chapter 4 Evidence Packet Builder

- [x] 2.1 Implement an importer for the current Chapter 4 JSON draft that preserves null as unknown and never converts missing values to zero.
- [x] 2.2 Implement stable registration and validation for `T01`–`T09` and optional candidate records `C01`–`C06` without implicit merges or promotions.
- [x] 2.3 Implement Q/N/H/M and external/derived evidence adapters with structured stages, values, sources, relation basis, limitations, `supports`, and `does_not_support` fields.
- [x] 2.4 Implement source-locator normalization for Chapter 4 tables, figures, paragraphs, files, and existing deterministic artifacts.
- [x] 2.5 Implement optional IPC-patent-topic mapping attachment ingestion and the supplied/verified/reported/unavailable state transitions.
- [x] 2.6 Implement optional representative-patent references without requiring a representative patent for every topic.
- [x] 2.7 Implement packet checksum, freeze, diff, version history, and validation-summary services under research contract v3.
- [x] 2.8 Add fixture packets for the robot and additive-manufacturing examples, including functional-only mappings and unsupported extrapolation boundaries.
- [x] 2.9 Add tests for bounded packet validity, optional fields, unknown handling, source resolution, mapping qualification, version immutability, and checksum stability.

## 3. Thesis and Discovery Mode Separation

- [x] 3.1 Add an explicit job mode contract for `thesis_evolution_forecast`, `ipc_fusion_discovery`, and legacy read-only results.
- [x] 3.2 Update thesis job readiness and start APIs to require a reviewed frozen evolution packet and research contract v3 instead of requiring an IPC-fusion candidate list.
- [x] 3.3 Preserve the current deterministic fusion path as discovery mode and label its probabilities, candidates, and concept outputs with discovery provenance.
- [x] 3.4 Implement a reviewed import action that maps a discovery artifact to thesis objects as `derived_model_evidence` without changing object definitions.
- [x] 3.5 Add API and contract tests preventing unreviewed discovery candidates from entering thesis packets or creating thesis themes.

## 4. Deterministic and Semantic Validation

- [x] 4.1 Implement `ReferenceValidator` for packet membership, evidence/object identity, research stage, IPC, date, and source-location checks.
- [x] 4.2 Implement `NumericClaimValidator` that resolves structured values, units, directions, stages, and object identifiers without LLM judgment.
- [x] 4.3 Implement `InferenceBoundaryValidator` rules for IPC-to-theme, centrality-to-performance, static-to-dynamic, patent-to-maturity, domain-to-topic-lifecycle, and scenario-to-observation transitions.
- [x] 4.4 Add a typed semantic-support review contract for whole, partial, contradictory, and indeterminate support.
- [x] 4.5 Implement finding persistence, stable IDs, severity, remediation, open/closed status, and closure references to claim versions.
- [x] 4.6 Enforce categorical support levels and remove free model confidence from new thesis-mode output contracts.
- [x] 4.7 Require maturity evidence IDs and a named scale before allowing an optional TRL value in thesis-mode milestones.
- [x] 4.8 Add validation tests covering the B25J-011 node/theme boundary, B33Y-070 divergent metric directions, static H relations, valid-but-irrelevant citations, and paraphrase-only revisions.

## 5. Five-Role Agent Contracts and Prompts

- [x] 5.1 Add versioned prompts and structured inputs/outputs for the evolution analyst with read-only numeric evidence and explicit missingness.
- [x] 5.2 Add the proposition-generator prompt and enforce atomic claim splitting, four claim types, and original-evidence access.
- [x] 5.3 Add the reverse-review prompt and finding categories for competing explanations, time leakage, scope shift, causality, maturity, and source independence.
- [x] 5.4 Add the engineering-review prompt and finding categories for task decomposition, interfaces, environment, safety, reliability, authorization, and validation.
- [x] 5.5 Add the adjudicator prompt and output contract for accept, revise, downgrade, and defer decisions with evidence-based reasons.
- [x] 5.6 Add the local claim-reviser prompt that can modify only the targeted claim fields and must address cited findings explicitly.
- [x] 5.7 Persist role-specific prompt/model manifests, run budgets, revision limits, and model-call traces for every thesis job.
- [x] 5.8 Add prompt contract tests proving that roles cannot alter frozen evidence, deterministic probability, object identity, or prior claim versions.

## 6. Claim-Centered LangGraph Runtime

- [x] 6.1 Define the thesis graph state using packet references, object tasks, claim/version IDs, review findings, adjudications, roadmaps, unresolved gaps, and per-claim statuses.
- [x] 6.2 Replace static ordered execution for thesis jobs with compiled conditional LangGraph edges and durable checkpoints.
- [x] 6.3 Implement object-level parallel evolution analysis and proposition generation with deterministic result ordering and partial-failure recording.
- [x] 6.4 Implement independent parallel reverse and engineering review branches that receive the same claim version and original evidence.
- [x] 6.5 Implement adjudication routing to accept, downgrade, local revise, or defer without vote-count logic.
- [x] 6.6 Implement bounded local revision, full affected-claim revalidation/rereview, finding closure, and revision-exhausted termination.
- [x] 6.7 Ensure a deferred, exhausted, or failed claim does not block unrelated claims and is included in job coverage summaries.
- [x] 6.8 Implement evidence-review, claim-review, and publication-review interrupts with resume, rejection, cancellation, and idempotent retry.
- [x] 6.9 Add graph tests for independent reviews, mixed claim outcomes, local revision, revision exhaustion, restart recovery, cancellation, and cross-job isolation.

## 7. Roadmaps, Synthesis, and Research Exports

- [x] 7.1 Implement per-theme roadmap construction from accepted or downgraded claim versions only.
- [x] 7.2 Add prerequisite ordering, entry-condition, validation-indicator, scenario-assumption, evidence, and retained-objection checks for milestones.
- [x] 7.3 Implement cross-theme synthesis from complete adjudicated claims and roadmaps with explicit relation-basis labels.
- [x] 7.4 Add result views and APIs for packet summary, claim lineage, dual reviews, adjudication, finding closure, roadmap prerequisites, gaps, and mixed terminal states.
- [x] 7.5 Make human claim edits create authoritative new versions and link review before/after values and reasons.
- [x] 7.6 Extend research exports with packet checksum, claim trace, prompts/models, validation findings, adjudications, support reasons, unresolved gaps, and coverage statistics.
- [x] 7.7 Preserve compatibility rendering for legacy 0–100 confidence and TRL outputs while clearly labeling them as legacy semantics.
- [x] 7.8 Add API, export, and frontend tests for source drill-down, mapping qualification, unsupported-claim visibility, human edit lineage, and mixed result coverage.

## 8. Controlled Method Evaluation

- [x] 8.1 Define a preregistered evaluation manifest covering evidence packet, objects, model, prompts, budgets, revision limits, repeats, annotation rules, and metrics.
- [x] 8.2 Implement paired runners for the single-agent baseline, five-role workflow, and budget-comparable staged-reflection baseline.
- [x] 8.3 Implement one-factor ablations for reverse review, engineering review, deterministic validation, and local rereview.
- [x] 8.4 Implement metrics for reference validity, numeric fidelity, semantic support, unsupported extrapolation, condition completeness, finding resolution, coverage, calls, tokens, elapsed time, retries, and failures.
- [x] 8.5 Implement substantive repeatability comparison over claim meaning, evidence, prerequisites, support levels, and unresolved gaps rather than text similarity alone.
- [x] 8.6 Implement copied-packet perturbations for evidence order, summary length, same-source duplication, and selected-evidence removal without mutating authentic packets.
- [x] 8.7 Add blinded human-review exports, disagreement capture, adjudication records, and protection against using model engineering review as its own sole label.
- [x] 8.8 Report `not_run`, `not_estimable`, and `insufficient_annotation` honestly and add tests preventing placeholder zeros or unsupported superiority claims.

## 9. Documentation, Migration, and Verification

- [x] 9.1 Document the bounded evidence-packet template, optional mapping attachment, source-locator conventions, null semantics, and examples for T03 and T08.
- [x] 9.2 Document the thesis/discovery/legacy mode distinction and the separation of support level, calibrated probability, agreement, and TRL.
- [x] 9.3 Add a dry-run migration/inventory command that reports compatible evidence, missing optional attachments, legacy jobs, and records requiring researcher review without modifying data.
- [x] 9.4 Add an apply mode that creates additive packet/object records only after review and writes a reversible migration report.
- [x] 9.5 Run backend unit/integration tests, research empirical fixtures, TypeScript build, and workflow browser tests.
- [x] 9.6 Run `openspec validate align-forecast-agent-with-evolution-evidence --type change --strict --no-interactive` and resolve all artifact or scenario errors.
- [x] 9.7 Record a verification report demonstrating that legacy results remain readable, thesis packets remain immutable, claims are traceable, and no workflow claims empirical superiority without completed evaluation.
