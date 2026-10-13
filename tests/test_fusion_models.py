# -*- coding: utf-8 -*-
import math

import pytest

from src.library import LibraryDatabase, LibraryRepository
from src.research.features import FusionFeaturePipeline
from src.research.models import FusionModelService, ModelParameters
from src.research.network import DynamicIPCNetworkService
from src.research.repository import ResearchRepository


def _rows(count=20):
    return [
        {
            "candidate_id": "candidate-%d" % index,
            "ipc1": "A%d" % index, "ipc2": "B%d" % index,
            "features": {
                "common_neighbors": float(index % 5),
                "adamic_adar": float(index) / count,
                "temporal": float((index * 3) % 7),
            },
            "label": int(index % 4 in {2, 3}),
        }
        for index in range(count)
    ]


def test_baselines_logistic_and_tree_are_deterministic_and_explainable():
    rows = _rows()
    service = FusionModelService.__new__(FusionModelService)
    baselines = service.mandatory_baselines(rows, seed=7)
    assert set(baselines) == {"random", "prevalence", "common_neighbors", "adamic_adar"}
    parameters = ModelParameters(iterations=100, bootstrap_repeats=5)
    first = service.fit(rows, parameters)
    second = service.fit(rows, parameters)
    assert first["checksum"] == second["checksum"]
    predictions = service.predict(first, rows)
    assert all(0 <= item["raw_score"] <= 1 for item in predictions)
    assert predictions[0]["feature_contributions"]
    tree = service.fit(rows, ModelParameters(model_kind="decision_stump"))
    assert tree["model_kind"] == "decision_stump"


def test_time_ordered_selection_calibration_and_intervals():
    rows = _rows(30)
    service = FusionModelService.__new__(FusionModelService)
    selected = service.select_time_ordered(rows[:20], rows[20:], ModelParameters(iterations=50))
    assert selected["selection_metric"] == "validation_log_loss"
    predictions = service.predict(selected["artifact"], rows[20:])
    calibration = service.calibrate(
        [item["raw_score"] for item in predictions], [item["label"] for item in rows[20:]], 10
    )
    assert calibration["status"] == "calibrated"
    assert 0 <= service.apply_calibration(0.5, calibration) <= 1
    fallback = service.calibrate([0.1, 0.2], [0, 0], 10)
    assert fallback["status"] == "not_estimable"
    intervals = service.prediction_intervals(
        rows[:12], ModelParameters(iterations=20, bootstrap_repeats=5)
    )
    assert len(intervals) == 12
    assert all(low is None or 0 <= low <= high <= 1 for low, high in intervals)


def test_authoritative_probability_guard_and_persistence(tmp_path):
    repository = LibraryRepository(LibraryDatabase(tmp_path / "models.sqlite3"))
    research = ResearchRepository(repository.db)
    network_run = research.create_network_run({
        "snapshot_checksum": "s", "algorithm_version": "n", "input_checksum": "ni"
    })
    network = DynamicIPCNetworkService.__new__(DynamicIPCNetworkService).build([
        {"patent_id": "p1", "year": 2020, "ipc_codes": ["A", "B"]},
        {"patent_id": "p2", "year": 2020, "ipc_codes": ["B", "C"]},
    ])
    pipeline = FusionFeaturePipeline(repository)
    feature_result = pipeline.build(network, cutoff_year=2020)
    feature_run_id = pipeline.persist(network_run["network_run_id"], feature_result)
    with repository.db.connect() as connection:
        candidate = connection.execute(
            "SELECT candidate_id FROM fusion_candidates WHERE feature_run_id=?", (feature_run_id,)
        ).fetchone()[0]
    training = _rows()
    service = FusionModelService(repository)
    artifact = service.fit(training, ModelParameters(iterations=50, bootstrap_repeats=3))
    target = {**training[0], "candidate_id": candidate}
    prediction = service.predict(artifact, [target])
    intervals = [(0.1, 0.9)]
    calibration = service.calibrate(
        [index / 20 for index in range(20)], [index % 2 for index in range(20)], 10
    )
    with pytest.raises(ValueError, match="确定性验证模型"):
        service.persist(feature_run_id, artifact, [target], prediction, calibration,
                        intervals, authority="llm")
    model_run_id = service.persist(
        feature_run_id, artifact, [target], prediction, calibration, intervals
    )
    assert service.persist(
        feature_run_id, artifact, [target], prediction, calibration, intervals
    ) == model_run_id
    with repository.db.connect() as connection:
        row = connection.execute(
            "SELECT rank,probability_status,calibrated_probability FROM fusion_predictions"
        ).fetchone()
    assert row[0] == 1
    assert row[1] == "calibrated"
    assert 0 <= row[2] <= 1
    with pytest.raises(Exception):
        with repository.db.transaction() as connection:
            connection.execute(
                "UPDATE fusion_predictions SET probability_authority='llm'"
            )
