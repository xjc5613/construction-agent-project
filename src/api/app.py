# -*- coding:utf-8 -*-
from datetime import datetime, timezone
from threading import Thread
from typing import Any, Dict, List
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from config.settings import ENABLE_WORKBENCH_API

from .asset_service import filter_assets, find_asset, resolve_asset_file
from .forecast_service import create_job, run_forecast_job
from .library_routes import router as library_router
from .project_routes import router as project_router
from .schemas import (
    CandidateTopic,
    CandidateTopicCreate,
    CandidateTopicUpdate,
    DocumentCreate,
    DocumentInfo,
    EvidenceGroundedTopicInput,
    ForecastJobCreate,
    ForecastJobStatus,
    ForecastResult,
    NormalizeTopicsRequest,
    ProjectForecastJobCreate,
    TopicExtractionRequest,
)
from .storage import WorkbenchStorage
from .topic_service import (
    _clean_text,
    extract_topics_from_document,
    normalize_topic,
    persist_extracted_topics,
    refine_topics_with_llm,
)

storage = WorkbenchStorage()
app = FastAPI(title="智能建造技术预测工作台 API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(library_router)
app.include_router(project_router)


@app.middleware("http")
async def add_legacy_api_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    is_legacy = (
        path.startswith("/api/documents")
        or (path.startswith("/api/topics") and not path.startswith("/api/projects"))
        or (path == "/api/forecast/jobs" and request.method == "POST")
    )
    if is_legacy:
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = "Fri, 01 Jan 2027 00:00:00 GMT"
        response.headers["Link"] = '</docs#tag/forecast-projects>; rel="successor-version"'
    return response


def _topic_or_404(topic_id: str) -> Dict[str, Any]:
    for topic in storage.list_topics():
        if topic["topic_id"] == topic_id:
            return topic
    raise HTTPException(status_code=404, detail="技术主题不存在")


@app.get("/api/health")
def health() -> Dict[str, bool]:
    return {"ok": ENABLE_WORKBENCH_API}


@app.post("/api/documents", response_model=DocumentInfo, status_code=201)
def create_document(payload: DocumentCreate) -> Dict[str, Any]:
    document_id = f"doc_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
    document = {
        "document_id": document_id,
        "title": payload.title.strip(),
        "content": payload.content,
        "cleaned_content": _clean_text(payload.content),
        "source_type": payload.source_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    storage.save_document(document)
    return document


@app.get("/api/documents/{document_id}", response_model=DocumentInfo)
def get_document(document_id: str) -> Dict[str, Any]:
    document = storage.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    return document


@app.post("/api/topics/extract", response_model=List[CandidateTopic])
def extract_topics(payload: TopicExtractionRequest) -> List[Dict[str, Any]]:
    all_topics: List[Dict[str, Any]] = []
    for document_id in payload.document_ids:
        document = storage.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail=f"文档不存在: {document_id}")
        candidates = extract_topics_from_document(
            document["cleaned_content"],
            document_id,
            include_seed_topics=payload.seed_topics == "use_existing",
        )
        if payload.extraction_mode == "rules_then_llm":
            candidates = refine_topics_with_llm(candidates, document["cleaned_content"])
        all_topics.extend(candidates)
    return persist_extracted_topics(storage, all_topics)


@app.get("/api/topics", response_model=List[CandidateTopic])
def list_topics() -> List[Dict[str, Any]]:
    return storage.list_topics()


@app.post("/api/topics", response_model=CandidateTopic, status_code=201)
def create_topic(payload: CandidateTopicCreate) -> Dict[str, Any]:
    topic = payload.model_dump()
    topic.update({
        "topic_id": f"topic_{uuid4().hex[:12]}",
        "evidence_score": 0,
        "requires_review": not bool(topic.get("ipc_evidence") or topic.get("sample_abstracts")),
    })
    topics = storage.list_topics()
    topics.append(topic)
    storage.save_topics(topics)
    return topic


@app.patch("/api/topics/{topic_id}", response_model=CandidateTopic)
def update_topic(topic_id: str, payload: CandidateTopicUpdate) -> Dict[str, Any]:
    topics = storage.list_topics()
    for index, topic in enumerate(topics):
        if topic["topic_id"] != topic_id:
            continue
        updates = payload.model_dump(exclude_unset=True)
        topic.update(updates)
        topics[index] = topic
        storage.save_topics(topics)
        return topic
    raise HTTPException(status_code=404, detail="技术主题不存在")


@app.post("/api/topics/normalize")
def normalize_topics(payload: NormalizeTopicsRequest = NormalizeTopicsRequest()) -> Dict[str, Any]:
    selected_ids = set(payload.topic_ids or [])
    topics = [
        topic for topic in storage.list_topics()
        if topic.get("selected") and (not selected_ids or topic["topic_id"] in selected_ids)
    ]
    return {"round1_inputs": [normalize_topic(topic) for topic in topics]}


@app.post("/api/forecast/jobs", response_model=ForecastJobStatus, status_code=202)
def create_forecast_job(payload: ForecastJobCreate) -> Dict[str, Any]:
    missing = [topic_id for topic_id in payload.topic_ids if not any(topic["topic_id"] == topic_id for topic in storage.list_topics())]
    if missing:
        raise HTTPException(status_code=404, detail=f"技术主题不存在: {', '.join(missing)}")
    job = create_job(storage, payload.topic_ids, payload.options.model_dump())
    Thread(target=run_forecast_job, args=(storage, job["job_id"]), daemon=True).start()
    return job


@app.post(
    "/api/projects/{project_id}/forecast-jobs",
    response_model=ForecastJobStatus,
    status_code=202,
)
def create_project_forecast_job(
    project_id: str, payload: ProjectForecastJobCreate
) -> Dict[str, Any]:
    from .project_routes import repository as project_repository

    project = project_repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="预测项目不存在")
    topics, packages, missing = [], [], []
    for topic_id in payload.topic_ids:
        topic = project_repository.get_topic(topic_id)
        if (
            not topic
            or topic["project_id"] != project_id
            or topic["status"] not in {"confirmed", "evidence_ready"}
            or topic["requires_review"]
        ):
            missing.append(f"{topic_id}: 主题未确认")
            continue
        package = project_repository.latest_package_for_topic(topic_id)
        if not package:
            missing.append(f"{topic['topic_name']}: 尚未检索证据")
            continue
        if not package["quality"].get("sufficient"):
            missing.append(
                f"{topic['topic_name']}: {', '.join(package['quality'].get('missing', []))}"
            )
        active_items = [
            item for item in package["items"] if not item.get("excluded")
        ]
        ipc_items = [
            item for item in active_items if item["evidence_type"] == "ipc_metric"
        ]
        fusion_items = [
            item for item in active_items if item["evidence_type"] == "ipc_fusion"
        ]
        paper_items = [
            item for item in active_items if item["evidence_type"] == "paper"
        ]
        topics.append({
            "topic_id": topic_id,
            "topic_name": topic["topic_name"],
            "keywords": topic["keywords"],
            "example": topic.get("description", ""),
            "operator_notes": topic.get("operator_notes", ""),
            "selected": True,
            "ipc_evidence": [
                {
                    "ipc": item["metadata"].get("ipc_code", ""),
                    "trend": item["content"],
                    "quote": item["content"],
                    "document_id": item["evidence_id"],
                }
                for item in ipc_items
            ],
            "ipc_trend": "\n".join(item["content"] for item in ipc_items),
            "fusion_pairs": [
                {
                    "ipc1": item["metadata"].get("ipc1", ""),
                    "ipc2": item["metadata"].get("ipc2", ""),
                    "prob": item["metadata"].get("probability", 0),
                }
                for item in fusion_items
            ],
            "sample_abstracts": [item["content"] for item in paper_items],
            "evidence_score": package["quality"].get("score", 0),
            "evidence_package": package,
        })
        packages.append(package)
    topics = [
        EvidenceGroundedTopicInput.model_validate(topic).model_dump()
        for topic in topics
    ]
    if not topics:
        raise HTTPException(status_code=422, detail="没有可用于预测的已确认主题和证据包")
    evidence_limited = bool(missing)
    if evidence_limited and (
        not payload.override_evidence_gate or not payload.override_reason
    ):
        raise HTTPException(
            status_code=422,
            detail={"message": "证据完整性门槛未通过", "missing": missing},
        )
    snapshot = {
        "project_id": project_id,
        "project_name": project["name"],
        "time_nodes": ["2030", "2035", "2040"],
        "topics": topics,
        "packages": packages,
        "evidence_limited": evidence_limited,
        "override_reason": payload.override_reason,
    }
    job = create_job(
        storage,
        payload.topic_ids,
        payload.options.model_dump(),
        project_id=project_id,
        topic_snapshot=topics,
        evidence_snapshot=snapshot,
        evidence_limited=evidence_limited,
        override_reason=payload.override_reason,
    )
    for package in packages:
        project_repository.freeze_package(
            package["package_id"], job["evidence_snapshot_checksum"]
        )
    project_repository.register_forecast_job(
        job["job_id"],
        project_id,
        str(storage.job_dir(job["job_id"]) / "evidence_snapshot.json"),
        topics,
        evidence_limited,
        payload.override_reason,
    )
    project_repository.update_project_status(project_id, "forecasting")
    Thread(target=run_forecast_job, args=(storage, job["job_id"]), daemon=True).start()
    return job


