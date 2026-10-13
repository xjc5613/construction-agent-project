# -*- coding: utf-8 -*-
import json
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel, Field

from src.library import LibraryRepository
from src.research.design import ResearchDesignService
from src.research.graph import BoundedAgentNodes, EvidenceConstrainedForecastGraph, GraphRuntimeContext
from config.settings import EXPORTS_DIR
from src.research.chart_factory import ScientificChartFactory
from src.research.visualization import ScientificFigureRenderer
from src.research.publication import ResearchBundleService
from src.research.validation import HistoricalValidationService
from src.research.features import CandidatePolicy, FusionFeaturePipeline
from src.research.models import FusionModelService, ModelParameters
from src.research.network import DynamicIPCNetworkService, NetworkParameters
from src.research.repository import canonical_checksum
from src.research.agent_schemas import CriticFinding, EvidenceAnalysis, ScenarioRoadmap, TechnologyConcept, ThemeForecast
from src.research.langchain_adapter import (
    JobModelConfig, create_chat_model, load_prompt_template, persist_model_manifest,
    persist_prompt_manifest, structured_model,
)


router = APIRouter(prefix="/api/research", tags=["research-v3"])
repository = LibraryRepository()


class NetworkRunCreate(BaseModel):
    dataset_ids: List[str] = Field(default_factory=list)
    minimum_support: int = Field(1, ge=1)
    completeness_policy: str = "include_partial_with_sensitivity"
    random_seed: int = 0


class GraphStart(BaseModel):
    initial_state: Dict[str, Any] = Field(default_factory=dict)
    model_options: Dict[str, Any] = Field(default_factory=dict)
    output_root: str = ""
    compute_concurrency: int = Field(4, ge=1, le=16)


class FeatureRunCreate(BaseModel):
    target_type: str = "emergence"
    cutoff_year: int = Field(2025, ge=2010, le=2025)
    minimum_support: int = Field(1, ge=1)
    edge_threshold: float = Field(0.0, ge=0)
    forecast_horizon: int = Field(5, ge=1, le=15)
    cross_domain_only: bool = False
    max_candidates: int = Field(10000, ge=1, le=100000)


class ModelRunCreate(BaseModel):
    model_kind: str = "logistic_regression"
    seed: int = 42
    bootstrap_repeats: int = Field(50, ge=10, le=1000)
    minimum_calibration_support: int = Field(10, ge=2)


class ReviewDecision(BaseModel):
    decision: str
    after: Dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    reviewer: str = "local-user"


class CandidateReview(ReviewDecision):
    job_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ThemeMutation(ReviewDecision):
    job_id: str
    theme_ids: List[str] = Field(default_factory=list)


class ExportCreate(BaseModel):
    bibliography: List[Dict[str, Any]] = Field(default_factory=list)


def _json_fields(row: Dict[str, Any], names: List[str]) -> Dict[str, Any]:
    for name in names:
        if name in row:
            value = row[name]
            row[name[:-5] if name.endswith("_json") else name] = (
                json.loads(value) if isinstance(value, str) and value else value
            )
            if name.endswith("_json"):
                row.pop(name, None)
    return row


def _job_state(job_id: str) -> Dict[str, Any]:
    job = repository.get_forecast_job(job_id)
    if not job or not job.get("graph_thread_id"):
        raise HTTPException(status_code=404, detail="图任务不存在")
    state = _graph(job_id).checkpointer.load(job["graph_thread_id"])
    if not state:
        raise HTTPException(status_code=404, detail="图检查点不存在")
    return {"job": job, "thread_id": job["graph_thread_id"], "state": state}


def _graph(job_id: str, override_options: Optional[Dict[str, Any]] = None,
           output_root: str = "", compute_concurrency: int = 4) -> EvidenceConstrainedForecastGraph:
    job = repository.get_forecast_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="预测任务不存在")
    options = {**job.get("options", {}), **(override_options or {})}
    context = GraphRuntimeContext(
        repository=repository, job_id=job_id, project_id=job["project_id"],
        model_config=options, output_root=output_root, compute_concurrency=compute_concurrency,
    )
    config = JobModelConfig(**{key: options[key] for key in (
        "provider", "model_name", "temperature", "max_tokens", "native_structured_output"
    ) if key in options})
    model = create_chat_model(config)
    schemas = {"evidence_analyst": EvidenceAnalysis,
               "technology_concept_synthesizer": TechnologyConcept,
               "scientific_critic": CriticFinding,
               "topic_forecaster": ThemeForecast, "scenario_roadmap": ScenarioRoadmap}

    def invoke_role(role: str, payload: Dict[str, Any]):
        schema = schemas[role]
        prompt = load_prompt_template(role)
        persist_prompt_manifest(repository, prompt)
        persist_model_manifest(repository, config)
        messages = prompt["template"].invoke({"payload": json.dumps(payload, ensure_ascii=False, sort_keys=True)})
        result = structured_model(model, schema, config.native_structured_output).invoke(messages)
        if isinstance(result, dict) and result.get("parsing_error"):
            raise ValueError("结构化模型输出解析失败: %s" % result["parsing_error"])
        parsed = result.get("parsed") if isinstance(result, dict) else result
        return parsed.model_dump() if hasattr(parsed, "model_dump") else parsed

    return EvidenceConstrainedForecastGraph(context, BoundedAgentNodes(invoke_role).handlers())


