# -*- coding: utf-8 -*-
"""Clean empirical-style vertical fixture for the complete v3 research path.

The fixture uses only records committed through the public ingestion service.  Agent
responses are provider-free but still pass through the production typed validators;
this keeps the test deterministic while exercising the LangGraph review boundaries.
"""

import json
from pathlib import Path

from src.ingestion.research import ResearchImportService
from src.library import LibraryDatabase, LibraryRepository
from src.research.design import ResearchDesignService
from src.research.features import CandidatePolicy, FusionFeaturePipeline
from src.research.graph import (
    BoundedAgentNodes,
    EvidenceConstrainedForecastGraph,
    GraphRuntimeContext,
)
from src.research.models import FusionModelService, ModelParameters
from src.research.network import DynamicIPCNetworkService, NetworkParameters
from src.research.publication import ResearchBundleService
from src.research.repository import canonical_checksum
from src.research.visualization import ChartSeries, ScientificChartData


IPCS = ["B25J9/00", "E04B1/00", "G06F30/00", "G01C15/00", "E04G21/00", "H04W4/00"]


def _load_feature_rows(repository, feature_run_id):
    with repository.db.connect() as connection:
        candidates = connection.execute(
            """SELECT candidate_id,ipc1,ipc2,label FROM fusion_candidates
               WHERE feature_run_id=? ORDER BY ipc1,ipc2""",
            (feature_run_id,),
        ).fetchall()
        return [
            {
                "candidate_id": row["candidate_id"],
                "ipc1": row["ipc1"],
                "ipc2": row["ipc2"],
                "label": int(row["label"]),
                "features": {
                    feature["feature_name"]: feature["feature_value"]
                    for feature in connection.execute(
                        """SELECT feature_name,feature_value FROM fusion_features
                           WHERE candidate_id=? ORDER BY feature_name""",
                        (row["candidate_id"],),
                    ).fetchall()
                },
            }
            for row in candidates
        ]


def _validated_role_provider(evidence_ids, candidate_id, ipc_pair):
    """Return schema-valid bounded semantic results without external model I/O."""
    patent_id, paper_id = evidence_ids

    def milestone(year, name, trl):
        return {
            "year": year,
            "name": name,
            "description": "基于冻结证据的条件性里程碑，仍存在不确定限制。",
            "trl": trl,
            "dependencies": [] if year == 2030 else ["前一阶段验证"],
            "indicators": ["完成可复核工程验证"],
            "evidence_ids": [patent_id, paper_id],
            "uncertainty": "medium",
        }

    def invoke(role, request):
        if role == "evidence_analyst":
            task = request["task"]
            return {
                "analysis_kind": task["kind"],
                "claims": [{
                    "claim": "该记录提供 IPC 融合的可追溯证据，但不表示因果关系。",
                    "evidence_ids": [task["evidence_id"]],
                    "confidence": "medium",
                    "limitation": "小样本证据限制外推。",
                }],
                "conflicts": [],
                "limitations": ["仅在冻结证据范围内解释。"],
            }
        if role == "technology_concept_synthesizer":
            return {
                "concept_name": "感知驱动的自适应建造机器人",
                "ipc_pairs": [ipc_pair],
                "mechanism": "机器人、建筑构造和数字感知可能融合，证据仍有样本限制。",
                "evidence_ids": [patent_id, paper_id],
                "model_candidate_ids": [candidate_id],
            }
        if role == "scientific_critic":
            return {
                "severity": "info",
                "category": "uncertainty",
                "message": "已明确证据范围与不确定限制。",
                "target_id": candidate_id,
                "remediation": "出版时保留限制说明。",
            }
        theme_id = request["task"]["theme_id"]
        milestones = [milestone(2030, "原型验证", 4), milestone(2035, "工程示范", 6),
                      milestone(2040, "规模应用评估", 8)]
        if role == "topic_forecaster":
            return {
                "theme_id": theme_id,
                "theme_name": "感知驱动的自适应建造机器人",
                "summary": "该主题在既定情景下可能逐步发展，结论受证据规模限制。",
                "ipc_pairs": [ipc_pair],
                "milestones": milestones,
                "limitations": ["预测不是确定事实。"],
            }
        if role == "scenario_roadmap":
            return {
                "theme_id": theme_id,
                "scenarios": [
                    {"name": name, "assumptions": ["证据与资源条件存在不确定限制。"],
                     "milestones": milestones}
                    for name in ("baseline", "accelerated", "constrained")
                ],
            }
        raise AssertionError("unexpected semantic role: %s" % role)

    return invoke