@app.get("/api/forecast/jobs/{job_id}", response_model=ForecastJobStatus)
def get_forecast_job(job_id: str) -> Dict[str, Any]:
    job = storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="预测任务不存在")
    return job


@app.get("/api/forecast/jobs/{job_id}/results", response_model=ForecastResult)
def get_forecast_results(job_id: str) -> Dict[str, Any]:
    result = storage.get_job_artifact(job_id, "result.json")
    if not result:
        raise HTTPException(status_code=409, detail="预测结果尚未生成")
    return result


@app.get("/api/forecast/jobs/{job_id}/charts")
def get_forecast_charts(job_id: str) -> Dict[str, Any]:
    charts = storage.get_job_artifact(job_id, "charts.json")
    if not charts:
        raise HTTPException(status_code=409, detail="图表数据尚未生成")
    return charts


def _job_result_or_404(job_id: str) -> Dict[str, Any]:
    if not storage.get_job(job_id):
        raise HTTPException(status_code=404, detail="预测任务不存在")
    result = storage.get_job_artifact(job_id, "result.json")
    if not result:
        raise HTTPException(status_code=409, detail="预测结果尚未生成")
    return result


def _topic_view(topic: Dict[str, Any], roadmap: Dict[str, Any], assets: List[Dict[str, Any]]) -> Dict[str, Any]:
    stages = roadmap.get("roadmap", {}) if roadmap else {}
    milestones = [
        milestone
        for stage in stages.values()
        for milestone in stage.get("milestones", [])
    ]
    terminal_stage = stages.get("2040", {})
    terminal_trls = [
        milestone.get("trl_level") for milestone in terminal_stage.get("milestones", [])
        if isinstance(milestone.get("trl_level"), (int, float))
    ]
    uncertainty_values = [
        milestone.get("uncertainty_level", "medium") for milestone in milestones
    ]
    dominant_uncertainty = max(
        ("low", "medium", "high"),
        key=lambda level: uncertainty_values.count(level),
        default="medium",
    )
    return {
        "topic_id": topic.get("topic_id"),
        "topic_name": topic.get("topic_name"),
        "keywords": topic.get("keywords", []),
        "evidence": topic.get("ipc_evidence", []),
        "milestone_count": len(milestones),
        "terminal_trl": round(sum(terminal_trls) / len(terminal_trls), 1) if terminal_trls else None,
        "dominant_uncertainty": dominant_uncertainty,
        "available_years": [year for year in ("2030", "2035", "2040") if stages.get(year)],
        "stages": stages,
        "assets": assets,
    }


