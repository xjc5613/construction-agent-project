## ADDED Requirements

### Requirement: Controlled workflow comparison
The evaluation system SHALL compare workflows using the same frozen evidence packet, object set, time range, base-model version, available tools, and output contract. It SHALL record input/output tokens, calls, elapsed time, retries, and failures.

#### Scenario: Multi-agent run receives more evidence
- **WHEN** the multi-agent arm receives sources unavailable to the single-agent arm
- **THEN** the run is rejected as a controlled comparison or reported as a different-input exploratory comparison

### Requirement: Required evaluation arms
The evaluation plan SHALL include a single-agent baseline, the five-role workflow, and a budget-comparable single-agent staged-reflection baseline. Predefined ablations SHALL isolate reverse review, engineering review, deterministic validation, and local rereview one factor at a time.

#### Scenario: Multiple components are removed together
- **WHEN** an experiment removes both reverse review and engineering review
- **THEN** it is labeled a combined ablation and is not attributed to either component individually

### Requirement: Evidence-use and coverage measures
Evaluation SHALL separately measure valid citation IDs, numeric fidelity, semantic support, unsupported extrapolation, relevant condition completeness, finding resolution, accepted/deferred/insufficient/failed coverage, and resource cost.

#### Scenario: Workflow reports only successful themes
- **WHEN** deferred or failed claims are omitted from the evaluation result
- **THEN** the evaluation fails the coverage requirement

### Requirement: Substantive repeatability assessment
Repeatability SHALL compare core proposition meaning, evidence references, prerequisites, support levels, and unresolved gaps rather than raw text similarity alone.

#### Scenario: Different wording preserves the same proposition
- **WHEN** two runs use different wording but retain equivalent claims, evidence, conditions, and boundaries
- **THEN** the evaluator may count them as substantively stable

#### Scenario: Identical wording repeats the same omission
- **WHEN** two runs use similar wording and both omit a required engineering condition
- **THEN** the evaluator does not treat textual stability as quality

### Requirement: Controlled evidence perturbation
The evaluator SHALL support copied test packets with altered evidence order, summary length, same-source duplication, or selected evidence removal while preserving the authentic packet unchanged and labeling the input as a method test.

#### Scenario: Key evidence is removed
- **WHEN** a copied perturbation packet removes the principal support for a claim
- **THEN** the evaluator checks whether the workflow reduces support, revises, or defers the claim and never writes the altered packet back as authentic evidence

### Requirement: Independent and blind review where practical
Human evaluation SHALL use predefined claim-level rules and SHALL hide workflow identity and role labels where practical. Model-generated engineering review SHALL NOT be the sole reference label for evaluating itself.

#### Scenario: Human reviewers disagree
- **WHEN** reviewers assign different semantic-support labels
- **THEN** the system records the disagreement, adjudication rule, and final label rather than silently selecting one

### Requirement: Honest evaluation status
The system SHALL report evaluation dimensions as `not_run`, `not_estimable`, or `insufficient_annotation` until the required real outputs, event labels, or independent annotations exist. It SHALL NOT publish placeholder zeros or claim multi-agent superiority from architecture alone.

#### Scenario: No controlled outputs exist
- **WHEN** the comparison pipeline is configured but no paired runs have been executed
- **THEN** the result states `not_run` and presents only the evaluation design

