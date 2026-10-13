# -*- coding: utf-8 -*-
"""Rolling-origin validation, scientific gates and reproducibility manifests."""

import json
import math
import platform
import random
import sys
from uuid import uuid4
from dataclasses import dataclass
from statistics import mean
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from src.research.repository import canonical_checksum
from src.library import LibraryRepository


VALIDATION_VERSION = "rolling-origin-v1"
MANDATORY_BASELINES = ("random", "prevalence", "common_neighbors", "adamic_adar")
PUBLICATION_GATES = (
    "evidence", "validation", "calibration", "stability",
    "schema", "citation", "asset", "human_review",
)


@dataclass(frozen=True)
class ValidationFold:
    name: str
    train_cutoff: int
    outcome_start: int
    outcome_end: int
    kind: str = "broad_transition"


def rolling_origin_folds(years: Iterable[int], include_annual: bool = True) -> List[ValidationFold]:
    observed = sorted(set(int(year) for year in years))
    folds = [
        ValidationFold("2010_2014-to-2015_2019", 2014, 2015, 2019),
        ValidationFold("pre2020-to-2020_2025", 2019, 2020, 2025),
    ]
    if include_annual:
        folds.extend(
            ValidationFold("annual-%d" % year, year - 1, year, year, "annual")
            for year in observed if year > min(observed or [year]) and year <= 2025
        )
    return folds


def ranking_metrics(labels: List[int], scores: List[float], k: int = 10) -> Dict[str, Any]:
    if len(labels) != len(scores) or not labels:
        return {name: {"status": "not_estimable", "value": None, "reason": "无评估样本"}
                for name in ("precision_at_k", "recall_at_k", "hit_rate_at_k", "map", "ndcg",
                             "pr_auc", "brier", "ece")}
    order = sorted(range(len(scores)), key=lambda index: (-scores[index], index))
    top = order[:min(k, len(order))]
    positives = sum(labels)
    hits = sum(labels[index] for index in top)
    precision = hits / len(top) if top else 0.0
    recall = hits / positives if positives else None
    hit_rate = float(hits > 0)
    running, average_precision = 0, 0.0
    dcg = 0.0
    for rank, index in enumerate(order, start=1):
        if labels[index]:
            running += 1
            average_precision += running / rank
            dcg += 1 / math.log2(rank + 1)
    average_precision = average_precision / positives if positives else None
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, positives + 1))
    ndcg = dcg / ideal if ideal else None
    pr_auc = _average_precision(labels, scores) if 0 < positives < len(labels) else None
    brier = mean((score - label) ** 2 for score, label in zip(scores, labels))
    ece = _ece(labels, scores)
    values = {"precision_at_k": precision, "recall_at_k": recall,
              "hit_rate_at_k": hit_rate, "map": average_precision, "ndcg": ndcg,
              "pr_auc": pr_auc, "brier": brier, "ece": ece}
    return {name: {"status": "estimated" if value is not None else "not_estimable",
                   "value": value, "reason": "" if value is not None else "类别支持不足"}
            for name, value in values.items()}


def _average_precision(labels, scores):
    order = sorted(range(len(scores)), key=lambda index: (-scores[index], index))
    positives, hits, total = sum(labels), 0, 0.0
    for rank, index in enumerate(order, start=1):
        if labels[index]:
            hits += 1
            total += hits / rank
    return total / positives


def _ece(labels, scores, bins=10):
    total = len(labels)
    value = 0.0
    for index in range(bins):
        low, high = index / bins, (index + 1) / bins
        members = [i for i, score in enumerate(scores)
                   if low <= score < high or (index == bins - 1 and score == 1)]
        if members:
            value += len(members) / total * abs(
                mean(scores[i] for i in members) - mean(labels[i] for i in members)
            )
    return value


