# -*- coding: utf-8 -*-
import importlib

from fastapi.testclient import TestClient

from src.ingestion.research import ResearchImportService
from src.library import DatasetEligibilityResolver, LibraryDatabase, LibraryRepository
from src.research.design import ResearchDesignService
from src.research.repository import ResearchRepository


def _context(tmp_path):
    repository = LibraryRepository(LibraryDatabase(tmp_path / "design.sqlite3"))
    project = repository.create_project(
        technology_node_id="tech_smart_construction", target_year=2040
    )
    dataset = repository.create_dataset(
        "ipc", "", "v3.1", technology_node_id="tech_robot",
        period_code="2020_2025", public_kind="ipc",
    )
    preview = ResearchImportService(repository).preview("patents", [{
        "publication_number": "CN-DESIGN-1", "application_year": 2024,
        "ipc_codes": "B25J9/16;E04B1/76",
    }], dataset_id=dataset["dataset_id"])
    ResearchImportService(repository).commit(preview)
    with repository.db.transaction() as connection:
        connection.execute(
            "UPDATE datasets SET status='published' WHERE dataset_id=?",
            (dataset["dataset_id"],),
        )
    return repository, project, dataset


def test_eligibility_reports_reconstruction_and_completeness(tmp_path):
    repository, project, dataset = _context(tmp_path)
    scope = DatasetEligibilityResolver(repository).resolve(project)
    selected = next(item for item in scope["eligible_datasets"]
                    if item["dataset_id"] == dataset["dataset_id"])
    assert selected["reconstruction_grade"] == "canonical_patent_incidence"
    assert selected["evidence_grade"] in {"A", "B"}
    period = scope["coverage"]["periods"]["2020_2025"]
    assert period["patent_records"] == 1
    assert period["included_year_denominator"] == 1


def test_design_versions_stale_artifacts_and_frozen_snapshot(tmp_path):
    repository, project, dataset = _context(tmp_path)
    designs = ResearchDesignService(repository)
    first = designs.create_version(project["project_id"], {
        "research_question": "哪些 IPC 融合将形成 2040 智能建造技术？",
        "paper_types": ["journal_article"], "ipc_analysis_level": "main_group",
        "candidate_target": "both",
    })
    designs.confirm(project["project_id"], first["design_id"])
    frozen = designs.freeze_snapshot(project["project_id"], [dataset["dataset_id"]])
    assert frozen["snapshot_schema_version"] == 3
    assert frozen["record_ids"]["patents"]
    assert frozen["research_contract"]["baseline_year"] == 2025

    runs = ResearchRepository(repository.db)
    run = runs.create_network_run({
        "project_id": project["project_id"], "snapshot_checksum": frozen["checksum"],
        "algorithm_version": "network-v1", "input_checksum": "design-run",
    })
    runs.complete_network_run(run["network_run_id"], "result-1")
    second = designs.create_version(project["project_id"], {
        "research_question": "调整论文类型后的 2040 IPC 融合是什么？",
        "paper_types": ["review"], "ipc_analysis_level": "main_group",
        "candidate_target": "emergence",
    })
    confirmed = designs.confirm(project["project_id"], second["design_id"])
    assert confirmed["stale_artifacts"]["network_runs"] == 1

    # Later database changes do not mutate the already materialized snapshot.
    before = frozen["checksum"]
    with repository.db.transaction() as connection:
        connection.execute(
            "UPDATE datasets SET version='v3.2' WHERE dataset_id=?",
            (dataset["dataset_id"],),
        )
    assert frozen["checksum"] == before
    assert frozen["scope"]["eligible_datasets"][0]["version"] == "v3.1"


def test_empty_requested_scope_never_falls_back_and_design_api(tmp_path, monkeypatch):
    repository, project, _ = _context(tmp_path)
    scope = DatasetEligibilityResolver(repository).resolve(
        project, requested_dataset_ids=[]
    )
    assert scope["selected_dataset_ids"] == []
    routes = importlib.import_module("src.api.project_routes")
    monkeypatch.setattr(routes, "repository", repository)
    monkeypatch.setattr(routes, "research_design_service", ResearchDesignService(repository))
    client = TestClient(importlib.import_module("src.api.app").app)
    response = client.post(
        "/api/projects/%s/research-designs" % project["project_id"],
        json={"research_question": "API research question"},
    )
    assert response.status_code == 201
    design = response.json()
    confirmed = client.post(
        "/api/projects/%s/research-designs/%s/confirm" %
        (project["project_id"], design["design_id"])
    )
    assert confirmed.status_code == 200
