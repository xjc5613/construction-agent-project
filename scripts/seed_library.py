# -*- coding: utf-8 -*-
"""Import legacy fixed topics and abstracts as a versioned compatibility dataset."""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.api.project_service import ProjectService
from src.library import LibraryRepository

IPC_PATTERN = re.compile(r"([A-H]\d{2}[A-Z](?:-\d{1,4})?)")
NUMBER_PATTERN = re.compile(r"度中心度(?:仅为|为|升至|增至|达)?\s*(0?\.\d+)")


def _dataset(repo: LibraryRepository, kind: str, name: str):
    existing = next(
        (item for item in repo.list_datasets(kind) if item["name"] == name and item["version"] == "1.0"),
        None,
    )
    if existing:
        return existing
    result = repo.create_dataset(
        kind, name, "1.0",
        "由旧固定主题资源迁移的兼容演示数据；IPC 历史点为可视化演示插值，不可替代正式统计数据。",
    )
    return repo.update_dataset_status(result["dataset_id"], "published")


def seed(repo: LibraryRepository) -> dict:
    seed_dir = ROOT / "data" / "seed"
    raw_dir = ROOT / "data" / "raw"
    source_dir = seed_dir if (seed_dir / "topics.json").exists() else raw_dir
    topics = json.loads((source_dir / "topics.json").read_text(encoding="utf-8"))
    pairs = json.loads((source_dir / "high_potential_pairs.json").read_text(encoding="utf-8"))
    metrics_dataset = _dataset(repo, "ipc_metrics", "内置 IPC 兼容演示数据")
    fusion_dataset = _dataset(repo, "ipc_fusions", "内置 IPC 融合数据")
    paper_dataset = _dataset(repo, "papers", "内置主题摘要数据")

    metric_rows = []
    for topic in topics:
        codes = list(dict.fromkeys(IPC_PATTERN.findall(topic.get("ipc_trend", ""))))
        values = [float(value) for value in NUMBER_PATTERN.findall(topic.get("ipc_trend", ""))]
        latest = values[-1] if values else 0.05
        for code in codes:
            for offset, year in enumerate(range(2021, 2026), start=1):
                metric_rows.append({
                    "ipc_code": code, "year": year,
                    "degree_centrality": round(latest * (0.68 + offset * 0.064), 6),
                    "source_row": None,
                })
    repo.upsert_ipc_metrics(metrics_dataset["dataset_id"], metric_rows)

    fusion_rows = []
    for entry in pairs:
        for pair in entry.get("pairs", []):
            fusion_rows.append({
                "ipc1": pair["ipc1"], "ipc2": pair["ipc2"],
                "year": 2025, "probability": pair["prob"],
            })
    repo.upsert_ipc_fusions(fusion_dataset["dataset_id"], fusion_rows)

    abstracts_dir = source_dir / "sample_abstracts"
    paper_count = 0
    for topic in topics:
        abstract_path = abstracts_dir / f"{topic['name']}.txt"
        abstract = abstract_path.read_text(encoding="utf-8").strip() if abstract_path.exists() else topic.get("ipc_trend", "")
        repo.add_paper(paper_dataset["dataset_id"], {
            "title": f"{topic['name']}研究摘要",
            "authors": "内置演示数据",
            "year": 2025,
            "keywords": ",".join(topic.get("keywords", [])),
            "abstract": abstract,
        }, [{"section": "摘要", "ordinal": 0, "content": abstract}])
        paper_count += 1
    return {
        "topics": len(topics), "ipc_metrics": len(metric_rows),
        "ipc_fusions": len(fusion_rows), "papers": paper_count,
    }


def migrate_legacy_project(repo: LibraryRepository) -> dict:
    project = repo.get_project("legacy-default")
    if not project:
        project = repo.create_project(
            "旧工作台迁移项目", "从 data/workbench 非破坏迁移", "legacy-default"
        )
    service = ProjectService(repo)
    documents_dir = ROOT / "data" / "workbench" / "documents"
    material_count = 0
    if documents_dir.exists():
        for path in documents_dir.glob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            try:
                service.add_text_material(
                    project["project_id"], payload.get("title", path.stem),
                    payload.get("content", ""),
                )
                material_count += 1
            except Exception:
                pass
    topics_path = ROOT / "data" / "workbench" / "topics" / "topics.json"
    topic_count = 0
    if topics_path.exists():
        existing_names = {
            topic["topic_name"] for topic in repo.list_topics(project["project_id"], include_deleted=True)
        }
        for topic in json.loads(topics_path.read_text(encoding="utf-8")):
            if topic["topic_name"] in existing_names:
                continue
            try:
                repo.save_topic({
                    "project_id": project["project_id"],
                    "topic_name": topic["topic_name"],
                    "description": topic.get("example", ""),
                    "keywords": topic.get("keywords", []),
                    "evidence": topic.get("ipc_evidence", []),
                    "fusion_pairs": topic.get("fusion_pairs", []),
                    "operator_notes": topic.get("operator_notes", ""),
                    "evidence_score": topic.get("evidence_score", 0),
                    "requires_review": topic.get("requires_review", True),
                    "selected": topic.get("selected", True),
                    "status": "candidate",
                })
                topic_count += 1
                existing_names.add(topic["topic_name"])
            except Exception:
                pass
    return {"project_id": project["project_id"], "materials": material_count, "topics": topic_count}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-legacy-project", action="store_true")
    args = parser.parse_args()
    repository = LibraryRepository()
    report = {"seed": seed(repository)}
    if args.include_legacy_project:
        report["legacy_project"] = migrate_legacy_project(repository)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