@router.get("/projects/{project_id}/data-quality")
def project_data_quality(project_id: str):
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="预测项目不存在")
    coverage = repository.dataset_coverage(project["technology_node_id"])
    with repository.db.connect() as connection:
        paper_types = [dict(row) for row in connection.execute(
            """SELECT paper_type,COUNT(*) count FROM papers p JOIN datasets d
               ON d.dataset_id=p.dataset_id WHERE d.technology_node_id IN (
               SELECT node_id FROM technology_nodes WHERE node_id=? OR parent_id IN
               (SELECT node_id FROM technology_nodes WHERE parent_id=?)) GROUP BY paper_type""",
            (project["technology_node_id"], project["technology_node_id"]),
        ).fetchall()]
        mappings = [dict(row) for row in connection.execute(
            "SELECT status,COUNT(*) count FROM ipc_code_mappings GROUP BY status"
        ).fetchall()]
        invalid = [dict(row) for row in connection.execute(
            """SELECT import_id,error_json FROM imports WHERE error_json NOT IN ('[]','{}','')
               ORDER BY created_at DESC LIMIT 100"""
        ).fetchall()]
        patent_count = int(connection.execute("SELECT COUNT(*) FROM patents").fetchone()[0])
        assignment_count = int(connection.execute("SELECT COUNT(*) FROM patent_ipcs").fetchone()[0])
        reduced_count = int(connection.execute("SELECT COUNT(*) FROM reduced_ipc_edges WHERE review_status='approved'").fetchone()[0])
        unresolved_count = int(connection.execute("SELECT COUNT(*) FROM patent_ipcs WHERE mapping_status!='mapped'").fetchone()[0])
        duplicate_count = int(connection.execute(
            """SELECT COUNT(*) FROM (SELECT dataset_id,publication_number,COUNT(*) n FROM patents
               GROUP BY dataset_id,publication_number HAVING n>1)"""
        ).fetchone()[0])
    reconstruction_grade = "canonical" if patent_count and assignment_count else "reduced_edge" if reduced_count else "insufficient"
    return {"coverage": coverage, "paper_types": paper_types, "ipc_mappings": mappings,
            "duplicate_count": duplicate_count,
            "unresolved_mapping_count": unresolved_count, "reconstruction_grade": reconstruction_grade,
            "record_counts": {"patents": patent_count, "patent_ipcs": assignment_count, "reduced_edges": reduced_count},
            "invalid_records": invalid, "partial_year_warnings": [
                "2025 年数据为部分年度，所有结论需标注截止日期"
            ] if 2025 in repository.get_project(project_id)["research_contract"]["incomplete_years"] else []}


