# -*- coding: utf-8 -*-
from pathlib import Path

import pytest

from src.api.project_service import ProjectService
from src.api.readiness_service import ReadinessService
from src.ingestion import ImportService
from src.library import (
    DatasetEligibilityResolver,
    LibraryDatabase,
    LibraryRepository,
    TechnologyRepository,
)
from src.retrieval import EvidenceRetrievalService


@pytest.fixture()
def repository(tmp_path):
    return LibraryRepository(LibraryDatabase(tmp_path / "streamlined.sqlite3"))


def _dataset(repo, kind, technology, period, rows):
    dataset = repo.create_dataset(
        kind, "", "1.0", technology_node_id=technology,
        period_code=period, public_kind=kind,
    )
    if kind == "ipc":
        repo.upsert_ipc_metrics(dataset["dataset_id"], rows)
    else:
        for row in rows:
            repo.add_paper(dataset["dataset_id"], row)
    return repo.update_dataset_status(dataset["dataset_id"], "published")


def test_effective_activation_hides_descendants_and_preserves_own_state(repository):
    technologies = TechnologyRepository(repository.db)
    assert technologies.get("tech_bim")["effective_status"] == "active"
    affected = technologies.affected_descendants("tech_engineering_software")
    assert any(item["node_id"] == "tech_bim" for item in affected)
    with pytest.raises(ValueError, match="确认"):
        technologies.archive("tech_engineering_software")
    technologies.archive("tech_engineering_software", confirm_descendants=True)
    bim = technologies.get("tech_bim")
    assert bim["status"] == "active"
    assert bim["effective_status"] == "inactive"
    assert "tech_bim" not in {
        item["node_id"] for item in technologies.list_nodes(level=3, status="active")
    }
    technologies.restore("tech_engineering_software")
    assert technologies.get("tech_bim")["effective_status"] == "active"


def test_empty_scope_never_falls_back_and_foreign_dataset_is_rejected(repository):
    foreign = _dataset(repository, "ipc", "tech_robot", "2021_2026", [
        {"ipc_code": "E04B", "year": year, "patent_count": year - 2020}
        for year in (2021, 2022, 2023)
    ])
    legacy = repository.create_dataset("papers", "未映射论文", "legacy.1")
    repository.add_paper(legacy["dataset_id"], {
        "title": "不应泄漏论文", "year": 2023,
        "keywords": "装配式建筑", "abstract": "不应进入新证据包",
    })
    with repository.db.transaction() as connection:
        connection.execute(
            "UPDATE datasets SET status='published',migration_status='needs_mapping' WHERE dataset_id=?",
            (legacy["dataset_id"],),
        )
    project = repository.create_project(
        technology_node_id="tech_smart_construction", target_year=2040
    )
    topic = repository.save_topic({
        "project_id": project["project_id"], "topic_name": "装配式建筑",
        "keywords": ["装配式建筑", "E04B"], "status": "confirmed",
        "requires_review": False,
        "technologies": [{
            "technology_node_id": "tech_prefabricated_building",
            "is_primary": True, "relevance": 1, "source": "manual",
        }],
    })
    resolved = DatasetEligibilityResolver(repository).resolve_for_topic(
        project["project_id"], topic
    )
    assert resolved["eligible_dataset_ids"] == []
    package = EvidenceRetrievalService(repository).retrieve(
        project["project_id"], topic["topic_id"], 2021, 2026
    )
    assert not [
        item for item in package["items"]
        if item["evidence_type"] in {"ipc_metric", "paper"}
    ]
    with pytest.raises(ValueError, match="不属于"):
        DatasetEligibilityResolver(repository).resolve_for_topic(
            project["project_id"], topic, [foreign["dataset_id"]]
        )


