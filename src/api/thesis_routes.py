# -*- coding: utf-8 -*-
"""HTTP contracts for Chapter 4 packets and Chapter 5 claim deliberation."""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.library import LibraryRepository
from src.research.evidence_packets import EvidencePacketService
from src.research.evolution_schemas import ThesisJobRequest
from src.research.repository import canonical_checksum
from src.research.thesis_repository import ThesisRepository
from src.research.thesis_runtime import build_thesis_graph


router = APIRouter(prefix="/api/thesis", tags=["thesis-evolution-forecast"])
repository = LibraryRepository()


def _services():
    thesis = ThesisRepository(repository.db)
    return thesis, EvidencePacketService(thesis)


class PacketCreate(BaseModel):
    packet_id: str = ""
    payload: Dict[str, Any]


class DiscoveryImport(BaseModel):
    discovery: Dict[str, Any]
    object_ids: list[str] = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    source_locator: Dict[str, Any]


class GateDecision(BaseModel):
    decision: str
    reason: str = ""
    reviewer: str = "local-user"
    after: Dict[str, Any] = Field(default_factory=dict)


@router.post("/projects/{project_id}/evolution-packets", status_code=201)
def create_packet(project_id: str, request: PacketCreate):
    if not repository.get_project(project_id):
        raise HTTPException(status_code=404, detail="预测项目不存在")
    _, service = _services()
    try:
        return service.create_from_draft(request.payload, project_id, request.packet_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/evolution-packets/{packet_id}")
def get_packet(packet_id: str, version: Optional[int] = None):
    thesis, _ = _services()
    value = thesis.get_packet(packet_id, version)
    if not value:
        raise HTTPException(status_code=404, detail="演化证据包不存在")
    return value


@router.get("/evolution-packets/{packet_id}/versions")
def packet_versions(packet_id: str):
    thesis, _ = _services()
    return {"items": thesis.list_packet_versions(packet_id)}


@router.post("/evolution-packet-versions/{packet_version_id}/review")
def review_packet(packet_version_id: str):
    _, service = _services()
    try:
        return service.review(packet_version_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/evolution-packet-versions/{packet_version_id}/freeze")
def freeze_packet(packet_version_id: str):
    _, service = _services()
    try:
        return service.freeze(packet_version_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/evolution-packet-versions/{left}/diff/{right}")
def diff_packets(left: str, right: str):
    _, service = _services()
    try:
        return service.diff(left, right)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/evolution-packets/{packet_id}/derived-discovery", status_code=201)
def import_discovery(packet_id: str, request: DiscoveryImport):
    _, service = _services()
    try:
        return service.import_reviewed_discovery(
            packet_id, request.discovery, request.object_ids,
            request.reviewer, request.source_locator,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/projects/{project_id}/jobs", status_code=201)
def start_thesis_job(project_id: str, request: ThesisJobRequest):
    if request.mode != "thesis_evolution_forecast":
        raise HTTPException(status_code=422, detail="该入口仅启动论文演化研判模式")
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="预测项目不存在")
    thesis, _ = _services()
    packet = thesis.get_packet(request.packet_id, request.packet_version)
    if not packet or packet["status"] != "frozen":
        raise HTTPException(status_code=409, detail="必须选择已审核并冻结的演化证据包")
    if packet["project_id"] != project_id:
        raise HTTPException(status_code=409, detail="证据包不属于该项目")
    job_id = "thesis_" + uuid4().hex[:16]
    checksum = canonical_checksum(request.model_dump())
    try:
        repository.reserve_forecast_job(
            job_id, project_id, request_checksum=checksum,
            idempotency_key=f"thesis:{project_id}:{checksum}",
            request=request.model_dump(), options={
                **request.model_options, "revision_limit": request.revision_limit,
                "compute_concurrency": request.compute_concurrency,
                "run_budget": request.run_budget,
            },
        )
    except sqlite3.IntegrityError as exc:
        existing = repository.get_forecast_job_by_idempotency(f"thesis:{project_id}:{checksum}")
        if existing:
            return {"job": existing, "state": build_thesis_graph(repository, existing["job_id"]).resume()}
        raise HTTPException(status_code=409, detail="项目已有活动任务") from exc
    with repository.db.transaction() as connection:
        connection.execute(
            """UPDATE forecast_jobs SET job_mode='thesis_evolution_forecast',
               evolution_packet_version_id=?,research_contract_version=3,baseline_year=2025,
               run_manifest_json=?,status='running',artifact_health='ready',current_stage='validate_packet'
               WHERE job_id=?""",
            (packet["packet_version_id"],
             json.dumps({"packet_checksum": packet["checksum"],
                         "revision_limit": request.revision_limit,
                         "run_budget": request.run_budget}, ensure_ascii=False, sort_keys=True),
             job_id),
        )
    graph = build_thesis_graph(repository, job_id)
    try:
        state = graph.start(packet["packet_version_id"])
    except Exception as exc:
        repository.update_forecast_job_status(
            job_id, "failed", current_stage="thesis_graph", error_code="thesis_graph_failed",
            error_message=str(exc), artifact_health="partial")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"job": repository.get_forecast_job(job_id), "state": state}


@router.get("/jobs/{job_id}")
def thesis_job(job_id: str):
    job = repository.get_forecast_job(job_id)
    if not job or job.get("job_mode") != "thesis_evolution_forecast":
        raise HTTPException(status_code=404, detail="论文研判任务不存在")
    graph = build_thesis_graph(repository, job_id)
    state = graph.checkpointer.load(job.get("graph_thread_id", ""))
    return {"job": job, "state": state}


@router.get("/jobs/{job_id}/trace")
def claim_trace(job_id: str):
    thesis, _ = _services()
    return thesis.job_claim_trace(job_id)


@router.get("/jobs/{job_id}/claims/{claim_id}/lineage")
def claim_lineage(job_id: str, claim_id: str):
    thesis, _ = _services()
    items = thesis.get_claim_lineage(job_id, claim_id)
    if not items:
        raise HTTPException(status_code=404, detail="命题不存在")
    return {"items": items}


@router.get("/jobs/{job_id}/result")
def thesis_result(job_id: str):
    job = repository.get_forecast_job(job_id)
    if not job or job.get("job_mode") != "thesis_evolution_forecast":
        raise HTTPException(status_code=404, detail="论文研判任务不存在")
    thesis, _ = _services()
    packet = thesis.get_packet_version(job.get("evolution_packet_version_id", ""))
    graph = build_thesis_graph(repository, job_id)
    state = graph.checkpointer.load(job.get("graph_thread_id", "")) or {}
    return {
        "schema_version": "thesis-evolution-result-v1",
        "job": job,
        "packet": {
            "packet_version_id": packet.get("packet_version_id") if packet else None,
            "checksum": packet.get("checksum") if packet else None,
            "validation_summary": packet.get("payload", {}).get("validation_summary", {}) if packet else {},
            "mapping_attachments": packet.get("attachments", []) if packet else [],
        },
        "state": state,
        "trace": thesis.job_claim_trace(job_id),
        "semantic_note": "support_level、概率、评审一致性与TRL是相互独立的量。",
    }


@router.get("/jobs/{job_id}/export")
def export_thesis_result(job_id: str):
    """Research export with packet checksum and complete claim/review lineage."""
    return thesis_result(job_id)


@router.post("/jobs/{job_id}/reviews/{gate}")
def decide_gate(job_id: str, gate: str, request: GateDecision):
    try:
        return build_thesis_graph(repository, job_id).decide(
            gate, request.decision, request.reason, request.reviewer, request.after)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/resume")
def resume_job(job_id: str):
    try:
        return build_thesis_graph(repository, job_id).resume()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    try:
        return build_thesis_graph(repository, job_id).cancel()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
