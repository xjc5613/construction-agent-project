# -*- coding: utf-8 -*-
import importlib
import sqlite3

import pytest
from fastapi.testclient import TestClient

from src.ingestion.research import ResearchImportService, normalize_ipc, parse_ipc_assignments
from src.library import LibraryDatabase, LibraryRepository


@pytest.fixture()
def context(tmp_path):
    repository = LibraryRepository(LibraryDatabase(tmp_path / "ingestion.sqlite3"))
    dataset = repository.create_dataset("mixed", "research", "v1")
    return repository, dataset, ResearchImportService(repository)


def test_ipc_normalization_keeps_raw_and_deduplicates_assignments():
    assert normalize_ipc("b25j 9/16")["normalized"] == "B25J9/00"
    assert normalize_ipc("E04B1/76", "subgroup")["normalized"] == "E04B1/76"
    values, invalid = parse_ipc_assignments("B25J 9/16; B25J9/02; bad; E04B 1/76")
    assert [item["normalized"] for item in values] == ["B25J9/00", "E04B1/00"]
    assert invalid == [" bad"]


def test_patent_preview_counts_pairs_duplicates_and_requires_partial_cutoff(context):
    _, dataset, service = context
    rows = [{
        "publication_number": "CN-1", "application_year": 2025,
        "ipc_codes": "B25J 9/16; E04B 1/76; G06F 30/13", "_source_row": 2,
    }, {
        "publication_number": "CN-1", "application_year": 2025,
        "ipc_codes": "B25J 9/16", "_source_row": 3,
    }]
    blocked = service.preview(
        "patents", rows, dataset_id=dataset["dataset_id"], completeness="partial"
    )
    assert blocked["pair_count"] == 3
    assert blocked["duplicate_source_count"] == 1
    assert "observation_cutoff" in blocked["errors"][-1]["message"]
    preview = service.preview(
        "patents", rows, dataset_id=dataset["dataset_id"], completeness="partial",
        observation_cutoff="2025-10-01", ipc_edition="2025.01",
    )
    result = service.commit(preview)
    assert result["committed"] == 1
    repeated = service.preview(
        "patents", rows[:1], dataset_id=dataset["dataset_id"], completeness="partial",
        observation_cutoff="2025-10-01",
    )
    assert repeated["duplicate_database_count"] == 1
    assert service.commit(repeated)["duplicates_skipped"] == 1
    with service.repository.db.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM patent_ipcs").fetchone()[0] == 3
        coverage = connection.execute("SELECT * FROM data_coverage WHERE year=2025").fetchone()
        assert coverage["completeness"] == "partial"
        assert coverage["observation_cutoff"] == "2025-10-01"


def test_probability_only_edges_quarantined_as_hypotheses(context):
    _, dataset, service = context
    rejected = service.preview("reduced_edges", [{
        "ipc1": "B25J9/16", "ipc2": "E04B1/76", "year": 2024,
        "probability": 0.8,
    }], dataset_id=dataset["dataset_id"])
    assert rejected["valid_count"] == 0
    assert "研究者假设" in rejected["errors"][0]["message"]
    hypothesis = service.preview("fusion_hypotheses", [{
        "ipc1": "B25J9/16", "ipc2": "E04B1/76", "probability": 0.8,
        "rationale": "expert elicitation",
    }], dataset_id=dataset["dataset_id"])
    service.commit(hypothesis)
    with service.repository.db.connect() as connection:
        assert connection.execute(
            "SELECT stated_probability FROM researcher_fusion_hypotheses"
        ).fetchone()[0] == 0.8
        assert connection.execute("SELECT COUNT(*) FROM fusion_predictions").fetchone()[0] == 0


def test_reduced_edge_and_paper_type_preview_commit_and_rollback(context):
    _, dataset, service = context
    edge = service.preview("reduced_edges", [{
        "ipc1": "E04B1/76", "ipc2": "B25J9/16", "year": 2024,
        "cooccurrence_count": 5, "source_patent_count": 5,
        "ipc1_count": 10, "ipc2_count": 8, "total_patent_count": 100,
        "normalization_method": "association_strength",
        "normalization_formula": "c_ij / sqrt(c_i*c_j)",
    }], dataset_id=dataset["dataset_id"])
    service.commit(edge)
    paper = service.preview("papers", [{
        "title": "Agentic construction", "year": 2024,
        "paper_type": "workshop", "source_database": "Scopus",
    }], dataset_id=dataset["dataset_id"])
    assert paper["paper_type_coverage"] == {"other": 1}
    assert paper["warnings"]
    with pytest.raises(ValueError, match="显式审核"):
        service.commit(paper)
    paper["rows"][0]["paper_type_reviewed"] = True
    service.commit(paper)
    with service.repository.db.connect() as connection:
        row = connection.execute("SELECT paper_type,source_database FROM papers").fetchone()
        assert tuple(row) == ("other", "Scopus")

    # A duplicate in a multi-row commit rolls back the whole transaction.
    duplicate = service.preview("reduced_edges", [
        {"ipc1": "B25J9/16", "ipc2": "G06F30/13", "year": 2024, "cooccurrence_count": 2,
         "source_patent_count": 2, "ipc1_count": 3, "ipc2_count": 4, "total_patent_count": 9,
         "normalization_method": "association_strength", "normalization_formula": "c/sqrt(a*b)"},
        {"ipc1": "B25J9/02", "ipc2": "G06F30/13", "year": 2024, "cooccurrence_count": 3,
         "source_patent_count": 3, "ipc1_count": 3, "ipc2_count": 4, "total_patent_count": 9,
         "normalization_method": "association_strength", "normalization_formula": "c/sqrt(a*b)"},
    ], dataset_id=dataset["dataset_id"])
    with pytest.raises(sqlite3.IntegrityError):
        service.commit(duplicate)
    with service.repository.db.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM reduced_ipc_edges").fetchone()[0] == 1


def test_research_import_api(context, monkeypatch):
    repository, dataset, service = context
    routes = importlib.import_module("src.api.library_routes")
    monkeypatch.setattr(routes, "repository", repository)
    monkeypatch.setattr(routes, "research_import_service", service)
    client = TestClient(importlib.import_module("src.api.app").app)
    response = client.post("/api/library/research-imports/preview", json={
        "kind": "patents", "dataset_id": dataset["dataset_id"],
        "rows": [{"publication_number": "CN-API", "application_year": 2023,
                  "ipc_codes": "B25J9/16;E04B1/76"}],
    })
    assert response.status_code == 200
    assert response.json()["pair_count"] == 1
