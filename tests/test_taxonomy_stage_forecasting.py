# -*- coding: utf-8 -*-
import importlib
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.analysis import StageAnalysisService
from src.api.forecast_service import create_job, run_forecast_job
from src.api.project_service import ProjectService
from src.api.storage import WorkbenchStorage
from src.ingestion import ImportService
from src.ingestion.models import ParsedTable
from src.ingestion.service import normalize_rows
from src.library import LibraryDatabase, LibraryRepository, TechnologyRepository
from src.library.constants import derive_forecast_nodes
from src.retrieval import EvidenceRetrievalService


@pytest.fixture()
def repository():
    with tempfile.TemporaryDirectory() as directory:
        yield LibraryRepository(
            LibraryDatabase(Path(directory) / "taxonomy.sqlite3")
        )


def _published_stage_dataset(repo, kind, technology_id, period, version="1.0"):
    return repo.create_dataset(
        kind, "", version, technology_node_id=technology_id,
        period_code=period, public_kind=kind,
    )


def test_taxonomy_seed_tree_constraints_and_audit(repository):
    technologies = TechnologyRepository(repository.db)
    assert len(technologies.tree()) == 1
    assert len(technologies.list_nodes(level=2)) == 5
    assert len(technologies.list_nodes(level=3)) == 20
    assert technologies.get("tech_robot")["path_text"] == (
        "智能建造 / 智能施工机械 / 机器人"
    )

    custom = technologies.create({
        "name": "自主测量", "level": 3,
        "parent_id": "tech_engineering_iot",
    })
    moved = technologies.move(
        custom["node_id"], "tech_construction_machinery", 99
    )
    assert moved["parent_id"] == "tech_construction_machinery"
    assert len(technologies.changes(custom["node_id"])) == 2
    with pytest.raises(ValueError):
        technologies.create({
            "name": "第四级", "level": 3, "parent_id": "tech_robot",
        })
    with pytest.raises(ValueError):
        technologies.move(
            "tech_engineering_iot", "tech_digital_twin", 0
        )


def test_technology_api_and_reference_protection(repository, monkeypatch):
    technology_routes = importlib.import_module("src.api.technology_routes")
    monkeypatch.setattr(
        technology_routes, "repository", TechnologyRepository(repository.db)
    )
    app = importlib.import_module("src.api.app").app
    client = TestClient(app)
    tree = client.get("/api/technologies").json()["items"]
    assert tree[0]["name"] == "智能建造"
    created = client.post("/api/technologies", json={
        "name": "智能巡检", "level": 3,
        "parent_id": "tech_engineering_iot",
    })
    assert created.status_code == 201
    node_id = created.json()["node_id"]
    assert client.post(
        f"/api/technologies/{node_id}/archive"
    ).json()["status"] == "archived"
    assert client.post(
        f"/api/technologies/{node_id}/restore"
    ).json()["status"] == "active"


def test_stage_dataset_validation_and_integrated_gate(repository, tmp_path):
    table = ParsedTable(
        columns=["IPC分类号", "年份"],
        rows=[
            {"IPC分类号": "E04B", "年份": 2020, "_source_row": 2},
            {"IPC分类号": "E04B", "年份": 2021, "_source_row": 3},
        ],
    )
    valid, errors = normalize_rows(
        "ipc_metrics", table,
        {"ipc_code": "IPC分类号", "year": "年份"}, "2016_2020",
    )
    assert len(valid) == 1
    assert "不属于阶段" in errors[0]["message"]

    legacy = repository.create_dataset("ipc_metrics", "旧机器人数据", "1.0")
    repository.upsert_ipc_metrics(legacy["dataset_id"], [{
        "ipc_code": "B25J", "year": 2022, "patent_count": 10,
    }])
    classified = repository.classify_legacy_dataset(
        legacy["dataset_id"], "tech_robot", "2021_2026", "ipc"
    )
    assert classified["migration_status"] == "mapped"
    assert classified["technology_node_id"] == "tech_robot"

    integrated = repository.create_dataset(
        "integrated", "", "1.0", technology_node_id="tech_robot",
        period_code="2021_2026", public_kind="integrated",
    )
    with pytest.raises(ValueError):
        repository.update_dataset_status(integrated["dataset_id"], "published")

    for index, component in enumerate(("ipc_metrics", "papers"), start=1):
        path = tmp_path / f"{component}.txt"
        path.write_text(component, encoding="utf-8")
        file_record = repository.create_source_file({
            "dataset_id": integrated["dataset_id"],
            "filename": path.name, "media_type": "text/plain",
            "checksum": f"checksum-{index}", "stored_path": str(path),
            "size_bytes": path.stat().st_size, "parse_status": "parsed",
            "content_role": component,
        })
        imported = repository.create_import({
            "dataset_id": integrated["dataset_id"],
            "file_id": file_record["file_id"], "kind": component,
            "component_kind": component,
        })
        repository.update_import(
            imported["import_id"], "committed", integrated["dataset_id"]
        )
    repository.upsert_ipc_metrics(integrated["dataset_id"], [{
        "ipc_code": "B25J", "year": 2022, "patent_count": 1,
    }])
    repository.add_paper(integrated["dataset_id"], {
        "title": "机器人综合数据论文", "year": 2022,
        "keywords": "机器人", "abstract": "机器人研究",
    })
    assert repository.update_dataset_status(
        integrated["dataset_id"], "published"
    )["status"] == "published"


