# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.library import LibraryRepository
from src.retrieval import EvidenceRetrievalService

from .project_service import ProjectService

router = APIRouter(prefix="/api/projects", tags=["forecast-projects"])
repository = LibraryRepository()
project_service = ProjectService(repository)
retrieval_service = EvidenceRetrievalService(repository)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""


class ProjectStatusUpdate(BaseModel):
    status: str


class TextMaterialCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=1_000_000)


class ExtractRequest(BaseModel):
    material_ids: List[str] = Field(min_length=1)
    refine_with_llm: bool = True


class ProjectTopicCreate(BaseModel):
    topic_name: str = Field(min_length=1, max_length=120)
    description: str = ""
    keywords: List[str] = Field(default_factory=list)
    operator_notes: str = ""


class ProjectTopicUpdate(BaseModel):
    topic_name: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
    evidence: Optional[List[Dict[str, Any]]] = None
    fusion_pairs: Optional[List[Dict[str, Any]]] = None
    operator_notes: Optional[str] = None
    selected: Optional[bool] = None
    requires_review: Optional[bool] = None
    status: Optional[str] = None


class TopicMergeRequest(BaseModel):
    topic_ids: List[str] = Field(min_length=2)
    topic_name: str = Field(min_length=1, max_length=120)


class EvidenceRetrieveRequest(BaseModel):
    topic_id: str
    start_year: int = 2000
    end_year: int = 2025
    paper_limit: int = Field(20, ge=1, le=100)
    dataset_ids: List[str] = Field(default_factory=list)
    min_relevance: float = Field(0, ge=0, le=1)
    operator_notes: str = Field("", max_length=2000)


class EvidenceItemUpdate(BaseModel):
    excluded: bool
    reason: str = ""


@router.get("")
def list_projects():
    items = repository.list_projects()
    return {"items": items, "total": len(items)}


@router.post("", status_code=201)
def create_project(payload: ProjectCreate):
    return repository.create_project(payload.name, payload.description)


def _project_or_404(project_id: str) -> Dict[str, Any]:
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="预测项目不存在")
    return project


@router.get("/{project_id}")
def get_project(project_id: str):
    project = _project_or_404(project_id)
    project["materials"] = repository.list_materials(project_id)
    project["topics"] = repository.list_topics(project_id)
    return project


@router.patch("/{project_id}/status")
def update_project_status(project_id: str, payload: ProjectStatusUpdate):
    _project_or_404(project_id)
    allowed = {
        "draft", "material_ready", "topics_review", "evidence_review",
        "ready_to_forecast", "forecasting", "completed", "partial_failed",
        "failed", "archived",
    }
    if payload.status not in allowed:
        raise HTTPException(status_code=422, detail="预测项目状态无效")
    return repository.update_project_status(project_id, payload.status)


@router.post("/{project_id}/materials/text", status_code=201)
def add_text_material(project_id: str, payload: TextMaterialCreate):
    try:
        material = project_service.add_text_material(
            project_id, payload.title, payload.content
        )
        repository.update_project_status(project_id, "material_ready")
        return material
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{project_id}/materials/upload", status_code=201)
async def add_file_material(project_id: str, file: UploadFile = File(...)):
    try:
        material = project_service.add_file_material(
            project_id, file.filename or "upload", file.content_type or "", await file.read()
        )
        repository.update_project_status(project_id, "material_ready")
        return material
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{project_id}/materials")
def list_materials(project_id: str):
    _project_or_404(project_id)
    items = repository.list_materials(project_id)
    return {"items": items, "total": len(items)}


