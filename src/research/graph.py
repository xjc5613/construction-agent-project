# -*- coding: utf-8 -*-
"""Persistent, bounded and evidence-constrained LangGraph runtime for v3 jobs."""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Annotated, Any, Callable, Dict, List, Optional, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from src.library import LibraryRepository
from src.research.repository import canonical_checksum
from src.research.agent_schemas import (
    CriticFinding, EvidenceAnalysis, ScenarioRoadmap, TechnologyConcept, ThemeForecast,
)
from src.research.langchain_adapter import invoke_with_bounded_correction


GRAPH_VERSION = "forecast-graph-v1"
STATE_SCHEMA_VERSION = "forecast-state-v1"
REVIEW_NODES = {"fusion_review", "theme_review", "publication_review"}


def append_values(left: List[Any], right: List[Any]) -> List[Any]:
    return [*left, *right]


class ArtifactReference(BaseModel):
    artifact_type: str
    artifact_id: str
    checksum: str
    schema_version: str


class ForecastState(TypedDict, total=False):
    job_id: str
    project_id: str
    snapshot_ref: Dict[str, Any]
    artifact_refs: Annotated[List[Dict[str, Any]], append_values]
    failures: Annotated[List[Dict[str, Any]], append_values]
    events: Annotated[List[Dict[str, Any]], append_values]
    evidence_tasks: List[Dict[str, Any]]
    theme_tasks: List[Dict[str, Any]]
    evidence_results: List[Dict[str, Any]]
    theme_results: List[Dict[str, Any]]
    critic_findings: List[Dict[str, Any]]
    correction_iteration: int
    review_decisions: Dict[str, Dict[str, Any]]
    publication_gate_result: Dict[str, Any]
    current_node: str
    status: str


@dataclass(frozen=True)
class GraphRuntimeContext:
    repository: LibraryRepository
    job_id: str
    project_id: str
    model_config: Dict[str, Any]
    output_root: str
    compute_concurrency: int = 4
    correction_limit: int = 2


class BoundedAgentNodes:
    """Typed agent roles; deterministic artifacts remain authoritative inputs."""
    def __init__(self, invoke_role: Callable[[str, Dict[str, Any]], Dict[str, Any]],
                 correction_limit: int = 2):
        self.invoke_role = invoke_role
        self.correction_limit = correction_limit

    def _invoke(self, role, payload, schema, frozen):
        return invoke_with_bounded_correction(
            lambda request: self.invoke_role(role, request), payload, schema, frozen,
            max_retries=self.correction_limit,
        ).model_dump()

    def evidence_analysis(self, state):
        task = state["task"]
        frozen = state.get("frozen_contract", {})
        return {"id": task.get("id", ""), "result": self._invoke(
            "evidence_analyst", {"task": task, "snapshot_ref": state.get("snapshot_ref")},
            EvidenceAnalysis, frozen,
        )}

    def concept_synthesis(self, state):
        concept = self._invoke(
            "technology_concept_synthesizer",
            {"evidence_results": state.get("evidence_results", []),
             "candidate_refs": state.get("candidate_refs", []),
             "stage_analysis": state.get("stage_analysis", []),
             "target_contract": state.get("frozen_contract", {})},
            TechnologyConcept, state.get("frozen_contract", {}),
        )
        theme_id = "theme_" + canonical_checksum(concept)[:12]
        return {"technology_concept": concept, "theme_tasks": [
            {"id": theme_id + "_forecast", "theme_id": theme_id, "output_kind": "forecast", "concept": concept},
            {"id": theme_id + "_scenario", "theme_id": theme_id, "output_kind": "scenario", "concept": concept},
        ]}

    def scientific_critic(self, state):
        finding = self._invoke(
            "scientific_critic", {"technology_concept": state.get("technology_concept", {})},
            CriticFinding, state.get("frozen_contract", {}),
        )
        return {"critic_findings": [finding],
                "requires_correction": finding.get("severity") == "blocking"}

    def theme_forecasts(self, state):
        task, frozen = state["task"], state.get("frozen_contract", {})
        schema = ScenarioRoadmap if task.get("output_kind") == "scenario" else ThemeForecast
        return {"id": task.get("id", ""), "result": self._invoke(
            "scenario_roadmap" if schema is ScenarioRoadmap else "topic_forecaster",
            {"task": task, "stage_analysis": state.get("stage_analysis", []),
             "candidate_refs": state.get("candidate_refs", []),
             "evidence_results": state.get("evidence_results", []),
             "target_contract": frozen}, schema, frozen,
        )}

    def handlers(self):
        return {"evidence_analysis": self.evidence_analysis,
                "concept_synthesis": self.concept_synthesis,
                "scientific_critic": self.scientific_critic,
                "theme_forecasts": self.theme_forecasts}


