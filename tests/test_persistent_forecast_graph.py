# -*- coding: utf-8 -*-
import json

import pytest

from src.library import LibraryDatabase, LibraryRepository
from src.research.graph import (
    BoundedAgentNodes, EvidenceConstrainedForecastGraph, GraphRuntimeContext, LocalGraphCheckpointer,
)
from src.research.agent_schemas import TechnologyConcept


def _graph(tmp_path, suffix="one", handlers=None, correction_limit=2):
    repository = LibraryRepository(LibraryDatabase(tmp_path / (suffix + ".sqlite3")))
    project = repository.create_project("project " + suffix)
    job_id = "job-" + suffix
    repository.reserve_forecast_job(
        job_id, project["project_id"], request_checksum="request-" + suffix,
        idempotency_key="key-" + suffix,
    )
    repository.update_forecast_job_status(job_id, "running")
    context = GraphRuntimeContext(
        repository=repository, job_id=job_id, project_id=project["project_id"],
        model_config={"model": "fake"}, output_root=str(tmp_path / suffix),
        compute_concurrency=2, correction_limit=correction_limit,
    )
    return repository, EvidenceConstrainedForecastGraph(context, handlers)


def test_normal_interrupt_resume_completion_and_audit(tmp_path):
    handlers = {
        "evidence_analysis": lambda state: {"id": state["task"]["id"], "status": "ok"},
        "theme_forecasts": lambda state: {"id": state["task"]["id"], "status": "ok"},
        "construct_network": lambda _state: {"artifact_refs": [{
            "artifact_type": "network", "artifact_id": "n1", "checksum": "abc",
            "schema_version": "v1",
        }]},
    }
    repository, graph = _graph(tmp_path, handlers=handlers)
    state = graph.start({
        "evidence_tasks": [{"id": "paper"}, {"id": "patent"}],
        "theme_tasks": [{"id": "theme-a"}],
    })
    assert state["status"] == "interrupted"
    assert state["current_node"] == "fusion_review"
    thread_id = repository.get_forecast_job("job-one")["graph_thread_id"]

    # A fresh process-equivalent instance resumes from the durable checkpoint.
    restarted = EvidenceConstrainedForecastGraph(graph.context, handlers)
    state = restarted.decide(thread_id, "fusion_review", "approve", {}, "model ranks reviewed")
    assert state["current_node"] == "theme_review"
    state = restarted.decide(thread_id, "theme_review", "edit", {"name": "edited"}, "clarified label")
    assert state["current_node"] == "publication_review"
    state = restarted.decide(thread_id, "publication_review", "approve", {}, "all gates reviewed")
    assert state["status"] == "completed"
    assert repository.get_forecast_job("job-one")["status"] == "completed"
    with repository.db.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM graph_checkpoints").fetchone()[0] > 10
        assert connection.execute("SELECT COUNT(*) FROM graph_node_events").fetchone()[0] > 10
        assert connection.execute("SELECT COUNT(*) FROM human_reviews").fetchone()[0] == 3


def test_parallel_partial_failure_is_visible_but_other_workers_continue(tmp_path):
    def worker(state):
        if state["task"]["id"] == "bad":
            raise RuntimeError("provider failed")
        return {"id": state["task"]["id"], "status": "ok"}
    _, graph = _graph(tmp_path, "partial", {"evidence_analysis": worker})
    state = graph.start({"evidence_tasks": [{"id": "good"}, {"id": "bad"}]})
    assert state["status"] == "interrupted"
    assert state["evidence_results"] == [{"id": "good", "status": "ok"}]
    assert any(item["task_id"] == "bad" for item in state["failures"])