@router.post("/projects/{project_id}/network-runs", status_code=201)
def start_network_run(project_id: str, payload: NetworkRunCreate):
    try:
        snapshot = ResearchDesignService(repository).freeze_snapshot(
            project_id, payload.dataset_ids or None
        )
        return DynamicIPCNetworkService(repository).build_and_persist(
            project_id, snapshot, NetworkParameters(
                minimum_support=payload.minimum_support,
                completeness_policy=payload.completeness_policy,
                random_seed=payload.random_seed,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/projects/{project_id}/network-runs")
def list_network_runs(project_id: str):
    with repository.db.connect() as connection:
        items = [dict(row) for row in connection.execute(
            "SELECT * FROM network_runs WHERE project_id=? ORDER BY created_at DESC", (project_id,)
        ).fetchall()]
    return {"items": items, "total": len(items)}


@router.get("/projects/{project_id}/chart-data")
def project_chart_data(project_id: str):
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="预测项目不存在")
    cutoff = project.get("research_contract", {}).get("default_cutoff", "2025-10-01")
    items = [chart.model_dump() for chart in ScientificChartFactory(repository).for_project(project_id, cutoff)]
    return {"schema_version": "scientific-chart-v1", "items": items, "total": len(items)}


@router.post("/projects/{project_id}/charts/render")
def render_project_charts(project_id: str):
    charts = ScientificChartFactory(repository).for_project(project_id)
    if not charts:
        raise HTTPException(status_code=409, detail="尚无可渲染的冻结科学图表数据")
    output = EXPORTS_DIR / project_id / "figures"
    items = [ScientificFigureRenderer().render(chart, output) for chart in charts]
    return {"items": items, "total": len(items), "output_checksum": canonical_checksum(items)}


@router.get("/network-runs/{run_id}")
def network_run_status(run_id: str):
    with repository.db.connect() as connection:
        row = connection.execute(
            "SELECT * FROM network_runs WHERE network_run_id=?", (run_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="网络运行不存在")
        result = _json_fields(dict(row), ["parameters_json"])
        result["period_summaries"] = [dict(item) for item in connection.execute(
            """SELECT period_code,COUNT(*) edge_count,SUM(cooccurrence_count) cooccurrence_count,
                      COUNT(DISTINCT ipc1)+COUNT(DISTINCT ipc2) endpoint_count
               FROM ipc_edges_period WHERE network_run_id=? GROUP BY period_code
               ORDER BY period_code""", (run_id,),
        ).fetchall()]
    return result


@router.post("/network-runs/{run_id}/feature-runs", status_code=201)
def start_feature_run(run_id: str, payload: FeatureRunCreate):
    network = network_run_status(run_id)
    if network["status"] != "completed":
        raise HTTPException(status_code=409, detail="仅已完成且未过期的网络可生成特征")
    if payload.target_type not in {"emergence", "strengthening"}:
        raise HTTPException(status_code=422, detail="候选目标无效")
    with repository.db.connect() as connection:
        annual_rows = [dict(row) for row in connection.execute(
            "SELECT * FROM ipc_edges_yearly WHERE network_run_id=? AND year<=? ORDER BY year,ipc1,ipc2",
            (run_id, payload.cutoff_year),
        ).fetchall()]
        layout_rows = connection.execute(
            """SELECT ipc_code,layout_x,layout_y FROM network_nodes WHERE network_run_id=?
               AND observation_kind='period' ORDER BY observation_key DESC""", (run_id,),
        ).fetchall()
    annual: Dict[str, Any] = {}
    for edge in annual_rows:
        annual.setdefault(str(edge["year"]), {"nodes": [], "edges": []})["edges"].append(edge)
    layout = {row["ipc_code"]: [row["layout_x"], row["layout_y"]] for row in layout_rows}
    # Include endpoints even when a period has no eligible edge at the configured threshold.
    for value in annual.values():
        value["nodes"] = sorted({code for item in value["edges"] for code in (item["ipc1"], item["ipc2"])})
    result = FusionFeaturePipeline(repository).build(
        {"annual": annual, "layout": layout}, cutoff_year=payload.cutoff_year,
        policy=CandidatePolicy(**payload.model_dump(exclude={"cutoff_year"})),
    )
    feature_run_id = FusionFeaturePipeline(repository).persist(run_id, result)
    return {"feature_run_id": feature_run_id, "candidate_count": len(result["candidates"]),
            "checksum": result["checksum"], "target_type": payload.target_type}


def _feature_rows(feature_run_id: str) -> List[Dict[str, Any]]:
    with repository.db.connect() as connection:
        candidates = [dict(row) for row in connection.execute(
            "SELECT * FROM fusion_candidates WHERE feature_run_id=? ORDER BY candidate_id",
            (feature_run_id,),
        ).fetchall()]
        rows = []
        for item in candidates:
            features = {row["feature_name"]: row["feature_value"] for row in connection.execute(
                "SELECT feature_name,feature_value FROM fusion_features WHERE candidate_id=?",
                (item["candidate_id"],),
            ).fetchall()}
            rows.append({**item, "features": features})
    return rows


@router.post("/feature-runs/{feature_run_id}/model-runs", status_code=201)
def start_model_run(feature_run_id: str, payload: ModelRunCreate):
    rows = _feature_rows(feature_run_id)
    training = [row for row in rows if row.get("label") in {0, 1}]
    if len(training) < 2 or len({row["label"] for row in training}) < 2:
        raise HTTPException(status_code=409, detail="至少需要两个类别的历史标签才能训练和验证模型")
    parameters = ModelParameters(**payload.model_dump())
    service = FusionModelService(repository)
    try:
        artifact = service.fit(training, parameters)
        predictions = service.predict(artifact, rows)
        train_predictions = service.predict(artifact, training)
        calibration = service.calibrate(
            [item["raw_score"] for item in train_predictions], [int(item["label"]) for item in training],
            parameters.minimum_calibration_support,
        )
        training_intervals = service.prediction_intervals(training, parameters)
        interval_by_id = {row["candidate_id"]: interval for row, interval in zip(training, training_intervals)}
        intervals = [interval_by_id.get(row["candidate_id"], (None, None)) for row in rows]
        model_run_id = service.persist(feature_run_id, artifact, rows, predictions, calibration, intervals)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return model_run_detail(model_run_id)


@router.get("/network-runs/{run_id}/nodes")
def network_nodes(run_id: str, observation_kind: str = "period", observation_key: str = "2020_2025",
                  page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=500)):
    with repository.db.connect() as connection:
        rows = [dict(row) for row in connection.execute(
            """SELECT * FROM network_nodes WHERE network_run_id=? AND observation_kind=?
               AND observation_key=? ORDER BY ipc_code LIMIT ? OFFSET ?""",
            (run_id, observation_kind, observation_key, page_size, (page - 1) * page_size),
        ).fetchall()]
    return {"items": rows, "page": page, "page_size": page_size}


@router.get("/network-runs/{run_id}/edges")
def network_edges(run_id: str, period_code: str = "2020_2025", year: Optional[int] = None,
                  page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=500)):
    with repository.db.connect() as connection:
        if year is not None:
            rows = [dict(row) for row in connection.execute(
                """SELECT * FROM ipc_edges_yearly WHERE network_run_id=? AND year=?
                   ORDER BY cooccurrence_count DESC,ipc1,ipc2 LIMIT ? OFFSET ?""",
                (run_id, year, page_size, (page - 1) * page_size),
            ).fetchall()]
        else:
            rows = [dict(row) for row in connection.execute(
                """SELECT * FROM ipc_edges_period WHERE network_run_id=? AND period_code=?
                   ORDER BY cooccurrence_count DESC,ipc1,ipc2 LIMIT ? OFFSET ?""",
                (run_id, period_code, page_size, (page - 1) * page_size),
            ).fetchall()]
    return {"items": rows, "page": page, "page_size": page_size,
            "observation_kind": "annual" if year is not None else "period",
            "observation_key": str(year) if year is not None else period_code}


@router.get("/network-runs/{run_id}/trajectories")
def network_trajectories(run_id: str):
    with repository.db.connect() as connection:
        items = [dict(row) for row in connection.execute(
            "SELECT * FROM node_transitions WHERE network_run_id=? ORDER BY ipc_code,from_observation",
            (run_id,),
        ).fetchall()]
    return {"items": items, "total": len(items)}


@router.get("/network-runs/{run_id}/communities")
def network_communities(run_id: str):
    with repository.db.connect() as connection:
        items = [dict(row) for row in connection.execute(
            """SELECT observation_kind,observation_key,stable_community_id,COUNT(*) node_count
               FROM community_memberships WHERE network_run_id=?
               GROUP BY observation_kind,observation_key,stable_community_id""", (run_id,)
        ).fetchall()]
    return {"items": items, "total": len(items)}


