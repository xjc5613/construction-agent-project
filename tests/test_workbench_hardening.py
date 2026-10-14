# -*- coding: utf-8 -*-
import json
from pathlib import Path

import pytest
from unittest.mock import patch

from scripts.reconcile_workbench_jobs import reconcile_jobs
from src.api.readiness_service import ReadinessService
from src.api.confirmation_service import ConfirmationError, ConfirmationService
from src.api.forecast_service import create_job, run_forecast_job
from src.api.storage import WorkbenchStorage
from src.library import LibraryDatabase, LibraryRepository, TechnologyRepository


@pytest.fixture()
def database(tmp_path):
    return LibraryDatabase(tmp_path / "hardening.sqlite3")


@pytest.fixture()
def repository(database):
    return LibraryRepository(database)


def test_v5_migration_is_additive_and_repeatable(database):
    LibraryDatabase(database.path)
    with database.connect() as connection:
        assert connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()[0] == 9
        projects = {row[1] for row in connection.execute("PRAGMA table_info(projects)")}
        jobs = {row[1] for row in connection.execute("PRAGMA table_info(forecast_jobs)")}
    assert {"lifecycle_status", "archived_at"} <= projects
    assert {
        "request_checksum", "idempotency_key", "parent_job_id", "progress",
        "current_stage", "cancel_requested_at", "artifact_health",
    } <= jobs


def test_active_job_unique_index_and_history(repository):
    project = repository.create_project("历史项目")
    repository.register_forecast_job(
        "job_one", project["project_id"], "snapshot.json", [], False, "",
        idempotency_key="same-click", request_checksum="checksum",
    )
    assert repository.get_active_forecast_job(project["project_id"])["job_id"] == "job_one"
    assert repository.get_forecast_job_by_idempotency("same-click")["job_id"] == "job_one"
    with pytest.raises(Exception):
        repository.register_forecast_job(
            "job_two", project["project_id"], "snapshot-2.json", [], False, "",
            idempotency_key="another-click", request_checksum="checksum-2",
        )
    repository.update_forecast_job_status("job_one", "completed", progress=1)
    repository.register_forecast_job(
        "job_two", project["project_id"], "snapshot-2.json", [], False, "",
        idempotency_key="another-click", parent_job_id="job_one",
    )
    assert [item["job_id"] for item in repository.list_forecast_jobs(project["project_id"])] == [
        "job_two", "job_one"
    ]


def test_reconcile_preserves_legacy_baseline_and_is_repeatable(repository, tmp_path):
    project = repository.create_project("2025 历史项目")
    jobs_dir = tmp_path / "jobs"
    job_dir = jobs_dir / "job_legacy"
    job_dir.mkdir(parents=True)
    (job_dir / "job.json").write_text(json.dumps({
        "job_id": "job_legacy", "project_id": project["project_id"],
        "status": "running", "baseline_year": 2025, "target_year": 2040,
        "forecast_nodes": [2030, 2035, 2040], "created_at": "2025-01-01T00:00:00Z",
    }), encoding="utf-8")
    first = reconcile_jobs(repository.db, jobs_dir)
    second = reconcile_jobs(repository.db, jobs_dir)
    job = repository.get_forecast_job("job_legacy")
    assert first["imported"] == 1
    assert second["updated"] == 1
    assert job["baseline_year"] == 2025
    assert job["status"] == "failed"
    assert job["error_code"] == "worker_interrupted"


def test_reconcile_infers_single_legacy_project_for_old_file_jobs(repository, tmp_path):
    project = repository.create_project("旧工作台迁移项目")
    job_dir = tmp_path / "jobs" / "forecast_old"
    job_dir.mkdir(parents=True)
    (job_dir / "job.json").write_text(json.dumps({
        "job_id": "forecast_old", "status": "partial_failed", "progress": 1,
        "created_at": "2025-01-01T00:00:00Z",
    }), encoding="utf-8")
    (job_dir / "result.json").write_text("{}", encoding="utf-8")
    summary = reconcile_jobs(repository.db, job_dir.parent)
    job = repository.get_forecast_job("forecast_old")
    assert summary["imported"] == 1
    assert job["project_id"] == project["project_id"]
    assert job["artifact_health"] == "ready"