@app.get("/api/forecast/jobs/{job_id}/topics")
def list_forecast_topics(
    job_id: str,
    q: str = "",
    year: str = Query("", pattern="^(|2030|2035|2040)$"),
    uncertainty: str = Query("", pattern="^(|low|medium|high)$"),
    min_trl: float = Query(0, ge=0, le=9),
) -> Dict[str, Any]:
    result = _job_result_or_404(job_id)
    asset_index = storage.get_job_artifact(job_id, "assets.json", {"assets": []})
    roadmaps_by_name = {
        roadmap.get("topic_name"): roadmap for roadmap in result.get("per_topic_roadmaps", [])
    }
    items = []
    for topic in result.get("topics", []):
        topic_assets = filter_assets(asset_index, topic_id=topic.get("topic_id"))
        view = _topic_view(topic, roadmaps_by_name.get(topic.get("topic_name"), {}), topic_assets)
        if q and q.lower() not in str(view["topic_name"]).lower() and not any(q.lower() in str(keyword).lower() for keyword in view["keywords"]):
            continue
        if year and year not in view["available_years"]:
            continue
        if uncertainty and view["dominant_uncertainty"] != uncertainty:
            continue
        if view["terminal_trl"] is not None and view["terminal_trl"] < min_trl:
            continue
        if min_trl and view["terminal_trl"] is None:
            continue
        items.append({
            key: value for key, value in view.items() if key not in {"stages", "evidence", "assets"}
        } | {"asset_count": len(topic_assets), "status": "completed"})
    return {"items": items, "total": len(items)}