def test_clean_empirical_import_to_publication_review_is_source_traceable(tmp_path):
    repository = LibraryRepository(LibraryDatabase(tmp_path / "empirical-e2e.sqlite3"))
    project = repository.create_project(
        name="clean empirical fixture", technology_node_id="tech_smart_construction", target_year=2040
    )
    dataset = repository.create_dataset(
        "Chapter 4 empirical trace fixture", "curated patent incidence and paper metadata", "v3.0",
        technology_node_id="tech_robot", period_code="2020_2025", public_kind="ipc",
    )
    ingestion = ResearchImportService(repository)

    # All six IPC nodes exist at the 2020 cutoff; five later records provide observed
    # first-emergence outcomes, leaving both positive and negative candidate labels.
    patents = [
        ("CN-E2E-01", 2020, "B25J9/16;E04B1/76"),
        ("CN-E2E-02", 2020, "E04B1/76;G06F30/13"),
        ("CN-E2E-03", 2020, "G06F30/13;G01C15/00"),
        ("CN-E2E-04", 2020, "G01C15/00;E04G21/00"),
        ("CN-E2E-05", 2020, "E04G21/00;H04W4/02"),
        ("CN-E2E-06", 2021, "B25J9/16;G06F30/13"),
        ("CN-E2E-07", 2022, "E04B1/76;G01C15/00"),
        ("CN-E2E-08", 2023, "G06F30/13;E04G21/00"),
        ("CN-E2E-09", 2024, "G01C15/00;H04W4/02"),
    ]
    complete_preview = ingestion.preview("patents", [
        {"publication_number": number, "application_year": year, "ipc_codes": codes,
         "title": "可追溯智能建造专利 %s" % number, "abstract": "机器人与建造信息融合证据。",
         "_source_row": index}
        for index, (number, year, codes) in enumerate(patents, start=2)
    ], dataset_id=dataset["dataset_id"], completeness="complete", ipc_edition="2025.01")
    assert not complete_preview["errors"]
    assert ingestion.commit(complete_preview)["committed"] == len(patents)
    partial_preview = ingestion.preview("patents", [{
        "publication_number": "CN-E2E-10", "application_year": 2025,
        "ipc_codes": "B25J9/16;H04W4/02", "title": "部分年度现场通信机器人专利",
        "abstract": "截至 2025-10-01 的机器人通信融合证据。", "_source_row": 11,
    }], dataset_id=dataset["dataset_id"], completeness="partial",
       observation_cutoff="2025-10-01", ipc_edition="2025.01")
    assert ingestion.commit(partial_preview)["committed"] == 1
    paper_preview = ingestion.preview("papers", [{
        "title": "Evidence-informed robotics for intelligent construction", "year": 2020,
        "paper_type": "journal_article", "authors": "Fixture Research Group",
        "doi": "10.0000/e2e.fixture", "source_database": "curated-fixture-index",
        "abstract": "Construction robotics and digital sensing evidence with explicit limitations.",
        "_source_row": 12,
    }], dataset_id=dataset["dataset_id"], completeness="complete")
    assert ingestion.commit(paper_preview)["committed"] == 1
    with repository.db.transaction() as connection:
        connection.execute("UPDATE datasets SET status='published' WHERE dataset_id=?",
                           (dataset["dataset_id"],))

    designs = ResearchDesignService(repository)
    design = designs.create_version(project["project_id"], {
        "research_question": "2010—2025 年证据支持哪些 IPC 融合可能形成 2040 智能建造技术？",
        "paper_types": ["journal_article"], "ipc_analysis_level": "main_group",
        "candidate_target": "emergence", "data_cutoff": "2025-10-01",
    })
    designs.confirm(project["project_id"], design["design_id"])
    snapshot = designs.freeze_snapshot(project["project_id"], [dataset["dataset_id"]])
    assert len(snapshot["record_ids"]["patents"]) == 10
    assert len(snapshot["record_ids"]["papers"]) == 1
    assert any(row["year"] == 2025 and row["completeness"] == "partial"
               for row in snapshot["coverage"])

    network_service = DynamicIPCNetworkService(repository)
    network_output = network_service.build_and_persist(
        project["project_id"], snapshot, NetworkParameters(random_seed=42)
    )
    network_run_id = network_output["run"]["network_run_id"]
    observed_edge = network_service.edge_evidence(network_run_id, "B25J9/00", "E04B1/00")
    assert observed_edge["items"] and observed_edge["items"][0]["supporting_patent_ids"]

    future_edges = {
        tuple(sorted((edge["ipc1"], edge["ipc2"])))
        for year, observation in network_output["result"]["annual"].items() if int(year) > 2020
        for edge in observation["edges"]
    }
    feature_pipeline = FusionFeaturePipeline(repository)
    feature_result = feature_pipeline.build(
        network_output["result"], cutoff_year=2020,
        policy=CandidatePolicy(target_type="emergence", forecast_horizon=5),
        patent_text_signals=[{"ipc1": "B25J9/00", "ipc2": "G06F30/00", "score": 0.7,
                              "observed_year": 2020, "evidence_id": snapshot["record_ids"]["patents"][0]}],
        paper_signals=[{"ipc1": "B25J9/00", "ipc2": "G06F30/00", "score": 0.6,
                       "observed_year": 2020, "evidence_id": snapshot["record_ids"]["papers"][0]}],
        taxonomy={code: code[:4] for code in IPCS},
    )
    for candidate in feature_result["candidates"]:
        pair = tuple(sorted((candidate["ipc1"], candidate["ipc2"])))
        candidate["label"] = int(pair in future_edges)
        candidate["label_window"] = "2021-2025 observed emergence"
    # Labels alter the immutable feature payload, so reseal it before persistence.
    feature_result["checksum"] = canonical_checksum({
        key: value for key, value in feature_result.items() if key != "checksum"
    })
    feature_run_id = feature_pipeline.persist(network_run_id, feature_result)
    feature_rows = _load_feature_rows(repository, feature_run_id)
    assert len(feature_rows) == 10 and {row["label"] for row in feature_rows} == {0, 1}

    model_service = FusionModelService(repository)
    parameters = ModelParameters(iterations=80, bootstrap_repeats=8, minimum_calibration_support=10)
    artifact = model_service.fit(feature_rows, parameters)
    predictions = model_service.predict(artifact, feature_rows)
    calibration = model_service.calibrate(
        [item["raw_score"] for item in predictions], [row["label"] for row in feature_rows], 10
    )
    intervals = model_service.prediction_intervals(feature_rows, parameters)
    model_run_id = model_service.persist(
        feature_run_id, artifact, feature_rows, predictions, calibration, intervals
    )
    with repository.db.connect() as connection:
        selected = dict(connection.execute(
            """SELECT fp.*,fc.ipc1,fc.ipc2 FROM fusion_predictions fp
               JOIN fusion_candidates fc ON fc.candidate_id=fp.candidate_id
               WHERE fp.model_run_id=? ORDER BY fp.rank LIMIT 1""",
            (model_run_id,),
        ).fetchone())
        patent_row = dict(connection.execute(
            "SELECT patent_id,dataset_id,publication_number,source_row FROM patents ORDER BY source_row LIMIT 1"
        ).fetchone())
        paper_row = dict(connection.execute(
            "SELECT paper_id,dataset_id,title,doi FROM papers LIMIT 1"
        ).fetchone())
    assert selected["probability_authority"] == "deterministic_model"
    assert selected["probability_status"] == "calibrated"

    job_id = "job_empirical_e2e"
    repository.reserve_forecast_job(job_id, project["project_id"], request_checksum=snapshot["checksum"],
                                    idempotency_key="empirical-e2e")
    repository.update_forecast_job_status(job_id, "running")
    evidence_ids = [patent_row["patent_id"], paper_row["paper_id"]]
    ipc_pair = "%s×%s" % (selected["ipc1"], selected["ipc2"])
    bounded = BoundedAgentNodes(_validated_role_provider(evidence_ids, selected["candidate_id"], ipc_pair))
    handlers = {
        **bounded.handlers(),
        "validate_scope": lambda _state: {"scope_validated": True},
        "freeze_snapshot": lambda _state: {"snapshot_ref": {
            "snapshot_checksum": snapshot["checksum"], "dataset_ids": snapshot["dataset_ids"]}},
        "construct_network": lambda _state: {"artifact_refs": [{
            "artifact_type": "network", "artifact_id": network_run_id,
            "checksum": network_output["result"]["result_checksum"], "schema_version": "network-v1"}]},
        "validation_model": lambda _state: {"artifact_refs": [{
            "artifact_type": "model", "artifact_id": model_run_id,
            "checksum": artifact["checksum"], "schema_version": artifact["model_version"]}]},
        "rank_candidates": lambda _state: {"candidate_refs": [{
            "candidate_id": selected["candidate_id"], "ipc1": selected["ipc1"],
            "ipc2": selected["ipc2"], "rank": selected["rank"],
            "probability": selected["calibrated_probability"], "model_run_id": model_run_id}]},
        "citation_validation": lambda state: {"citations_valid": set(evidence_ids).issubset(
            set(state["frozen_contract"]["evidence_ids"]))},
        "publication_gates": lambda _state: {"publication_gate_result": {
            "publishable": True, "evidence": True, "calibration": True,
            "citations": True, "human_review_required": True}},
        "asset_generation": lambda _state: {"assets_ready": True},
    }
    graph = EvidenceConstrainedForecastGraph(GraphRuntimeContext(
        repository=repository, job_id=job_id, project_id=project["project_id"],
        model_config={"provider": "deterministic-test-provider"},
        output_root=str(tmp_path / "graph-output"), compute_concurrency=2,
    ), handlers)
    state = graph.start({
        "snapshot_ref": {"snapshot_checksum": snapshot["checksum"]},
        "frozen_contract": {"evidence_ids": evidence_ids, "ipc_codes": IPCS,
                            "forecast_nodes": [2030, 2035, 2040]},
        "stage_analysis": [{"period": "2020_2025", "network_run_id": network_run_id}],
        "candidate_refs": [{"candidate_id": selected["candidate_id"], "model_run_id": model_run_id}],
        "evidence_tasks": [{"id": "patent-evidence", "kind": "patent", "evidence_id": patent_row["patent_id"]},
                           {"id": "paper-evidence", "kind": "paper", "evidence_id": paper_row["paper_id"]}],
    })
    thread_id = repository.get_forecast_job(job_id)["graph_thread_id"]
    assert state["current_node"] == "fusion_review"
    state = graph.decide(thread_id, "fusion_review", "approve", {}, "模型排序与来源已复核")
    assert state["current_node"] == "theme_review"
    state = graph.decide(thread_id, "theme_review", "approve", {}, "主题证据链已复核")
    assert state["current_node"] == "publication_review"
    state = graph.decide(thread_id, "publication_review", "approve", {}, "出版门与图件已复核")
    assert state["status"] == "completed" and state["citations_valid"] is True

    forecast = next(item["result"] for item in state["theme_results"]
                    if item["id"].endswith("_forecast"))
    roadmap = next(item["result"] for item in state["theme_results"]
                   if item["id"].endswith("_scenario"))
    with repository.db.connect() as connection:
        reviews = [dict(row) for row in connection.execute(
            "SELECT * FROM human_reviews WHERE thread_id=? ORDER BY created_at,review_id", (thread_id,)
        ).fetchall()]
        feature_lineage = [json.loads(row[0]) for row in connection.execute(
            """SELECT ff.lineage_json FROM fusion_features ff
               WHERE ff.candidate_id=? ORDER BY ff.feature_name""", (selected["candidate_id"],)
        ).fetchall()]
    assert len(reviews) == 3
    assert all(item["cutoff_year"] == 2020 and max(item["source_years"]) <= 2020
               for item in feature_lineage)

    scenario_payload = {
        scenario["name"]: [{
            "year": item["year"], "title": item["name"], "trl": item["trl"],
            "dependencies": item["dependencies"], "indicators": item["indicators"],
            "evidence_ids": item["evidence_ids"], "uncertainty": item["uncertainty"],
        } for item in scenario["milestones"]]
        for scenario in roadmap["scenarios"]
    }
    bundle_service = ResearchBundleService()
    dossier = bundle_service.assemble_dossier({
        "theme_id": forecast["theme_id"], "theme_name": forecast["theme_name"],
        "definition": forecast["summary"],
        "ipc_pairs": [{"ipc1": selected["ipc1"], "ipc2": selected["ipc2"],
                       "candidate_id": selected["candidate_id"], "model_run_id": model_run_id}],
        "patent_evidence_ids": [patent_row["patent_id"]],
        "paper_evidence_ids": [paper_row["paper_id"]],
        "probability_status": selected["probability_status"],
        "probability": selected["calibrated_probability"],
        "interval": [selected["interval_low"], selected["interval_high"]],
        "limitations": forecast["limitations"], "partial_2025": True,
        "stability_status": selected["stability_status"], "scenarios": scenario_payload,
        "review_refs": [item["review_id"] for item in reviews],
    })
    chart = ScientificChartData(
        figure_number="图E2E-1", chart_kind="roadmap_swimlane", title=forecast["theme_name"],
        caption="三种情景是条件性预测，不表示因果关系；全部节点关联冻结证据。",
        source_note="冻结快照 %s" % snapshot["checksum"][:12], sample_size=10,
        cutoff="2025-10-01", series=[ChartSeries(
            series_id=name, label=name, evidence_status="human_reviewed",
            values=[{"start": 2025 if item["year"] == 2030 else item["year"] - 5,
                     "end": item["year"], "label": item["title"], "trl": item["trl"]}
                    for item in milestones],
        ) for name, milestones in scenario_payload.items()],
    )
    bibliography = [
        {"id": patent_row["patent_id"], "kind": "patent", **patent_row},
        {"id": paper_row["paper_id"], "kind": "paper", **paper_row},
    ]
    export = bundle_service.export(
        tmp_path / "publication", project, [dossier], [chart], bibliography, reviews,
        state["publication_gate_result"],
        validation_artifacts={"network_run_id": network_run_id, "feature_run_id": feature_run_id,
                              "model_run_id": model_run_id, "snapshot_checksum": snapshot["checksum"]},
        known_evidence_ids=evidence_ids,
    )
    assert Path(export["bundle"]).is_file()
    assert bundle_service.verify(tmp_path / "publication")["valid"] is True

    # Final trace proof: every published evidence ID resolves to an imported row in
    # the frozen dataset, while every deterministic result resolves through its run chain.
    assert {dossier.patent_evidence_ids[0], dossier.paper_evidence_ids[0]} == set(evidence_ids)
    assert patent_row["dataset_id"] == paper_row["dataset_id"] == dataset["dataset_id"]
    assert patent_row["patent_id"] in snapshot["record_ids"]["patents"]
    assert paper_row["paper_id"] in snapshot["record_ids"]["papers"]
    assert selected["candidate_id"] in {row["candidate_id"] for row in feature_rows}
    assert all(milestone["evidence_ids"] == evidence_ids
               for milestones in scenario_payload.values() for milestone in milestones)
    structured = json.loads((tmp_path / "publication" / "structured-artifacts.json").read_text("utf-8"))
    assert structured["dossiers"][0]["checksum"] == dossier.checksum
    assert structured["dossiers"][0]["review_refs"] == [item["review_id"] for item in reviews]
