# -*- coding: utf-8 -*-
"""FastAPI entry for legacy, discovery, and thesis forecasting modes."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from src.forecast import service
from src.api.library_routes import router as library_router
from src.api.project_routes import router as project_router
from src.api.research_routes import router as research_router
from src.api.technology_routes import router as technology_router
from src.api.thesis_routes import router as thesis_router
from src.api.schemas import (
    CandidateTopic, CandidateTopicCreate, CandidateTopicUpdate, DocumentCreate,
    DocumentInfo, NormalizeTopicsRequest, TopicExtractionRequest,
)
from src.api.storage import WorkbenchStorage
from src.api.topic_service import (
    _clean_text, extract_topics_from_document, normalize_topic,
    persist_extracted_topics, refine_topics_with_llm,
)

app = FastAPI(title="智能建造 2040 技术预测系统", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(library_router)
app.include_router(project_router)
app.include_router(technology_router)
app.include_router(research_router)
app.include_router(thesis_router)
storage = WorkbenchStorage()


@app.middleware("http")
async def add_legacy_api_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if (path.startswith("/api/documents")
            or (path.startswith("/api/topics") and not path.startswith("/api/projects"))
            or (path == "/api/forecast/jobs" and request.method == "POST")):
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = "Fri, 01 Jan 2027 00:00:00 GMT"
        response.headers["Link"] = '</docs#tag/forecast-projects>; rel="successor-version"'
    return response


def _joined_project_job(repository, job_id: str) -> Dict[str, Any]:
    """Merge DB status with recoverable legacy files and report missing artifacts."""
    database_job = repository.get_forecast_job(job_id)
    if not database_job:
        raise ValueError("预测任务不存在")
    file_job = storage.get_job(job_id) or {}
    required = ("job.json", "result.json")
    missing = [name for name in required if not (storage.jobs_dir / job_id / name).exists()]
    result = {**database_job, **file_job}
    result["missing_artifacts"] = missing
    result["artifact_health"] = "degraded" if missing else database_job.get("artifact_health", "ready")
    return result


def reconcile_forecast_workers() -> None:
    """Mark file-backed jobs left running across process restart as interrupted."""
    from src.api.project_routes import repository as project_repository
    with project_repository.db.connect() as connection:
        job_ids = [row[0] for row in connection.execute(
            "SELECT job_id FROM forecast_jobs WHERE status IN ('queued','running','cancelling')"
        ).fetchall()]
    for job_id in job_ids:
        file_job = storage.get_job(job_id)
        if not file_job or file_job.get("status") not in {"queued", "running", "cancelling"}:
            continue
        file_job.update({"status": "failed", "error": "服务重启导致工作线程中断",
                         "stage": "interrupted"})
        storage.save_job(job_id, file_job)
        project_repository.update_forecast_job_status(
            job_id, "failed", current_stage="interrupted",
            error_code="worker_interrupted", error_message="服务重启导致工作线程中断",
            artifact_health="degraded",
        )


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "forecast-2040", "paradigm": "think-and-execute"}


@app.get("/api/seed-topics")
def seed_topics() -> dict:
    evidence = service.load_seed_evidence()
    return {
        "items": [e.model_dump() for e in evidence],
        "total": len(evidence),
    }


@app.post("/api/documents", response_model=DocumentInfo, status_code=201)
def create_document(payload: DocumentCreate) -> Dict[str, Any]:
    document = {
        "document_id": "doc_%s_%s" % (
            datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"), uuid4().hex[:6]),
        "title": payload.title.strip(), "content": payload.content,
        "cleaned_content": _clean_text(payload.content), "source_type": payload.source_type,
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
    values: List[Dict[str, Any]] = []
    for document_id in payload.document_ids:
        document = storage.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="文档不存在: %s" % document_id)
        candidates = extract_topics_from_document(
            document["cleaned_content"], document_id,
            include_seed_topics=payload.seed_topics == "use_existing",
        )
        if payload.extraction_mode == "rules_then_llm":
            candidates = refine_topics_with_llm(candidates, document["cleaned_content"])
        values.extend(candidates)
    return persist_extracted_topics(storage, values)


@app.get("/api/topics", response_model=List[CandidateTopic])
def list_topics() -> List[Dict[str, Any]]:
    return storage.list_topics()


@app.post("/api/topics", response_model=CandidateTopic, status_code=201)
def create_topic(payload: CandidateTopicCreate) -> Dict[str, Any]:
    topic = payload.model_dump()
    topic.update({"topic_id": "topic_" + uuid4().hex[:12], "evidence_score": 0,
                  "requires_review": not bool(topic.get("ipc_evidence") or topic.get("sample_abstracts"))})
    topics = storage.list_topics(); topics.append(topic); storage.save_topics(topics)
    return topic


@app.patch("/api/topics/{topic_id}", response_model=CandidateTopic)
def update_topic(topic_id: str, payload: CandidateTopicUpdate) -> Dict[str, Any]:
    topics = storage.list_topics()
    for index, topic in enumerate(topics):
        if topic["topic_id"] == topic_id:
            topic.update(payload.model_dump(exclude_unset=True)); topics[index] = topic
            storage.save_topics(topics)
            return topic
    raise HTTPException(status_code=404, detail="技术主题不存在")


@app.post("/api/topics/normalize")
def normalize_topics(payload: NormalizeTopicsRequest = NormalizeTopicsRequest()) -> Dict[str, Any]:
    selected = set(payload.topic_ids or [])
    topics = [item for item in storage.list_topics()
              if item.get("selected") and (not selected or item["topic_id"] in selected)]
    return {"round1_inputs": [normalize_topic(item) for item in topics]}


def _legacy_result(job_id: str) -> Dict[str, Any]:
    if not storage.get_job(job_id):
        raise HTTPException(status_code=404, detail="预测任务不存在")
    result = storage.get_job_artifact(job_id, "result.json")
    if not result:
        raise HTTPException(status_code=409, detail="预测结果尚未生成")
    return result


def _topic_view(topic: Dict[str, Any], roadmap: Dict[str, Any], assets: List[Dict[str, Any]]) -> Dict[str, Any]:
    stages = roadmap.get("roadmap", {}) if roadmap else {}
    milestones = [item for stage in stages.values() for item in stage.get("milestones", [])]
    terminal = [item.get("trl_level") for item in stages.get("2040", {}).get("milestones", [])
                if isinstance(item.get("trl_level"), (int, float))]
    uncertainty = [item.get("uncertainty_level", "medium") for item in milestones]
    dominant = max(("low", "medium", "high"), key=uncertainty.count, default="medium")
    return {"topic_id": topic.get("topic_id"), "topic_name": topic.get("topic_name"),
            "keywords": topic.get("keywords", []), "evidence": topic.get("ipc_evidence", []),
            "milestone_count": len(milestones),
            "terminal_trl": round(sum(terminal) / len(terminal), 1) if terminal else None,
            "dominant_uncertainty": dominant,
            "available_years": [year for year in ("2030", "2035", "2040") if stages.get(year)],
            "stages": stages, "assets": assets,
            "legacy_semantics": "TRL/confidence are retained legacy fields"}


@app.get("/api/forecast/jobs/{job_id}/topics")
def legacy_job_topics(job_id: str, q: str = "") -> Dict[str, Any]:
    result = _legacy_result(job_id)
    asset_index = storage.get_job_artifact(job_id, "assets.json", {"assets": []})
    roadmaps = {item.get("topic_name"): item for item in result.get("per_topic_roadmaps", [])}
    items = []
    for topic in result.get("topics", []):
        assets = [item for item in asset_index.get("assets", [])
                  if item.get("topic_id") == topic.get("topic_id")]
        value = _topic_view(topic, roadmaps.get(topic.get("topic_name"), {}), assets)
        if q and q.lower() not in str(value["topic_name"]).lower() and not any(
                q.lower() in str(key).lower() for key in value["keywords"]):
            continue
        value = {key: item for key, item in value.items() if key not in {"stages", "evidence", "assets"}}
        value.update({"asset_count": len(assets), "status": "completed"}); items.append(value)
    return {"items": items, "total": len(items)}


@app.get("/api/forecast/jobs/{job_id}/topics/{topic_id}")
def legacy_job_topic(job_id: str, topic_id: str) -> Dict[str, Any]:
    result = _legacy_result(job_id)
    topic = next((item for item in result.get("topics", []) if item.get("topic_id") == topic_id), None)
    if not topic:
        raise HTTPException(status_code=404, detail="预测主题不存在")
    roadmap = next((item for item in result.get("per_topic_roadmaps", [])
                    if item.get("topic_name") == topic.get("topic_name")), {})
    assets = [item for item in storage.get_job_artifact(job_id, "assets.json", {"assets": []}).get("assets", [])
              if item.get("topic_id") == topic_id]
    return _topic_view(topic, roadmap, assets)


@app.get("/api/forecast/jobs/{job_id}/assets/{asset_id}")
def legacy_job_asset(job_id: str, asset_id: str, download: bool = False):
    _legacy_result(job_id)
    index = storage.get_job_artifact(job_id, "assets.json", {"assets": []})
    asset = next((item for item in index.get("assets", []) if item.get("asset_id") == asset_id), None)
    if not asset:
        raise HTTPException(status_code=404, detail="图表资产不存在")
    assets_dir = (storage.job_dir(job_id) / "assets").resolve()
    path = (assets_dir / str(asset.get("relative_path", ""))).resolve()
    try:
        safe = os.path.commonpath([str(path), str(assets_dir)]) == str(assets_dir)
    except ValueError:
        safe = False
    if not safe or not path.is_file():
        raise HTTPException(status_code=404, detail="图表文件不可用")
    return FileResponse(path, media_type=asset.get("media_type", "application/octet-stream"),
                        filename=asset.get("filename") if download else None,
                        content_disposition_type="attachment" if download else "inline")


@app.post("/api/forecast", status_code=202)
def start_forecast() -> dict:
    return service.create_job()


@app.get("/api/forecast/{job_id}")
def job_status(job_id: str) -> dict:
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="预测任务不存在")
    return job


@app.get("/api/forecast/{job_id}/result")
def job_result(job_id: str) -> dict:
    result = service.get_result(job_id)
    if not result:
        raise HTTPException(status_code=409, detail="结果尚未生成")
    return result
