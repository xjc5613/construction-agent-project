# -*- coding: utf-8 -*-
"""Deterministic interpretable fusion models, calibration and authority guards."""

import json
import math
import random
from dataclasses import asdict, dataclass
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4

from src.library import LibraryRepository
from src.research.repository import canonical_checksum


MODEL_VERSION = "fusion-model-v1"
AUTHORITATIVE_SOURCES = {"deterministic_model", "validated_model"}


def _id(prefix: str) -> str:
    return "%s_%s" % (prefix, uuid4().hex[:16])


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1 / (1 + z)
    z = math.exp(value)
    return z / (1 + z)


@dataclass(frozen=True)
class ModelParameters:
    model_kind: str = "logistic_regression"
    seed: int = 42
    learning_rate: float = 0.1
    iterations: int = 500
    l2: float = 0.01
    bootstrap_repeats: int = 50
    minimum_calibration_support: int = 10


class FusionModelService:
    def __init__(self, repository: Optional[LibraryRepository] = None):
        self.repository = repository or LibraryRepository()

    @staticmethod
    def mandatory_baselines(rows: List[Dict[str, Any]], seed: int = 42) -> Dict[str, List[float]]:
        prevalence = mean(float(row["label"]) for row in rows) if rows else 0.0
        rng = random.Random(seed)
        return {
            "random": [rng.random() for _ in rows],
            "prevalence": [prevalence for _ in rows],
            "common_neighbors": [float(row["features"].get("common_neighbors", 0)) for row in rows],
            "adamic_adar": [float(row["features"].get("adamic_adar", 0)) for row in rows],
        }

    def fit(self, rows: List[Dict[str, Any]], parameters: Optional[ModelParameters] = None) -> Dict[str, Any]:
        parameters = parameters or ModelParameters()
        if not rows or any("label" not in row for row in rows):
            raise ValueError("训练数据必须包含标签")
        feature_names = sorted({name for row in rows for name in row["features"]})
        matrix = [[float(row["features"].get(name) or 0) for name in feature_names] for row in rows]
        labels = [int(row["label"]) for row in rows]
        means = [mean(column) for column in zip(*matrix)] if feature_names else []
        scales = []
        for index in range(len(feature_names)):
            variance = mean((row[index] - means[index]) ** 2 for row in matrix)
            scales.append(math.sqrt(variance) or 1.0)
        transformed = [[(value - means[i]) / scales[i] for i, value in enumerate(row)] for row in matrix]
        if parameters.model_kind == "logistic_regression":
            artifact = self._fit_logistic(transformed, labels, parameters)
        elif parameters.model_kind == "decision_stump":
            artifact = self._fit_stump(transformed, labels, feature_names)
        else:
            raise ValueError("不支持的模型类型")
        artifact.update({"model_version": MODEL_VERSION, "feature_names": feature_names,
                         "means": means, "scales": scales, "parameters": asdict(parameters)})
        artifact["checksum"] = canonical_checksum(artifact)
        return artifact

    @staticmethod
    def _fit_logistic(matrix, labels, parameters):
        weights, intercept = [0.0] * (len(matrix[0]) if matrix else 0), 0.0
        count = len(labels)
        for _ in range(parameters.iterations):
            probabilities = [_sigmoid(intercept + sum(w * x for w, x in zip(weights, row))) for row in matrix]
            intercept -= parameters.learning_rate * mean(p - y for p, y in zip(probabilities, labels))
            for index in range(len(weights)):
                gradient = sum((p - y) * row[index] for p, y, row in zip(probabilities, labels, matrix)) / count
                gradient += parameters.l2 * weights[index]
                weights[index] -= parameters.learning_rate * gradient
        return {"model_kind": "logistic_regression", "weights": weights, "intercept": intercept}

    @staticmethod
    def _fit_stump(matrix, labels, names):
        best = None
        for index, name in enumerate(names):
            values = sorted(set(row[index] for row in matrix))
            thresholds = [(a + b) / 2 for a, b in zip(values, values[1:])] or values or [0]
            for threshold in thresholds:
                left = [label for row, label in zip(matrix, labels) if row[index] <= threshold]
                right = [label for row, label in zip(matrix, labels) if row[index] > threshold]
                left_p = mean(left) if left else mean(labels)
                right_p = mean(right) if right else mean(labels)
                loss = sum((label - (left_p if row[index] <= threshold else right_p)) ** 2
                           for row, label in zip(matrix, labels))
                candidate = (loss, name, index, threshold, left_p, right_p)
                if best is None or candidate < best:
                    best = candidate
        _, name, index, threshold, left_p, right_p = best
        return {"model_kind": "decision_stump", "feature": name, "feature_index": index,
                "threshold": threshold, "left_probability": left_p, "right_probability": right_p}

    def predict(self, artifact: Dict[str, Any], rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        for row in rows:
            transformed = [(float(row["features"].get(name) or 0) - artifact["means"][i]) / artifact["scales"][i]
                           for i, name in enumerate(artifact["feature_names"])]
            if artifact["model_kind"] == "logistic_regression":
                contributions = {name: artifact["weights"][i] * transformed[i]
                                 for i, name in enumerate(artifact["feature_names"])}
                raw = _sigmoid(artifact["intercept"] + sum(contributions.values()))
            else:
                value = transformed[artifact["feature_index"]]
                raw = artifact["left_probability"] if value <= artifact["threshold"] else artifact["right_probability"]
                contributions = {artifact["feature"]: raw - 0.5}
            results.append({**{key: row.get(key) for key in ("candidate_id", "ipc1", "ipc2")},
                            "raw_score": raw, "feature_contributions": contributions})
        return results

    def calibrate(self, scores: List[float], labels: List[int], minimum_support: int = 10) -> Dict[str, Any]:
        if len(scores) < minimum_support or len(set(labels)) < 2:
            return {"status": "not_estimable", "method": "none", "support_count": len(scores),
                    "reason": "校准样本不足或仅含单一类别", "a": 1.0, "b": 0.0}
        a, b = 1.0, 0.0
        for _ in range(500):
            probabilities = [_sigmoid(a * score + b) for score in scores]
            a -= 0.1 * mean((p - y) * score for p, y, score in zip(probabilities, labels, scores))
            b -= 0.1 * mean(p - y for p, y in zip(probabilities, labels))
        return {"status": "calibrated", "method": "platt", "support_count": len(scores), "a": a, "b": b}

    @staticmethod
    def apply_calibration(score: float, calibration: Dict[str, Any]) -> Optional[float]:
        return _sigmoid(calibration["a"] * score + calibration["b"]) if calibration["status"] == "calibrated" else None

    def prediction_intervals(self, rows, parameters=None):
        parameters = parameters or ModelParameters()
        rng, samples = random.Random(parameters.seed), [[] for _ in rows]
        for _ in range(parameters.bootstrap_repeats):
            training = [rows[rng.randrange(len(rows))] for _ in rows]
            if len({row["label"] for row in training}) < 2:
                continue
            artifact = self.fit(training, parameters)
            for index, prediction in enumerate(self.predict(artifact, rows)):
                samples[index].append(prediction["raw_score"])
        intervals = []
        for values in samples:
            ordered = sorted(values)
            if not ordered:
                intervals.append((None, None))
            else:
                intervals.append((ordered[int(0.025 * (len(ordered) - 1))],
                                  ordered[int(0.975 * (len(ordered) - 1))]))
        return intervals

    def select_time_ordered(self, training_rows, validation_rows, parameters=None):
        parameters = parameters or ModelParameters()
        candidates = []
        for kind in ("logistic_regression", "decision_stump"):
            configured = ModelParameters(**{**asdict(parameters), "model_kind": kind})
            artifact = self.fit(training_rows, configured)
            predictions = self.predict(artifact, validation_rows)
            loss = mean(-(row["label"] * math.log(max(pred["raw_score"], 1e-12)) +
                          (1 - row["label"]) * math.log(max(1 - pred["raw_score"], 1e-12)))
                        for row, pred in zip(validation_rows, predictions))
            candidates.append((loss, kind, artifact))
        loss, kind, artifact = min(candidates, key=lambda item: (item[0], item[1]))
        return {"selected_kind": kind, "selection_metric": "validation_log_loss",
                "validation_loss": loss, "artifact": artifact}

    def persist(self, feature_run_id: str, artifact: Dict[str, Any], rows: List[Dict[str, Any]],
                predictions: List[Dict[str, Any]], calibration: Dict[str, Any],
                intervals: List[Tuple[Optional[float], Optional[float]]], *,
                authority: str = "deterministic_model") -> str:
        if authority not in AUTHORITATIVE_SOURCES:
            raise ValueError("只有确定性验证模型可以写入权威概率")
        input_checksum = canonical_checksum({"feature_run_id": feature_run_id, "rows": rows,
                                             "artifact": artifact["checksum"]})
        with self.repository.db.transaction() as connection:
            existing = connection.execute(
                """SELECT model_run_id FROM model_runs WHERE input_checksum=?
                   AND model_kind=? AND model_version=?""",
                (input_checksum, artifact["model_kind"], artifact["model_version"]),
            ).fetchone()
            if existing:
                return existing[0]
            model_run_id = _id("model")
            connection.execute(
                """INSERT INTO model_runs(model_run_id,feature_run_id,model_kind,model_version,
                   parameters_json,random_seed,input_checksum,result_checksum,status,selected)
                   VALUES (?,?,?,?,?,?,?,?, 'completed',1)""",
                (model_run_id, feature_run_id, artifact["model_kind"], artifact["model_version"],
                 json.dumps(artifact["parameters"], sort_keys=True), artifact["parameters"]["seed"],
                 input_checksum, canonical_checksum(predictions)),
            )
            connection.execute(
                """INSERT INTO model_calibrations(calibration_id,model_run_id,method,support_count,
                   parameters_json,metrics_json,status) VALUES (?,?,?,?,?,? ,?)""",
                (_id("calibration"), model_run_id, calibration["method"], calibration["support_count"],
                 json.dumps({"a": calibration["a"], "b": calibration["b"]}), "{}", calibration["status"]),
            )
            ordered = sorted(zip(predictions, intervals), key=lambda item: (-item[0]["raw_score"], item[0].get("candidate_id") or ""))
            for rank, (prediction, interval) in enumerate(ordered, start=1):
                probability = self.apply_calibration(prediction["raw_score"], calibration)
                connection.execute(
                    """INSERT INTO fusion_predictions(prediction_id,model_run_id,candidate_id,rank,
                       raw_score,probability_status,calibrated_probability,interval_low,interval_high,
                       explanation_json,limitations_json,stability_status,evidence_grade,
                       probability_authority) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (_id("prediction"), model_run_id, prediction["candidate_id"], rank,
                     prediction["raw_score"], "calibrated" if probability is not None else "uncalibrated",
                     probability, interval[0], interval[1],
                     json.dumps(prediction["feature_contributions"], sort_keys=True),
                     json.dumps([] if probability is not None else [calibration.get("reason", "未校准")], ensure_ascii=False),
                     "not_evaluated", "model_derived", authority),
                )
        return model_run_id
