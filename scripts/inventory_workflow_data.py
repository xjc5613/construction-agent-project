#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only inventory for the scoped workflow migration."""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import EXPORTS_DIR, JOBS_DIR, LIBRARY_DB_PATH, LIBRARY_RAW_DIR, PROJECTS_DIR
from src.library import LibraryDatabase
from src.library.constants import HISTORICAL_PERIODS
from src.research.contracts import get_research_contract


def _count_files(path: Path) -> int:
    return sum(1 for item in path.rglob("*") if item.is_file()) if path.exists() else 0


def _file_inventory(path: Path) -> list:
    if not path.exists():
        return []
    return [
        {
            "path": str(item),
            "size": item.stat().st_size,
            "sha256": hashlib.sha256(item.read_bytes()).hexdigest(),
        }
        for item in sorted(path.rglob("*")) if item.is_file()
    ]


def inventory(database: Optional[LibraryDatabase] = None) -> Dict[str, Any]:
    db = database or LibraryDatabase()
    with db.connect() as connection:
        technologies = [
            dict(row) for row in connection.execute(
                """WITH RECURSIVE effective(node_id,effective_active) AS (
                     SELECT node_id,status='active'
                     FROM technology_nodes WHERE parent_id IS NULL
                     UNION ALL
                     SELECT n.node_id,e.effective_active AND n.status='active'
                     FROM technology_nodes n JOIN effective e ON n.parent_id=e.node_id
                   )
                   SELECT n.node_id,n.parent_id,n.level,n.name,n.status,
                          CASE WHEN e.effective_active THEN 'active' ELSE 'inactive' END effective_status
                   FROM technology_nodes n JOIN effective e ON e.node_id=n.node_id
                   ORDER BY n.level,n.sort_order,n.name"""
            ).fetchall()
        ]
        datasets = []
        for row in connection.execute(
            """SELECT d.*,
                      (SELECT COUNT(*) FROM papers p WHERE p.dataset_id=d.dataset_id) papers,
                      (SELECT COUNT(*) FROM ipc_metrics m WHERE m.dataset_id=d.dataset_id) ipc_metrics,
                      (SELECT COUNT(*) FROM ipc_fusions f WHERE f.dataset_id=d.dataset_id) ipc_fusions,
                      (SELECT COUNT(*) FROM imports i WHERE i.dataset_id=d.dataset_id AND i.status='committed') committed_imports
               FROM datasets d ORDER BY d.imported_at"""
        ).fetchall():
            item = dict(row)
            years = [
                int(value["year"])
                for table in ("papers", "ipc_metrics", "ipc_fusions")
                for value in connection.execute(
                    f"SELECT year FROM {table} WHERE dataset_id=? AND year IS NOT NULL",
                    (item["dataset_id"],),
                ).fetchall()
            ]
            periods = sorted({
                code for year in years
                for code, (start, end) in HISTORICAL_PERIODS.items()
                if start <= year <= end
            })
            if item.get("migration_status") == "mapped":
                disposition = "mapped"
            elif len(periods) > 1:
                disposition = "needs_split"
            else:
                disposition = "needs_mapping"
            item["observed_years"] = sorted(set(years))
            item["observed_periods"] = periods
            item["migration_disposition"] = disposition
            item["eligible_for_new_work"] = bool(
                item.get("technology_node_id")
                and item.get("migration_status") == "mapped"
                and item.get("lifecycle_status", "active") == "active"
                and item.get("status") == "published"
                and (item["papers"] or item["ipc_metrics"] or item["ipc_fusions"])
            )
            datasets.append(item)
        counts = {
            table: int(connection.execute(
                f"SELECT COUNT(*) value FROM {table}"
            ).fetchone()["value"])
            for table in (
                "papers", "ipc_metrics", "ipc_fusions", "projects",
                "project_materials", "project_topics", "evidence_packages",
                "forecast_jobs",
            )
        }
        schema_version = int(connection.execute(
            "SELECT MAX(version) value FROM schema_migrations"
        ).fetchone()["value"])
        source_files = [dict(row) for row in connection.execute(
            """SELECT file_id,dataset_id,filename,checksum,parse_status,created_at
               FROM source_files ORDER BY created_at,file_id"""
        ).fetchall()]
        mappings = [dict(row) for row in connection.execute(
            """SELECT status,rule_version,COUNT(*) count
               FROM ipc_code_mappings GROUP BY status,rule_version
               ORDER BY status,rule_version"""
        ).fetchall()]
        projects = [dict(row) for row in connection.execute(
            """SELECT project_id,name,baseline_year,target_year,legacy_mode,
                      research_contract_version,status,lifecycle_status
               FROM projects ORDER BY created_at,project_id"""
        ).fetchall()]
        jobs = [dict(row) for row in connection.execute(
            """SELECT job_id,project_id,status,research_contract_version,
                      evidence_snapshot_path,snapshot_checksum,
                      artifact_health
               FROM forecast_jobs ORDER BY created_at,job_id"""
        ).fetchall()]
    for job in jobs:
        snapshot = Path(job.get("evidence_snapshot_path") or "")
        result = JOBS_DIR / job["job_id"] / "result.json"
        job["snapshot_exists"] = bool(snapshot.is_file())
        job["result_exists"] = bool(result.is_file())
    return {
        "databases": [{"path": str(db.path), "size": db.path.stat().st_size}],
        "schema_version": schema_version,
        "current_research_contract": get_research_contract().to_dict(),
        "technologies": technologies,
        "datasets": datasets,
        "source_files": source_files,
        "mapping_states": mappings,
        "projects": projects,
        "jobs": jobs,
        "counts": counts,
        "artifacts": {
            "library_raw": {"path": str(LIBRARY_RAW_DIR), "files": _file_inventory(LIBRARY_RAW_DIR)},
            "projects": {"path": str(PROJECTS_DIR), "files": _file_inventory(PROJECTS_DIR)},
            "jobs": {"path": str(JOBS_DIR), "files": _file_inventory(JOBS_DIR)},
            "exports": {"path": str(EXPORTS_DIR), "files": _file_inventory(EXPORTS_DIR)},
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory workflow data without modifying it.")
    parser.add_argument("--database", type=Path, default=LIBRARY_DB_PATH)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = inventory(LibraryDatabase(args.database))
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