class LocalGraphCheckpointer:
    def __init__(self, repository: LibraryRepository):
        self.repository = repository

    def create_thread(self, job_id: str) -> str:
        with self.repository.db.transaction() as connection:
            existing = connection.execute(
                "SELECT thread_id FROM graph_threads WHERE job_id=?", (job_id,)
            ).fetchone()
            if existing:
                return existing[0]
            thread_id = "thread_" + uuid4().hex[:16]
            connection.execute(
                """INSERT INTO graph_threads(thread_id,job_id,graph_version,state_schema_version)
                   VALUES (?,?,?,?)""", (thread_id, job_id, GRAPH_VERSION, STATE_SCHEMA_VERSION)
            )
            connection.execute(
                "UPDATE forecast_jobs SET graph_thread_id=? WHERE job_id=?", (thread_id, job_id)
            )
        return thread_id

    def save(self, thread_id: str, node_name: str, state: Dict[str, Any], status="completed") -> str:
        rendered = json.dumps(state, ensure_ascii=False, sort_keys=True, default=str)
        checksum = canonical_checksum(state)
        with self.repository.db.transaction() as connection:
            existing = connection.execute(
                "SELECT checkpoint_id FROM graph_checkpoints WHERE thread_id=? AND state_checksum=?",
                (thread_id, checksum),
            ).fetchone()
            if existing:
                return existing[0]
            sequence = int(connection.execute(
                "SELECT COALESCE(MAX(sequence),0)+1 FROM graph_checkpoints WHERE thread_id=?",
                (thread_id,),
            ).fetchone()[0])
            checkpoint_id = "checkpoint_" + uuid4().hex[:16]
            connection.execute(
                """INSERT INTO graph_checkpoints(checkpoint_id,thread_id,sequence,node_name,
                   state_json,state_checksum,status) VALUES (?,?,?,?,?,?,?)""",
                (checkpoint_id, thread_id, sequence, node_name, rendered, checksum, status),
            )
            connection.execute(
                "UPDATE graph_threads SET status=?,current_node=?,updated_at=CURRENT_TIMESTAMP WHERE thread_id=?",
                (state.get("status", status), node_name, thread_id),
            )
        return checkpoint_id

    def load(self, thread_id: str) -> Optional[Dict[str, Any]]:
        with self.repository.db.connect() as connection:
            row = connection.execute(
                """SELECT state_json,state_checksum FROM graph_checkpoints WHERE thread_id=?
                   ORDER BY sequence DESC LIMIT 1""", (thread_id,)
            ).fetchone()
        if not row:
            return None
        state = json.loads(row["state_json"])
        if canonical_checksum(state) != row["state_checksum"]:
            raise ValueError("图检查点校验和不匹配")
        return state

    def event(self, thread_id: str, node_name: str, event_type: str,
              input_refs=None, output_refs=None, error=None, metadata=None) -> str:
        event_id = "event_" + uuid4().hex[:16]
        output_refs = output_refs or []
        with self.repository.db.transaction() as connection:
            connection.execute(
                """INSERT INTO graph_node_events(event_id,thread_id,node_name,event_type,
                   input_refs_json,output_refs_json,output_checksum,metadata_json,error_json)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (event_id, thread_id, node_name, event_type,
                 json.dumps(input_refs or [], sort_keys=True), json.dumps(output_refs, sort_keys=True),
                 canonical_checksum(output_refs), json.dumps(metadata or {}, sort_keys=True),
                 json.dumps(error or {}, ensure_ascii=False, sort_keys=True)),
            )
        return event_id


class EvidenceConstrainedForecastGraph:
    ORDER = [
        "validate_scope", "freeze_snapshot", "construct_network", "validation_model",
        "rank_candidates", "evidence_analysis", "fusion_review", "concept_synthesis",
        "scientific_critic", "theme_review", "theme_forecasts", "citation_validation",
        "publication_gates", "asset_generation", "publication_review", "completed",
    ]

    def __init__(self, context: GraphRuntimeContext,
                 handlers: Optional[Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]]] = None):
        self.context = context
        self.repository = context.repository
        self.checkpointer = LocalGraphCheckpointer(self.repository)
        self.handlers = handlers or {}
        self.compiled = self._compile_langgraph()

    def _compile_langgraph(self):
        builder = StateGraph(ForecastState)
        for node in self.ORDER[:-1]:
            builder.add_node(node, lambda state, name=node: self._node(name, state))
        builder.add_edge(START, self.ORDER[0])
        for current, following in zip(self.ORDER[:-2], self.ORDER[1:-1]):
            builder.add_edge(current, following)
        builder.add_edge(self.ORDER[-2], END)
        return builder.compile()

    def _node(self, name: str, state: Dict[str, Any]) -> Dict[str, Any]:
        handler = self.handlers.get(name)
        if handler:
            return handler(state) or {}
        return {"events": [{"node": name, "status": "completed"}]}

    def start(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        thread_id = self.checkpointer.create_thread(self.context.job_id)
        state = {**initial_state, "job_id": self.context.job_id,
                 "project_id": self.context.project_id, "artifact_refs": [], "failures": [],
                 "events": [], "review_decisions": {}, "correction_iteration": 0,
                 "current_node": "", "status": "running"}
        self.checkpointer.save(thread_id, "start", state)
        return self.run(thread_id)

    def run(self, thread_id: str) -> Dict[str, Any]:
        state = self.checkpointer.load(thread_id)
        if not state:
            raise ValueError("图检查点不存在")
        if state.get("status") in {"cancelled", "abandoned", "completed"}:
            return state
        start_index = 0
        if state.get("current_node") in self.ORDER:
            start_index = self.ORDER.index(state["current_node"])
            if state.get("status") != "interrupted":
                start_index += 1
        for name in self.ORDER[start_index:]:
            if self._cancel_requested():
                state.update({"status": "cancelled", "current_node": name})
                self.checkpointer.save(thread_id, name, state, "cancelled")
                return state
            if name == "completed":
                state.update({"status": "completed", "current_node": name})
                self.checkpointer.save(thread_id, name, state)
                self.repository.update_forecast_job_status(
                    self.context.job_id, "completed", progress=1, current_stage="completed"
                )
                return state
            if name in REVIEW_NODES and name not in state.get("review_decisions", {}):
                state.update({"status": "interrupted", "current_node": name})
                self.checkpointer.event(thread_id, name, "interrupt")
                self.checkpointer.save(thread_id, name, state, "interrupted")
                self.repository.update_forecast_job_status(
                    self.context.job_id, "running", current_stage=name,
                    progress=self.ORDER.index(name) / (len(self.ORDER) - 1),
                )
                return state
            try:
                self.checkpointer.event(thread_id, name, "started", state.get("artifact_refs", []))
                update = self._parallel_node(name, state) if name in {"evidence_analysis", "theme_forecasts"} else self._node(name, state)
                if name == "scientific_critic" and update.get("requires_correction"):
                    correction = self.handlers.get("schema_correction")
                    corrected = False
                    for iteration in range(1, self.context.correction_limit + 1):
                        state["correction_iteration"] = iteration
                        correction_update = correction(state) if correction else {}
                        state = self._merge(state, correction_update)
                        if not correction_update.get("requires_correction", False):
                            corrected = True
                            break
                    if not corrected:
                        raise ValueError("科学批评/结构校正超过最大迭代次数")
                state = self._merge(state, update)
                state.update({"status": "running", "current_node": name})
                self.checkpointer.event(thread_id, name, "completed",
                                        output_refs=update.get("artifact_refs", []))
                self.checkpointer.save(thread_id, name, state)
                self.repository.update_forecast_job_status(
                    self.context.job_id, "running", current_stage=name,
                    progress=(self.ORDER.index(name) + 1) / (len(self.ORDER) - 1),
                )
            except Exception as exc:
                state = self._merge(state, {"failures": [{"node": name, "error": str(exc)}]})
                state.update({"status": "failed", "current_node": name})
                self.checkpointer.event(thread_id, name, "failed", error={"message": str(exc)})
                self.checkpointer.save(thread_id, name, state, "failed")
                self.repository.update_forecast_job_status(
                    self.context.job_id, "failed", current_stage=name,
                    error_code="graph_node_failed", error_message=str(exc), artifact_health="partial",
                )
                return state
        return state

    def _parallel_node(self, name, state):
        tasks_key = "evidence_tasks" if name == "evidence_analysis" else "theme_tasks"
        output_key = "evidence_results" if name == "evidence_analysis" else "theme_results"
        worker = self.handlers.get(name)
        if not worker:
            return {output_key: [], "events": [{"node": name, "status": "skipped"}]}
        results, failures = [], []
        with ThreadPoolExecutor(max_workers=max(1, self.context.compute_concurrency)) as pool:
            futures = {pool.submit(worker, {**state, "task": task}): task
                       for task in state.get(tasks_key, [])}
            for future in as_completed(futures):
                task = futures[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    failures.append({"node": name, "task_id": task.get("id", ""), "error": str(exc)})
        return {output_key: sorted(results, key=lambda item: str(item.get("id", ""))),
                "failures": failures}

    @staticmethod
    def _merge(state, update):
        result = dict(state)
        for key, value in update.items():
            if key in {"artifact_refs", "failures", "events"}:
                result[key] = [*result.get(key, []), *value]
            else:
                result[key] = value
        return result

    def decide(self, thread_id: str, review_node: str, decision: str,
               after: Dict[str, Any], reason: str, reviewer="local-user") -> Dict[str, Any]:
        if review_node not in REVIEW_NODES or decision not in {"approve", "edit", "reject"}:
            raise ValueError("审核决策无效")
        state = self.checkpointer.load(thread_id)
        if not state or state.get("current_node") != review_node or state.get("status") != "interrupted":
            raise ValueError("当前不在该审核中断点")
        before_key = {
            "fusion_review": "candidate_refs",
            "theme_review": "theme_results",
            "publication_review": "publication_gate_result",
        }[review_node]
        before = state.get(before_key, {})
        with self.repository.db.transaction() as connection:
            connection.execute(
                """INSERT INTO human_reviews(review_id,thread_id,review_kind,target_id,decision,
                   before_json,after_json,reason,reviewer) VALUES (?,?,?,?,?,?,?,?,?)""",
                ("review_" + uuid4().hex[:16], thread_id, review_node, self.context.job_id,
                 decision, json.dumps(before, ensure_ascii=False, sort_keys=True),
                 json.dumps(after, ensure_ascii=False, sort_keys=True), reason, reviewer),
            )
        decisions = dict(state.get("review_decisions", {}))
        decisions[review_node] = {"decision": decision, "after": after, "reason": reason,
                                  "reviewer": reviewer}
        state.update({"review_decisions": decisions, "status": "running", "current_node": review_node})
        self.checkpointer.save(thread_id, review_node, state)
        if decision == "reject":
            state["status"] = "abandoned"
            self.checkpointer.save(thread_id, review_node, state, "abandoned")
            return state
        return self.run(thread_id)

    def cancel(self, thread_id: str) -> Dict[str, Any]:
        self.repository.request_forecast_cancellation(self.context.job_id)
        state = self.checkpointer.load(thread_id) or {}
        state.update({"status": "cancelled"})
        self.checkpointer.save(thread_id, state.get("current_node", "cancelled"), state, "cancelled")
        return state

    def abandon(self, thread_id: str) -> Dict[str, Any]:
        state = self.checkpointer.load(thread_id) or {}
        state.update({"status": "abandoned"})
        self.checkpointer.save(thread_id, state.get("current_node", "abandoned"), state, "abandoned")
        return state

    def retry(self, thread_id: str) -> Dict[str, Any]:
        state = self.checkpointer.load(thread_id) or {}
        if state.get("status") != "failed" or state.get("current_node") not in self.ORDER:
            raise ValueError("只有失败节点可以重试")
        index = self.ORDER.index(state["current_node"])
        state["current_node"] = self.ORDER[index - 1] if index else ""
        state["status"] = "running"
        self.checkpointer.save(thread_id, state["current_node"] or "retry", state)
        return self.run(thread_id)

    def _cancel_requested(self):
        job = self.repository.get_forecast_job(self.context.job_id)
        return bool(job and job.get("cancel_requested_at"))
