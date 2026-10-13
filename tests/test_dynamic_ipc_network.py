# -*- coding: utf-8 -*-
import math

from src.ingestion.research import ResearchImportService
from src.library import LibraryDatabase, LibraryRepository
from src.research.design import ResearchDesignService
from src.research.network import (
    DynamicIPCNetworkService, NetworkParameters, calculate_node_measures,
)


def test_known_path_centrality_and_undefined_states():
    edges = {
        ("A", "B"): {"cooccurrence_count": 1},
        ("B", "C"): {"cooccurrence_count": 1},
    }
    values = {item["ipc_code"]: item for item in calculate_node_measures(
        ["A", "B", "C", "D"], edges
    )}
    assert values["B"]["degree_centrality"] == 2 / 3
    assert values["B"]["betweenness_centrality"] > values["A"]["betweenness_centrality"]
    assert values["A"]["eccentricity"] is None  # graph is disconnected
    assert values["D"]["closeness_centrality"] is None


def test_annual_period_edges_deduplicate_ipcs_and_are_deterministic():
    service = DynamicIPCNetworkService.__new__(DynamicIPCNetworkService)
    patents = [
        {"patent_id": "p1", "year": 2014, "ipc_codes": ["A", "A", "B"]},
        {"patent_id": "p2", "year": 2014, "ipc_codes": ["A", "B", "C"]},
        {"patent_id": "p3", "year": 2022, "ipc_codes": ["B", "C"]},
    ]
    first = service.build(patents)
    second = service.build(reversed(patents))
    assert first["result_checksum"] == second["result_checksum"]
    edge = next(item for item in first["annual"]["2014"]["edges"]
                if item["ipc1"] == "A" and item["ipc2"] == "B")
    assert edge["cooccurrence_count"] == 2
    assert edge["supporting_patent_ids"] == ["p1", "p2"]
    assert math.isclose(edge["jaccard"], 1.0)
    assert first["periods"]["2015_2019"]["patent_count"] == 0
    assert first["layout"] == second["layout"]


def test_reduced_edges_have_lower_grade_and_missing_measures_are_explicit():
    service = DynamicIPCNetworkService.__new__(DynamicIPCNetworkService)
    result = service.build([], reduced_edges=[{
        "year": 2020, "ipc1": "A", "ipc2": "B", "cooccurrence_count": 4,
        "source_patent_count": 4, "ipc1_count": None, "ipc2_count": None,
        "total_patent_count": None,
    }])
    edge = result["annual"]["2020"]["edges"][0]
    assert edge["evidence_grade"] == "reduced_edge"
    assert edge["association_strength"] is None
    assert edge["pmi"] is None


def test_persisted_run_is_idempotent_and_edge_evidence_is_traceable(tmp_path):
    repository = LibraryRepository(LibraryDatabase(tmp_path / "network.sqlite3"))
    project = repository.create_project(technology_node_id="tech_smart_construction")
    dataset = repository.create_dataset(
        "ipc", "", "v1", technology_node_id="tech_robot",
        period_code="2020_2025", public_kind="ipc",
    )
    preview = ResearchImportService(repository).preview("patents", [
        {"publication_number": "CN-N1", "application_year": 2023,
         "ipc_codes": "B25J9/16;E04B1/76"},
        {"publication_number": "CN-N2", "application_year": 2024,
         "ipc_codes": "B25J9/02;E04B1/76"},
    ], dataset_id=dataset["dataset_id"])
    ResearchImportService(repository).commit(preview)
    with repository.db.transaction() as connection:
        connection.execute("UPDATE datasets SET status='published' WHERE dataset_id=?",
                           (dataset["dataset_id"],))
    designs = ResearchDesignService(repository)
    design = designs.create_version(project["project_id"], {
        "research_question": "IPC fusion", "candidate_target": "both",
    })
    designs.confirm(project["project_id"], design["design_id"])
    snapshot = designs.freeze_snapshot(project["project_id"], [dataset["dataset_id"]])
    service = DynamicIPCNetworkService(repository)
    first = service.build_and_persist(project["project_id"], snapshot, NetworkParameters())
    second = service.build_and_persist(project["project_id"], snapshot, NetworkParameters())
    assert first["run"]["network_run_id"] == second["run"]["network_run_id"]
    evidence = service.edge_evidence(
        first["run"]["network_run_id"], "B25J9/00", "E04B1/00"
    )
    assert evidence["items"][0]["supporting_patent_ids"]
    with repository.db.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM network_nodes").fetchone()[0] > 0
        assert connection.execute("SELECT COUNT(*) FROM node_transitions").fetchone()[0] > 0