def test_guided_import_splits_periods_and_record_pages_show_provenance(repository):
    service = ImportService(repository)
    content = (
        "IPC分类号,年份,专利数,增长率\n"
        "B25J,2019,3,0.1\nB25J,2020,5,0.2\n"
        "B25J,2021,8,0.3\nB25J,2022,13,0.4\n"
    ).encode()
    staged = service.guided_stage(
        content, "robot.csv", "text/csv", "ipc_metrics",
        "tech_robot", "ipc",
    )
    assert staged["plan"]["split_required"] is True
    committed = service.guided_commit(
        staged["import"]["import_id"], "tech_robot", "ipc",
        mapping=staged["import"]["mapping"],
        versions=staged["plan"]["generated_versions"],
    )
    assert committed["total"] == 2
    for item in committed["items"]:
        repository.update_dataset_status(
            item["dataset"]["dataset_id"], "published"
        )
    page = repository.ipc_page(
        scope_node_id="tech_robot", page=1, page_size=2
    )
    assert page["total"] == 4
    assert page["items"][0]["technology_path"].endswith("机器人")
    assert page["items"][0]["source_filename"] == "robot.csv"
    assert repository.library_files(scope_node_id="tech_robot")
    assert repository.list_imports(scope_node_id="tech_robot")


def test_record_coverage_ignores_empty_and_unmapped_containers(repository):
    empty = repository.create_dataset(
        "ipc", "", "1.0", technology_node_id="tech_robot",
        period_code="2010_2015", public_kind="ipc",
    )
    with repository.db.transaction() as connection:
        connection.execute(
            "UPDATE datasets SET status='published' WHERE dataset_id=?",
            (empty["dataset_id"],),
        )
    coverage = repository.dataset_coverage("tech_smart_construction")
    assert coverage["complete"] is False
    assert coverage["periods"]["2010_2014"]["ipc_records"] == 0


def test_legacy_period_split_preserves_source_and_creates_mapped_drafts(repository):
    source = repository.create_dataset("ipc_metrics", "跨阶段旧数据", "legacy.1")
    repository.upsert_ipc_metrics(source["dataset_id"], [
        {"ipc_code": "B25J", "year": 2019, "patent_count": 3},
        {"ipc_code": "B25J", "year": 2022, "patent_count": 8},
    ])
    targets = repository.split_legacy_dataset(
        source["dataset_id"], "tech_robot", "ipc"
    )
    assert len(targets) == 2
    assert repository.get_dataset(source["dataset_id"]) is not None
    assert {item["period_code"] for item in targets} == {
        "2015_2019", "2020_2025",
    }
    assert all(item["status"] == "draft" for item in targets)
    assert all(item["migration_status"] == "mapped" for item in targets)
    assert sum(
        len(repository.ipc_series(
            dataset_ids=[item["dataset_id"]]
        ))
        for item in targets
    ) == 0
    with repository.db.connect() as connection:
        assert sum(
            connection.execute(
                "SELECT COUNT(*) value FROM ipc_metrics WHERE dataset_id=?",
                (item["dataset_id"],),
            ).fetchone()["value"]
            for item in targets
        ) == 2


def test_readiness_v3_exposes_six_research_steps_and_recommended_action(repository):
    project = repository.create_project(
        technology_node_id="tech_smart_construction", target_year=2035
    )
    readiness = ReadinessService(repository).project_readiness(
        project["project_id"]
    )
    assert readiness["contract_version"] == 3
    assert readiness["recommended_action"]["step_id"] == "research-design"
    assert [item["id"] for item in readiness["steps"]] == [
        "research-design", "data-quality", "network-evolution",
        "fusion-forecast", "technology-themes", "roadmap-report",
    ]
    assert readiness["steps"][-1]["visible"] is True
    ProjectService(repository).add_text_material(
        project["project_id"], "机器人分析",
        "2021年机器人B25J专利和论文研究持续增长。",
        "integrated_analysis",
    )
    readiness = ReadinessService(repository).project_readiness(
        project["project_id"]
    )
    assert readiness["recommended_action"]["step_id"] == "research-design"
    repository.set_project_lifecycle(project["project_id"], "archived")
    archived = ReadinessService(repository).project_readiness(project["project_id"])
    assert "归档项目不能创建新的预测任务" in archived["forecast"]["blocking_reasons"]