@app.get("/api/forecast/jobs/{job_id}/topics/{topic_id}")
def get_forecast_topic(job_id: str, topic_id: str) -> Dict[str, Any]:
    result = _job_result_or_404(job_id)
    topic = next((item for item in result.get("topics", []) if item.get("topic_id") == topic_id), None)
    if not topic:
        raise HTTPException(status_code=404, detail="预测主题不存在")
    roadmap = next(
        (item for item in result.get("per_topic_roadmaps", []) if item.get("topic_name") == topic.get("topic_name")),
        {},
    )
    asset_index = storage.get_job_artifact(job_id, "assets.json", {"assets": []})
    return _topic_view(topic, roadmap, filter_assets(asset_index, topic_id=topic_id))


@app.get("/api/forecast/jobs/{job_id}/assets")
def list_forecast_assets(
    job_id: str,
    topic_id: str = "",
    kind: str = Query("", pattern="^(|combined|timeline|radar|comparison)$"),
) -> Dict[str, Any]:
    _job_result_or_404(job_id)
    asset_index = storage.get_job_artifact(job_id, "assets.json", {"assets": [], "failed_assets": []})
    assets = filter_assets(asset_index, topic_id=topic_id or None, kind=kind or None)
    return {"items": assets, "total": len(assets), "failed_assets": asset_index.get("failed_assets", [])}


@app.get("/api/forecast/jobs/{job_id}/assets/{asset_id}")
def get_forecast_asset(job_id: str, asset_id: str, download: bool = False):
    _job_result_or_404(job_id)
    asset_index = storage.get_job_artifact(job_id, "assets.json", {"assets": []})
    asset = find_asset(asset_index, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="图表资产不存在")
    path = resolve_asset_file(storage.job_dir(job_id), asset)
    if not path:
        raise HTTPException(status_code=404, detail="图表文件不可用")
    return FileResponse(
        path,
        media_type=asset.get("media_type", "image/png"),
        filename=asset.get("filename") if download else None,
        content_disposition_type="attachment" if download else "inline",
    )


@app.get("/api/forecast/jobs/{job_id}/export")
def export_forecast(job_id: str, format: str = Query("markdown", pattern="^(markdown|json)$")):
    if format == "json":
        result = storage.get_job_artifact(job_id, "result.json")
        if not result:
            raise HTTPException(status_code=409, detail="预测结果尚未生成")
        return JSONResponse(result)
    path = storage.job_dir(job_id) / "report.md"
    if not path.exists():
        raise HTTPException(status_code=409, detail="报告尚未生成")
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")
