# -*- coding: utf-8 -*-
"""Back up and reconcile file-backed workbench jobs into SQLite metadata."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from config.settings import JOBS_DIR, LIBRARY_DB_PATH
from src.library.database import LibraryDatabase


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def backup_database(database_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = backup_dir / f"{database_path.stem}-{timestamp}{database_path.suffix}"
    if database_path.exists():
        shutil.copy2(database_path, destination)
    else:
        destination.touch()
    return destination


def reconcile_jobs(database: LibraryDatabase, jobs_dir: Path) -> Dict[str, int]:
    summary = {"discovered": 0, "imported": 0, "updated": 0, "skipped": 0}
    jobs_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    with database.transaction() as connection:
        project_rows = connection.execute(
            "SELECT project_id,baseline_year,target_year FROM projects"
        ).fetchall()
        projects = {row["project_id"]: dict(row) for row in project_rows}
        for job_path in sorted(jobs_dir.glob("*/job.json")):
            summary["discovered"] += 1
            payload = _read_json(job_path)
            job_id = str(payload.get("job_id") or job_path.parent.name)
            project_id = str(payload.get("project_id") or "")
            if not project_id and "legacy-default" in projects:
                project_id = "legacy-default"
            elif not project_id and len(projects) == 1:
                project_id = next(iter(projects))
            if not job_id or project_id not in projects:
                summary["skipped"] += 1
                continue
            status = str(payload.get("status") or "failed")
            error_code = ""
            error_message = str(payload.get("error") or "")
            if status in {"running", "cancelling"}:
                status = "failed"
                error_code = "worker_interrupted"
                error_message = "服务重启中断了正在执行的任务，请显式重试"
            artifact_health = "ready" if (job_path.parent / "result.json").exists() else "partial"
            existing = connection.execute(
                "SELECT job_id FROM forecast_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if existing:
                connection.execute(
                    """UPDATE forecast_jobs SET status=?,progress=?,current_stage=?,
                       error_code=?,error_message=?,artifact_health=?,updated_at=?,
                       completed_at=CASE WHEN ? IN ('completed','partial_failed','failed','cancelled')
                                         THEN COALESCE(completed_at,?) ELSE completed_at END
                       WHERE job_id=?""",
                    (
                        status, float(payload.get("progress") or 0),
                        str(payload.get("current_stage") or status), error_code,
                        error_message, artifact_health, now, status, now, job_id,
                    ),
                )
                summary["updated"] += 1
                continue
            if status in {"queued", "running", "cancelling"}:
                active = connection.execute(
                    """SELECT 1 FROM forecast_jobs WHERE project_id=?
                       AND status IN ('queued','running','cancelling')""",
                    (project_id,),
                ).fetchone()
                if active:
                    status = "failed"
                    error_code = "duplicate_active_migration"
                    error_message = "迁移时发现同一项目存在重复活动任务"
            snapshot_path = job_path.parent / "evidence_snapshot.json"
            connection.execute(
                """INSERT INTO forecast_jobs(
                    job_id,project_id,evidence_snapshot_path,topic_snapshot_json,status,
                    evidence_limited,override_reason,baseline_year,target_year,
                    forecast_nodes_json,taxonomy_snapshot_json,options_json,progress,
                    current_stage,artifact_health,error_code,error_message,created_at,
                    updated_at,completed_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    job_id, project_id, str(snapshot_path),
                    json.dumps(payload.get("topic_snapshot", []), ensure_ascii=False),
                    status, int(bool(payload.get("evidence_limited"))),
                    str(payload.get("override_reason") or ""),
                    int(payload.get("baseline_year") or projects[project_id]["baseline_year"]),
                    int(payload.get("target_year") or projects[project_id]["target_year"]),
                    json.dumps(payload.get("forecast_nodes") or [
                        year for year in (2030, 2035, 2040)
                        if year <= int(projects[project_id]["target_year"])
                    ]),
                    json.dumps(payload.get("taxonomy_snapshot", {}), ensure_ascii=False),
                    json.dumps(payload.get("options", {}), ensure_ascii=False),
                    float(payload.get("progress") or 0),
                    str(payload.get("current_stage") or status), artifact_health,
                    error_code, error_message,
                    str(payload.get("created_at") or now), now,
                    now if status in {"completed", "partial_failed", "failed", "cancelled"} else None,
                ),
            )
            summary["imported"] += 1
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=LIBRARY_DB_PATH)
    parser.add_argument("--jobs-dir", type=Path, default=JOBS_DIR)
    parser.add_argument(
        "--backup-dir", type=Path, default=LIBRARY_DB_PATH.parent / "backups"
    )
    args = parser.parse_args()
    backup = backup_database(args.database, args.backup_dir)
    summary = reconcile_jobs(LibraryDatabase(args.database), args.jobs_dir)
    print(json.dumps({"backup": str(backup), **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
