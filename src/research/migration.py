# -*- coding: utf-8 -*-
"""Read-only-first classifier for explicit research-contract v3 migrations."""

from typing import Any, Dict, List

from src.library import LibraryRepository


def classify_datasets(repository: LibraryRepository) -> List[Dict[str, Any]]:
    with repository.db.connect() as connection:
        datasets = connection.execute("SELECT * FROM datasets ORDER BY dataset_id").fetchall()
        results = []
        for row in datasets:
            dataset = dict(row); identifier = dataset["dataset_id"]
            patents = connection.execute("SELECT COUNT(*) FROM patents WHERE dataset_id=?", (identifier,)).fetchone()[0]
            assignments = connection.execute(
                "SELECT COUNT(*) FROM patent_ipcs WHERE patent_id IN (SELECT patent_id FROM patents WHERE dataset_id=?)", (identifier,)
            ).fetchone()[0]
            reduced = connection.execute("SELECT COUNT(*) FROM reduced_ipc_edges WHERE dataset_id=?", (identifier,)).fetchone()[0]
            if int(dataset.get("research_contract_version") or 2) == 3:
                category, reason = "mapped", "已使用研究契约 v3"
            elif patents and assignments:
                category, reason = "mapped", "已有规范专利—IPC 归属，可经人工复核后迁移"
            elif patents:
                category, reason = "needs_patent_ipc_reconstruction", "有专利记录但缺少多值 IPC 归属"
            elif reduced:
                category, reason = "reduced_edge_only", "仅可提供降级网络证据，不能冒充规范专利共现"
            elif dataset.get("period_code") in {"2010_2015", "2016_2020", "2021_2026"}:
                category, reason = "needs_period_split", "旧时期边界与 2010—2014/2015—2019/2020—2025 不一致"
            else:
                category, reason = "quarantined_legacy", "缺少可证明的 v3 时间与证据映射"
            results.append({"dataset_id": identifier, "name": dataset["name"], "version": dataset["version"],
                            "category": category, "reason": reason, "patent_count": patents,
                            "assignment_count": assignments, "reduced_edge_count": reduced,
                            "original_contract_version": int(dataset.get("research_contract_version") or 2)})
    return results


def migration_plan(repository: LibraryRepository) -> Dict[str, Any]:
    datasets = classify_datasets(repository)
    with repository.db.connect() as connection:
        projects = [dict(row) for row in connection.execute(
            "SELECT project_id,name,research_contract_version,lifecycle_status FROM projects ORDER BY project_id"
        ).fetchall()]
    return {"dry_run": True, "requires_explicit_review": True, "datasets": datasets,
            "projects": projects, "eligible_dataset_ids": [item["dataset_id"] for item in datasets if item["category"] == "mapped"]}