@router.get("/network-runs/{run_id}/edge-evidence")
def network_edge_evidence(run_id: str, ipc1: str, ipc2: str,
                          page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    return DynamicIPCNetworkService(repository).edge_evidence(
        run_id, ipc1, ipc2, page=page, page_size=page_size
    )


@router.get("/model-runs/{model_run_id}")
def model_run_detail(model_run_id: str):
    with repository.db.connect() as connection:
        model = connection.execute("SELECT * FROM model_runs WHERE model_run_id=?", (model_run_id,)).fetchone()
        if not model:
            raise HTTPException(status_code=404, detail="模型运行不存在")
        result = dict(model)
        for key, table in (("calibration", "model_calibrations"), ("folds", "validation_folds"),
                           ("metrics", "validation_metrics"), ("ablations", "ablation_runs"),
                           ("sensitivities", "sensitivity_runs")):
            result[key] = [dict(row) for row in connection.execute(
                "SELECT * FROM %s WHERE model_run_id=?" % table, (model_run_id,)
            ).fetchall()]
        result["gates"] = [_json_fields(dict(row), ["details_json"]) for row in connection.execute(
            "SELECT * FROM publication_gates WHERE model_run_id=? ORDER BY gate_name",
            (model_run_id,),
        ).fetchall()]
        result["manifest"] = {
            "input_checksum": result["input_checksum"],
            "result_checksum": result["result_checksum"],
            "model_kind": result["model_kind"],
            "model_version": result["model_version"],
            "random_seed": result["random_seed"],
        }
        labeled = [dict(row) for row in connection.execute(
            """SELECT c.candidate_id,c.label,p.raw_score,
                      COALESCE((SELECT feature_value FROM fusion_features x WHERE x.candidate_id=c.candidate_id
                                AND x.feature_name='common_neighbors'),0) common_neighbors,
                      COALESCE((SELECT feature_value FROM fusion_features x WHERE x.candidate_id=c.candidate_id
                                AND x.feature_name='adamic_adar'),0) adamic_adar
               FROM fusion_predictions p JOIN fusion_candidates c ON c.candidate_id=p.candidate_id
               WHERE p.model_run_id=? AND c.label IS NOT NULL ORDER BY c.candidate_id""", (model_run_id,)
        ).fetchall()]
        if labeled:
            labels = [int(item["label"]) for item in labeled]
            prevalence = sum(labels) / len(labels)
            import random
            rng = random.Random(int(result["random_seed"]))
            result["baselines"] = HistoricalValidationService().compare_baselines(
                labels, [float(item["raw_score"]) for item in labeled], {
                    "random": [rng.random() for _ in labeled], "prevalence": [prevalence for _ in labeled],
                    "common_neighbors": [float(item["common_neighbors"]) for item in labeled],
                    "adamic_adar": [float(item["adamic_adar"]) for item in labeled],
                })
        else:
            result["baselines"] = {"status": "not_estimable", "reason": "缺少历史标签"}
        result = _json_fields(result, ["parameters_json"])
        for key in ("calibration", "folds", "metrics", "ablations", "sensitivities"):
            result[key] = [_json_fields(item, [name for name in list(item) if name.endswith("_json")])
                           for item in result[key]]
    return result


@router.get("/projects/{project_id}/model-runs")
def project_model_runs(project_id: str):
    with repository.db.connect() as connection:
        rows = [dict(row) for row in connection.execute(
            """SELECT m.*,f.target_type,f.cutoff_year,f.network_run_id FROM model_runs m
               JOIN feature_runs f ON f.feature_run_id=m.feature_run_id JOIN network_runs n
               ON n.network_run_id=f.network_run_id WHERE n.project_id=? ORDER BY m.created_at DESC""",
            (project_id,),
        ).fetchall()]
    return {"items": [_json_fields(row, ["parameters_json"]) for row in rows], "total": len(rows)}


@router.get("/model-runs/{model_run_id}/validation")
def model_validation_detail(model_run_id: str):
    result = model_run_detail(model_run_id)
    return {key: result[key] for key in (
        "model_run_id", "folds", "metrics", "baselines", "calibration", "ablations",
        "sensitivities", "gates", "manifest",
    )}


@router.get("/model-runs/{model_run_id}/predictions")
def model_predictions(model_run_id: str, page: int = Query(1, ge=1),
                      page_size: int = Query(50, ge=1, le=200)):
    with repository.db.connect() as connection:
        total = connection.execute(
            "SELECT COUNT(*) FROM fusion_predictions WHERE model_run_id=?", (model_run_id,)
        ).fetchone()[0]
        items = [_json_fields(dict(row), ["explanation_json", "limitations_json"])
                 for row in connection.execute(
            """SELECT p.*,c.ipc1,c.ipc2,c.target_type FROM fusion_predictions p
               JOIN fusion_candidates c ON c.candidate_id=p.candidate_id
               WHERE p.model_run_id=? ORDER BY p.rank LIMIT ? OFFSET ?""",
            (model_run_id, page_size, (page - 1) * page_size),
        ).fetchall()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/fusion-candidates/{candidate_id}")
def fusion_candidate_detail(candidate_id: str):
    with repository.db.connect() as connection:
        row = connection.execute(
            """SELECT c.*,f.network_run_id,f.cutoff_year,f.schema_version,n.project_id
               FROM fusion_candidates c JOIN feature_runs f ON f.feature_run_id=c.feature_run_id
               JOIN network_runs n ON n.network_run_id=f.network_run_id
               WHERE c.candidate_id=?""", (candidate_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="融合候选不存在")
        result = dict(row)
        result["features"] = [_json_fields(dict(item), ["lineage_json"])
                              for item in connection.execute(
            "SELECT feature_name,feature_value,feature_status,lineage_json FROM fusion_features WHERE candidate_id=? ORDER BY feature_name",
            (candidate_id,),
        ).fetchall()]
        result["predictions"] = [_json_fields(dict(item), ["explanation_json", "limitations_json"])
                                 for item in connection.execute(
            "SELECT * FROM fusion_predictions WHERE candidate_id=? ORDER BY rank", (candidate_id,),
        ).fetchall()]
        result["reviews"] = [_json_fields(dict(item), ["before_json", "after_json"])
                             for item in connection.execute(
            "SELECT * FROM human_reviews WHERE review_kind='fusion_candidate' AND target_id=? ORDER BY created_at",
            (candidate_id,),
        ).fetchall()]
    return result


@router.post("/fusion-candidates/{candidate_id}/review")
def review_fusion_candidate(candidate_id: str, payload: CandidateReview):
    detail = fusion_candidate_detail(candidate_id)
    context = _job_state(payload.job_id)
    if context["job"]["project_id"] != detail["project_id"]:
        raise HTTPException(status_code=409, detail="评审任务与候选所属项目不一致")
    if payload.decision not in {"approve", "edit", "reject"}:
        raise HTTPException(status_code=422, detail="评审决定无效")
    # Human edits may annotate a candidate, but never replace model-owned numeric fields.
    protected = {"rank", "raw_score", "calibrated_probability", "interval_low", "interval_high"}
    attempted = protected.intersection(payload.after)
    if attempted:
        raise HTTPException(status_code=409, detail="人工评审不可修改模型权威字段: " + ", ".join(sorted(attempted)))
    review_id = "review_" + uuid4().hex[:16]
    with repository.db.transaction() as connection:
        connection.execute(
            """INSERT INTO human_reviews(review_id,thread_id,review_kind,target_id,decision,
               before_json,after_json,reason,reviewer) VALUES (?,?,?,?,?,?,?,?,?)""",
            (review_id, context["thread_id"], "fusion_candidate", candidate_id,
             payload.decision, json.dumps(detail, ensure_ascii=False, sort_keys=True),
             json.dumps({**payload.after, "metadata": payload.metadata}, ensure_ascii=False, sort_keys=True),
             payload.reason, payload.reviewer),
        )
    return {"review_id": review_id, "candidate_id": candidate_id, "decision": payload.decision,
            "authoritative_prediction_unchanged": True}


@router.get("/graph/jobs/{job_id}/themes")
def graph_themes(job_id: str):
    context = _job_state(job_id)
    state = context["state"]
    concept = state.get("technology_concept")
    generated = [item.get("result", item) for item in state.get("theme_results", []) if isinstance(item, dict)]
    proposals = ([concept] if concept else []) + generated
    with repository.db.connect() as connection:
        reviews = [_json_fields(dict(row), ["before_json", "after_json"])
                   for row in connection.execute(
            "SELECT * FROM human_reviews WHERE thread_id=? AND review_kind IN ('technology_theme','theme_review') ORDER BY created_at",
            (context["thread_id"],),
        ).fetchall()]
        approved_pairs = [dict(row) for row in connection.execute(
            """SELECT r.target_id candidate_id,c.ipc1,c.ipc2,c.target_type FROM human_reviews r
               JOIN fusion_candidates c ON c.candidate_id=r.target_id WHERE r.thread_id=?
               AND r.review_kind='fusion_candidate' AND r.decision='approve'""", (context["thread_id"],)
        ).fetchall()]
    return {"items": proposals, "critic_findings": state.get("critic_findings", []),
            "evidence_results": state.get("evidence_results", []), "approved_pairs": approved_pairs,
            "artifact_refs": state.get("artifact_refs", []), "reviews": reviews,
            "confirmed": "theme_review" in state.get("review_decisions", {})}


@router.post("/graph/jobs/{job_id}/themes/{theme_id}/review")
def review_theme(job_id: str, theme_id: str, payload: ThemeMutation):
    context = _job_state(job_id)
    if payload.job_id != job_id:
        raise HTTPException(status_code=409, detail="评审任务与主题任务不一致")
    if payload.decision not in {"approve", "edit", "reject"}:
        raise HTTPException(status_code=422, detail="评审决定无效")
    if payload.decision == "edit":
        operation = payload.after.get("operation", "rename")
        if operation == "rename" and not str(payload.after.get("theme_name", "")).strip():
            raise HTTPException(status_code=422, detail="主题重命名不能为空")
        if operation == "merge" and len(set(payload.theme_ids)) < 2:
            raise HTTPException(status_code=422, detail="主题合并至少需要两个不同主题")
    review_id = "review_" + uuid4().hex[:16]
    with repository.db.transaction() as connection:
        connection.execute(
            """INSERT INTO human_reviews(review_id,thread_id,review_kind,target_id,decision,
               before_json,after_json,reason,reviewer) VALUES (?,?,?,?,?,?,?,?,?)""",
            (review_id, context["thread_id"], "technology_theme", theme_id, payload.decision,
             json.dumps({"theme_id": theme_id}, sort_keys=True),
             json.dumps({**payload.after, "merged_theme_ids": payload.theme_ids}, ensure_ascii=False, sort_keys=True),
             payload.reason, payload.reviewer),
        )
    return {"review_id": review_id, "theme_id": theme_id, "decision": payload.decision}


@router.get("/graph/jobs/{job_id}/provenance")
def graph_provenance(job_id: str, theme_id: str = "", evidence_id: str = "", candidate_id: str = ""):
    context = _job_state(job_id)
    with repository.db.connect() as connection:
        events = [_json_fields(dict(row), ["input_refs_json", "output_refs_json", "metadata_json", "error_json"])
                  for row in connection.execute(
            "SELECT * FROM graph_node_events WHERE thread_id=? ORDER BY created_at,event_id",
            (context["thread_id"],),
        ).fetchall()]
        reviews = [_json_fields(dict(row), ["before_json", "after_json"])
                   for row in connection.execute(
            "SELECT * FROM human_reviews WHERE thread_id=? ORDER BY created_at,review_id",
            (context["thread_id"],),
        ).fetchall()]
        sources = []
        if evidence_id:
            patent = connection.execute("SELECT * FROM patents WHERE patent_id=?", (evidence_id,)).fetchone()
            paper = connection.execute("SELECT * FROM papers WHERE paper_id=?", (evidence_id,)).fetchone()
            if patent: sources.append({"source_kind": "patent", **dict(patent)})
            if paper: sources.append({"source_kind": "paper", **dict(paper)})
        candidate = fusion_candidate_detail(candidate_id) if candidate_id else None
    themes = [item.get("result", item) for item in context["state"].get("theme_results", []) if isinstance(item, dict)]
    return {"job_id": job_id, "thread_id": context["thread_id"],
            "artifact_refs": context["state"].get("artifact_refs", []),
            "theme": next((item for item in themes if item.get("theme_id") == theme_id), None),
            "candidate": candidate, "sources": sources,
            "events": events, "reviews": reviews}


@router.get("/graph/jobs/{job_id}/dossiers")
def graph_dossiers(job_id: str):
    state = _job_state(job_id)["state"]
    items = [item.get("result", item) for item in state.get("theme_results", []) if isinstance(item, dict)]
    return {"items": [item for item in items if "summary" in item],
            "roadmaps": [item for item in items if "scenarios" in item],
            "limitations": sorted({value for item in items for value in item.get("limitations", [])}),
            "publication_gates": state.get("publication_gate_result", {})}


def _dossiers_from_state(state: Dict[str, Any], review_ids: List[str]):
    forecasts, scenarios = {}, {}
    for wrapper in state.get("theme_results", []):
        value = wrapper.get("result", wrapper) if isinstance(wrapper, dict) else {}
        if "summary" in value:
            forecasts[value.get("theme_id")] = value
        if "scenarios" in value:
            scenarios[value.get("theme_id")] = value
    dossiers = []
    conflicts = sorted({conflict for wrapper in state.get("evidence_results", [])
                        for conflict in (wrapper.get("result", wrapper).get("conflicts", []) if isinstance(wrapper, dict) else [])})
    validation_limits = [item.get("error", "") for item in state.get("failures", []) if item.get("error")]
    overrides = [value.get("reason", "") for value in state.get("review_decisions", {}).values()
                 if value.get("decision") == "edit" and value.get("reason")]
    candidate_stability = {item.get("stability_status") for item in state.get("candidate_refs", []) if isinstance(item, dict)}
    stability = "unstable" if "unstable" in candidate_stability else "stable" if candidate_stability == {"stable"} else "not_evaluated"
    for theme_id, forecast in forecasts.items():
        scenario = scenarios.get(theme_id)
        if not scenario:
            continue
        scenario_map = {}
        for item in scenario["scenarios"]:
            scenario_map[item["name"]] = [{
                "year": milestone["year"], "title": milestone.get("name", ""),
                "trl": milestone.get("trl"), "dependencies": milestone.get("dependencies", []),
                "indicators": milestone.get("indicators", []), "evidence_ids": milestone.get("evidence_ids", []),
                "uncertainty": milestone.get("uncertainty", "not_estimable"),
            } for milestone in item["milestones"]]
        evidence = sorted({identifier for values in scenario_map.values() for milestone in values
                           for identifier in milestone["evidence_ids"]})
        pairs = []
        for pair in forecast.get("ipc_pairs", []):
            parts = [part.strip() for part in str(pair).replace("×", "|").replace("+", "|").split("|")]
            pairs.append({"ipc1": parts[0], "ipc2": parts[1] if len(parts) > 1 else ""})
        dossiers.append(ResearchBundleService().assemble_dossier({
            "theme_id": theme_id, "theme_name": forecast["theme_name"], "definition": forecast["summary"],
            "ipc_pairs": pairs, "patent_evidence_ids": evidence, "paper_evidence_ids": evidence,
            "probability_status": "uncalibrated", "probability": None, "interval": None,
            "limitations": forecast.get("limitations", []), "partial_2025": True,
            "validation_limits": validation_limits, "evidence_conflicts": conflicts,
            "expert_overrides": overrides, "stability_status": stability,
            "scenarios": scenario_map, "review_refs": review_ids,
        }))
    return dossiers


@router.post("/graph/jobs/{job_id}/exports", status_code=201)
def export_research_bundle(job_id: str, payload: ExportCreate):
    context = _job_state(job_id); state, job = context["state"], context["job"]
    publication_review = state.get("review_decisions", {}).get("publication_review", {})
    if publication_review.get("decision") not in {"approve", "edit"}:
        raise HTTPException(status_code=409, detail="必须先完成人工发布评审")
    with repository.db.connect() as connection:
        review_ids = [row[0] for row in connection.execute(
            "SELECT review_id FROM human_reviews WHERE thread_id=? ORDER BY created_at", (context["thread_id"],)
        ).fetchall()]
    dossiers = _dossiers_from_state(state, review_ids)
    if not dossiers:
        raise HTTPException(status_code=409, detail="缺少通过结构校验的主题预测与三情景路线图")
    charts = ScientificChartFactory(repository).for_project(job["project_id"])
    with repository.db.connect() as connection:
        model_ids = [row[0] for row in connection.execute(
            """SELECT m.model_run_id FROM model_runs m JOIN feature_runs f ON f.feature_run_id=m.feature_run_id
               JOIN network_runs n ON n.network_run_id=f.network_run_id WHERE n.project_id=?""", (job["project_id"],)
        ).fetchall()]
    validation_artifacts = {identifier: model_validation_detail(identifier) for identifier in model_ids}
    gates = state.get("publication_gate_result") or {"publishable": True, "source": "human_publication_review"}
    if not gates.get("publishable"):
        gates = {**gates, "publishable": True, "expert_override": publication_review.get("reason", "人工发布评审")}
    output = EXPORTS_DIR / job["project_id"] / job_id
    result = ResearchBundleService().export(output, repository.get_project(job["project_id"]), dossiers,
                                             charts, payload.bibliography, [{"review_id": value} for value in review_ids], gates,
                                             validation_artifacts=validation_artifacts,
                                             known_evidence_ids=state.get("frozen_contract", {}).get("evidence_ids", []))
    manifest_id = "export_" + uuid4().hex[:16]
    with repository.db.transaction() as connection:
        connection.execute(
            """INSERT OR IGNORE INTO export_manifests(export_manifest_id,project_id,job_id,manifest_version,
               manifest_json,manifest_checksum,export_path,status,completed_at)
               VALUES (?,?,?,?,?,?,?,'completed',CURRENT_TIMESTAMP)""",
            (manifest_id, job["project_id"], job_id, "export-manifest-v1",
             json.dumps(result["manifest"], ensure_ascii=False, sort_keys=True), result["manifest"]["checksum"], result["bundle"]),
        )
        stored = connection.execute(
            "SELECT export_manifest_id FROM export_manifests WHERE manifest_checksum=?",
            (result["manifest"]["checksum"],),
        ).fetchone()[0]
    return {**result, "export_manifest_id": stored,
            "download_url": "/api/research/exports/%s/download" % stored}


@router.get("/exports/{manifest_id}/download")
def download_research_bundle(manifest_id: str):
    with repository.db.connect() as connection:
        row = connection.execute(
            "SELECT export_path FROM export_manifests WHERE export_manifest_id=? AND status='completed'",
            (manifest_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="研究包不存在")
    path, root = Path(row["export_path"]).resolve(), EXPORTS_DIR.resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(status_code=409, detail="研究包路径校验失败")
    return FileResponse(path, media_type="application/zip", filename="research-bundle-%s.zip" % manifest_id)


@router.post("/projects/{project_id}/assets/regenerate")
def regenerate_project_assets(project_id: str):
    charts = ScientificChartFactory(repository).for_project(project_id)
    if not charts:
        raise HTTPException(status_code=409, detail="没有冻结图表数据可供重生成")
    output = EXPORTS_DIR / project_id / "regenerated"
    items = [ScientificFigureRenderer().render(chart, output) for chart in charts]
    return {"items": items, "input_checksums": [item.checksum for item in charts],
            "models_or_agents_rerun": False}


@router.get("/graph/jobs/{job_id}/manifest")
def graph_manifest(job_id: str):
    context = _job_state(job_id)
    job, state = context["job"], context["state"]
    with repository.db.connect() as connection:
        export = connection.execute(
            "SELECT * FROM export_manifests WHERE job_id=? ORDER BY created_at DESC LIMIT 1", (job_id,)
        ).fetchone()
    result = {"job_id": job_id, "project_id": job["project_id"],
              "research_contract_version": job.get("research_contract_version", 3),
              "graph_version": "forecast-graph-v1", "state_checksum": canonical_checksum(state),
              "artifact_refs": state.get("artifact_refs", [])}
    if export:
        result["export"] = _json_fields(dict(export), ["manifest_json"])
    return result


@router.post("/graph/jobs/{job_id}/start")
def start_graph(job_id: str, payload: GraphStart):
    graph = _graph(job_id, payload.model_options, payload.output_root, payload.compute_concurrency)
    try:
        snapshot = ResearchDesignService(repository).freeze_snapshot(graph.context.project_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    with repository.db.connect() as connection:
        codes = [row[0] for row in connection.execute(
            """SELECT DISTINCT pi.ipc_code_normalized FROM patent_ipcs pi JOIN patents p ON p.patent_id=pi.patent_id
               WHERE p.patent_id IN (%s) ORDER BY pi.ipc_code_normalized""" % (
                ",".join("?" for _ in snapshot["record_ids"]["patents"]) or "''"
            ), snapshot["record_ids"]["patents"],
        ).fetchall()]
        predictions = [dict(row) for row in connection.execute(
            """SELECT p.prediction_id,p.candidate_id,p.rank,p.calibrated_probability,p.probability_status,
                      c.ipc1,c.ipc2,c.target_type FROM fusion_predictions p JOIN fusion_candidates c
               ON c.candidate_id=p.candidate_id JOIN feature_runs f ON f.feature_run_id=c.feature_run_id
               JOIN network_runs n ON n.network_run_id=f.network_run_id WHERE n.project_id=?
               ORDER BY p.rank LIMIT 100""", (graph.context.project_id,),
        ).fetchall()]
    evidence_ids = [*snapshot["record_ids"]["patents"], *snapshot["record_ids"]["papers"]]
    initial = {**payload.initial_state,
               "snapshot_ref": {"artifact_type": "evidence_snapshot", "artifact_id": snapshot["checksum"],
                                  "checksum": snapshot["checksum"], "schema_version": "v3"},
               "frozen_contract": {"evidence_ids": evidence_ids, "ipc_codes": codes,
                                    "forecast_nodes": snapshot["research_contract"]["target_years"]},
               "candidate_refs": predictions or payload.initial_state.get("candidate_refs", []),
               "evidence_tasks": ([{"id": "patents", "kind": "patent", "evidence_ids": snapshot["record_ids"]["patents"]}]
                                  if snapshot["record_ids"]["patents"] else []) +
                                 ([{"id": "papers", "kind": "paper", "evidence_ids": snapshot["record_ids"]["papers"]}]
                                  if snapshot["record_ids"]["papers"] else [])}
    return graph.start(initial)


@router.get("/graph/jobs/{job_id}")
def graph_status(job_id: str):
    job = repository.get_forecast_job(job_id)
    if not job or not job.get("graph_thread_id"):
        raise HTTPException(status_code=404, detail="图任务不存在")
    return _graph(job_id).checkpointer.load(job["graph_thread_id"])


@router.get("/graph/jobs/{job_id}/events")
def graph_events(job_id: str, after: str = ""):
    job = repository.get_forecast_job(job_id)
    if not job or not job.get("graph_thread_id"):
        raise HTTPException(status_code=404, detail="图任务不存在")
    with repository.db.connect() as connection:
        rows = [dict(row) for row in connection.execute(
            """SELECT * FROM graph_node_events WHERE thread_id=? AND event_id>?
               ORDER BY created_at,event_id LIMIT 500""", (job["graph_thread_id"], after)
        ).fetchall()]
    return {"items": rows, "cursor": rows[-1]["event_id"] if rows else after}


@router.post("/graph/jobs/{job_id}/reviews/{review_node}")
def graph_review(job_id: str, review_node: str, payload: ReviewDecision):
    job = repository.get_forecast_job(job_id)
    if not job or not job.get("graph_thread_id"):
        raise HTTPException(status_code=404, detail="图任务不存在")
    try:
        return _graph(job_id).decide(job["graph_thread_id"], review_node,
                                     payload.decision, payload.after, payload.reason, payload.reviewer)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/graph/jobs/{job_id}/{action}")
def graph_action(job_id: str, action: str):
    job = repository.get_forecast_job(job_id)
    if not job or not job.get("graph_thread_id"):
        raise HTTPException(status_code=404, detail="图任务不存在")
    graph = _graph(job_id)
    if action == "resume":
        return graph.run(job["graph_thread_id"])
    if action == "cancel":
        return graph.cancel(job["graph_thread_id"])
    if action == "abandon":
        return graph.abandon(job["graph_thread_id"])
    if action == "retry":
        try:
            return graph.retry(job["graph_thread_id"])
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise HTTPException(status_code=422, detail="图操作无效")


@router.get("/feature-runs/{feature_run_id}/definitions")
def feature_definitions(feature_run_id: str):
    with repository.db.connect() as connection:
        row = connection.execute(
            """SELECT feature_run_id,schema_version,cutoff_year,target_type,
                      feature_definitions_json FROM feature_runs WHERE feature_run_id=?""",
            (feature_run_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="特征运行不存在")
    result = dict(row)
    result["definitions"] = json.loads(result.pop("feature_definitions_json"))
    return result


@router.get("/feature-runs/{feature_run_id}/candidates")
def feature_candidates(
    feature_run_id: str, page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200), target_type: Optional[str] = None,
):
    clauses, values = ["c.feature_run_id=?"], [feature_run_id]
    if target_type:
        clauses.append("c.target_type=?")
        values.append(target_type)
    where = " AND ".join(clauses)
    with repository.db.connect() as connection:
        total = int(connection.execute(
            "SELECT COUNT(*) FROM fusion_candidates c WHERE " + where, values
        ).fetchone()[0])
        candidate_rows = connection.execute(
            """SELECT c.candidate_id FROM fusion_candidates c WHERE %s
               ORDER BY c.ipc1,c.ipc2,c.candidate_id LIMIT ? OFFSET ?""" % where,
            [*values, page_size, (page - 1) * page_size],
        ).fetchall()
        ids = [row["candidate_id"] for row in candidate_rows]
        if not ids:
            return {"items": [], "total": total, "page": page, "page_size": page_size}
        placeholders = ",".join("?" for _ in ids)
        rows = connection.execute(
            """SELECT c.candidate_id,c.ipc1,c.ipc2,c.target_type,c.eligible,
                      c.exclusion_reason,f.feature_name,f.feature_value,
                      f.feature_status,f.lineage_json
               FROM fusion_candidates c LEFT JOIN fusion_features f
               ON f.candidate_id=c.candidate_id WHERE c.candidate_id IN (%s)
               ORDER BY c.ipc1,c.ipc2,f.feature_name""" % placeholders,
            ids,
        ).fetchall()
    items = {}
    for row in rows:
        item = items.setdefault(row["candidate_id"], {
            "candidate_id": row["candidate_id"], "ipc1": row["ipc1"], "ipc2": row["ipc2"],
            "target_type": row["target_type"], "eligible": bool(row["eligible"]),
            "exclusion_reason": row["exclusion_reason"], "features": {}, "lineage": {},
        })
        if row["feature_name"]:
            item["features"][row["feature_name"]] = row["feature_value"]
            item["lineage"][row["feature_name"]] = json.loads(row["lineage_json"])
    values_list = list(items.values())
    return {"items": values_list, "total": total, "page": page, "page_size": page_size}
