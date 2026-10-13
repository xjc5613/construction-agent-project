# -*- coding: utf-8 -*-
import hashlib
import json
import math
import re
from collections import Counter
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from src.library import (
    DatasetEligibilityResolver,
    LibraryRepository,
    TechnologyRepository,
)
from src.library.constants import HISTORICAL_PERIODS, PERIOD_LABELS

ALGORITHM_VERSION = "stage-evolution-v1"


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:16]}"


def _slope(points: List[tuple[int, float]]) -> Optional[float]:
    if len(points) < 2:
        return None
    x_mean = mean(item[0] for item in points)
    y_mean = mean(item[1] for item in points)
    denominator = sum((item[0] - x_mean) ** 2 for item in points)
    if not denominator:
        return 0
    return sum(
        (x - x_mean) * (y - y_mean) for x, y in points
    ) / denominator


def _cagr(points: List[tuple[int, float]]) -> Optional[float]:
    positive = [(year, value) for year, value in points if value is not None and value > 0]
    if len(positive) < 2:
        return None
    years = positive[-1][0] - positive[0][0]
    if years <= 0:
        return None
    return (positive[-1][1] / positive[0][1]) ** (1 / years) - 1


def _direction(first: Optional[float], last: Optional[float]) -> str:
    if first is None or last is None:
        return "insufficient"
    scale = max(abs(first), 1e-9)
    change = (last - first) / scale
    if change > 0.1:
        return "growing"
    if change < -0.1:
        return "declining"
    return "stable"


