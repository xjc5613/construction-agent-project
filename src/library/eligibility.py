# -*- coding: utf-8 -*-
"""Canonical technology and dataset eligibility for new project work."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List, Optional

from .constants import HISTORICAL_PERIODS
from .technology import TechnologyRepository


class DatasetEligibilityResolver:
    def __init__(self, repository):
        self.repository = repository
        self.technologies = TechnologyRepository(repository.db)

    def resolve_for_topic(
        self, project_id: str, topic: Dict[str, Any],
        requested_dataset_ids: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        project = self.repository.get_project(project_id)
        if not project:
            raise ValueError("预测项目不存在")
        technology_ids = [
            item["technology_node_id"]
            for item in topic.get("technologies", [])
            if item.get("technology_node_id")
        ]
        return self.resolve(
            project, technology_ids,
            requested_dataset_ids=requested_dataset_ids,
        )

    def resolve(
        self, project: Dict[str, Any], technology_ids: Iterable[str] = (),
        *, requested_dataset_ids: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        root_id = project.get("technology_node_id")
        if not root_id:
            return self._empty(project, "历史项目未绑定技术目录")

        scope_nodes = self.technologies.descendants(
            root_id, level=3, active_only=True
        )
        scope_by_id = {item["node_id"]: item for item in scope_nodes}
        requested_technologies = list(dict.fromkeys(technology_ids))
        selected_technology_ids = requested_technologies or list(scope_by_id)
        invalid = [
            node_id for node_id in selected_technology_ids
            if node_id not in scope_by_id
        ]
        if invalid:
            raise ValueError(
                "技术不在项目范围或已停用：" + "、".join(invalid)
            )

        datasets = self._dataset_candidates(selected_technology_ids)
        eligible, excluded = [], []
        for dataset in datasets:
            reasons = self._dataset_exclusion_reasons(dataset)
            if reasons:
                excluded.append({**dataset, "exclusion_reasons": reasons})
            else:
                eligible.append(dataset)

        eligible_ids = [item["dataset_id"] for item in eligible]
        selected_ids = eligible_ids
        if requested_dataset_ids is not None:
            requested_ids = list(dict.fromkeys(
                item for item in requested_dataset_ids if item
            ))
            foreign = [item for item in requested_ids if item not in eligible_ids]
            if foreign:
                raise ValueError(
                    "所选数据集不属于当前项目主题技术范围：" + "、".join(foreign)
                )
            selected_ids = requested_ids

        coverage = self._coverage(eligible)
        technology_snapshot = [
            {
                "node_id": scope_by_id[node_id]["node_id"],
                "name": scope_by_id[node_id]["name"],
                "path_text": scope_by_id[node_id].get("path_text", ""),
                "taxonomy_version": scope_by_id[node_id]["taxonomy_version"],
            }
            for node_id in selected_technology_ids
        ]
        payload = {
            "contract_version": 1,
            "project_id": project["project_id"],
            "root_node_id": root_id,
            "technology_ids": selected_technology_ids,
            "technologies": technology_snapshot,
            "eligible_dataset_ids": eligible_ids,
            "selected_dataset_ids": selected_ids,
            "eligible_datasets": eligible,
            "excluded_datasets": excluded,
            "coverage": coverage,
            "legacy_scope": False,
        }
        payload["scope_checksum"] = self._checksum(payload)
        return payload

    def _dataset_candidates(self, technology_ids: List[str]) -> List[Dict[str, Any]]:
        if not technology_ids:
            return []
        placeholders = ",".join("?" for _ in technology_ids)
        with self.repository.db.connect() as connection:
            rows = connection.execute(
                f"""SELECT d.*,n.name technology_name,
                           (SELECT COUNT(*) FROM papers p WHERE p.dataset_id=d.dataset_id) paper_count,
                           (SELECT COUNT(*) FROM ipc_metrics m WHERE m.dataset_id=d.dataset_id) ipc_record_count,
                           (SELECT COUNT(*) FROM ipc_fusions f WHERE f.dataset_id=d.dataset_id) fusion_record_count,
                           (SELECT COUNT(*) FROM patents p WHERE p.dataset_id=d.dataset_id) patent_count,
                           (SELECT COUNT(*) FROM reduced_ipc_edges e WHERE e.dataset_id=d.dataset_id) reduced_edge_count,
                           (SELECT COUNT(*) FROM patent_ipcs pi JOIN patents p ON p.patent_id=pi.patent_id
                            WHERE p.dataset_id=d.dataset_id AND pi.mapping_status!='mapped') unresolved_mapping_count,
                           (SELECT COUNT(*) FROM papers p WHERE p.dataset_id=d.dataset_id
                            AND p.paper_type!='unknown') typed_paper_count,
                           (SELECT COUNT(*) FROM data_coverage c WHERE c.dataset_id=d.dataset_id) coverage_record_count,
                           (SELECT COUNT(*) FROM data_coverage c WHERE c.dataset_id=d.dataset_id
                            AND c.completeness='complete') complete_year_count,
                           (SELECT COUNT(*) FROM imports i
                            WHERE i.dataset_id=d.dataset_id AND i.status='committed') committed_import_count
                    FROM datasets d JOIN technology_nodes n
                    ON n.node_id=d.technology_node_id
                    WHERE d.technology_node_id IN ({placeholders})
                    ORDER BY d.period_code,d.public_kind,d.version""",
                technology_ids,
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            node = self.technologies.get(item["technology_node_id"])
            item["technology_path"] = node.get("path_text", "") if node else ""
            patent_count = int(item.get("patent_count") or 0)
            reduced_count = int(item.get("reduced_edge_count") or 0)
            item["reconstruction_grade"] = (
                "canonical_patent_incidence" if patent_count else
                "reviewed_reduced_edge" if reduced_count else "legacy_aggregate"
            )
            item["evidence_grade"] = (
                "A" if patent_count and item.get("complete_year_count") else
                "B" if patent_count else "C" if reduced_count else "D"
            )
            item["quality_dimensions"] = {
                "canonical_patent_incidence": patent_count,
                "reviewed_reduced_edges": reduced_count,
                "typed_papers": int(item.get("typed_paper_count") or 0),
                "unresolved_ipc_mappings": int(item.get("unresolved_mapping_count") or 0),
                "coverage_records": int(item.get("coverage_record_count") or 0),
            }
            results.append(item)
        return results

    @staticmethod
    def _dataset_exclusion_reasons(dataset: Dict[str, Any]) -> List[str]:
        reasons = []
        if dataset.get("migration_status") != "mapped":
            reasons.append("数据集尚未完成技术与阶段映射")
        if dataset.get("lifecycle_status", "active") != "active":
            reasons.append("数据集已废弃")
        if dataset.get("status") != "published":
            reasons.append("数据集未发布")
        kind = dataset.get("public_kind")
        ipc_count = int(dataset.get("ipc_record_count") or 0)
        paper_count = int(dataset.get("paper_count") or 0)
        if kind == "ipc" and not ipc_count and not int(dataset.get("fusion_record_count") or 0) \
                and not int(dataset.get("patent_count") or 0) \
                and not int(dataset.get("reduced_edge_count") or 0):
            reasons.append("没有有效 IPC 记录")
        elif kind == "paper" and not paper_count:
            reasons.append("没有有效论文记录")
        elif kind == "integrated" and (not ipc_count or not paper_count):
            reasons.append("综合数据缺少有效 IPC 或论文记录")
        elif kind not in {"ipc", "paper", "integrated"}:
            reasons.append("数据类型未完成校准")
        return reasons

    def _coverage(self, datasets: List[Dict[str, Any]]) -> Dict[str, Any]:
        periods = {
            code: {
                "ipc": 0, "paper": 0, "integrated": 0,
                "ipc_records": 0, "paper_records": 0,
                "patent_records": 0, "reduced_edge_records": 0,
                "included_years": [], "complete_years": [],
            }
            for code in HISTORICAL_PERIODS
        }
        for dataset in datasets:
            period = dataset.get("period_code")
            kind = dataset.get("public_kind")
            if period not in periods or kind not in {"ipc", "paper", "integrated"}:
                continue
            periods[period][kind] += 1
            periods[period]["ipc_records"] += int(dataset.get("ipc_record_count") or 0)
            periods[period]["paper_records"] += int(dataset.get("paper_count") or 0)
            periods[period]["patent_records"] += int(dataset.get("patent_count") or 0)
            periods[period]["reduced_edge_records"] += int(dataset.get("reduced_edge_count") or 0)
            with self.repository.db.connect() as connection:
                rows = connection.execute(
                    "SELECT year,completeness FROM data_coverage WHERE dataset_id=? ORDER BY year",
                    (dataset["dataset_id"],),
                ).fetchall()
            periods[period]["included_years"].extend(int(row["year"]) for row in rows)
            periods[period]["complete_years"].extend(
                int(row["year"]) for row in rows if row["completeness"] == "complete"
            )
        for values in periods.values():
            values["included_years"] = sorted(set(values["included_years"]))
            values["complete_years"] = sorted(set(values["complete_years"]))
            values["included_year_denominator"] = len(values["included_years"])
            values["complete_year_denominator"] = len(values["complete_years"])
        missing = [
            period for period, values in periods.items()
            if not values["ipc_records"] and not values["paper_records"]
            and not values["patent_records"] and not values["reduced_edge_records"]
        ]
        return {
            "periods": periods,
            "missing_periods": missing,
            "complete": not missing,
        }

    def _empty(self, project: Dict[str, Any], reason: str) -> Dict[str, Any]:
        payload = {
            "contract_version": 1,
            "project_id": project["project_id"],
            "root_node_id": project.get("technology_node_id"),
            "technology_ids": [],
            "technologies": [],
            "eligible_dataset_ids": [],
            "selected_dataset_ids": [],
            "eligible_datasets": [],
            "excluded_datasets": [],
            "coverage": {
                "periods": {
                    code: {
                        "ipc": 0, "paper": 0, "integrated": 0,
                        "ipc_records": 0, "paper_records": 0,
                    }
                    for code in HISTORICAL_PERIODS
                },
                "missing_periods": list(HISTORICAL_PERIODS),
                "complete": False,
            },
            "legacy_scope": bool(project.get("legacy_mode")),
            "blocking_reason": reason,
        }
        payload["scope_checksum"] = self._checksum(payload)
        return payload

    @staticmethod
    def _checksum(payload: Dict[str, Any]) -> str:
        rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(rendered.encode("utf-8")).hexdigest()
