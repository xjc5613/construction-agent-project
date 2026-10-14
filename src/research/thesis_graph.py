# -*- coding: utf-8 -*-
"""Claim-centered LangGraph implementing the five Chapter 5 responsibilities."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from src.library import LibraryRepository
from src.research.claim_validation import ClaimValidationSuite
from src.research.evolution_schemas import (
    Adjudication, AdjudicationBatch, ClaimRunSummary, CrossThemeRelation,
    CrossThemeSynthesis, DevelopmentClaim, DevelopmentClaimBatch,
    EvolutionEvidencePacket, EvolutionSummary, EvolutionSummaryBatch,
    ReviewFinding, ReviewFindingBatch, RoadmapBatch, RoadmapMilestone,
)
from src.research.graph import LocalGraphCheckpointer
from src.research.repository import canonical_checksum
from src.research.thesis_repository import ThesisRepository


THESIS_GRAPH_VERSION = "thesis-claim-graph-v1"
THESIS_STATE_VERSION = "thesis-claim-state-v1"
HUMAN_GATES = {"evidence_review", "claim_review", "publication_review"}


class ThesisState(TypedDict, total=False):
    job_id: str
    project_id: str
    packet_version_id: str
    packet: Dict[str, Any]
    run_manifest: Dict[str, Any]
    object_tasks: List[Dict[str, Any]]
    evolution_summaries: List[Dict[str, Any]]
    claims: List[Dict[str, Any]]
    findings: List[Dict[str, Any]]
    adjudications: List[Dict[str, Any]]
    roadmaps: List[Dict[str, Any]]
    synthesis: Dict[str, Any]
    claim_states: Dict[str, str]
    revision_counts: Dict[str, int]
    active_claim_ids: List[str]
    review_decisions: Dict[str, Dict[str, Any]]
    completed_nodes: List[str]
    failures: List[Dict[str, Any]]
    coverage: Dict[str, Any]
    status: str
    waiting_for: str
    current_node: str


@dataclass(frozen=True)
class ThesisGraphContext:
    repository: LibraryRepository
    thesis_repository: ThesisRepository
    job_id: str
    project_id: str
    revision_limit: int = 2
    compute_concurrency: int = 4
    run_budget: Optional[Dict[str, Any]] = None


class ThesisAgentRoles:
    """Typed role adapter. The callback owns provider-specific structured output."""

    SCHEMAS = {
        "evolution_analyst": EvolutionSummaryBatch,
        "proposition_generator": DevelopmentClaimBatch,
        "reverse_reviewer": ReviewFindingBatch,
        "engineering_reviewer": ReviewFindingBatch,
        "adjudicator": AdjudicationBatch,
        "claim_reviser": DevelopmentClaim,
    }

    def __init__(self, invoke_role: Callable[[str, Dict[str, Any], Any], Dict[str, Any]]):
        self.invoke_role = invoke_role

    def invoke(self, role: str, payload: Dict[str, Any]):
        schema = self.SCHEMAS[role]
        raw = self.invoke_role(role, payload, schema)
        return raw if isinstance(raw, schema) else schema.model_validate(raw)


class ThesisDeliberationGraph:
    """Conditional graph with resumable human gates and bounded local claim loops."""

    def __init__(self, context: ThesisGraphContext, roles: ThesisAgentRoles):
        self.context = context
        self.roles = roles
        self.checkpointer = LocalGraphCheckpointer(context.repository)
        self.thread_id: str = ""
        self.validator = ClaimValidationSuite()
        self.compiled = self._compile()

    def _compile(self):
        graph = StateGraph(ThesisState)
        nodes = {
            "validate_packet": self._validate_packet,
            "evidence_review": self._evidence_review,
            "evolution_analysis": self._evolution_analysis,
            "generate_claims": self._generate_claims,
            "validate_claims": self._validate_claims,
            "dual_review": self._dual_review,
            "adjudicate": self._adjudicate,
            "revise_claims": self._revise_claims,
            "build_roadmaps": self._build_roadmaps,
            "cross_theme_synthesis": self._cross_theme_synthesis,
            "final_validation": self._final_validation,
            "claim_review": self._claim_review,
            "publication_gate": self._publication_gate,
            "publication_review": self._publication_review,
            "complete": self._complete,
        }
        for name, handler in nodes.items():
            graph.add_node(name, self._wrapped(name, handler))
        graph.add_edge(START, "validate_packet")
        graph.add_edge("validate_packet", "evidence_review")
        graph.add_conditional_edges("evidence_review", self._gate_route,
                                    {"wait": END, "continue": "evolution_analysis"})
        graph.add_edge("evolution_analysis", "generate_claims")
        graph.add_edge("generate_claims", "validate_claims")
        graph.add_edge("validate_claims", "dual_review")
        graph.add_edge("dual_review", "adjudicate")
        graph.add_conditional_edges("adjudicate", self._adjudication_route,
                                    {"revise": "revise_claims", "roadmap": "build_roadmaps"})
        graph.add_edge("revise_claims", "validate_claims")
        graph.add_edge("build_roadmaps", "cross_theme_synthesis")
        graph.add_edge("cross_theme_synthesis", "final_validation")
        graph.add_edge("final_validation", "claim_review")
        graph.add_conditional_edges("claim_review", self._gate_route,
                                    {"wait": END, "continue": "publication_gate"})
        graph.add_edge("publication_gate", "publication_review")
        graph.add_conditional_edges("publication_review", self._gate_route,
                                    {"wait": END, "continue": "complete"})
        graph.add_edge("complete", END)
        return graph.compile()

    def _wrapped(self, name, handler):
        def run(state):
            if name not in HUMAN_GATES and name in state.get("completed_nodes", []):
                # LangGraph requires every state node to write at least one declared key.
                # Keeping the current marker also makes replayed checkpoints observable.
                return {"current_node": name}
            update = handler(state) or {}
            completed = list(state.get("completed_nodes", []))
            if name not in HUMAN_GATES and name not in {"validate_claims", "dual_review", "adjudicate", "revise_claims"}:
                if name not in completed:
                    completed.append(name)
                update["completed_nodes"] = completed
            update["current_node"] = name
            if self.thread_id:
                merged = self._merge(state, update)
                self.checkpointer.event(self.thread_id, name, "completed")
                self.checkpointer.save(self.thread_id, name, merged, merged.get("status", "running"))
            return update
        return run

    @staticmethod
    def _merge(state, update):
        value = dict(state)
        value.update(update)
        return value

    def start(self, packet_version_id: str) -> Dict[str, Any]:
        packet_row = self.context.thesis_repository.get_packet_version(packet_version_id)
        if not packet_row:
            raise ValueError("演化证据包不存在")
        if packet_row["status"] != "frozen":
            raise ValueError("论文研判只能使用冻结证据包")
        self.thread_id = self.checkpointer.create_thread(self.context.job_id)
        state: ThesisState = {
            "job_id": self.context.job_id, "project_id": self.context.project_id,
            "packet_version_id": packet_version_id, "packet": packet_row["payload"],
            "run_manifest": {"revision_limit": self.context.revision_limit,
                             "compute_concurrency": self.context.compute_concurrency,
                             "budget": self.context.run_budget or {}},
            "object_tasks": [
                {"object_id": item["object_id"], "status": "pending", "error": ""}
                for item in packet_row["payload"].get("objects", [])
                if item.get("object_kind") == "theme"
            ],
            "evolution_summaries": [], "claims": [], "findings": [], "adjudications": [],
            "roadmaps": [], "synthesis": {}, "claim_states": {}, "revision_counts": {},
            "active_claim_ids": [], "review_decisions": {}, "completed_nodes": [],
            "failures": [], "coverage": {}, "status": "running", "waiting_for": "",
            "current_node": "start",
        }
        self.checkpointer.save(self.thread_id, "start", state)
        return self._invoke(state)

    def _invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        final = self.compiled.invoke(state, {"recursion_limit": 100})
        self.checkpointer.save(self.thread_id, final.get("current_node", "graph"), final,
                               final.get("status", "running"))
        return final

    def decide(self, gate: str, decision: str, reason: str, reviewer="local-user",
               after: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if gate not in HUMAN_GATES or decision not in {"approve", "edit", "reject"}:
            raise ValueError("人工审核决定无效")
        if not self.thread_id:
            self.thread_id = self.context.repository.get_forecast_job(self.context.job_id).get("graph_thread_id", "")
        state = self.checkpointer.load(self.thread_id)
        if not state or state.get("waiting_for") != gate:
            raise ValueError("任务当前不在指定审核点")
        decisions = dict(state.get("review_decisions", {}))
        decisions[gate] = {"decision": decision, "reason": reason, "reviewer": reviewer,
                           "after": after or {}}
        state.update({"review_decisions": decisions, "waiting_for": "", "status": "running"})
        if decision == "reject":
            state["status"] = "abandoned"
            self.checkpointer.save(self.thread_id, gate, state, "abandoned")
            return state
        if gate == "claim_review" and decision == "edit" and after:
            state = self._apply_human_claim_edit(state, after, reason)
        self.checkpointer.save(self.thread_id, gate, state, "running")
        return self._invoke(state)

    def resume(self) -> Dict[str, Any]:
        if not self.thread_id:
            job = self.context.repository.get_forecast_job(self.context.job_id) or {}
            self.thread_id = job.get("graph_thread_id", "")
        state = self.checkpointer.load(self.thread_id)
        if not state:
            raise ValueError("论文研判检查点不存在")
        if state.get("status") == "interrupted" and state.get("waiting_for"):
            return state
        if state.get("status") in {"completed", "abandoned", "cancelled"}:
            return state
        state["status"] = "running"
        return self._invoke(state)

    def cancel(self) -> Dict[str, Any]:
        if not self.thread_id:
            job = self.context.repository.get_forecast_job(self.context.job_id) or {}
            self.thread_id = job.get("graph_thread_id", "")
        state = self.checkpointer.load(self.thread_id) or {"job_id": self.context.job_id}
        claim_states = dict(state.get("claim_states", {}))
        for claim_id, status in list(claim_states.items()):
            if status not in {"accepted", "downgraded", "deferred", "revision_exhausted", "execution_failed"}:
                claim_states[claim_id] = "cancelled"
                latest = self._latest_claims(state).get(claim_id)
                if latest:
                    self.context.thesis_repository.set_claim_state(
                        self.context.job_id, claim_id,
                        self.context.thesis_repository.claim_version_id(
                            self.context.job_id, claim_id, latest.version),
                        "cancelled", {"reason": "job_cancelled"})
        state.update({"status": "cancelled", "waiting_for": "", "claim_states": claim_states})
        self.context.repository.update_forecast_job_status(
            self.context.job_id, "cancelled", current_stage="cancelled", artifact_health="partial")
        if self.thread_id:
            self.checkpointer.save(self.thread_id, state.get("current_node", "cancelled"), state, "cancelled")
        return state

    def _validate_packet(self, state):
        packet = EvolutionEvidencePacket.model_validate(state["packet"])
        if packet.status != "frozen":
            raise ValueError("证据包状态必须为frozen")
        return {"packet": packet.model_dump(), "status": "running"}

    def _human_gate(self, name, state):
        decision = state.get("review_decisions", {}).get(name)
        if not decision:
            return {"status": "interrupted", "waiting_for": name}
        if decision["decision"] == "reject":
            return {"status": "abandoned", "waiting_for": ""}
        return {"status": "running", "waiting_for": ""}

    def _evidence_review(self, state): return self._human_gate("evidence_review", state)
    def _claim_review(self, state):
        return {**self._publication_gate(state), **self._human_gate("claim_review", state)}
    def _publication_review(self, state): return self._human_gate("publication_review", state)

    @staticmethod
    def _gate_route(state):
        return "wait" if state.get("status") in {"interrupted", "abandoned"} else "continue"

    def _parallel(self, items, worker):
        results, failures = [], []
        with ThreadPoolExecutor(max_workers=max(1, self.context.compute_concurrency)) as pool:
            futures = {pool.submit(worker, item): item for item in items}
            for future in as_completed(futures):
                item = futures[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    failures.append({"item": str(item), "error": str(exc)})
        return results, failures

    def _evolution_analysis(self, state):
        packet = EvolutionEvidencePacket.model_validate(state["packet"])
        themes = sorted((item for item in packet.objects if item.object_kind == "theme"),
                        key=lambda item: item.object_id)
        def one(obj):
            records = [item.model_dump() for item in packet.records if obj.object_id in item.object_ids]
            result = self.roles.invoke("evolution_analyst", {
                "object": obj.model_dump(), "records": records,
                "packet_checksum": packet.checksum,
            })
            return [item.model_dump() for item in result.summaries]
        values, failures = self._parallel(themes, one)
        summaries = sorted([item for group in values for item in group], key=lambda item: item["object_id"])
        completed_ids = {item["object_id"] for item in summaries}
        tasks = []
        for item in state.get("object_tasks", []):
            if item["object_id"] in completed_ids:
                tasks.append({**item, "status": "completed", "error": ""})
            else:
                error = next((failure["error"] for failure in failures
                              if item["object_id"] in failure.get("item", "")), "")
                tasks.append({**item, "status": "execution_failed" if error else item["status"],
                              "error": error})
        return {"evolution_summaries": summaries,
                "object_tasks": tasks,
                "failures": [*state.get("failures", []), *failures]}

    def _generate_claims(self, state):
        packet = EvolutionEvidencePacket.model_validate(state["packet"])
        summaries = [EvolutionSummary.model_validate(item) for item in state.get("evolution_summaries", [])]
        def one(summary):
            records = [item.model_dump() for item in packet.records
                       if summary.object_id in item.object_ids]
            result = self.roles.invoke("proposition_generator", {
                "summary": summary.model_dump(), "original_records": records,
                "allowed_object_ids": [item.object_id for item in packet.objects],
                "allowed_evidence_ids": [item.evidence_id for item in packet.records],
                "target_periods": ["2026_2030", "2031_2035", "2036_2040"],
            })
            return [item.model_dump() for item in result.claims]
        values, failures = self._parallel(summaries, one)
        claims = sorted([item for group in values for item in group],
                        key=lambda item: (item["object_ids"], item["claim_id"]))
        persisted = []
        for raw in claims:
            claim = DevelopmentClaim.model_validate(raw)
            row = self.context.thesis_repository.create_claim_version(
                self.context.job_id, state["packet_version_id"], claim)
            persisted.append(row["claim"])
        return {"claims": persisted, "active_claim_ids": [item["claim_id"] for item in persisted],
                "claim_states": {item["claim_id"]: "proposed" for item in persisted},
                "revision_counts": {item["claim_id"]: 0 for item in persisted},
                "failures": [*state.get("failures", []), *failures]}

    def _latest_claims(self, state):
        by_id = {}
        for item in state.get("claims", []):
            claim = DevelopmentClaim.model_validate(item)
            if claim.claim_id not in by_id or claim.version > by_id[claim.claim_id].version:
                by_id[claim.claim_id] = claim
        return by_id

    def _validate_claims(self, state):
        packet = EvolutionEvidencePacket.model_validate(state["packet"])
        active = set(state.get("active_claim_ids", []))
        latest = self._latest_claims(state)
        findings = [ReviewFinding.model_validate(item) for item in state.get("findings", [])]
        for claim_id in sorted(active):
            claim = latest[claim_id]
            new = self.validator.validate(claim, packet)
            new_keys = {(item.check_kind, item.category) for item in new}
            if claim.version > 1:
                closed_by = self.context.thesis_repository.claim_version_id(
                    self.context.job_id, claim.claim_id, claim.version)
                for prior in findings:
                    if (prior.claim_id == claim.claim_id
                            and prior.claim_version < claim.version
                            and prior.reviewer_role == "deterministic"
                            and prior.status == "open"
                            and (prior.check_kind, prior.category) not in new_keys):
                        self.context.thesis_repository.close_finding(
                            prior.finding_id, closed_by, self.context.job_id)
                        prior.status = "closed"
                        prior.closed_by_version = claim.version
            findings.extend(new)
            row_id = self.context.thesis_repository.claim_version_id(
                self.context.job_id, claim.claim_id, claim.version)
            self.context.thesis_repository.save_findings(self.context.job_id, row_id, new)
        return {"findings": [item.model_dump() for item in findings]}

    def _dual_review(self, state):
        packet = EvolutionEvidencePacket.model_validate(state["packet"])
        latest, active = self._latest_claims(state), set(state.get("active_claim_ids", []))
        existing = [ReviewFinding.model_validate(item) for item in state.get("findings", [])]
        def one(value):
            role, claim = value
            records = [item.model_dump() for item in packet.records if item.evidence_id in claim.evidence_ids]
            result = self.roles.invoke(role, {"claim": claim.model_dump(), "original_records": records})
            normalized = []
            for finding in result.findings:
                if finding.reviewer_role != role:
                    finding = finding.model_copy(update={"reviewer_role": role})
                normalized.append(finding)
            return normalized
        work = [(role, latest[claim_id]) for claim_id in sorted(active)
                for role in ("reverse_reviewer", "engineering_reviewer")]
        values, failures = self._parallel(work, one)
        new = [item for group in values for item in group]
        for finding in new:
            self.context.thesis_repository.save_findings(
                self.context.job_id,
                self.context.thesis_repository.claim_version_id(
                    self.context.job_id, finding.claim_id, finding.claim_version),
                [finding])
        for claim_id in sorted(active):
            claim = latest[claim_id]
            if claim.version <= 1:
                continue
            new_keys = {(item.reviewer_role, item.check_kind, item.category) for item in new
                        if item.claim_id == claim_id}
            closed_by = self.context.thesis_repository.claim_version_id(
                self.context.job_id, claim_id, claim.version)
            for prior in existing:
                key = (prior.reviewer_role, prior.check_kind, prior.category)
                if (prior.claim_id == claim_id and prior.claim_version < claim.version
                        and prior.reviewer_role in {"reverse_reviewer", "engineering_reviewer"}
                        and prior.status == "open" and key not in new_keys):
                    self.context.thesis_repository.close_finding(
                        prior.finding_id, closed_by, self.context.job_id)
                    prior.status = "closed"
                    prior.closed_by_version = claim.version
        return {"findings": [item.model_dump() for item in [*existing, *new]],
                "failures": [*state.get("failures", []), *failures]}

    def _adjudicate(self, state):
        latest, active = self._latest_claims(state), set(state.get("active_claim_ids", []))
        findings = [ReviewFinding.model_validate(item) for item in state.get("findings", [])]
        def one(claim):
            relevant = [item.model_dump() for item in findings
                        if item.claim_id == claim.claim_id and item.claim_version == claim.version]
            result = self.roles.invoke("adjudicator", {"claim": claim.model_dump(), "findings": relevant})
            return result.adjudications
        values, failures = self._parallel([latest[item] for item in sorted(active)], one)
        adjudications = [item for group in values for item in group]
        states = dict(state.get("claim_states", {})); revisions = dict(state.get("revision_counts", {}))
        to_revise = []
        for value in adjudications:
            relevant = [item for item in findings
                        if item.claim_id == value.claim_id
                        and item.claim_version == value.claim_version
                        and item.status == "open"]
            blocking = [item for item in relevant if item.severity == "blocking"]
            if blocking and value.decision == "accept":
                value = value.model_copy(update={
                    "decision": "revise",
                    "reason": "确定性阻断意见尚未解决；" + value.reason,
                    "finding_ids": sorted(set(value.finding_ids + [item.finding_id for item in blocking])),
                    "unresolved_finding_ids": sorted(set(
                        value.unresolved_finding_ids + [item.finding_id for item in blocking])),
                    "required_changes": [*value.required_changes, "解决所有确定性阻断意见"],
                })
            self.context.thesis_repository.save_adjudication(
                self.context.job_id,
                self.context.thesis_repository.claim_version_id(
                    self.context.job_id, value.claim_id, value.claim_version),
                value)
            if value.decision == "revise":
                if revisions.get(value.claim_id, 0) < self.context.revision_limit:
                    states[value.claim_id] = "revision_required"; to_revise.append(value.claim_id)
                else:
                    states[value.claim_id] = "revision_exhausted"
            elif value.decision == "accept": states[value.claim_id] = "accepted"
            elif value.decision == "downgrade": states[value.claim_id] = "downgraded"
            else: states[value.claim_id] = "deferred"
            if states[value.claim_id] != "revision_required":
                self.context.thesis_repository.set_claim_state(
                    self.context.job_id, value.claim_id,
                    self.context.thesis_repository.claim_version_id(
                        self.context.job_id, value.claim_id, value.claim_version),
                    states[value.claim_id], {"adjudication_id": value.adjudication_id})
        adjudicated_ids = {item.claim_id for item in adjudications}
        for claim_id in sorted(active - adjudicated_ids):
            states[claim_id] = "execution_failed"
            claim = latest[claim_id]
            self.context.thesis_repository.set_claim_state(
                self.context.job_id, claim_id,
                self.context.thesis_repository.claim_version_id(
                    self.context.job_id, claim_id, claim.version),
                "execution_failed", {"stage": "adjudication"})
        return {"adjudications": [*state.get("adjudications", []),
                                  *[item.model_dump() for item in adjudications]],
                "claim_states": states, "active_claim_ids": to_revise,
                "failures": [*state.get("failures", []), *failures]}

    @staticmethod
    def _adjudication_route(state):
        return "revise" if state.get("active_claim_ids") else "roadmap"

    def _revise_claims(self, state):
        latest, active = self._latest_claims(state), set(state.get("active_claim_ids", []))
        findings = [ReviewFinding.model_validate(item) for item in state.get("findings", [])]
        adjudications = [Adjudication.model_validate(item) for item in state.get("adjudications", [])]
        def one(claim):
            relevant = [item.model_dump() for item in findings
                        if item.claim_id == claim.claim_id and item.claim_version == claim.version
                        and item.status != "closed"]
            decision = next(item for item in reversed(adjudications)
                            if item.claim_id == claim.claim_id and item.claim_version == claim.version)
            revised = self.roles.invoke("claim_reviser", {
                "claim": claim.model_dump(), "findings": relevant,
                "required_changes": decision.required_changes,
                "required_version": claim.version + 1,
                "required_parent_version_id": f"{claim.claim_id}:v{claim.version}",
            })
            if revised.claim_id != claim.claim_id or revised.object_ids != claim.object_ids:
                raise ValueError("局部修订不得改变命题或对象身份")
            if revised.version != claim.version + 1 or revised.parent_version_id != f"{claim.claim_id}:v{claim.version}":
                raise ValueError("局部修订版本链无效")
            return revised
        values, failures = self._parallel([latest[item] for item in sorted(active)], one)
        claims = list(state.get("claims", [])); revisions = dict(state.get("revision_counts", {}))
        for claim in values:
            row = self.context.thesis_repository.create_claim_version(
                self.context.job_id, state["packet_version_id"], claim)
            claims.append(row["claim"]); revisions[claim.claim_id] = revisions.get(claim.claim_id, 0) + 1
        states = dict(state.get("claim_states", {}))
        revised_ids = {item.claim_id for item in values}
        for claim_id in sorted(active - revised_ids):
            states[claim_id] = "execution_failed"
            claim = latest[claim_id]
            self.context.thesis_repository.set_claim_state(
                self.context.job_id, claim_id,
                self.context.thesis_repository.claim_version_id(
                    self.context.job_id, claim_id, claim.version),
                "execution_failed", {"stage": "revision"})
        return {"claims": claims, "revision_counts": revisions, "claim_states": states,
                "active_claim_ids": [item.claim_id for item in values],
                "failures": [*state.get("failures", []), *failures]}

    def _build_roadmaps(self, state):
        latest, statuses = self._latest_claims(state), state.get("claim_states", {})
        milestones = []
        for claim_id in sorted(latest):
            claim = latest[claim_id]
            if statuses.get(claim_id) not in {"accepted", "downgraded"} or claim.target_period == "historical":
                continue
            period = claim.target_period if claim.target_period != "cross_period" else "2036_2040"
            milestones.append(RoadmapMilestone(
                milestone_id="milestone_" + canonical_checksum({"claim": claim_id, "v": claim.version})[:12],
                object_id=claim.object_ids[0], period=period, capability=claim.statement,
                claim_version_ids=[self.context.thesis_repository.logical_claim_version_id(
                    claim.claim_id, claim.version)],
                prerequisites=claim.enabling_conditions,
                entry_conditions=claim.assumptions or claim.enabling_conditions,
                validation_indicators=claim.validation_requirements,
                scenario_assumptions=[claim.scenario], evidence_ids=claim.evidence_ids,
                retained_objections=claim.unresolved_gaps,
            ).model_dump())
        return {"roadmaps": milestones}

    def _cross_theme_synthesis(self, state):
        packet = EvolutionEvidencePacket.model_validate(state["packet"])
        eligible = {item["object_id"] for item in state.get("roadmaps", [])}
        relations = []
        for record in packet.records:
            if len(record.object_ids) < 2 or not set(record.object_ids) <= eligible:
                continue
            basis = ("static_semantic_relation" if record.evidence_kind == "semantic_relation"
                     else "network_observation" if record.evidence_kind == "network_observation"
                     else "reviewed_model_evidence" if record.evidence_kind == "derived_model_evidence"
                     else "engineering_functional_hypothesis")
            relations.append(CrossThemeRelation(
                relation_id="relation_" + canonical_checksum(record.model_dump())[:12],
                source_object_id=record.object_ids[0], target_object_id=record.object_ids[1],
                relation_basis=basis, statement=record.statement,
                evidence_ids=[record.evidence_id], limitations=record.limitations,
            ))
        synthesis = CrossThemeSynthesis(
            relations=relations,
            summary="跨主题综合仅使用已裁决命题及其完整路线图。",
            unresolved_gaps=sorted({gap for item in self._latest_claims(state).values()
                                    for gap in item.unresolved_gaps}),
        )
        return {"synthesis": synthesis.model_dump()}

    def _final_validation(self, state):
        # Dependency IDs may point to earlier milestones or capability labels. Reject only
        # explicit milestone IDs scheduled later than their consumer.
        milestones = [RoadmapMilestone.model_validate(item) for item in state.get("roadmaps", [])]
        order = {"2026_2030": 0, "2031_2035": 1, "2036_2040": 2}
        by_id = {item.milestone_id: item for item in milestones}
        errors = []
        for item in milestones:
            if not item.entry_conditions:
                errors.append({"milestone_id": item.milestone_id,
                               "error": "路线图里程碑缺少进入条件"})
            if not item.validation_indicators:
                errors.append({"milestone_id": item.milestone_id,
                               "error": "路线图里程碑缺少验证指标"})
            if not item.scenario_assumptions:
                errors.append({"milestone_id": item.milestone_id,
                               "error": "路线图里程碑缺少情景假设"})
            for dependency in item.prerequisites:
                if dependency in by_id and order[by_id[dependency].period] > order[item.period]:
                    errors.append({"milestone_id": item.milestone_id,
                                   "error": "路线图前置能力晚于当前里程碑"})
        if errors:
            raise ValueError(str(errors))
        return {}

    def _publication_gate(self, state):
        statuses = state.get("claim_states", {})
        coverage = ClaimRunSummary(
            total=len(statuses),
            accepted=sum(value == "accepted" for value in statuses.values()),
            downgraded=sum(value == "downgraded" for value in statuses.values()),
            deferred=sum(value == "deferred" for value in statuses.values()),
            insufficient_evidence=sum(value == "insufficient_evidence" for value in statuses.values()),
            revision_exhausted=sum(value == "revision_exhausted" for value in statuses.values()),
            execution_failed=sum(value == "execution_failed" for value in statuses.values()),
            cancelled=sum(value == "cancelled" for value in statuses.values()),
        )
        return {"coverage": coverage.model_dump()}

    def _complete(self, state):
        self.context.repository.update_forecast_job_status(
            self.context.job_id, "completed", progress=1, current_stage="completed")
        return {"status": "completed", "waiting_for": ""}

    def _apply_human_claim_edit(self, state, after, reason):
        claim_id = after.get("claim_id")
        latest = self._latest_claims(state)
        if claim_id not in latest:
            raise ValueError("人工编辑目标命题不存在")
        current = latest[claim_id]
        payload = current.model_dump()
        allowed = {"statement", "reasoning_bridge", "assumptions", "enabling_conditions",
                   "validation_requirements", "competing_explanations", "uncertainty_sources",
                   "support_level", "support_reason", "unresolved_gaps", "status"}
        for key, value in after.get("changes", {}).items():
            if key not in allowed:
                raise ValueError("人工编辑不得改变命题身份或冻结引用")
            payload[key] = value
        payload.update({"version": current.version + 1,
                        "parent_version_id": f"{current.claim_id}:v{current.version}",
                        "change_reason": reason})
        revised = DevelopmentClaim.model_validate(payload)
        row = self.context.thesis_repository.create_claim_version(
            self.context.job_id, state["packet_version_id"], revised)
        state["claims"] = [*state.get("claims", []), row["claim"]]
        state["active_claim_ids"] = [claim_id]
        state.setdefault("claim_states", {})[claim_id] = "proposed"
        state["roadmaps"] = []
        state["synthesis"] = {}
        state["coverage"] = {}
        invalidated = {"build_roadmaps", "cross_theme_synthesis", "final_validation", "publication_gate", "complete"}
        state["completed_nodes"] = [item for item in state.get("completed_nodes", [])
                                    if item not in invalidated]
        return state
