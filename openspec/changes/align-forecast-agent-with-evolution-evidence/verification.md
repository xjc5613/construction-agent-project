# Verification Report

Date: 2026-10-15

## Verified outcomes

- SQLite migration v9 is additive. A regression test constructs a completed legacy job and a v3 graph checkpoint, removes v9, reapplies the migration, and confirms both records remain readable and unchanged. Legacy jobs receive `legacy_read_only` semantics.
- Evidence packets retain `None` as unknown, distinguish reported-but-not-supplied mapping from verified mapping, use stable checksums, reject same-version overwrite, and require reviewed/frozen state before thesis execution.
- Claims use immutable job-scoped storage identities and readable logical parent IDs. Tests cover local model revision, authoritative human edit lineage, finding closure, restart recovery, cancellation, cross-job isolation, mixed accepted/revision-exhausted outcomes, and unrelated-roadmap continuation.
- B25J-011, B33Y-070, static H evidence, irrelevant citations, paraphrase-only boundary evasion, and TRL scale/evidence constraints are covered by deterministic tests.
- Discovery artifacts cannot enter a thesis packet unless reviewed, mapped to existing T/C objects, and recorded as `derived_model_evidence` with provenance and explicit limitations.
- Research exports include packet checksum and mapping qualification, graph state, coverage, claim versions, findings and closure, adjudications, agent-call manifests, roadmaps, and gaps.
- Controlled evaluation uses explicit `not_run`, `not_estimable`, and `insufficient_annotation` states. Empty denominators return null, not placeholder zero. The implementation and UI make no empirical-superiority claim; superiority can only be assessed after preregistered paired runs and independent annotation.

## Commands and results

- `PYTHONPYCACHEPREFIX=/tmp/thesis-agent-pycache MPLCONFIGDIR=/tmp/matplotlib-cache .venv/bin/python -m pytest -q`
  - Result: **392 passed**.
- `npm run build` in `frontend/`
  - Result: TypeScript and Vite production build passed. Vite reported only a bundle-size warning.
- `npx playwright test e2e/thesis-result.spec.ts` in `frontend/`
  - Result: **1 passed**. It verifies mapping qualification, claim lineage, unsupported/mixed coverage, reviewer findings, and roadmap prerequisites.
- `openspec validate align-forecast-agent-with-evolution-evidence --type change --strict --no-interactive`
  - Result: change is valid.
- `python scripts/migrate_evolution_evidence.py --db <temporary-db>`
  - Result: dry-run inventory completed without modifying records.

## Known repository-wide browser-suite issue

The complete `npm run test:e2e` command was executed. The new thesis-result test and two layout tests passed, while 13 older workbench tests failed because the current branch's active `frontend/src/App.tsx` is the simplified forecast application and those tests still target the dormant multi-page project shell. This mismatch predates the thesis-agent change and is not hidden as a success. The focused thesis workflow is verified; restoring or removing the obsolete shell suite remains separate frontend consolidation work.
