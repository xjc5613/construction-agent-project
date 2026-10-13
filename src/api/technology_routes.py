# -*- coding: utf-8 -*-
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.library import TechnologyRepository
from .confirmation_service import ConfirmationError, confirmation_service

router = APIRouter(prefix="/api/technologies", tags=["technology-taxonomy"])
relation_router = APIRouter(
    prefix="/api/technology-relations", tags=["technology-taxonomy"]
)
repository = TechnologyRepository()


class TechnologyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    level: int = Field(ge=1, le=3)
    parent_id: Optional[str] = None
    description: str = ""
    keywords: List[str] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)
    sort_order: int = 0


class TechnologyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
    aliases: Optional[List[str]] = None
    sort_order: Optional[int] = None
    parent_id: Optional[str] = None


class TechnologyMove(BaseModel):
    parent_id: Optional[str] = None
    sort_order: int = 0


class TechnologyRelationCreate(BaseModel):
    source_node_id: str
    target_node_id: str
    relation_type: str
    status: str = "confirmed"


class TechnologyActionPreview(BaseModel):
    action: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class TechnologyActionCommit(TechnologyActionPreview):
    confirmation_token: str = Field(min_length=1)


def _handle_value_error(exc: ValueError):
    raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("")
def list_technologies(
    q: str = "", level: Optional[int] = Query(None, ge=1, le=3),
    include_archived: bool = False, flat: bool = False,
):
    if flat or level is not None:
        items = repository.list_nodes(
            level=level, status="" if include_archived else "active", query=q
        )
    else:
        items = repository.tree(include_archived=include_archived, query=q)
    return {"items": items, "total": len(items)}


@router.post("", status_code=201)
def create_technology(payload: TechnologyCreate):
    try:
        return repository.create(payload.model_dump())
    except ValueError as exc:
        _handle_value_error(exc)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{node_id}")
def get_technology(node_id: str):
    node = repository.get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="技术节点不存在")
    node["references"] = repository.references(node_id)
    node["changes"] = repository.changes(node_id)
    return node


@router.get("/{node_id}/summary")
def get_technology_summary(node_id: str):
    try:
        return repository.summary(node_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{node_id}")
def update_technology(node_id: str, payload: TechnologyUpdate):
    try:
        return repository.update(node_id, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        _handle_value_error(exc)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/{node_id}", status_code=204)
def delete_technology(node_id: str):
    try:
        repository.delete(node_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{node_id}/move")
def move_technology(node_id: str, payload: TechnologyMove):
    try:
        return repository.move(node_id, payload.parent_id, payload.sort_order)
    except ValueError as exc:
        _handle_value_error(exc)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{node_id}/archive")
def archive_technology(node_id: str):
    try:
        return repository.archive(node_id)
    except ValueError as exc:
        _handle_value_error(exc)


@router.post("/{node_id}/restore")
def restore_technology(node_id: str):
    try:
        return repository.restore(node_id)
    except ValueError as exc:
        _handle_value_error(exc)


@router.post("/{node_id}/actions/preview")
def preview_technology_action(node_id: str, payload: TechnologyActionPreview):
    node = repository.get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="技术节点不存在")
    if payload.action not in {"archive", "restore", "delete", "move"}:
        raise HTTPException(status_code=422, detail="技术操作无效")
    after = dict(node)
    if payload.action == "archive":
        after["status"] = "archived"
    elif payload.action == "restore":
        after["status"] = "active"
    elif payload.action == "delete":
        after["status"] = "deleted"
    else:
        parent = repository.get(str(payload.payload.get("parent_id") or ""))
        if not parent:
            raise HTTPException(status_code=422, detail="父技术不存在")
        after["parent_id"] = parent["node_id"]
        after["path_text"] = f"{parent['path_text']} / {node['name']}"
        after["sort_order"] = int(payload.payload.get("sort_order", node["sort_order"]))
    references = repository.references(node_id)
    affected_descendants = (
        repository.affected_descendants(node_id)
        if payload.action == "archive" else []
    )
    warnings = []
    if payload.action == "delete" and any(references.values()):
        warnings.append("技术已被引用，只能归档")
    if affected_descendants:
        warnings.append(
            f"停用父技术将使 {len(affected_descendants)} 个下级技术继承停用状态"
        )
    return confirmation_service.preview(
        f"technology:{payload.action}", payload.payload,
        impact={
            **references,
            "affected_descendants": [
                {
                    "node_id": item["node_id"],
                    "name": item["name"],
                    "path_text": item.get("path_text", ""),
                }
                for item in affected_descendants
            ],
        },
        before=node, after=after, warnings=warnings,
    )


@router.post("/{node_id}/actions/commit")
def commit_technology_action(node_id: str, payload: TechnologyActionCommit):
    if not repository.get(node_id):
        raise HTTPException(status_code=404, detail="技术节点不存在")
    try:
        confirmation_service.validate(
            payload.confirmation_token,
            f"technology:{payload.action}", payload.payload,
        )
        if payload.action == "archive":
              result = repository.archive(
                  node_id,
                  confirm_descendants=bool(payload.payload.get("cascade")),
              )
        elif payload.action == "restore":
            result = repository.restore(node_id)
        elif payload.action == "delete":
            repository.delete(node_id)
            result = {"deleted": True, "node_id": node_id}
        elif payload.action == "move":
            result = repository.update(node_id, {
                "parent_id": payload.payload.get("parent_id"),
                "sort_order": int(payload.payload.get("sort_order", 0)),
            })
        else:
            raise HTTPException(status_code=422, detail="技术操作无效")
        return {"ok": True, "resource": result}
    except ConfirmationError as exc:
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={
            "code": "technology_lifecycle_conflict", "message": str(exc),
        }) from exc


@router.get("/{node_id}/references")
def get_technology_references(node_id: str):
    if not repository.get(node_id):
        raise HTTPException(status_code=404, detail="技术节点不存在")
    return repository.references(node_id)


@router.get("/{node_id}/changes")
def get_technology_changes(
    node_id: str, limit: int = Query(100, ge=1, le=500)
):
    if not repository.get(node_id):
        raise HTTPException(status_code=404, detail="技术节点不存在")
    items = repository.changes(node_id, limit)
    return {"items": items, "total": len(items)}


@relation_router.post("", status_code=201)
def create_technology_relation(payload: TechnologyRelationCreate):
    try:
        return repository.create_relation(**payload.model_dump())
    except ValueError as exc:
        _handle_value_error(exc)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@relation_router.delete("/{relation_id}", status_code=204)
def delete_technology_relation(relation_id: str):
    if not repository.delete_relation(relation_id):
        raise HTTPException(status_code=404, detail="技术关系不存在")
