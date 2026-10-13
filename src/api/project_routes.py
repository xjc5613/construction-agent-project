# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.analysis import StageAnalysisService
from src.library import LibraryRepository
from src.library.constants import ANALYSIS_KINDS, BASELINE_YEAR
from src.retrieval import EvidenceRetrievalService
from src.research.design import ResearchDesignService

from .project_service import ProjectService
from .readiness_service import ReadinessService
from .confirmation_service import (
    ConfirmationError, confirmation_service,
)

router = APIRouter(prefix="/api/projects", tags=["forecast-projects"])
repository = LibraryRepository()
project_service = ProjectService(repository)
retrieval_service = EvidenceRetrievalService(repository)
stage_analysis_service = StageAnalysisService(repository)
research_design_service = ResearchDesignService(repository)


class ProjectCreate(BaseModel):
    technology_node_id: str
    target_year: Literal[2030, 2035, 2040]
    name: str = Field("", max_length=160)
    description: str = ""


class ProjectStatusUpdate(BaseModel):
    status: str


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=160)
    description: Optional[str] = None


class MaterialUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1, max_length=1_000_000)
    analysis_kind: Optional[Literal[
        "ipc_analysis", "paper_analysis", "integrated_analysis"
    ]] = None


class ActionPreviewRequest(BaseModel):
    action: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class ActionCommitRequest(ActionPreviewRequest):
    confirmation_token: str = Field(min_length=1)


class TextMaterialCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=1_000_000)
    analysis_kind: Literal[
        "ipc_analysis", "paper_analysis", "integrated_analysis"
    ] = "integrated_analysis"


class ExtractRequest(BaseModel):
    material_ids: List[str] = Field(min_length=1)
    refine_with_llm: bool = True


class ProjectTopicCreate(BaseModel):
    topic_name: str = Field(min_length=1, max_length=120)
    description: str = ""
    keywords: List[str] = Field(default_factory=list)
    operator_notes: str = ""
    technologies: List[Dict[str, Any]] = Field(default_factory=list)


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
    technologies: Optional[List[Dict[str, Any]]] = None


class TopicMergeRequest(BaseModel):
    topic_ids: List[str] = Field(min_length=2)
    topic_name: str = Field(min_length=1, max_length=120)
    primary_technology_node_id: Optional[str] = None


class EvidenceRetrieveRequest(BaseModel):
    topic_id: str
    start_year: int = 2000
    end_year: int = BASELINE_YEAR
    paper_limit: int = Field(20, ge=1, le=100)
    dataset_ids: List[str] = Field(default_factory=list)
    min_relevance: float = Field(0, ge=0, le=1)
    operator_notes: str = Field("", max_length=2000)


class EvidenceItemUpdate(BaseModel):
    excluded: bool
    reason: str = ""


class StageAnalysisRequest(BaseModel):
    technology_node_ids: List[str] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ResearchDesignCreate(BaseModel):
    research_question: str = Field(min_length=1, max_length=2000)
    paper_types: List[str] = Field(default_factory=lambda: ["journal_article", "conference_paper"])
    ipc_analysis_level: Literal["subclass", "main_group", "subgroup"] = "main_group"
    candidate_target: Literal["emergence", "strengthening", "both"] = "both"
    data_cutoff: str = ""
    completeness_policy: str = "include_partial_with_sensitivity"
    parameters: Dict[str, Any] = Field(default_factory=dict)


class SnapshotCreate(BaseModel):
    dataset_ids: List[str] = Field(default_factory=list)


@router.get("/{project_id}/research-designs")
def list_research_designs(project_id: str):
    _project_or_404(project_id)
    items = research_design_service.list_versions(project_id)
    return {"items": items, "total": len(items)}