@router.get("/{project_id}/materials/{material_id}")
def get_material(project_id: str, material_id: str):
    material = repository.get_material(material_id)
    if not material or material["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="项目材料不存在")
    return material


@router.get("/{project_id}/materials/{material_id}/file")
def download_material(project_id: str, material_id: str):
    material = repository.get_material(material_id)
    if not material or material["project_id"] != project_id or not material["stored_path"]:
        raise HTTPException(status_code=404, detail="材料文件不存在")
    path = Path(material["stored_path"]).resolve()
    expected = (Path(path).parents[1]).resolve()
    if not path.is_file() or project_id not in path.parts or expected.name != project_id:
        raise HTTPException(status_code=404, detail="材料文件不可用")
    return FileResponse(path, filename=material["original_filename"])


@router.post("/{project_id}/topics/extract")
def extract_topics(project_id: str, payload: ExtractRequest):
    try:
        return project_service.extract_topics(
            project_id, payload.material_ids, payload.refine_with_llm
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{project_id}/topics")
def list_topics(project_id: str, include_deleted: bool = False):
    _project_or_404(project_id)
    items = repository.list_topics(project_id, include_deleted)
    return {"items": items, "total": len(items)}


@router.post("/{project_id}/topics", status_code=201)
def create_topic(project_id: str, payload: ProjectTopicCreate):
    _project_or_404(project_id)
    return repository.save_topic({
        "project_id": project_id, "topic_name": payload.topic_name,
        "description": payload.description, "keywords": payload.keywords,
        "operator_notes": payload.operator_notes, "status": "candidate",
        "requires_review": True, "selected": True,
    })


@router.patch("/{project_id}/topics/{topic_id}")
def update_topic(project_id: str, topic_id: str, payload: ProjectTopicUpdate):
    topic = repository.get_topic(topic_id)
    if not topic or topic["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="项目主题不存在")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("status") and changes["status"] not in {
        "candidate", "confirmed", "evidence_ready", "archived", "deleted", "merged"
    }:
        raise HTTPException(status_code=422, detail="项目主题状态无效")
    updated = repository.update_topic(topic_id, changes)
    return updated


@router.delete("/{project_id}/topics/{topic_id}")
def delete_topic(project_id: str, topic_id: str):
    topic = repository.get_topic(topic_id)
    if not topic or topic["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="项目主题不存在")
    return repository.update_topic(topic_id, {"status": "deleted", "selected": False})


@router.post("/{project_id}/topics/{topic_id}/archive")
def archive_topic(project_id: str, topic_id: str):
    topic = repository.get_topic(topic_id)
    if not topic or topic["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="项目主题不存在")
    if topic["status"] == "merged":
        raise HTTPException(status_code=409, detail="已合并主题不能归档")
    return repository.update_topic(
        topic_id, {"status": "archived", "selected": False}
    )


@router.post("/{project_id}/topics/{topic_id}/restore")
def restore_topic(project_id: str, topic_id: str):
    topic = repository.get_topic(topic_id)
    if not topic or topic["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="项目主题不存在")
    if topic["status"] not in {"archived", "deleted"}:
        raise HTTPException(status_code=409, detail="当前主题无需恢复")
    return repository.update_topic(
        topic_id,
        {
            "status": "candidate", "selected": True,
            "requires_review": True, "merged_into": None,
        },
    )


@router.post("/{project_id}/topics/{topic_id}/confirm")
def confirm_topic(project_id: str, topic_id: str):
    topic = repository.get_topic(topic_id)
    if not topic or topic["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="项目主题不存在")
    if not topic["topic_name"].strip():
        raise HTTPException(status_code=422, detail="主题名称不能为空")
    return repository.update_topic(
        topic_id, {"status": "confirmed", "requires_review": False, "selected": True}
    )


@router.post("/{project_id}/topics/merge", status_code=201)
def merge_topics(project_id: str, payload: TopicMergeRequest):
    topics = [repository.get_topic(topic_id) for topic_id in payload.topic_ids]
    if any(not topic or topic["project_id"] != project_id for topic in topics):
        raise HTTPException(status_code=404, detail="待合并主题不存在")
    keywords = list(dict.fromkeys(
        keyword for topic in topics for keyword in topic.get("keywords", [])
    ))
    evidence = [
        evidence for topic in topics for evidence in topic.get("evidence", [])
    ]
    fusions = [
        pair for topic in topics for pair in topic.get("fusion_pairs", [])
    ]
    merged = repository.save_topic({
        "project_id": project_id, "topic_name": payload.topic_name,
        "keywords": keywords, "evidence": evidence, "fusion_pairs": fusions,
        "status": "candidate", "requires_review": True, "selected": True,
    })
    for topic in topics:
        repository.update_topic(
            topic["topic_id"], {"status": "merged", "selected": False, "merged_into": merged["topic_id"]}
        )
    return merged


@router.post("/{project_id}/evidence-packages", status_code=201)
def retrieve_evidence(project_id: str, payload: EvidenceRetrieveRequest):
    try:
        package = retrieval_service.retrieve(
            project_id, payload.topic_id, payload.start_year,
            payload.end_year, payload.paper_limit, payload.dataset_ids,
            payload.min_relevance, payload.operator_notes,
        )
        repository.update_project_status(project_id, "evidence_review")
        return package
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{project_id}/evidence-packages/{package_id}")
def get_evidence_package(project_id: str, package_id: str):
    package = repository.get_evidence_package(package_id)
    if not package or package["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="证据包不存在")
    return package


@router.patch("/{project_id}/evidence-items/{evidence_id}")
def update_evidence_item(project_id: str, evidence_id: str, payload: EvidenceItemUpdate):
    evidence = retrieval_service.resolve_evidence(evidence_id, project_id)
    if not evidence or evidence["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="证据不存在")
    retrieval_service.update_item(
        evidence_id, payload.excluded, payload.reason, project_id
    )
    return retrieval_service.resolve_evidence(evidence_id, project_id)


@router.get("/{project_id}/evidence-items/{evidence_id}")
def get_evidence_item(project_id: str, evidence_id: str):
    evidence = retrieval_service.resolve_evidence(evidence_id, project_id)
    if not evidence or evidence["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="证据不存在")
    return evidence
