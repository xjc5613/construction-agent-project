# -*- coding: utf-8 -*-
import pytest

from src.research.validation import (
    HistoricalValidationService, PublicationGateService, build_run_manifest,
    diff_manifests, ranking_metrics, rolling_origin_folds,
)


def _rows():
    return [
        {"year": year, "label": int(year % 3 == 0), "score": (year % 5) / 5,
         "features": {"topology": year % 4, "paper": year % 2}}
        for year in range(2010, 2026)
    ]


def test_rolling_origin_folds_and_metrics_cover_rank_and_calibration():
    folds = rolling_origin_folds(range(2010, 2026))
    assert folds[0].train_cutoff == 2014
    assert folds[1].outcome_end == 2025
    service = HistoricalValidationService()
    result = service.validate(
        _rows(), lambda _training, outcome: [row["score"] for row in outcome],
        k=3, bootstrap_repeats=20,
    )
    assert len(result["folds"]) > 2
    names = result["folds"][0]["metrics"]
    assert {"precision_at_k", "recall_at_k", "hit_rate_at_k", "map", "ndcg",
            "pr_auc", "brier", "ece"} <= set(names)


def test_not_estimable_class_imbalance_and_mandatory_baseline_failure():
    metrics = ranking_metrics([0, 0, 0], [0.1, 0.2, 0.3])
    assert metrics["pr_auc"]["status"] == "not_estimable"
    service = HistoricalValidationService()
    with pytest.raises(ValueError, match="缺少必选基线"):
        service.compare_baselines([0, 1], [0.2, 0.8], {"random": [0.1, 0.2]})
    scores = {
        "random": [0.1, 0.9], "prevalence": [0.5, 0.5],
        "common_neighbors": [0, 1], "adamic_adar": [0.2, 0.7],
    }
    assert service.compare_baselines([0, 1], [0.1, 0.8], scores)["criterion"] == "ndcg_then_brier"


def test_ablations_sensitivity_and_unstable_candidates():
    service = HistoricalValidationService()
    rows = _rows()[:8]
    ablations = service.ablations(
        rows, {"topology": ["topology"], "paper_signal": ["paper"]},
        lambda values: [sum(row["features"].values()) / 10 for row in values],
    )
    assert {item["omitted_feature_family"] for item in ablations} == {"topology", "paper_signal"}
    base = [{"candidate_id": "a", "rank": 1, "probability": 0.8}]
    sensitivity = service.sensitivity(base, {
        "partial_2025_excluded": [{"candidate_id": "a", "rank": 8, "probability": 0.5}],
        "ipc_subclass": [{"candidate_id": "new", "rank": 1, "probability": 0.7}],
    })
    assert sensitivity["unstable_candidate_ids"] == ["a", "new"]


def test_publication_gates_override_preserves_failure_and_limitations():
    service = PublicationGateService()
    result = service.evaluate({name: True for name in (
        "evidence", "validation", "calibration", "schema", "citation", "asset", "human_review"
    )})
    stability = next(item for item in result["gates"] if item["gate_name"] == "stability")
    assert stability["status"] == "failed"
    with pytest.raises(ValueError):
        service.override(result, "stability", "")
    overridden = service.override(result, "stability", "敏感性样本不足，但保留限制")
    gate = next(item for item in overridden["gates"] if item["gate_name"] == "stability")
    assert gate["status"] == "failed"
    assert gate["overridden"] is True
    assert overridden["limitations"]


def test_manifest_is_reproducible_and_reports_field_differences():
    payload = {
        "seed": 42, "sources": [{"id": "dataset", "checksum": "abc"}],
        "algorithms": {"network": "v1"}, "models": {"fusion": "v1"},
        "prompts": {"forecast": "p1"}, "reviews": [{"decision": "approve"}],
        "outputs": {"report": "sha256"}, "dependencies": {"python": "stdlib"},
    }
    first, second = build_run_manifest(payload), build_run_manifest(payload)
    assert first["checksum"] == second["checksum"]
    changed = build_run_manifest({**payload, "seed": 7})
    assert diff_manifests(first, changed) == [{"field": "seed", "expected": 42, "actual": 7}]
