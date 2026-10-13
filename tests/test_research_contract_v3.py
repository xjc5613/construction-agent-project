# -*- coding: utf-8 -*-
import importlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.forecast_service import _build_result
from src.library import LibraryDatabase, LibraryRepository
from src.research.contracts import (
    CURRENT_RESEARCH_CONTRACT_VERSION,
    get_research_contract,
)


@pytest.fixture()
def repository(tmp_path):
    return LibraryRepository(LibraryDatabase(tmp_path / "contract.sqlite3"))


def test_contract_fixture_and_v3_constants():
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "research_contracts.json").read_text(
            encoding="utf-8"
        )
    )
    contract = get_research_contract(CURRENT_RESEARCH_CONTRACT_VERSION)
    assert contract.baseline_year == 2025
    assert list(contract.periods) == fixture["version_3_project"]["periods"]
    assert contract.derive_forecast_nodes(2035) == [2030, 2035]
    with pytest.raises(ValueError, match="不属于研究合同 v3"):
        contract.validate_period("2021_2026")
    assert fixture["mapped_dataset"]["migration_status"] == "mapped"
    assert fixture["unmapped_dataset"]["migration_status"] == "needs_mapping"
    assert fixture["partial_result"]["status"] == "partial_failed"


def test_new_project_uses_v3_and_rejects_legacy_contract(repository):
    project = repository.create_project(
        technology_node_id="tech_smart_construction", target_year=2035
    )
    assert project["research_contract_version"] == 3
    assert project["baseline_year"] == 2025
    assert project["historical_periods"] == [
        "2010_2014", "2015_2019", "2020_2025"
    ]
    assert project["forecast_nodes"] == [2030, 2035]
    with pytest.raises(ValueError, match="基线必须是 2025"):
        repository.create_project(
            technology_node_id="tech_smart_construction",
            baseline_year=2026,
        )
    with pytest.raises(ValueError, match="必须使用研究合同 v3"):
        repository.create_project(
            technology_node_id="tech_smart_construction",
            research_contract_version=2,
            baseline_year=2026,
        )


def test_legacy_project_and_result_resolve_stored_contract(repository):
    with repository.db.transaction() as connection:
        connection.execute(
            """INSERT INTO projects(
                   project_id,name,baseline_year,target_year,legacy_mode,
                   research_contract_version
               ) VALUES ('legacy-v2','legacy',2026,2040,1,2)"""
        )
    project = repository.get_project("legacy-v2")
    assert project["historical_periods"] == [
        "2010_2015", "2016_2020", "2021_2026"
    ]
    result = _build_result(
        "job-v2", [], [], {}, {}, [],
        {
            "baseline_year": 2026,
            "target_year": 2040,
            "forecast_nodes": [2030, 2035, 2040],
            "research_contract_version": 2,
            "research_contract": project["research_contract"],
        },
    )
    assert result["historical_periods"] == project["historical_periods"]
    assert result["research_contract_version"] == 2


def test_project_creation_api_returns_v3_contract(repository, monkeypatch):
    project_routes = importlib.import_module("src.api.project_routes")
    monkeypatch.setattr(project_routes, "repository", repository)
    client = TestClient(importlib.import_module("src.api.app").app)
    response = client.post("/api/projects", json={
        "technology_node_id": "tech_smart_construction",
        "target_year": 2030,
    })
    assert response.status_code == 201
    payload = response.json()
    assert payload["research_contract_version"] == 3
    assert payload["baseline_year"] == 2025
    assert payload["forecast_nodes"] == [2030]