class HistoricalValidationService:
    def __init__(self, repository: Optional[LibraryRepository] = None):
        self.repository = repository

    def evaluate_fold(self, fold: ValidationFold, rows: List[Dict[str, Any]],
                      scorer: Callable[[List[Dict[str, Any]], List[Dict[str, Any]]], List[float]],
                      k: int = 10) -> Dict[str, Any]:
        training = [row for row in rows if int(row["year"]) <= fold.train_cutoff]
        outcome = [row for row in rows if fold.outcome_start <= int(row["year"]) <= fold.outcome_end]
        if not training or not outcome:
            return {"fold": fold.__dict__, "status": "not_estimable",
                    "reason": "训练或结果窗口样本不足", "metrics": ranking_metrics([], [], k)}
        scores = scorer(training, outcome)
        return {"fold": fold.__dict__, "status": "completed", "train_count": len(training),
                "outcome_count": len(outcome),
                "metrics": ranking_metrics([int(row["label"]) for row in outcome], scores, k)}

    def validate(self, rows, scorer, k=10, bootstrap_repeats=200, seed=42):
        folds = rolling_origin_folds([row["year"] for row in rows])
        results = [self.evaluate_fold(fold, rows, scorer, k) for fold in folds]
        estimated = [item for item in results if item["status"] == "completed"]
        aggregate = {}
        for name in ("precision_at_k", "recall_at_k", "hit_rate_at_k", "map", "ndcg",
                     "pr_auc", "brier", "ece"):
            values = [item["metrics"][name]["value"] for item in estimated
                      if item["metrics"][name]["value"] is not None]
            aggregate[name] = self._bootstrap_mean(values, bootstrap_repeats, seed)
        return {"version": VALIDATION_VERSION, "folds": results, "aggregate": aggregate}

    @staticmethod
    def _bootstrap_mean(values, repeats, seed):
        if len(values) < 2:
            return {"status": "not_estimable", "value": mean(values) if values else None,
                    "interval_low": None, "interval_high": None,
                    "reason": "有效折数不足，无法估计区间"}
        rng, samples = random.Random(seed), []
        for _ in range(repeats):
            samples.append(mean(values[rng.randrange(len(values))] for _ in values))
        samples.sort()
        return {"status": "estimated", "value": mean(values),
                "interval_low": samples[int(0.025 * (len(samples) - 1))],
                "interval_high": samples[int(0.975 * (len(samples) - 1))], "reason": ""}

    def compare_baselines(self, labels, selected_scores, baseline_scores):
        missing = [name for name in MANDATORY_BASELINES if name not in baseline_scores]
        if missing:
            raise ValueError("缺少必选基线: " + ", ".join(missing))
        results = {"selected": ranking_metrics(labels, selected_scores)}
        results.update({name: ranking_metrics(labels, baseline_scores[name])
                        for name in MANDATORY_BASELINES})
        return {"criterion": "ndcg_then_brier", "results": results}

    def ablations(self, rows, feature_families, scorer):
        results = []
        for family, names in feature_families.items():
            ablated = [{**row, "features": {name: value for name, value in row["features"].items()
                                             if name not in set(names)}} for row in rows]
            scores = scorer(ablated)
            results.append({"omitted_feature_family": family,
                            "metrics": ranking_metrics([row["label"] for row in rows], scores)})
        return results

    @staticmethod
    def sensitivity(base_predictions, variants, rank_limit=5, probability_limit=0.15):
        base = {item["candidate_id"]: item for item in base_predictions}
        results, unstable = [], set()
        for name, predictions in variants.items():
            changes = []
            for item in predictions:
                original = base.get(item["candidate_id"])
                if not original:
                    unstable.add(item["candidate_id"])
                    changes.append({"candidate_id": item["candidate_id"], "selection_changed": True})
                    continue
                rank_change = abs(int(item["rank"]) - int(original["rank"]))
                probability_change = abs(float(item.get("probability") or 0) -
                                         float(original.get("probability") or 0))
                is_unstable = rank_change > rank_limit or probability_change > probability_limit
                if is_unstable:
                    unstable.add(item["candidate_id"])
                changes.append({"candidate_id": item["candidate_id"], "rank_change": rank_change,
                                "probability_change": probability_change, "unstable": is_unstable})
            results.append({"sensitivity_kind": name, "candidate_changes": changes})
        return {"runs": results, "unstable_candidate_ids": sorted(unstable)}

    def persist(self, model_run_id: str, validation: Dict[str, Any],
                ablations: Iterable[Dict[str, Any]] = (),
                sensitivities: Iterable[Dict[str, Any]] = ()) -> None:
        if not self.repository:
            raise ValueError("持久化验证结果需要数据库仓储")
        with self.repository.db.transaction() as connection:
            for item in validation["folds"]:
                fold = item["fold"]
                fold_id = "fold_" + uuid4().hex[:16]
                connection.execute(
                    """INSERT OR IGNORE INTO validation_folds(fold_id,model_run_id,fold_name,
                       train_cutoff,outcome_start,outcome_end,input_checksum,support_json,status)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (fold_id, model_run_id, fold["name"], fold["train_cutoff"], fold["outcome_start"],
                     fold["outcome_end"], canonical_checksum(fold),
                     json.dumps({"train": item.get("train_count", 0), "outcome": item.get("outcome_count", 0)}),
                     item["status"]),
                )
                stored = connection.execute(
                    "SELECT fold_id FROM validation_folds WHERE model_run_id=? AND fold_name=?",
                    (model_run_id, fold["name"]),
                ).fetchone()[0]
                for name, metric in item["metrics"].items():
                    connection.execute(
                        """INSERT OR IGNORE INTO validation_metrics(metric_id,model_run_id,fold_id,
                           metric_name,metric_value,status,reason,metadata_json) VALUES (?,?,?,?,?,?,?,?)""",
                        ("metric_" + uuid4().hex[:16], model_run_id, stored, name, metric["value"],
                         metric["status"], metric["reason"], "{}"),
                    )
            for item in ablations:
                connection.execute(
                    """INSERT OR IGNORE INTO ablation_runs(ablation_id,model_run_id,
                       omitted_feature_family,metrics_json,rank_changes_json,status)
                       VALUES (?,?,?,?,?,'completed')""",
                    ("ablation_" + uuid4().hex[:16], model_run_id, item["omitted_feature_family"],
                     json.dumps(item.get("metrics", {}), sort_keys=True),
                     json.dumps(item.get("rank_changes", {}), sort_keys=True)),
                )
            for item in sensitivities:
                connection.execute(
                    """INSERT INTO sensitivity_runs(sensitivity_id,model_run_id,sensitivity_kind,
                       parameters_json,metrics_json,candidate_changes_json,status)
                       VALUES (?,?,?,?,?,?,'completed')""",
                    ("sensitivity_" + uuid4().hex[:16], model_run_id, item["sensitivity_kind"],
                     json.dumps(item.get("parameters", {}), sort_keys=True),
                     json.dumps(item.get("metrics", {}), sort_keys=True),
                     json.dumps(item.get("candidate_changes", []), sort_keys=True)),
                )


class PublicationGateService:
    def __init__(self, repository: Optional[LibraryRepository] = None):
        self.repository = repository

    def evaluate(self, criteria: Dict[str, bool], details: Optional[Dict[str, Any]] = None):
        details = details or {}
        gates = [{"gate_name": name, "status": "passed" if criteria.get(name, False) else "failed",
                  "details": details.get(name, {}), "overridden": False, "override_reason": ""}
                 for name in PUBLICATION_GATES]
        return {"gates": gates, "publishable": all(item["status"] == "passed" for item in gates)}

    @staticmethod
    def override(result, gate_name, reason, reviewer="local-user"):
        if not reason.strip():
            raise ValueError("专家覆盖必须填写理由")
        updated = json.loads(json.dumps(result))
        gate = next((item for item in updated["gates"] if item["gate_name"] == gate_name), None)
        if not gate:
            raise ValueError("发布门不存在")
        gate.update({"overridden": True, "override_reason": reason, "reviewer": reviewer})
        updated["publishable"] = all(
            item["status"] == "passed" or item["overridden"] for item in updated["gates"]
        )
        updated["limitations"] = [
            "%s 发布门失败，由 %s 覆盖：%s" % (item["gate_name"], item.get("reviewer"), item["override_reason"])
            for item in updated["gates"] if item["status"] == "failed" and item["overridden"]
        ]
        return updated

    def persist(self, project_id: str, result: Dict[str, Any], *,
                job_id: Optional[str] = None, model_run_id: Optional[str] = None) -> None:
        if not self.repository:
            raise ValueError("持久化发布门需要数据库仓储")
        with self.repository.db.transaction() as connection:
            for gate in result["gates"]:
                connection.execute(
                    """INSERT INTO publication_gates(gate_id,project_id,job_id,model_run_id,
                       gate_name,status,details_json,overridden,override_reason)
                       VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(project_id,job_id,gate_name)
                       DO UPDATE SET status=excluded.status,details_json=excluded.details_json,
                       overridden=excluded.overridden,override_reason=excluded.override_reason,
                       evaluated_at=CURRENT_TIMESTAMP""",
                    ("gate_" + uuid4().hex[:16], project_id, job_id, model_run_id,
                     gate["gate_name"], gate["status"], json.dumps(gate.get("details", {}), sort_keys=True),
                     int(gate.get("overridden", False)), gate.get("override_reason", "")),
                )


def build_run_manifest(payload: Dict[str, Any]) -> Dict[str, Any]:
    manifest = {
        "manifest_version": "research-run-manifest-v1",
        "environment": {"python": sys.version.split()[0], "platform": platform.platform()},
        "dependencies": payload.get("dependencies", {}), "seed": payload.get("seed"),
        "sources": payload.get("sources", []), "algorithms": payload.get("algorithms", {}),
        "models": payload.get("models", {}), "prompts": payload.get("prompts", {}),
        "reviews": payload.get("reviews", []), "outputs": payload.get("outputs", {}),
    }
    manifest["checksum"] = canonical_checksum(manifest)
    return manifest


def diff_manifests(expected: Dict[str, Any], actual: Dict[str, Any]) -> List[Dict[str, Any]]:
    differences = []
    def visit(left, right, path=""):
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(set(left) | set(right)):
                if key == "checksum":
                    continue
                visit(left.get(key), right.get(key), "%s.%s" % (path, key) if path else key)
        elif left != right:
            differences.append({"field": path, "expected": left, "actual": right})
    visit(expected, actual)
    return differences
