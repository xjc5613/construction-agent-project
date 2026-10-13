# -*- coding: utf-8 -*-
"""Dry-run first migration for taxonomy and staged evidence metadata."""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.library import LibraryRepository, TechnologyRepository
from src.library.constants import HISTORICAL_PERIODS, LEGACY_TOPIC_MAPPINGS


def _period_for_years(years: List[int]) -> Optional[str]:
    if not years:
        return None
    matches = [
        code for code, (start, end) in HISTORICAL_PERIODS.items()
        if all(start <= year <= end for year in years)
    ]
    return matches[0] if len(matches) == 1 else None


def _dataset_years(repository: LibraryRepository, dataset_id: str) -> List[int]:
    with repository.db.connect() as connection:
        rows = []
        for table in ("ipc_metrics", "ipc_fusions", "papers"):
            rows.extend(connection.execute(
                f"SELECT year FROM {table} WHERE dataset_id=? AND year IS NOT NULL",
                (dataset_id,),
            ).fetchall())
        return sorted({int(row["year"]) for row in rows})


def _technology_candidates(
    repository: LibraryRepository, dataset: Dict[str, Any]
) -> List[str]:
    technologies = TechnologyRepository(repository.db).list_nodes(level=3)
    haystack = " ".join([
        dataset.get("name", ""), dataset.get("description", ""),
    ]).lower()
    matches = [
        node["node_id"] for node in technologies
        if node["name"].lower() in haystack
    ]
    return matches


def migrate(apply: bool, repository: Optional[LibraryRepository] = None) -> Dict[str, Any]:
    repository = repository or LibraryRepository()
    report: Dict[str, Any] = {
        "mode": "apply" if apply else "dry-run",
        "datasets": [], "projects": [], "topic_mappings": LEGACY_TOPIC_MAPPINGS,
        "topic_results": [],
        "ok": True,
    }
    public_kind_map = {
        "ipc_metrics": "ipc", "ipc_fusions": "ipc",
        "papers": "paper", "mixed": "integrated",
    }
    for dataset in repository.list_datasets():
        years = _dataset_years(repository, dataset["dataset_id"])
        period = _period_for_years(years)
        technologies = _technology_candidates(repository, dataset)
        migration_status = (
            "mapped" if period and len(technologies) == 1
            else "needs_split" if years and not period
            else "needs_mapping"
        )
        item = {
            "dataset_id": dataset["dataset_id"],
            "public_kind": public_kind_map.get(dataset["kind"], dataset.get("public_kind") or ""),
            "years": years,
            "period_code": period,
            "technology_candidates": technologies,
            "migration_status": migration_status,
        }
        if apply:
            with repository.db.transaction() as connection:
                connection.execute(
                    """UPDATE datasets SET public_kind=?,period_code=?,
                       technology_node_id=?,migration_status=?,lineage_json=?
                       WHERE dataset_id=?""",
                    (
                        item["public_kind"], period,
                        technologies[0] if len(technologies) == 1 else None,
                        migration_status,
                        json.dumps({
                            "legacy_dataset_id": dataset["dataset_id"],
                            "migration": "taxonomy-stage-v1",
                        }, ensure_ascii=False),
                        dataset["dataset_id"],
                    ),
                )
        report["datasets"].append(item)
    for project in repository.list_projects():
        item = {
            "project_id": project["project_id"],
            "legacy_mode": not bool(project.get("technology_node_id")),
            "baseline_year": project.get("baseline_year", 2025),
        }
        if apply and item["legacy_mode"]:
            with repository.db.transaction() as connection:
                connection.execute(
                    """UPDATE projects SET legacy_mode=1,baseline_year=2025,
                       target_year=2040 WHERE project_id=?""",
                    (project["project_id"],),
                )
        report["projects"].append(item)
        for topic in repository.list_topics(project["project_id"], include_deleted=True):
            node_ids = LEGACY_TOPIC_MAPPINGS.get(topic["topic_name"], [])
            topic_item = {
                "topic_id": topic["topic_id"], "topic_name": topic["topic_name"],
                "technology_node_ids": node_ids,
                "status": "suggested" if node_ids else "needs_mapping",
            }
            if apply and node_ids and not topic.get("technologies"):
                repository.set_topic_technologies(topic["topic_id"], [
                    {
                        "technology_node_id": node_id,
                        "is_primary": index == 0,
                        "relevance": 1,
                        "source": "migration_suggestion",
                    }
                    for index, node_id in enumerate(node_ids)
                ])
            report["topic_results"].append(topic_item)
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True)
    report["checksum"] = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Map legacy datasets and projects to taxonomy/stage metadata."
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--report", type=Path,
        default=ROOT / "var" / "migration" / "taxonomy-stage-migration.json",
    )
    args = parser.parse_args()
    report = migrate(args.apply)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
