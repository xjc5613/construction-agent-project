# -*- coding: utf-8 -*-
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, field_validator

from src.ingestion import ImportService, ResearchImportService
from src.library import LibraryRepository, TechnologyRepository
from src.library.validation import validate_dataset_version
from .confirmation_service import ConfirmationError, confirmation_service

router = APIRouter(prefix="/api/library", tags=["evidence-library"])
repository = LibraryRepository()
import_service = ImportService(repository)
research_import_service = ResearchImportService(repository)


class DatasetCreate(BaseModel):
    kind: str
    technology_node_id: str = ""
    period_code: str = ""
    name: str = Field("", max_length=160)
    version: str = Field(min_length=1, max_length=60)
    description: str = ""

    @field_validator("version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        return validate_dataset_version(value)


class DatasetStatusUpdate(BaseModel):
    status: str


class DatasetClassificationUpdate(BaseModel):
    technology_node_id: str
    period_code: str
    kind: str


class DatasetSplitRequest(BaseModel):
    technology_node_id: str
    kind: str


class ImportCommit(BaseModel):
    dataset_id: str
    mapping: Dict[str, str] = Field(default_factory=dict)


class GuidedImportCommit(BaseModel):
    technology_node_id: str
    public_kind: str
    mapping: Dict[str, str] = Field(default_factory=dict)
    versions: Dict[str, str] = Field(default_factory=dict)


class DatasetActionPreview(BaseModel):
    action: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class DatasetActionCommit(DatasetActionPreview):
    confirmation_token: str = Field(min_length=1)


class ResearchImportPreview(BaseModel):
    kind: str
    dataset_id: str
    rows: list[Dict[str, Any]]
    ipc_level: str = "main_group"
    ipc_edition: str = ""
    observation_cutoff: str = ""
    completeness: str = "complete"
    source_database: str = ""
    project_id: str = ""


class ResearchImportCommit(BaseModel):
    preview: Dict[str, Any]
    file_id: Optional[str] = None


@router.post("/research-imports/preview")
def preview_research_import(payload: ResearchImportPreview):
    if not repository.get_dataset(payload.dataset_id):
        raise HTTPException(status_code=404, detail="数据集不存在")
    try:
        return research_import_service.preview(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/research-imports/commit")
def commit_research_import(payload: ResearchImportCommit):
    try:
        return research_import_service.commit(payload.preview, file_id=payload.file_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/datasets")
def list_datasets(
    kind: str = "", technology_node_id: str = "",
    period_code: str = "", status: str = "", scope_node_id: str = "",
    lifecycle_status: str = "", migration_status: str = "",
):
    items = repository.list_datasets(
        kind, technology_node_id, period_code, status, scope_node_id,
        lifecycle_status, migration_status,
    )
    return {"items": items, "total": len(items)}


@router.post("/datasets", status_code=201)
def create_dataset(payload: DatasetCreate):
    try:
        return repository.create_dataset(
            payload.kind, payload.name, payload.version, payload.description,
            technology_node_id=payload.technology_node_id,
            period_code=payload.period_code,
            public_kind=payload.kind if payload.technology_node_id else "",
            research_contract_version=3,
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: str):
    dataset = repository.get_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return dataset


@router.patch("/datasets/{dataset_id}/status")
def update_dataset_status(dataset_id: str, payload: DatasetStatusUpdate):
    if payload.status not in {"draft", "published", "inactive", "failed"}:
        raise HTTPException(status_code=422, detail="数据集状态无效")
    try:
        dataset = repository.update_dataset_status(dataset_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return dataset


@router.patch("/datasets/{dataset_id}/classification")
def classify_legacy_dataset(
    dataset_id: str, payload: DatasetClassificationUpdate
):
    try:
        return repository.classify_legacy_dataset(
            dataset_id, payload.technology_node_id,
            payload.period_code, payload.kind,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/datasets/{dataset_id}/split", status_code=201)
def split_legacy_dataset(dataset_id: str, payload: DatasetSplitRequest):
    try:
        items = repository.split_legacy_dataset(
            dataset_id, payload.technology_node_id, payload.kind
        )
        return {"items": items, "total": len(items), "source_dataset_id": dataset_id}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/datasets/{dataset_id}/actions/preview")
def preview_dataset_action(dataset_id: str, payload: DatasetActionPreview):
    dataset = repository.get_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    impact = repository.dataset_reference_impact(dataset_id)
    if payload.action == "classify":
        classification = DatasetClassificationUpdate.model_validate(payload.payload)
        technology = TechnologyRepository(repository.db).get(
            classification.technology_node_id
        )
        if not technology or technology["level"] != 3 or technology["status"] != "active":
            raise HTTPException(status_code=422, detail="必须选择未归档的三级技术")
        after = {
            **dataset, "technology_node_id": technology["node_id"],
            "technology_path": technology["path_text"],
            "period_code": classification.period_code,
            "public_kind": classification.kind,
        }
    elif payload.action in {"deprecate", "restore", "delete"}:
        after = {**dataset, "lifecycle_status": {
            "deprecate": "deprecated", "restore": "active", "delete": "deleted",
        }[payload.action]}
    else:
        raise HTTPException(status_code=422, detail="数据集操作无效")
    warnings = []
    if payload.action == "delete" and impact["referenced"]:
        warnings.append("该数据集已有记录或引用，只能废弃")
    if payload.action == "deprecate":
        warnings.append("历史证据和任务快照仍保留该数据集引用")
    return confirmation_service.preview(
        f"dataset:{payload.action}", payload.payload,
        impact=impact, before=dataset, after=after, warnings=warnings,
    )


@router.post("/datasets/{dataset_id}/actions/commit")
def commit_dataset_action(dataset_id: str, payload: DatasetActionCommit):
    if not repository.get_dataset(dataset_id):
        raise HTTPException(status_code=404, detail="数据集不存在")
    try:
        confirmation_service.validate(
            payload.confirmation_token, f"dataset:{payload.action}", payload.payload
        )
        if payload.action == "classify":
            request = DatasetClassificationUpdate.model_validate(payload.payload)
            result = repository.classify_legacy_dataset(
                dataset_id, request.technology_node_id,
                request.period_code, request.kind,
            )
        elif payload.action == "deprecate":
            result = repository.set_dataset_lifecycle(dataset_id, "deprecated")
        elif payload.action == "restore":
            result = repository.set_dataset_lifecycle(dataset_id, "active")
        elif payload.action == "delete":
            result = {"deleted": repository.delete_dataset_draft(dataset_id)}
        else:
            raise HTTPException(status_code=422, detail="数据集操作无效")
        return {"ok": True, "resource": result}
    except ConfirmationError as exc:
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={
            "code": "dataset_lifecycle_conflict", "message": str(exc),
        }) from exc


@router.post("/imports", status_code=201)
async def stage_import(
    file: UploadFile = File(...),
    kind: str = Form(...),
    dataset_id: str = Form(""),
    sheet_name: str = Form(""),
    document_year: Optional[int] = Form(None),
):
    if kind not in {"ipc_metrics", "ipc_fusions", "papers", "analysis_document"}:
        raise HTTPException(status_code=422, detail="导入类型无效")
    try:
        content = await file.read()
        result = import_service.stage_file(
            content, file.filename or "upload", file.content_type or "",
            kind, dataset_id,
            {"sheet_name": sheet_name, "document_year": document_year},
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])
    return result


@router.get("/imports")
def list_imports(scope_node_id: str = "", include_ineligible: bool = False):
    items = repository.list_imports(
        scope_node_id=scope_node_id,
        include_ineligible=include_ineligible,
    )
    return {"items": items, "total": len(items)}


@router.post("/imports/guided/stage", status_code=201)
async def stage_guided_import(
    file: UploadFile = File(...),
    technology_node_id: str = Form(...),
    public_kind: str = Form(...),
    component_kind: str = Form(...),
    sheet_name: str = Form(""),
    document_year: Optional[int] = Form(None),
):
    try:
        result = import_service.guided_stage(
            await file.read(), file.filename or "upload",
            file.content_type or "", component_kind,
            technology_node_id, public_kind,
            {"sheet_name": sheet_name, "document_year": document_year},
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])
    return result


@router.post("/imports/{import_id}/guided-commit")
def commit_guided_import(import_id: str, payload: GuidedImportCommit):
    try:
        return import_service.guided_commit(
            import_id, payload.technology_node_id, payload.public_kind,
            mapping=payload.mapping, versions=payload.versions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/datasets/{dataset_id}/files", status_code=201)
async def stage_dataset_file(
    dataset_id: str, file: UploadFile = File(...),
    component_kind: str = Form(...), sheet_name: str = Form(""),
    document_year: Optional[int] = Form(None),
):
    if component_kind not in {
        "ipc_metrics", "ipc_fusions", "papers", "analysis_document"
    }:
        raise HTTPException(status_code=422, detail="数据组成类型无效")
    dataset = repository.get_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    allowed = {
        "ipc": {"ipc_metrics", "ipc_fusions"},
        "paper": {"papers"},
        "integrated": {
            "ipc_metrics", "ipc_fusions", "papers", "analysis_document"
        },
    }
    public_kind = dataset.get("public_kind")
    if public_kind and component_kind not in allowed.get(public_kind, set()):
        raise HTTPException(status_code=422, detail="组成类型与数据集类型不匹配")
    try:
        return import_service.stage_file(
            await file.read(), file.filename or "upload",
            file.content_type or "", component_kind, dataset_id,
            {"sheet_name": sheet_name, "document_year": document_year},
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/imports/{import_id}")
def get_import(import_id: str):
    result = repository.get_import(import_id)
    if not result:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    return result


@router.post("/imports/{import_id}/commit")
def commit_import(import_id: str, payload: ImportCommit):
    try:
        return import_service.commit_import(import_id, payload.dataset_id, payload.mapping)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/papers")
def search_papers(
    q: str = "", limit: Optional[int] = Query(None, ge=1, le=100),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    scope_node_id: str = "", dataset_id: str = "", period_code: str = "",
    start_year: Optional[int] = Query(None, ge=1900, le=2100),
    end_year: Optional[int] = Query(None, ge=1900, le=2100),
    include_ineligible: bool = False,
):
    return repository.paper_page(
        query=q, scope_node_id=scope_node_id, dataset_id=dataset_id,
        period_code=period_code, start_year=start_year, end_year=end_year,
        page=page, page_size=limit or page_size,
        include_ineligible=include_ineligible,
    )


@router.get("/papers/{paper_id}")
def get_paper(paper_id: str):
    paper = repository.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    return paper


@router.get("/ipc/trends")
def get_ipc_trends(
    codes: str = "", start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    scope_node_id: str = "", dataset_id: str = "", period_code: str = "",
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    include_ineligible: bool = False,
):
    return repository.ipc_page(
        codes=[code.strip().upper() for code in codes.split(",") if code.strip()],
        start_year=start_year, end_year=end_year,
        scope_node_id=scope_node_id, dataset_id=dataset_id,
        period_code=period_code, page=page, page_size=page_size,
        include_ineligible=include_ineligible,
    )


@router.get("/ipc/fusions")
def get_ipc_fusions(codes: str = ""):
    items = repository.ipc_fusions(
        [code.strip().upper() for code in codes.split(",") if code.strip()]
    )
    return {"items": items, "total": len(items)}


@router.get("/files")
def list_source_files(scope_node_id: str = "", include_ineligible: bool = False):
    items = repository.library_files(
        scope_node_id=scope_node_id,
        include_ineligible=include_ineligible,
    )
    return {"items": items, "total": len(items)}


@router.get("/technologies/{node_id}/summary")
def get_technology_data_summary(node_id: str):
    try:
        return TechnologyRepository(repository.db).summary(node_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/coverage/{root_node_id}")
def get_dataset_coverage(root_node_id: str):
    try:
        return repository.dataset_coverage(root_node_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