class StageAnalysisService:
    def __init__(self, repository: Optional[LibraryRepository] = None):
        self.repository = repository or LibraryRepository()
        self.technologies = TechnologyRepository(self.repository.db)

    def _scope(
        self, technology_node_id: str, project_id: str = ""
    ) -> Dict[str, Any]:
        project = self.repository.get_project(project_id) if project_id else {
            "project_id": f"stage:{technology_node_id}",
            "technology_node_id": technology_node_id,
            "legacy_mode": False,
        }
        if not project:
            raise ValueError("预测项目不存在")
        return DatasetEligibilityResolver(self.repository).resolve(
            project, [technology_node_id]
        )

    def _datasets(
        self, technology_node_id: str, project_id: str = ""
    ) -> List[Dict[str, Any]]:
        return self._scope(
            technology_node_id, project_id
        )["eligible_datasets"]

    def _raw_data(
        self, technology_node_id: str, project_id: str = ""
    ) -> tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        datasets = self._datasets(technology_node_id, project_id)
        by_period: Dict[str, Dict[str, Any]] = {
            code: {
                "datasets": [], "ipc": [], "fusions": [], "papers": [],
            }
            for code in HISTORICAL_PERIODS
        }
        with self.repository.db.connect() as connection:
            for dataset in datasets:
                period = dataset.get("period_code")
                if period not in by_period:
                    continue
                by_period[period]["datasets"].append(dataset)
                by_period[period]["ipc"].extend(dict(row) for row in connection.execute(
                    "SELECT * FROM ipc_metrics WHERE dataset_id=? AND year<=2025",
                    (dataset["dataset_id"],),
                ).fetchall())
                by_period[period]["fusions"].extend(dict(row) for row in connection.execute(
                    """SELECT * FROM ipc_fusions
                       WHERE dataset_id=? AND (year IS NULL OR year<=2025)""",
                    (dataset["dataset_id"],),
                ).fetchall())
                by_period[period]["papers"].extend(dict(row) for row in connection.execute(
                    """SELECT * FROM papers
                       WHERE dataset_id=? AND (year IS NULL OR year<=2025)""",
                    (dataset["dataset_id"],),
                ).fetchall())
        return datasets, by_period

    @staticmethod
    def _period_metrics(
        period: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        start, end = HISTORICAL_PERIODS[period]
        duration = end - start + 1
        ipc_rows = data["ipc"]
        papers = data["papers"]
        patent_by_year: Dict[int, float] = {}
        for row in ipc_rows:
            if row.get("patent_count") is not None:
                patent_by_year[row["year"]] = (
                    patent_by_year.get(row["year"], 0) + row["patent_count"]
                )
        patent_points = sorted(patent_by_year.items())
        degrees = [
            row["degree_centrality"] for row in ipc_rows
            if row.get("degree_centrality") is not None
        ]
        keywords = Counter()
        for paper in papers:
            for keyword in re.split(r"[,，;；\s]+", paper.get("keywords") or ""):
                if keyword:
                    keywords[keyword] += 1
        fusion_values = [
            row["probability"] for row in data["fusions"]
            if row.get("probability") is not None
        ]
        patent_total = sum(patent_by_year.values())
        return {
            "period_code": period,
            "period_label": PERIOD_LABELS[period],
            "duration_years": duration,
            "dataset_ids": [item["dataset_id"] for item in data["datasets"]],
            "ipc_record_count": len(ipc_rows),
            "patent_total": patent_total,
            "patent_annual_average": patent_total / duration,
            "patent_cagr": _cagr(patent_points),
            "patent_slope": _slope(patent_points),
            "degree_centrality_average": mean(degrees) if degrees else None,
            "fusion_average": mean(fusion_values) if fusion_values else None,
            "paper_total": len(papers),
            "paper_annual_average": len(papers) / duration,
            "top_keywords": [
                {"keyword": keyword, "count": count}
                for keyword, count in keywords.most_common(12)
            ],
            "representative_papers": [
                {
                    "paper_id": paper["paper_id"], "title": paper["title"],
                    "year": paper["year"],
                }
                for paper in sorted(
                    papers, key=lambda item: item.get("year") or 0, reverse=True
                )[:5]
            ],
        }

    @staticmethod
    def _keyword_evolution(
        metrics: Dict[str, Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        sets = {
            period: {item["keyword"] for item in values["top_keywords"]}
            for period, values in metrics.items()
        }
        ordered = list(HISTORICAL_PERIODS)
        early, middle, recent = (sets[period] for period in ordered)
        return {
            "emerging": sorted(recent - early - middle),
            "persistent": sorted(early & middle & recent),
            "fading": sorted((early | middle) - recent),
        }

    def analyze(
        self, technology_node_id: str, project_id: str = "",
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        technology = self.technologies.get(technology_node_id)
        if not technology or technology["level"] != 3:
            raise ValueError("阶段分析必须选择三级技术")
        parameters = parameters or {}
        scope = self._scope(technology_node_id, project_id)
        datasets, raw = self._raw_data(technology_node_id, project_id)
        checksum_payload = {
            "technology_node_id": technology_node_id,
            "scope_checksum": scope["scope_checksum"],
            "datasets": [
                {
                    "dataset_id": item["dataset_id"], "version": item["version"],
                    "period_code": item.get("period_code"),
                }
                for item in datasets
            ],
            "counts": {
                period: {
                    key: len(value[key]) for key in ("ipc", "fusions", "papers")
                }
                for period, value in raw.items()
            },
            "records": {
                period: {
                    key: [
                        dict(sorted(item.items())) for item in value[key]
                    ]
                    for key in ("ipc", "fusions", "papers")
                }
                for period, value in raw.items()
            },
            "parameters": parameters,
        }
        checksum = hashlib.sha256(
            json.dumps(checksum_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        cached = self.get_by_checksum(
            technology_node_id, checksum, ALGORITHM_VERSION
        )
        if cached:
            return cached

        metrics = {
            period: self._period_metrics(period, data)
            for period, data in raw.items()
        }
        ordered = list(HISTORICAL_PERIODS)
        first, last = metrics[ordered[0]], metrics[ordered[-1]]
        ipc_direction = _direction(
            first["patent_annual_average"], last["patent_annual_average"]
        )
        paper_direction = _direction(
            first["paper_annual_average"], last["paper_annual_average"]
        )
        if "insufficient" in {ipc_direction, paper_direction}:
            relation = "insufficient"
        elif ipc_direction == paper_direction:
            relation = "convergent"
        elif "stable" in {ipc_direction, paper_direction}:
            relation = "complementary"
        else:
            relation = "conflicting"
        missing = [
            PERIOD_LABELS[period] for period, value in metrics.items()
            if not value["ipc_record_count"] and not value["paper_total"]
        ]
        limitations = [
            f"缺少 {label} 阶段数据" for label in missing
        ]
        exclusions = sorted({
            reason
            for dataset in scope["excluded_datasets"]
            for reason in dataset.get("exclusion_reasons", [])
        })
        limitations.extend(
            f"排除数据集：{reason}" for reason in exclusions
        )
        quality = {
            "complete": not missing, "missing_periods": missing,
            "limitations": limitations,
            "data_cutoff": 2026,
            "scope_checksum": scope["scope_checksum"],
            "excluded_dataset_reasons": exclusions,
        }
        analysis_id = (
            "stage_" + hashlib.sha256(
                f"{technology_node_id}:{checksum}".encode("utf-8")
            ).hexdigest()[:20]
        )
        item = {
            "analysis_id": analysis_id,
            "direction_key": technology["name"],
            "relation": relation,
            "stages": metrics,
            "metrics": {
                "ipc_direction": ipc_direction,
                "paper_direction": paper_direction,
                "keyword_evolution": self._keyword_evolution(metrics),
            },
            "evidence_ids": [
                f"dataset:{item['dataset_id']}" for item in datasets
            ] + [
                f"ipc:{item['metric_id']}"
                for value in raw.values() for item in value["ipc"]
            ] + [
                f"fusion:{item['fusion_id']}"
                for value in raw.values() for item in value["fusions"]
            ] + [
                f"paper:{item['paper_id']}"
                for value in raw.values() for item in value["papers"]
            ],
            "confidence": max(0.2, 1 - len(missing) / 3),
            "limitations": limitations,
        }
        run_id = _id("stage_run")
        with self.repository.db.transaction() as connection:
            connection.execute(
                """INSERT INTO stage_analysis_runs(
                    run_id,project_id,technology_node_id,input_checksum,
                    algorithm_version,parameters_json,quality_json,status
                ) VALUES (?,?,?,?,?,?,?,'completed')""",
                (
                    run_id, project_id or None, technology_node_id, checksum,
                    ALGORITHM_VERSION, json.dumps(parameters, ensure_ascii=False),
                    json.dumps(quality, ensure_ascii=False),
                ),
            )
            connection.execute(
                """INSERT INTO stage_analysis_items(
                    analysis_id,run_id,direction_key,relation,stages_json,
                    metrics_json,evidence_ids_json,confidence,limitations_json
                ) VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    analysis_id, run_id, item["direction_key"], relation,
                    json.dumps(metrics, ensure_ascii=False),
                    json.dumps(item["metrics"], ensure_ascii=False),
                    json.dumps(item["evidence_ids"], ensure_ascii=False),
                    item["confidence"],
                    json.dumps(limitations, ensure_ascii=False),
                ),
            )
        return self.get(run_id)

    def get_by_checksum(
        self, technology_node_id: str, checksum: str, algorithm_version: str
    ) -> Optional[Dict[str, Any]]:
        with self.repository.db.connect() as connection:
            row = connection.execute(
                """SELECT run_id FROM stage_analysis_runs
                   WHERE technology_node_id=? AND input_checksum=?
                   AND algorithm_version=?""",
                (technology_node_id, checksum, algorithm_version),
            ).fetchone()
        return self.get(row["run_id"]) if row else None

    def get(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self.repository.db.connect() as connection:
            row = connection.execute(
                """SELECT r.*,n.name technology_name
                   FROM stage_analysis_runs r JOIN technology_nodes n
                   ON n.node_id=r.technology_node_id WHERE r.run_id=?""",
                (run_id,),
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            result["parameters"] = json.loads(result.pop("parameters_json"))
            result["quality"] = json.loads(result.pop("quality_json"))
            result["items"] = []
            for item_row in connection.execute(
                "SELECT * FROM stage_analysis_items WHERE run_id=?",
                (run_id,),
            ).fetchall():
                item = dict(item_row)
                for key in (
                    "stages_json", "metrics_json", "evidence_ids_json",
                    "limitations_json",
                ):
                    item[key.removesuffix("_json")] = json.loads(item.pop(key))
                result["items"].append(item)
            return result

    def analyze_project(self, project_id: str) -> List[Dict[str, Any]]:
        project = self.repository.get_project(project_id)
        if not project or not project.get("technology_node_id"):
            raise ValueError("项目未绑定一级技术")
        leaves = self.technologies.descendants(
            project["technology_node_id"], level=3, active_only=True
        )
        return [
            self.analyze(leaf["node_id"], project_id)
            for leaf in leaves if self._datasets(leaf["node_id"], project_id)
        ]

    def latest_for_project(self, project_id: str) -> List[Dict[str, Any]]:
        with self.repository.db.connect() as connection:
            rows = connection.execute(
                """SELECT run_id FROM stage_analysis_runs
                   WHERE project_id=? ORDER BY created_at DESC""",
                (project_id,),
            ).fetchall()
        seen, results = set(), []
        for row in rows:
            result = self.get(row["run_id"])
            if result and result["technology_node_id"] not in seen:
                seen.add(result["technology_node_id"])
                results.append(result)
        return results
