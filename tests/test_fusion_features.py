# -*- coding: utf-8 -*-
from copy import deepcopy

from src.library import LibraryDatabase, LibraryRepository
from src.research.features import CandidatePolicy, FusionFeaturePipeline
from src.research.network import DynamicIPCNetworkService
from src.research.repository import ResearchRepository


def _network():
    service = DynamicIPCNetworkService.__new__(DynamicIPCNetworkService)
    return service.build([
        {"patent_id": "p1", "year": 2020, "ipc_codes": ["A", "B"]},
        {"patent_id": "p2", "year": 2021, "ipc_codes": ["A", "B"]},
        {"patent_id": "p3", "year": 2021, "ipc_codes": ["B", "C"]},
        {"patent_id": "future", "year": 2025, "ipc_codes": ["A", "C"]},
    ])


def test_emergence_and_strengthening_universes_are_separate():
    pipeline = FusionFeaturePipeline.__new__(FusionFeaturePipeline)
    network = _network()
    emergence = pipeline.build(network, cutoff_year=2021)
    strengthening = pipeline.build(
        network, cutoff_year=2021,
        policy=CandidatePolicy(target_type="strengthening"),
    )
    assert {(item["ipc1"], item["ipc2"]) for item in emergence["candidates"]} == {("A", "C")}
    assert {(item["ipc1"], item["ipc2"]) for item in strengthening["candidates"]} == {
        ("A", "B"), ("B", "C")
    }
    candidate = emergence["candidates"][0]
    assert candidate["features"]["common_neighbors"] == 1
    assert candidate["features"]["adamic_adar"] > 0


def test_future_only_records_cannot_change_historical_features():
    pipeline = FusionFeaturePipeline.__new__(FusionFeaturePipeline)
    network = _network()
    baseline = pipeline.build(
        network, cutoff_year=2021,
        patent_text_signals=[{"ipc1": "A", "ipc2": "C", "score": 0.2, "observed_year": 2021}],
        paper_signals=[{"ipc1": "A", "ipc2": "C", "score": 0.3, "observed_year": 2021}],
    )
    injected = deepcopy(network)
    injected["annual"]["2030"] = injected["annual"]["2025"]
    comparison = pipeline.build(
        injected, cutoff_year=2021,
        patent_text_signals=[
            {"ipc1": "A", "ipc2": "C", "score": 0.2, "observed_year": 2021},
            {"ipc1": "A", "ipc2": "C", "score": 1.0, "observed_year": 2030},
        ],
        paper_signals=[
            {"ipc1": "A", "ipc2": "C", "score": 0.3, "observed_year": 2021},
            {"ipc1": "A", "ipc2": "C", "score": 0.9, "observed_year": 2030},
        ],
        mappings=[{"ipc_code_raw": "A", "ipc_code_normalized": "A", "observed_year": 2030}],
    )
    assert baseline["candidates"][0]["features"] == comparison["candidates"][0]["features"]


def test_candidate_policy_and_persistence_are_deterministic(tmp_path):
    repository = LibraryRepository(LibraryDatabase(tmp_path / "features.sqlite3"))
    research = ResearchRepository(repository.db)
    network_run = research.create_network_run({
        "snapshot_checksum": "snapshot", "algorithm_version": "network-v1",
        "input_checksum": "network-input",
    })
    pipeline = FusionFeaturePipeline(repository)
    result = pipeline.build(
        _network(), cutoff_year=2021,
        policy=CandidatePolicy(minimum_support=2, forecast_horizon=10,
                               negative_sampling="all_eligible"),
        taxonomy={"A": "design", "B": "robot", "C": "data"},
    )
    first = pipeline.persist(network_run["network_run_id"], result)
    second = pipeline.persist(network_run["network_run_id"], result)
    assert first == second
    with repository.db.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM fusion_candidates").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM fusion_features").fetchone()[0] > 5