def test_reference_aware_lifecycle(repository):
    project = repository.create_project("生命周期项目")
    repository.set_project_lifecycle(project["project_id"], "archived")
    assert repository.list_projects() == []
    assert repository.list_projects(include_archived=True)[0]["lifecycle_status"] == "archived"

    dataset = repository.create_dataset("ipc_metrics", "草稿", "1.0")
    assert repository.delete_dataset_draft(dataset["dataset_id"]) is True
    assert repository.get_dataset(dataset["dataset_id"]) is None


def _evidence_items(excluded_papers=0):
    items = [
        {
            "evidence_id": f"ipc-{year}", "evidence_type": "ipc_metric",
            "source_id": f"ipc-{year}", "content": str(year),
            "metadata": {"year": year, "ipc_code": "B25J"}, "excluded": False,
        }
        for year in (2022, 2023, 2024)
    ]
    items += [
        {
            "evidence_id": f"paper-{index}", "evidence_type": "paper",
            "source_id": f"paper-{index}", "content": "论文片段",
            "metadata": {"year": 2024}, "excluded": index < excluded_papers,
        }
        for index in range(3)
    ]
    return items


def test_canonical_quality_never_scores_100_when_period_is_missing(repository):
    project = repository.create_project(
        technology_node_id="tech_smart_construction", target_year=2040
    )
    topic = {
        "topic_id": "topic-quality", "technologies": [{
            "technology_node_id": "tech_robot", "is_primary": True,
        }],
    }
    quality = ReadinessService(repository).evaluate_evidence_items(
        project, topic, _evidence_items()
    )
    assert quality["sufficient"] is False
    assert quality["score"] == 75
    assert "historical_periods" in {
        item["id"] for item in quality["requirements"] if not item["passed"]
    }


def test_quality_recomputes_from_included_items(repository):
    legacy = repository.create_project("legacy readiness")
    topic = {"topic_id": "legacy-topic", "technologies": []}
    service = ReadinessService(repository)
    ready = service.evaluate_evidence_items(legacy, topic, _evidence_items())
    excluded = service.evaluate_evidence_items(
        legacy, topic, _evidence_items(excluded_papers=2)
    )
    assert ready["score"] == 100 and ready["sufficient"] is True
    assert excluded["score"] < 100 and excluded["sufficient"] is False


def test_project_readiness_separates_structural_and_override_blocks(repository):
    project = repository.create_project("readiness project")
    topic = repository.save_topic({
        "project_id": project["project_id"], "topic_name": "机器人",
        "status": "candidate", "requires_review": True,
    })
    readiness = ReadinessService(repository).project_readiness(
        project["project_id"], [topic["topic_id"]]
    )
    assert readiness["forecast"]["can_start"] is False
    assert readiness["forecast"]["can_override"] is False
    assert any("主题尚未确认" in item for item in readiness["forecast"]["blocking_reasons"])


def test_confirmation_token_is_payload_bound_and_single_use():
    service = ConfirmationService(secret=b"test-secret")
    preview = service.preview("dataset:delete", {"reason": "duplicate"})
    with pytest.raises(ConfirmationError) as mismatch:
        service.validate(
            preview["confirmation_token"], "dataset:delete", {"reason": "changed"}
        )
    assert mismatch.value.code == "confirmation_mismatch"
    service.validate(
        preview["confirmation_token"], "dataset:delete", {"reason": "duplicate"}
    )
    with pytest.raises(ConfirmationError) as replay:
        service.validate(
            preview["confirmation_token"], "dataset:delete", {"reason": "duplicate"}
        )
    assert replay.value.code == "confirmation_replayed"


def test_dataset_version_and_reference_deletion_are_guarded(repository):
    with pytest.raises(ValueError):
        repository.create_dataset("ipc_metrics", "非法版本", "@@@")
    dataset = repository.create_dataset("ipc_metrics", "已有记录", "1.0")
    repository.upsert_ipc_metrics(dataset["dataset_id"], [{
        "ipc_code": "E04B", "year": 2024, "patent_count": 1,
    }])
    with pytest.raises(ValueError):
        repository.delete_dataset_draft(dataset["dataset_id"])


