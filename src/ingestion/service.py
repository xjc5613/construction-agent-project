# -*- coding: utf-8 -*-
import hashlib
import json
import math
import shutil
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from config.settings import LIBRARY_RAW_DIR
from src.library import LibraryRepository

from .models import ParsedDocument, ParsedTable
from .parsers import parse_file, validate_upload

FIELD_ALIASES = {
    "ipc_code": {"ipc", "ipc_code", "ipc分类号", "分类号"},
    "year": {"year", "年份", "年度"},
    "patent_count": {"patent_count", "专利数", "申请量"},
    "degree_centrality": {"degree_centrality", "度中心度"},
    "betweenness_centrality": {"betweenness_centrality", "中介中心度"},
    "growth_rate": {"growth_rate", "增长率"},
    "ipc1": {"ipc1", "源ipc", "分类号1"},
    "ipc2": {"ipc2", "目标ipc", "分类号2"},
    "probability": {"probability", "prob", "融合概率"},
    "title": {"title", "题名", "标题", "论文题目"},
    "authors": {"authors", "作者"},
    "doi": {"doi"},
    "keywords": {"keywords", "关键词"},
    "abstract": {"abstract", "摘要"},
}


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _auto_mapping(columns: Iterable[str]) -> Dict[str, str]:
    mapping = {}
    for column in columns:
        normalized = str(column).strip().lower()
        for target, aliases in FIELD_ALIASES.items():
            if normalized in {alias.lower() for alias in aliases}:
                mapping[target] = column
                break
    return mapping


def _number(value: Any, required: bool = False) -> Optional[float]:
    if value in (None, ""):
        if required:
            raise ValueError("必填数值为空")
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("数值不是有限数")
    return result