def test_project_scope_material_topic_and_stage_analysis(repository):
    project = repository.create_project(
        technology_node_id="tech_smart_construction", target_year=2035
    )
    assert project["baseline_year"] == 2025
    assert project["forecast_nodes"] == [2030, 2035]
    assert derive_forecast_nodes(2040) == [2030, 2035, 2040]
    with pytest.raises(ValueError):
        repository.create_project(
            technology_node_id="tech_robot", target_year=2035
        )

    periods = {
        "2010_2014": [(2012, 10), (2014, 15)],
        "2015_2019": [(2015, 18), (2019, 28)],
        "2020_2025": [(2020, 35), (2025, 60)],
    }
    for period, points in periods.items():
        ipc = _published_stage_dataset(
            repository, "ipc", "tech_robot", period
        )
        repository.upsert_ipc_metrics(ipc["dataset_id"], [
            {"ipc_code": "B25J", "year": year, "patent_count": value}
            for year, value in points
        ])
        repository.update_dataset_status(ipc["dataset_id"], "published")
        papers = _published_stage_dataset(
            repository, "paper", "tech_robot", period
        )
        for index, (year, _) in enumerate(points):
            repository.add_paper(papers["dataset_id"], {
                "title": f"机器人研究 {period}-{index}", "year": year,
                "keywords": "机器人,智能施工",
                "abstract": "建筑机器人与智能施工研究。",
            })
        repository.update_dataset_status(papers["dataset_id"], "published")
    analysis = StageAnalysisService(repository).analyze(
        "tech_robot", project["project_id"]
    )
    assert analysis["quality"]["complete"] is True
    stages = analysis["items"][0]["stages"]
    assert stages["2020_2025"]["patent_annual_average"] > stages["2010_2014"]["patent_annual_average"]
    assert StageAnalysisService(repository).analyze(
        "tech_robot", project["project_id"]
    )["run_id"] == analysis["run_id"]

    service = ProjectService(repository)
    material = service.add_text_material(
        project["project_id"], "机器人IPC分析",
        "2016年至2020年机器人B25J专利增长，2021年至2026年论文与专利进一步加速。",
        "ipc_analysis",
    )
    topics = service.extract_topics(
        project["project_id"], [material["material_id"]], False
    )
    assert topics[0]["technologies"]
    assert any(
        item["technology_node_id"] == "tech_robot"
        for item in topics[0]["technologies"]
    )


def test_dynamic_2035_forecast_result(tmp_path):
    topic = {
        "topic_id": "topic_dynamic", "topic_name": "机器人自主施工",
        "keywords": ["机器人"], "selected": True, "ipc_evidence": [],
        "fusion_pairs": [], "sample_abstracts": ["机器人研究"],
        "forecast_context": {
            "baseline_year": 2026, "target_year": 2035,
            "forecast_nodes": [2030, 2035],
        },
    }
    storage = WorkbenchStorage(tmp_path / "jobs")
    job = create_job(
        storage, [topic["topic_id"]],
        {"enable_per_topic_roadmap": True},
        topic_snapshot=[topic], baseline_year=2026, target_year=2035,
        forecast_nodes=[2030, 2035],
    )
    round1 = [{
        "topic_name": topic["topic_name"],
        "bottlenecks_2030_2035": ["协同控制"],
        "breakthroughs_by_2040": [], "evidence_ids": [],
    }]
    round3 = [
        {"year": 2030, "category": "技术里程碑", "description": "验证"},
        {"year": 2035, "category": "技术里程碑", "description": "应用"},
        {"year": 2040, "category": "技术里程碑", "description": "不应保留"},
    ]
    roadmaps = [{
        "topic_name": topic["topic_name"],
        "roadmap": {
            year: {"stage_description": year, "milestones": [{
                "name": year, "description": "节点", "trl_level": trl,
                "uncertainty_level": "medium",
            }]}
            for year, trl in (("2026", 3), ("2030", 5), ("2035", 7), ("2040", 9))
        },
    }]
    with patch("src.api.forecast_service.run_round1", return_value=round1), \
         patch("src.api.forecast_service.run_round2", return_value={"new_paradigm_name": "自主施工"}), \
         patch("src.api.forecast_service.run_round3", return_value=round3), \
         patch("src.api.forecast_service.run_all_topics_roadmap", return_value=roadmaps), \
         patch("src.api.forecast_service.generate_job_assets", return_value={"assets": [], "failed_assets": []}):
        run_forecast_job(storage, job["job_id"])
    result = storage.get_job_artifact(job["job_id"], "result.json")
    assert result["baseline_year"] == 2026
    assert result["time_nodes"] == ["2030", "2035"]
    assert [item["year"] for item in result["round3_result"]] == [2030, 2035]
    assert set(result["per_topic_roadmaps"][0]["roadmap"]) == {
        "2026", "2030", "2035"
    }