def test_taxonomy_parent_and_fields_commit_in_one_audit(repository):
    technologies = TechnologyRepository(repository.db)
    node = technologies.create({
        "name": "统一保存节点", "level": 3, "parent_id": "tech_engineering_iot",
    })
    before_count = len(technologies.changes(node["node_id"]))
    updated = technologies.update(node["node_id"], {
        "name": "统一保存后的节点", "description": "一次事务",
        "parent_id": "tech_construction_machinery", "sort_order": 9,
    })
    assert updated["parent_id"] == "tech_construction_machinery"
    assert updated["name"] == "统一保存后的节点"
    assert len(technologies.changes(node["node_id"])) == before_count + 1


def test_queued_cancellation_stops_before_model_work(repository, tmp_path, monkeypatch):
    import src.library as library_module

    project = repository.create_project("cancel project")
    storage = WorkbenchStorage(tmp_path / "workbench")
    topic = {
        "topic_id": "cancel-topic", "topic_name": "取消测试",
        "selected": True, "keywords": [], "ipc_evidence": [],
        "fusion_pairs": [], "sample_abstracts": ["测试"],
    }
    repository.reserve_forecast_job(
        "job_cancel", project["project_id"], request_checksum="cancel-checksum",
        idempotency_key="cancel-key",
    )
    job = create_job(
        storage, [topic["topic_id"]], {}, job_id="job_cancel",
        project_id=project["project_id"], topic_snapshot=[topic],
        evidence_snapshot={"project_id": project["project_id"], "topics": [topic]},
    )
    repository.register_forecast_job(
        job["job_id"], project["project_id"],
        str(storage.job_dir(job["job_id"]) / "evidence_snapshot.json"),
        [topic], False, "", request_checksum="cancel-checksum",
        idempotency_key="cancel-key", snapshot_checksum=job["evidence_snapshot_checksum"],
    )
    repository.request_forecast_cancellation(job["job_id"])
    monkeypatch.setattr(library_module, "LibraryRepository", lambda: repository)
    with patch("src.api.forecast_service.run_round1") as round1:
        run_forecast_job(storage, job["job_id"])
    round1.assert_not_called()
    assert storage.get_job(job["job_id"])["status"] == "cancelled"
    assert repository.get_forecast_job(job["job_id"])["status"] == "cancelled"


def test_job_history_reports_missing_artifacts(repository, tmp_path, monkeypatch):
    import src.api.app as app_module
    project = repository.create_project("degraded history")
    repository.reserve_forecast_job(
        "job_degraded", project["project_id"], request_checksum="d",
        idempotency_key="degraded-key",
    )
    repository.update_forecast_job_status("job_degraded", "completed", progress=1)
    monkeypatch.setattr(app_module, "storage", WorkbenchStorage(tmp_path / "degraded"))
    result = app_module._joined_project_job(repository, "job_degraded")
    assert result["artifact_health"] == "degraded"
    assert {"job.json", "result.json"} <= set(result["missing_artifacts"])


def test_startup_reconciliation_marks_running_job_interrupted(
    repository, tmp_path, monkeypatch
):
    import src.api.app as app_module
    import src.api.project_routes as project_routes
    project = repository.create_project("restart project")
    storage = WorkbenchStorage(tmp_path / "restart")
    repository.reserve_forecast_job(
        "job_restart", project["project_id"], request_checksum="r",
        idempotency_key="restart-key",
    )
    file_job = create_job(
        storage, [], {}, job_id="job_restart", project_id=project["project_id"]
    )
    file_job["status"] = "running"
    storage.save_job("job_restart", file_job)
    repository.update_forecast_job_status("job_restart", "running")
    monkeypatch.setattr(project_routes, "repository", repository)
    monkeypatch.setattr(app_module, "storage", storage)
    app_module.reconcile_forecast_workers()
    assert repository.get_forecast_job("job_restart")["error_code"] == "worker_interrupted"
    assert storage.get_job("job_restart")["status"] == "failed"