def normalize_rows(
    kind: str, table: ParsedTable, mapping: Dict[str, str]
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    valid, errors = [], []
    for row in table.rows:
        source_row = int(row.get("_source_row", 0))
        try:
            if kind == "ipc_metrics":
                year = int(_number(row.get(mapping.get("year", "")), required=True))
                if year < 1900 or year > 2100:
                    raise ValueError("年份超出 1900-2100")
                ipc_code = str(row.get(mapping.get("ipc_code", ""), "")).strip().upper()
                if not ipc_code:
                    raise ValueError("IPC 分类号为空")
                valid.append({
                    "ipc_code": ipc_code, "year": year,
                    "patent_count": _number(row.get(mapping.get("patent_count", ""))),
                    "degree_centrality": _number(row.get(mapping.get("degree_centrality", ""))),
                    "betweenness_centrality": _number(row.get(mapping.get("betweenness_centrality", ""))),
                    "growth_rate": _number(row.get(mapping.get("growth_rate", ""))),
                    "source_row": source_row,
                })
            elif kind == "ipc_fusions":
                probability = _number(row.get(mapping.get("probability", "")), required=True)
                if probability < 0 or probability > 1:
                    raise ValueError("融合概率必须在 0-1 之间")
                ipc1 = str(row.get(mapping.get("ipc1", ""), "")).strip().upper()
                ipc2 = str(row.get(mapping.get("ipc2", ""), "")).strip().upper()
                if not ipc1 or not ipc2:
                    raise ValueError("融合 IPC 不能为空")
                year_value = row.get(mapping.get("year", ""))
                valid.append({
                    "ipc1": ipc1, "ipc2": ipc2,
                    "year": int(float(year_value)) if year_value not in (None, "") else None,
                    "probability": probability, "source_row": source_row,
                })
            elif kind == "papers":
                title = str(row.get(mapping.get("title", ""), "")).strip()
                if not title:
                    raise ValueError("论文题名为空")
                year_value = row.get(mapping.get("year", ""))
                valid.append({
                    "title": title,
                    "authors": str(row.get(mapping.get("authors", ""), "") or ""),
                    "year": int(float(year_value)) if year_value not in (None, "") else None,
                    "doi": str(row.get(mapping.get("doi", ""), "") or ""),
                    "keywords": str(row.get(mapping.get("keywords", ""), "") or ""),
                    "abstract": str(row.get(mapping.get("abstract", ""), "") or ""),
                    "source_row": source_row,
                })
            else:
                raise ValueError("未知导入类型")
        except (TypeError, ValueError) as exc:
            errors.append({"row": source_row, "message": str(exc)})
    return valid, errors


def calculate_ipc_trends(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["ipc_code"], []).append(row)
    result = {}
    for code, items in grouped.items():
        items.sort(key=lambda item: item["year"])
        values = [
            item.get("patent_count") if item.get("patent_count") is not None
            else item.get("degree_centrality")
            for item in items
        ]
        points = [(item["year"], value) for item, value in zip(items, values) if value is not None]
        slope = None
        if len(points) >= 2:
            x_mean = mean(point[0] for point in points)
            y_mean = mean(point[1] for point in points)
            denominator = sum((point[0] - x_mean) ** 2 for point in points)
            slope = (
                sum((point[0] - x_mean) * (point[1] - y_mean) for point in points) / denominator
                if denominator else 0
            )
        growth = None
        if len(points) >= 2 and points[-2][1] not in (None, 0):
            growth = (points[-1][1] - points[-2][1]) / abs(points[-2][1])
        degree_change = None
        degrees = [item["degree_centrality"] for item in items if item.get("degree_centrality") is not None]
        if len(degrees) >= 2:
            degree_change = degrees[-1] - degrees[0]
        result[code] = {
            "start_year": items[0]["year"], "end_year": items[-1]["year"],
            "slope": slope, "latest_growth_rate": growth,
            "degree_centrality_change": degree_change,
            "change_point_year": _change_point(points),
        }
    return result


def _change_point(points: List[tuple[int, float]]) -> Optional[int]:
    if len(points) < 4:
        return None
    changes = [
        (points[index][0], abs(points[index][1] - points[index - 1][1]))
        for index in range(1, len(points))
    ]
    return max(changes, key=lambda item: item[1])[0]


class ImportService:
    def __init__(self, repository: Optional[LibraryRepository] = None):
        self.repository = repository or LibraryRepository()

    def stage_file(
        self, content: bytes, filename: str, media_type: str, kind: str,
        dataset_id: str = "", options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        safe_name = validate_upload(filename, media_type, len(content))
        digest = sha256_bytes(content)
        existing = self.repository.find_file_by_checksum(digest)
        if existing:
            return {"duplicate": True, "file": existing}
        file_id = f"file_{uuid4().hex[:16]}"
        directory = LIBRARY_RAW_DIR / (dataset_id or "staging")
        directory.mkdir(parents=True, exist_ok=True)
        stored_path = directory / f"{file_id}{Path(safe_name).suffix.lower()}"
        stored_path.write_bytes(content)
        try:
            parsed = parse_file(stored_path, **(options or {}))
        except Exception as exc:
            file_record = self.repository.create_source_file({
                "file_id": file_id, "dataset_id": dataset_id or None, "filename": safe_name,
                "media_type": media_type or "application/octet-stream", "checksum": digest,
                "stored_path": str(stored_path), "size_bytes": len(content),
                "parse_status": "failed", "parse_error": str(exc),
            })
            return {"duplicate": False, "file": file_record, "error": str(exc)}
        coverage = parsed.text_coverage if isinstance(parsed, ParsedDocument) else 1
        status = "needs_review" if isinstance(parsed, ParsedDocument) and parsed.warnings else "parsed"
        file_record = self.repository.create_source_file({
            "file_id": file_id, "dataset_id": dataset_id or None, "filename": safe_name,
            "media_type": media_type or "application/octet-stream", "checksum": digest,
            "stored_path": str(stored_path), "size_bytes": len(content),
            "parse_status": status, "text_coverage": coverage,
        })
        if isinstance(parsed, ParsedTable):
            mapping = _auto_mapping(parsed.columns)
            valid, errors = normalize_rows(kind, parsed, mapping)
            preview = {
                "columns": parsed.columns, "mapping": mapping,
                "rows": valid[:20], "valid_count": len(valid), "error_count": len(errors),
                "sheet_name": parsed.sheet_name, "warnings": parsed.warnings,
            }
        else:
            errors = []
            preview = {
                "title": parsed.title, "text_preview": parsed.text[:2000],
                "section_count": len(parsed.sections), "text_coverage": parsed.text_coverage,
                "warnings": parsed.warnings, "parsed_document": parsed.as_dict(),
            }
            mapping = {}
        import_record = self.repository.create_import({
            "dataset_id": dataset_id or None, "file_id": file_id, "kind": kind,
            "mapping": mapping, "preview": preview, "errors": errors,
        })
        return {"duplicate": False, "file": file_record, "import": import_record}

    def commit_import(
        self, import_id: str, dataset_id: str, mapping: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        record = self.repository.get_import(import_id)
        dataset = self.repository.get_dataset(dataset_id)
        if not record or not dataset:
            raise ValueError("导入任务或数据集不存在")
        with self.repository.db.connect() as connection:
            file_row = connection.execute(
                "SELECT * FROM source_files WHERE file_id=?", (record["file_id"],)
            ).fetchone()
        path = Path(file_row["stored_path"])
        parsed = parse_file(path)
        count = 0
        errors: List[Dict[str, Any]] = []
        if isinstance(parsed, ParsedTable):
            selected_mapping = mapping or record["mapping"] or _auto_mapping(parsed.columns)
            rows, errors = normalize_rows(record["kind"], parsed, selected_mapping)
            if record["kind"] == "ipc_metrics":
                count = self.repository.upsert_ipc_metrics(dataset_id, rows)
            elif record["kind"] == "ipc_fusions":
                count = self.repository.upsert_ipc_fusions(dataset_id, rows)
            elif record["kind"] == "papers":
                for row in rows:
                    self.repository.add_paper(dataset_id, row)
                    count += 1
        elif isinstance(parsed, ParsedDocument):
            if not parsed.text.strip() or parsed.text_coverage < 0.05:
                raise ValueError("文档没有足够文本，不能作为论文证据")
            paper = self.repository.add_paper(dataset_id, {
                "title": parsed.title, "file_id": record["file_id"],
                "abstract": parsed.text[:1000],
            }, [
                {
                    "section": section.section, "ordinal": section.ordinal,
                    "page_number": section.page_number, "content": section.content,
                }
                for section in parsed.sections
            ])
            count = 1 if paper else 0
        self.repository.update_import(import_id, "committed", dataset_id)
        return {"import_id": import_id, "dataset_id": dataset_id, "committed": count, "errors": errors}
