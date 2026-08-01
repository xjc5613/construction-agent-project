# -*- coding: utf-8 -*-
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from src.ingestion import ImportService
from src.library import LibraryRepository

router = APIRouter(prefix="/api/library", tags=["evidence-library"])
repository = LibraryRepository()
import_service = ImportService(repository)


class DatasetCreate(BaseModel):
    kind: str
    name: str = Field(min_length=1, max_length=160)
    version: str = Field(min_length=1, max_length=60)
    description: str = ""


class DatasetStatusUpdate(BaseModel):
    status: str


class ImportCommit(BaseModel):
    dataset_id: str
    mapping: Dict[str, str] = Field(default_factory=dict)


@router.get("/datasets")
def list_datasets(kind: str = ""):
    return {"items": repository.list_datasets(kind), "total": len(repository.list_datasets(kind))}


@router.post("/datasets", status_code=201)
def create_dataset(payload: DatasetCreate):
    try:
        return repository.create_dataset(
            payload.kind, payload.name, payload.version, payload.description
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
    dataset = repository.update_dataset_status(dataset_id, payload.status)
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return dataset


@router.post("/imports", status_code=201)
async def stage_import(
    file: UploadFile = File(...),
    kind: str = Form(...),
    dataset_id: str = Form(""),
    sheet_name: str = Form(""),
):
    if kind not in {"ipc_metrics", "ipc_fusions", "papers"}:
        raise HTTPException(status_code=422, detail="导入类型无效")
    try:
        content = await file.read()
        result = import_service.stage_file(
            content, file.filename or "upload", file.content_type or "",
            kind, dataset_id, {"sheet_name": sheet_name},
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])
    return result


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
    q: str = "", limit: int = Query(20, ge=1, le=100),
    end_year: Optional[int] = Query(None, ge=1900, le=2100),
):
    items = repository.search_papers(q, limit, end_year)
    return {"items": items, "total": len(items)}


@router.get("/papers/{paper_id}")
def get_paper(paper_id: str):
    paper = repository.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    return paper


@router.get("/ipc/trends")
def get_ipc_trends(
    codes: str = "", start_year: Optional[int] = None, end_year: Optional[int] = None
):
    items = repository.ipc_series(
        [code.strip().upper() for code in codes.split(",") if code.strip()],
        start_year, end_year,
    )
    return {"items": items, "total": len(items)}


@router.get("/ipc/fusions")
def get_ipc_fusions(codes: str = ""):
    items = repository.ipc_fusions(
        [code.strip().upper() for code in codes.split(",") if code.strip()]
    )
    return {"items": items, "total": len(items)}