@router.post("/{project_id}/research-designs", status_code=201)
def create_research_design(project_id: str, payload: ResearchDesignCreate):
    _project_or_404(project_id)
    try:
        return research_design_service.create_version(project_id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{project_id}/research-designs/{design_id}/confirm")
def confirm_research_design(project_id: str, design_id: str):
    _project_or_404(project_id)
    try:
        return research_design_service.confirm(project_id, design_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{project_id}/stale-artifacts")
def get_stale_artifacts(project_id: str):
    _project_or_404(project_id)
    return research_design_service.stale_artifacts(project_id)


@router.post("/{project_id}/evidence-snapshots")
def freeze_research_snapshot(project_id: str, payload: SnapshotCreate):
    _project_or_404(project_id)
    try:
        return research_design_service.freeze_snapshot(
            project_id, payload.dataset_ids or None
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("")
def list_projects(include_archived: bool = False):
    items = repository.list_projects(include_archived=include_archived)
    return {"items": items, "total": len(items)}


@router.post("", status_code=201)
def create_project(payload: ProjectCreate):
    try:
        return repository.create_project(
            payload.name, payload.description,
            technology_node_id=payload.technology_node_id,
            target_year=payload.target_year,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
    if project.get("technology_node_id"):
        project["technology_scope"] = repository.project_technology_scope(project_id)
        project["coverage"] = repository.dataset_coverage(
            project["technology_node_id"]
        )
    return project


@router.patch("/{project_id}")
def update_project(project_id: str, payload: ProjectUpdate):
    _project_or_404(project_id)
    try:
        return repository.update_project(
            project_id, payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={
            "code": "project_validation", "message": str(exc),
        }) from exc


@router.post("/{project_id}/actions/preview")
def preview_project_action(project_id: str, payload: ActionPreviewRequest):
    project = _project_or_404(project_id)
    if payload.action not in {"archive", "restore"}:
        raise HTTPException(status_code=422, detail="项目操作无效")
    after = {**project, "lifecycle_status": (
        "archived" if payload.action == "archive" else "active"
    )}
    return confirmation_service.preview(
        f"project:{payload.action}", payload.payload,
        impact=repository.project_reference_impact(project_id),
        before=project, after=after,
        warnings=["归档后不会删除任务和结果"] if payload.action == "archive" else [],
    )


@router.post("/{project_id}/actions/commit")
def commit_project_action(project_id: str, payload: ActionCommitRequest):
    _project_or_404(project_id)
    try:
        confirmation_service.validate(
            payload.confirmation_token, f"project:{payload.action}", payload.payload
        )
        target = {"archive": "archived", "restore": "active"}[payload.action]
        result = repository.set_project_lifecycle(project_id, target)
        return {"ok": True, "resource": result}
    except KeyError as exc:
        raise HTTPException(status_code=422, detail="项目操作无效") from exc
    except ConfirmationError as exc:
        raise HTTPException(status_code=409, detail={
            "code": exc.code, "message": str(exc),
        }) from exc


@router.get("/{project_id}/technology-scope")
def get_project_technology_scope(project_id: str):
    _project_or_404(project_id)
    return repository.project_technology_scope(project_id)


@router.post("/{project_id}/technology-scope/refresh")
def refresh_project_technology_scope(project_id: str):
    project = _project_or_404(project_id)
    if project["legacy_mode"]:
        raise HTTPException(status_code=409, detail="历史项目不能刷新技术范围")
    return repository.refresh_project_scope(project_id)


@router.get("/{project_id}/coverage")
def get_project_coverage(project_id: str):
    project = _project_or_404(project_id)
    if not project.get("technology_node_id"):
        return {"complete": False, "missing": ["历史项目未绑定技术目录"]}
    return repository.dataset_coverage(project["technology_node_id"])


@router.get("/{project_id}/readiness")
def get_project_readiness(project_id: str, topic_ids: str = ""):
    _project_or_404(project_id)
    try:
        selected = [item for item in topic_ids.split(",") if item] or None
        return ReadinessService(repository).project_readiness(project_id, selected)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{project_id}/topics/{topic_id}/readiness")
def get_topic_readiness(project_id: str, topic_id: str):
    _project_or_404(project_id)
    try:
        return ReadinessService(repository).topic_readiness(project_id, topic_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{project_id}/stage-analysis", status_code=201)
def create_stage_analysis(project_id: str, payload: StageAnalysisRequest):
    _project_or_404(project_id)
    try:
        if payload.technology_node_ids:
            items = [
                stage_analysis_service.analyze(
                    node_id, project_id, payload.parameters
                )
                for node_id in payload.technology_node_ids
            ]
        else:
            items = stage_analysis_service.analyze_project(project_id)
        return {"items": items, "total": len(items)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{project_id}/stage-analysis")
def list_stage_analysis(project_id: str):
    _project_or_404(project_id)
    items = stage_analysis_service.latest_for_project(project_id)
    return {"items": items, "total": len(items)}


@router.get("/{project_id}/stage-analysis/{run_id}")
def get_stage_analysis(project_id: str, run_id: str):
    _project_or_404(project_id)
    result = stage_analysis_service.get(run_id)
    if not result or result.get("project_id") != project_id:
        raise HTTPException(status_code=404, detail="阶段分析不存在")
    return result


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
            project_id, payload.title, payload.content, payload.analysis_kind
        )
        repository.update_project_status(project_id, "material_ready")
        return material
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{project_id}/materials/upload", status_code=201)
async def add_file_material(
    project_id: str, file: UploadFile = File(...),
    analysis_kind: str = Form("integrated_analysis"),
):
    if analysis_kind not in ANALYSIS_KINDS:
        raise HTTPException(status_code=422, detail="分析材料类型无效")
    try:
        material = project_service.add_file_material(
            project_id, file.filename or "upload", file.content_type or "",
            await file.read(), analysis_kind,
        )
        repository.update_project_status(project_id, "material_ready")
        return material
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{project_id}/materials")
def list_materials(project_id: str, include_inactive: bool = False):
    _project_or_404(project_id)
    items = repository.list_materials(project_id, include_inactive=include_inactive)
    return {"items": items, "total": len(items)}


@router.get("/{project_id}/materials/{material_id}")
def get_material(project_id: str, material_id: str):
    material = repository.get_material(material_id)
    if not material or material["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="项目材料不存在")
    return material


@router.patch("/{project_id}/materials/{material_id}")
def update_material(project_id: str, material_id: str, payload: MaterialUpdate):
    material = repository.get_material(material_id)
    if not material or material["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="项目材料不存在")
    changes = payload.model_dump(exclude_unset=True)
    if "content" in changes:
        from .topic_service import _clean_text
        changes["cleaned_content"] = _clean_text(changes["content"])
    try:
        return repository.update_material(material_id, changes)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={
            "code": "material_referenced", "message": str(exc),
        }) from exc


@router.post("/{project_id}/materials/{material_id}/actions/preview")
def preview_material_action(
    project_id: str, material_id: str, payload: ActionPreviewRequest,
):
    material = repository.get_material(material_id)
    if not material or material["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="项目材料不存在")
    if payload.action not in {"deactivate", "restore"}:
        raise HTTPException(status_code=422, detail="材料操作无效")
    return confirmation_service.preview(
        f"material:{payload.action}", payload.payload,
        impact=repository.material_reference_impact(material_id), before=material,
        after={**material, "lifecycle_status": (
            "inactive" if payload.action == "deactivate" else "active"
        )},
        warnings=["已冻结任务仍会保留该材料"] if payload.action == "deactivate" else [],
    )


@router.post("/{project_id}/materials/{material_id}/actions/commit")
def commit_material_action(
    project_id: str, material_id: str, payload: ActionCommitRequest,
):
    material = repository.get_material(material_id)
    if not material or material["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="项目材料不存在")
    try:
        confirmation_service.validate(
            payload.confirmation_token, f"material:{payload.action}", payload.payload
        )
        target = {"deactivate": "inactive", "restore": "active"}[payload.action]
        return {"ok": True, "resource": repository.set_material_lifecycle(material_id, target)}
    except KeyError as exc:
        raise HTTPException(status_code=422, detail="材料操作无效") from exc
    except ConfirmationError as exc:
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)}) from exc


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
        "technologies": payload.technologies,
    })


@router.patch("/{project_id}/topics/{topic_id}")
def update_topic(project_id: str, topic_id: str, payload: ProjectTopicUpdate):
    topic = repository.get_topic(topic_id)
    if not topic or topic["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="项目主题不存在")
    changes = payload.model_dump(exclude_unset=True)
    technologies = changes.pop("technologies", None)
    if changes.get("status") and changes["status"] not in {
        "candidate", "confirmed", "evidence_ready", "archived", "deleted", "merged"
    }:
        raise HTTPException(status_code=422, detail="项目主题状态无效")
    updated = repository.update_topic(topic_id, changes)
    if technologies is not None:
        repository.set_topic_technologies(topic_id, technologies)
        updated = repository.get_topic(topic_id)
    return updated


@router.put("/{project_id}/topics/{topic_id}/technologies")
def replace_topic_technologies(
    project_id: str, topic_id: str,
    technologies: List[Dict[str, Any]],
):
    topic = repository.get_topic(topic_id)
    if not topic or topic["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="项目主题不存在")
    try:
        return {
            "items": repository.set_topic_technologies(topic_id, technologies)
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
    technologies = repository.get_topic_technologies(topic_id)
    if not technologies or sum(bool(item["is_primary"]) for item in technologies) != 1:
        raise HTTPException(
            status_code=422, detail="主题确认前必须关联三级技术并设置唯一主技术"
        )
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
    technologies_by_id = {}
    for topic in topics:
        for technology in topic.get("technologies", []):
            technologies_by_id[technology["technology_node_id"]] = {
                "technology_node_id": technology["technology_node_id"],
                "is_primary": False,
                "relevance": max(
                    float(technology.get("relevance", 1)),
                    float(technologies_by_id.get(
                        technology["technology_node_id"], {}
                    ).get("relevance", 0)),
                ),
                "source": "merge",
            }
    primary_id = payload.primary_technology_node_id or next(
        iter(technologies_by_id), None
    )
    if primary_id in technologies_by_id:
        technologies_by_id[primary_id]["is_primary"] = True
    merged = repository.save_topic({
        "project_id": project_id, "topic_name": payload.topic_name,
        "keywords": keywords, "evidence": evidence, "fusion_pairs": fusions,
        "status": "candidate", "requires_review": True, "selected": True,
        "technologies": list(technologies_by_id.values()),
    })
    for topic in topics:
        repository.update_topic(
            topic["topic_id"], {"status": "merged", "selected": False, "merged_into": merged["topic_id"]}
        )
    return merged


@router.post("/{project_id}/topics/actions/preview")
def preview_topic_action(project_id: str, payload: ActionPreviewRequest):
    _project_or_404(project_id)
    if payload.action == "merge":
        request = TopicMergeRequest.model_validate(payload.payload)
        topics = [repository.get_topic(item) for item in request.topic_ids]
        if any(not item or item["project_id"] != project_id for item in topics):
            raise HTTPException(status_code=404, detail="待合并主题不存在")
        impact = {
            "topics": [
                {"topic_id": item["topic_id"], "topic_name": item["topic_name"],
                 **repository.topic_reference_impact(item["topic_id"])}
                for item in topics
            ]
        }
        after = {"topic_name": request.topic_name, "status": "candidate"}
        before = topics
    elif payload.action in {"archive", "delete", "restore"}:
        topic_id = str(payload.payload.get("topic_id") or "")
        topic = repository.get_topic(topic_id)
        if not topic or topic["project_id"] != project_id:
            raise HTTPException(status_code=404, detail="项目主题不存在")
        impact = repository.topic_reference_impact(topic_id)
        before = topic
        after = {**topic, "status": {
            "archive": "archived", "delete": "deleted", "restore": "candidate",
        }[payload.action]}
    else:
        raise HTTPException(status_code=422, detail="主题操作无效")
    return confirmation_service.preview(
        f"topic:{payload.action}", payload.payload,
        impact=impact, before=before, after=after,
        warnings=["历史任务快照不会被修改"],
    )


@router.post("/{project_id}/topics/actions/commit")
def commit_topic_action(project_id: str, payload: ActionCommitRequest):
    _project_or_404(project_id)
    try:
        confirmation_service.validate(
            payload.confirmation_token, f"topic:{payload.action}", payload.payload
        )
        if payload.action == "merge":
            result = merge_topics(
                project_id, TopicMergeRequest.model_validate(payload.payload)
            )
        else:
            topic_id = str(payload.payload.get("topic_id") or "")
            topic = repository.get_topic(topic_id)
            if not topic or topic["project_id"] != project_id:
                raise HTTPException(status_code=404, detail="项目主题不存在")
            changes = {
                "archive": {"status": "archived", "selected": False},
                "delete": {"status": "deleted", "selected": False},
                "restore": {
                    "status": "candidate", "selected": True,
                    "requires_review": True, "merged_into": None,
                },
            }[payload.action]
            result = repository.update_topic(topic_id, changes)
        return {"ok": True, "resource": result}
    except KeyError as exc:
        raise HTTPException(status_code=422, detail="主题操作无效") from exc
    except ConfirmationError as exc:
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)}) from exc


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
    try:
        retrieval_service.update_item(
            evidence_id, payload.excluded, payload.reason, project_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    package = repository.get_evidence_package(evidence["package_id"])
    readiness = ReadinessService(repository).topic_readiness(
        project_id, package["topic_id"], package
    )
    return {
        "item": retrieval_service.resolve_evidence(evidence_id, project_id),
        "package": {**package, "quality": readiness["quality"]},
        "readiness": ReadinessService(repository).project_readiness(project_id),
    }


@router.get("/{project_id}/evidence-items/{evidence_id}")
def get_evidence_item(project_id: str, evidence_id: str):
    evidence = retrieval_service.resolve_evidence(evidence_id, project_id)
    if not evidence or evidence["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="证据不存在")
    return evidence
