# -*- coding: utf-8 -*-
import importlib

from fastapi.testclient import TestClient

from src.ingestion.research import ResearchImportService
from src.library import LibraryDatabase, LibraryRepository
from src.research.design import ResearchDesignService


def _client(tmp_path, monkeypatch):
    repository = LibraryRepository(LibraryDatabase(tmp_path / "api-v3.sqlite3"))
    project_routes = importlib.import_module("src.api.project_routes")
    research_routes = importlib.import_module("src.api.research_routes")
    monkeypatch.setattr(project_routes, "repository", repository)
    monkeypatch.setattr(project_routes, "research_design_service", ResearchDesignService(repository))
    monkeypatch.setattr(research_routes, "repository", repository)
    return repository, TestClient(importlib.import_module("src.api.app").app)


def test_v3_readiness_data_quality_network_and_graph_api(tmp_path, monkeypatch):
    repository, client = _client(tmp_path, monkeypatch)
    project = repository.create_project(technology_node_id="tech_smart_construction")
    project_id = project["project_id"]
    readiness = client.get("/api/projects/%s/readiness" % project_id)
    assert readiness.status_code == 200
    assert [item["id"] for item in readiness.json()["steps"]] == [
        "research-design", "data-quality", "network-evolution",
        "fusion-forecast", "technology-themes", "roadmap-report",
    ]
    blocked = client.post("/api/research/projects/%s/network-runs" % project_id, json={})
    assert blocked.status_code == 422

    design = client.post("/api/projects/%s/research-designs" % project_id, json={
        "research_question": "哪些 IPC 融合将形成 2040 智能建造技术？"
    }).json()
    assert client.post(
        "/api/projects/%s/research-designs/%s/confirm" % (project_id, design["design_id"])
    ).status_code == 200
    dataset = repository.create_dataset(
        "ipc", "", "api.v1", technology_node_id="tech_robot",
        period_code="2020_2025", public_kind="ipc",
    )
    import_service = ResearchImportService(repository)
    preview = import_service.preview("patents", [{
        "publication_number": "CN-API-NET", "application_year": 2024,
        "ipc_codes": "B25J9/16;E04B1/76",
    }], dataset_id=dataset["dataset_id"])
    import_service.commit(preview)
    with repository.db.transaction() as connection:
        connection.execute("UPDATE datasets SET status='published' WHERE dataset_id=?",
                           (dataset["dataset_id"],))
    quality = client.get("/api/research/projects/%s/data-quality" % project_id)
    assert quality.status_code == 200
    run = client.post("/api/research/projects/%s/network-runs" % project_id, json={
        "dataset_ids": [dataset["dataset_id"]]
    })
    assert run.status_code == 201
    run_id = run.json()["run"]["network_run_id"]
    repeated = client.post("/api/research/projects/%s/network-runs" % project_id, json={
        "dataset_ids": [dataset["dataset_id"]]
    })
    assert repeated.json()["run"]["network_run_id"] == run_id
    assert client.get("/api/research/network-runs/%s/nodes" % run_id).status_code == 200
    assert client.get("/api/research/network-runs/%s/edges" % run_id).status_code == 200
    assert client.get("/api/research/network-runs/%s/trajectories" % run_id).status_code == 200
    feature = client.post("/api/research/network-runs/%s/feature-runs" % run_id, json={
        "target_type": "strengthening"
    })
    assert feature.status_code == 201 and feature.json()["candidate_count"] == 1
    candidates = client.get("/api/research/feature-runs/%s/candidates?page=1&page_size=1" % feature.json()["feature_run_id"])
    assert candidates.status_code == 200 and candidates.json()["total"] == 1
    candidate_id = candidates.json()["items"][0]["candidate_id"]
    chart_data = client.get("/api/research/projects/%s/chart-data" % project_id)
    assert chart_data.status_code == 200
    assert chart_data.json()["schema_version"] == "scientific-chart-v1"
    assert {item["chart_kind"] for item in chart_data.json()["items"]} >= {
        "network_small_multiples", "centrality_trajectory", "community_evolution",
    }

    job_id = "job-api-graph"
    repository.reserve_forecast_job(
        job_id, project_id, request_checksum="api", idempotency_key="api-graph"
    )
    repository.update_forecast_job_status(job_id, "running")
    started = client.post("/api/research/graph/jobs/%s/start" % job_id, json={
        "initial_state": {"candidate_refs": [{"id": "candidate"}]}
    })
    assert started.status_code == 200
    assert started.json()["current_node"] == "fusion_review"
    recovered = client.get("/api/research/graph/jobs/%s" % job_id)
    assert recovered.status_code == 200 and recovered.json()["snapshot_ref"]["checksum"]
    cannot_overwrite = client.post("/api/research/fusion-candidates/%s/review" % candidate_id, json={
        "job_id": job_id, "decision": "edit", "after": {"calibrated_probability": .99},
        "reason": "attempt overwrite",
    })
    assert cannot_overwrite.status_code == 409
    still_interrupted = client.post("/api/research/graph/jobs/%s/resume" % job_id)
    assert still_interrupted.status_code == 200
    assert still_interrupted.json()["current_node"] == "fusion_review"
    events = client.get("/api/research/graph/jobs/%s/events" % job_id)
    assert events.status_code == 200 and events.json()["items"]
    rejected = client.post(
        "/api/research/graph/jobs/%s/reviews/fusion_review" % job_id,
        json={"decision": "reject", "reason": "证据不足"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "abandoned"

    legacy = repository.create_project("legacy project")
    legacy_readiness = client.get("/api/projects/%s/readiness" % legacy["project_id"])
    assert legacy_readiness.status_code == 200
    assert legacy_readiness.json()["contract_version"] == 2
    assert legacy_readiness.json()["steps"][0]["id"] == "overview"
