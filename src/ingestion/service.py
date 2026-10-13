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
from src.library.constants import COMPATIBLE_HISTORICAL_PERIODS, HISTORICAL_PERIODS

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
    kind: str, table: ParsedTable, mapping: Dict[str, str],
    period_code: str = "",
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    valid, errors = [], []
    for row in table.rows:
        source_row = int(row.get("_source_row", 0))
        try:
            if kind == "ipc_metrics":
                year = int(_number(row.get(mapping.get("year", "")), required=True))
                if year < 1900 or year > 2100:
                    raise ValueError("年份超出 1900-2100")
                _validate_period_year(year, period_code)
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
                year = int(float(year_value)) if year_value not in (None, "") else None
                if period_code and year is None:
                    raise ValueError("阶段化 IPC 融合记录必须填写年份")
                _validate_period_year(year, period_code)
                valid.append({
                    "ipc1": ipc1, "ipc2": ipc2,
                    "year": year,
                    "probability": probability, "source_row": source_row,
                })
            elif kind == "papers":
                title = str(row.get(mapping.get("title", ""), "")).strip()
                if not title:
                    raise ValueError("论文题名为空")
                year_value = row.get(mapping.get("year", ""))
                year = int(float(year_value)) if year_value not in (None, "") else None
                if period_code and year is None:
                    raise ValueError("阶段化论文必须填写年份")
                _validate_period_year(year, period_code)
                valid.append({
                    "title": title,
                    "authors": str(row.get(mapping.get("authors", ""), "") or ""),
                    "year": year,
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


def _validate_period_year(year: Optional[int], period_code: str) -> None:
    if not period_code or year is None:
        return
    bounds = COMPATIBLE_HISTORICAL_PERIODS.get(period_code)
    if not bounds:
        raise ValueError("历史阶段无效")
    if not bounds[0] <= year <= bounds[1]:
        raise ValueError(
            f"年份 {year} 不属于阶段 {bounds[0]}-{bounds[1]}"
        )


def period_for_year(year: int) -> str:
    for code, (start, end) in HISTORICAL_PERIODS.items():
        if start <= year <= end:
            return code
    raise ValueError(f"年份 {year} 不属于支持的历史阶段")


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
        options = options or {}
        safe_name = validate_upload(filename, media_type, len(content))
        dataset = self.repository.get_dataset(dataset_id) if dataset_id else None
        period_code = dataset.get("period_code", "") if dataset else ""
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
                "content_role": kind,
            })
            return {"duplicate": False, "file": file_record, "error": str(exc)}
        coverage = parsed.text_coverage if isinstance(parsed, ParsedDocument) else 1
        status = "needs_review" if isinstance(parsed, ParsedDocument) and parsed.warnings else "parsed"
        file_record = self.repository.create_source_file({
            "file_id": file_id, "dataset_id": dataset_id or None, "filename": safe_name,
            "media_type": media_type or "application/octet-stream", "checksum": digest,
            "stored_path": str(stored_path), "size_bytes": len(content),
            "parse_status": status, "text_coverage": coverage,
            "content_role": kind,
        })
        if isinstance(parsed, ParsedTable):
            mapping = _auto_mapping(parsed.columns)
            valid, errors = normalize_rows(kind, parsed, mapping, period_code)
            preview = {
                "columns": parsed.columns, "mapping": mapping,
                "rows": valid[:20], "valid_count": len(valid), "error_count": len(errors),
                "sheet_name": parsed.sheet_name, "warnings": parsed.warnings,
            }
        else:
            errors = []
            document_year = options.get("document_year")
            if kind == "papers" and period_code:
                if document_year is None:
                    errors.append({"row": 0, "message": "论文文档需要补充年份"})
                else:
                    try:
                        _validate_period_year(int(document_year), period_code)
                    except ValueError as exc:
                        errors.append({"row": 0, "message": str(exc)})
            preview = {
                "title": parsed.title, "text_preview": parsed.text[:2000],
                "section_count": len(parsed.sections), "text_coverage": parsed.text_coverage,
                "warnings": parsed.warnings, "parsed_document": parsed.as_dict(),
                "document_year": document_year,
            }
            mapping = {}
        import_record = self.repository.create_import({
            "dataset_id": dataset_id or None, "file_id": file_id, "kind": kind,
            "component_kind": kind, "mapping": mapping,
            "preview": preview, "errors": errors,
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
            rows, errors = normalize_rows(
                record["component_kind"] or record["kind"], parsed,
                selected_mapping, dataset.get("period_code") or "",
            )
            if record["kind"] == "ipc_metrics":
                count = self.repository.upsert_ipc_metrics(dataset_id, rows)
            elif record["kind"] == "ipc_fusions":
                count = self.repository.upsert_ipc_fusions(dataset_id, rows)
            elif record["kind"] == "papers":
                for row in rows:
                    self.repository.add_paper(
                        dataset_id, {**row, "file_id": record["file_id"]}
                    )
                    count += 1
        elif isinstance(parsed, ParsedDocument):
            if not parsed.text.strip() or parsed.text_coverage < 0.05:
                raise ValueError("文档没有足够文本，不能作为论文证据")
            if record["component_kind"] == "analysis_document":
                count = 1
                self.repository.update_import(import_id, "committed", dataset_id)
                return {
                    "import_id": import_id, "dataset_id": dataset_id,
                    "committed": count, "errors": [],
                }
            document_year = record["preview"].get("document_year")
            if dataset.get("period_code") and document_year is None:
                raise ValueError("论文文档需要补充年份")
            _validate_period_year(
                int(document_year) if document_year is not None else None,
                dataset.get("period_code") or "",
            )
            paper = self.repository.add_paper(dataset_id, {
                "title": parsed.title, "file_id": record["file_id"],
                "abstract": parsed.text[:1000], "year": document_year,
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

    def guided_stage(
        self, content: bytes, filename: str, media_type: str,
        component_kind: str, technology_node_id: str,
        public_kind: str, options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        allowed = {
            "ipc": {"ipc_metrics", "ipc_fusions"},
            "paper": {"papers"},
            "integrated": {
                "ipc_metrics", "ipc_fusions", "papers", "analysis_document",
            },
        }
        if component_kind not in allowed.get(public_kind, set()):
            raise ValueError("导入组成与数据类型不匹配")
        from src.library import TechnologyRepository
        technology = TechnologyRepository(self.repository.db).get(
            technology_node_id
        )
        if (
            not technology or technology["level"] != 3
            or technology.get("effective_status") != "active"
        ):
            raise ValueError("引导导入必须选择有效启用的三级技术")
        result = self.stage_file(
            content, filename, media_type, component_kind, "", options
        )
        if result.get("duplicate") or result.get("error"):
            return result
        record = result["import"]
        periods = self._guided_periods(record)
        versions = {
            period: self.repository.generated_dataset_version(
                technology_node_id, period, public_kind
            )
            for period in periods
        }
        result["plan"] = {
            "technology_node_id": technology_node_id,
            "technology_path": technology["path_text"],
            "public_kind": public_kind,
            "component_kind": component_kind,
            "periods": periods,
            "generated_versions": versions,
            "split_required": len(periods) > 1,
        }
        return result

    def _guided_periods(self, record: Dict[str, Any]) -> List[str]:
        with self.repository.db.connect() as connection:
            file_row = connection.execute(
                "SELECT * FROM source_files WHERE file_id=?",
                (record["file_id"],),
            ).fetchone()
        parsed = parse_file(Path(file_row["stored_path"]))
        years: List[int] = []
        if isinstance(parsed, ParsedTable):
            mapping = record.get("mapping") or _auto_mapping(parsed.columns)
            rows, errors = normalize_rows(
                record["component_kind"], parsed, mapping
            )
            if errors and not rows:
                raise ValueError("导入文件没有可用记录")
            years = [
                int(item["year"]) for item in rows
                if item.get("year") is not None
            ]
        else:
            document_year = record.get("preview", {}).get("document_year")
            if document_year is not None:
                years = [int(document_year)]
        if not years:
            raise ValueError("无法从导入记录推断历史阶段，请补充年份")
        return sorted({period_for_year(year) for year in years})

    def guided_commit(
        self, import_id: str, technology_node_id: str, public_kind: str,
        *, mapping: Optional[Dict[str, str]] = None,
        versions: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        record = self.repository.get_import(import_id)
        if not record:
            raise ValueError("导入任务不存在")
        periods = self._guided_periods(record)
        versions = versions or {}
        with self.repository.db.connect() as connection:
            file_row = connection.execute(
                "SELECT * FROM source_files WHERE file_id=?",
                (record["file_id"],),
            ).fetchone()
        parsed = parse_file(Path(file_row["stored_path"]))
        component = record["component_kind"]
        selected_mapping = mapping or record.get("mapping") or {}
        grouped: Dict[str, List[Dict[str, Any]]] = {
            period: [] for period in periods
        }
        document = isinstance(parsed, ParsedDocument)
        if isinstance(parsed, ParsedTable):
            rows, errors = normalize_rows(
                component, parsed,
                selected_mapping or _auto_mapping(parsed.columns),
            )
            if errors and not rows:
                raise ValueError("导入文件没有可提交记录")
            for row in rows:
                if row.get("year") is None:
                    raise ValueError("引导导入的记录必须包含年份")
                grouped[period_for_year(int(row["year"]))].append(row)
        else:
            year = record.get("preview", {}).get("document_year")
            if year is None:
                raise ValueError("论文文档需要补充年份")
            grouped[period_for_year(int(year))].append({
                "title": parsed.title, "file_id": record["file_id"],
                "abstract": parsed.text[:1000], "year": int(year),
            })

        committed = []
        for index, period in enumerate(periods):
            version = versions.get(period) or self.repository.generated_dataset_version(
                technology_node_id, period, public_kind
            )
            dataset = self.repository.create_dataset(
                public_kind, "", version,
                technology_node_id=technology_node_id,
                period_code=period, public_kind=public_kind,
            )
            rows = grouped[period]
            if component == "ipc_metrics":
                count = self.repository.upsert_ipc_metrics(dataset["dataset_id"], rows)
            elif component == "ipc_fusions":
                count = self.repository.upsert_ipc_fusions(dataset["dataset_id"], rows)
            elif component == "papers":
                count = 0
                for row in rows:
                    row = {**row, "file_id": record["file_id"]}
                    chunks = []
                    if document:
                        chunks = [
                            {
                                "section": section.section,
                                "ordinal": section.ordinal,
                                "page_number": section.page_number,
                                "content": section.content,
                            }
                            for section in parsed.sections
                        ]
                    self.repository.add_paper(dataset["dataset_id"], row, chunks)
                    count += 1
            else:
                count = 1
            if index == 0:
                target_import_id = import_id
            else:
                target_import_id = self.repository.create_import({
                    "dataset_id": dataset["dataset_id"],
                    "file_id": record["file_id"],
                    "kind": record["kind"],
                    "component_kind": component,
                    "mapping": selected_mapping,
                    "preview": record.get("preview", {}),
                    "errors": [],
                })["import_id"]
            self.repository.update_import(
                target_import_id, "committed", dataset["dataset_id"]
            )
            committed.append({
                "import_id": target_import_id,
                "dataset": self.repository.get_dataset(dataset["dataset_id"]),
                "committed": count,
                "publication_ready": count > 0,
            })
        return {
            "items": committed,
            "total": len(committed),
            "split": len(committed) > 1,
        }