def test_correction_limit_cancel_abandon_and_checkpoint_integrity(tmp_path):
    _, graph = _graph(
        tmp_path, "correction",
        {"scientific_critic": lambda _: {"requires_correction": True},
         "schema_correction": lambda _: {"requires_correction": True}},
        correction_limit=1,
    )
    state = graph.start({})
    thread_id = graph.repository.get_forecast_job("job-correction")["graph_thread_id"]
    state = graph.decide(thread_id, "fusion_review", "approve", {}, "review")
    assert state["status"] == "failed"
    assert "最大迭代" in state["failures"][-1]["error"]

    _, cancel_graph = _graph(tmp_path, "cancel")
    interrupted = cancel_graph.start({})
    cancel_thread = cancel_graph.repository.get_forecast_job("job-cancel")["graph_thread_id"]
    assert cancel_graph.cancel(cancel_thread)["status"] == "cancelled"

    _, abandon_graph = _graph(tmp_path, "abandon")
    abandon_graph.start({})
    abandon_thread = abandon_graph.repository.get_forecast_job("job-abandon")["graph_thread_id"]
    assert abandon_graph.abandon(abandon_thread)["status"] == "abandoned"

    # Corrupting persisted state is detected before resume.
    with abandon_graph.repository.db.transaction() as connection:
        connection.execute(
            """UPDATE graph_checkpoints SET state_json='{}' WHERE checkpoint_id=(
               SELECT checkpoint_id FROM graph_checkpoints WHERE thread_id=? ORDER BY sequence DESC LIMIT 1)""",
            (abandon_thread,),
        )
    with pytest.raises(ValueError, match="校验和不匹配"):
        LocalGraphCheckpointer(abandon_graph.repository).load(abandon_thread)


def test_cross_job_thread_isolation_and_reject_policy(tmp_path):
    repo1, graph1 = _graph(tmp_path, "isolation-one")
    repo2, graph2 = _graph(tmp_path, "isolation-two")
    graph1.start({"theme_tasks": [{"id": "a"}]})
    graph2.start({"theme_tasks": [{"id": "b"}]})
    thread1 = repo1.get_forecast_job("job-isolation-one")["graph_thread_id"]
    thread2 = repo2.get_forecast_job("job-isolation-two")["graph_thread_id"]
    assert thread1 != thread2
    assert graph1.checkpointer.load(thread1)["job_id"] == "job-isolation-one"
    rejected = graph1.decide(thread1, "fusion_review", "reject", {}, "insufficient evidence")
    assert rejected["status"] == "abandoned"


def test_failed_node_can_be_retried_without_skipping_it(tmp_path):
    attempts = {"count": 0}
    def flaky(_state):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("transient")
        return {"artifact_refs": []}
    repository, graph = _graph(tmp_path, "retry", {"construct_network": flaky})
    failed = graph.start({})
    assert failed["status"] == "failed" and failed["current_node"] == "construct_network"
    thread = repository.get_forecast_job("job-retry")["graph_thread_id"]
    retried = graph.retry(thread)
    assert attempts["count"] == 2
    assert retried["status"] == "interrupted" and retried["current_node"] == "fusion_review"


def test_first_theme_synthesis_call_receives_all_frozen_scientific_inputs(monkeypatch):
    captured = {}
    node = BoundedAgentNodes(lambda role, payload: captured.update(role=role, payload=payload) or {
        "concept_name": "融合概念", "ipc_pairs": ["B25J9/16×E04G21/00"],
        "mechanism": "基于冻结证据的可能融合机制，仍存在不确定限制。",
        "evidence_ids": ["e1"], "model_candidate_ids": ["c1"],
    })
    monkeypatch.setattr("src.research.graph.invoke_with_bounded_correction",
                        lambda invoke, payload, schema, frozen, max_retries: schema.model_validate(invoke(payload)))
    result = node.concept_synthesis({
        "evidence_results": [{"evidence_id": "e1"}], "candidate_refs": [{"candidate_id": "c1"}],
        "stage_analysis": [{"period": "2020_2025"}],
        "frozen_contract": {"forecast_nodes": [2030, 2035, 2040], "evidence_ids": ["e1"]},
    })
    assert captured["role"] == "technology_concept_synthesizer"
    assert set(captured["payload"]) == {"evidence_results", "candidate_refs", "stage_analysis", "target_contract"}
    assert result["theme_tasks"] and result["technology_concept"]["concept_name"] == "融合概念"
