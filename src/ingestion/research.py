# -*- coding: utf-8 -*-
"""Strict preview/commit ingestion for empirical v3 research inputs."""

import itertools
import json
import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4

from src.library import LibraryRepository


IPC_PATTERN = re.compile(
    r"^([A-H]\d{2}[A-Z])\s*(\d{1,4})(?:\s*/\s*(\d{1,6}))?$", re.IGNORECASE
)
PAPER_TYPES = {
    "journal_article", "conference_paper", "review", "book_chapter", "thesis", "other"
}
PAPER_TYPE_ALIASES = {
    "journal": "journal_article", "article": "journal_article", "期刊论文": "journal_article",
    "conference": "conference_paper", "会议论文": "conference_paper",
    "综述": "review", "review_article": "review", "学位论文": "thesis",
    "book": "book_chapter", "专著章节": "book_chapter",
}
STAGING_SCHEMAS = {
    "patents": {
        "required": ["publication_number", "application_year", "ipc_codes"],
        "optional": ["title", "abstract", "applicant_type", "legal_status", "ipc_edition"],
    },
    "reduced_edges": {
        "required": ["year", "ipc1", "ipc2", "cooccurrence_count", "source_patent_count",
                     "ipc1_count", "ipc2_count", "total_patent_count",
                     "normalization_method", "normalization_formula"],
    },
    "papers": {"required": ["title", "year", "paper_type"]},
}


def _id(prefix: str) -> str:
    return "%s_%s" % (prefix, uuid4().hex[:16])


def normalize_ipc(raw: Any, level: str = "main_group") -> Dict[str, str]:
    value = re.sub(r"[.·]", "", str(raw or "").strip().upper())
    match = IPC_PATTERN.match(value)
    if not match:
        raise ValueError("IPC 分类号格式无效: %s" % raw)
    subclass, group, subgroup = match.groups()
    if level == "subclass":
        normalized = subclass
    elif level == "main_group":
        normalized = "%s%s/00" % (subclass, int(group))
    elif level == "subgroup":
        if subgroup is None:
            raise ValueError("子组分析要求 IPC 包含 / 子组")
        normalized = "%s%s/%s" % (subclass, int(group), subgroup)
    else:
        raise ValueError("IPC 分析层级必须是 subclass、main_group 或 subgroup")
    return {"raw": str(raw), "normalized": normalized, "level": level}


def parse_ipc_assignments(raw: Any, level: str = "main_group") -> Tuple[List[Dict[str, str]], List[str]]:
    values = raw if isinstance(raw, (list, tuple, set)) else re.split(r"[,，;；|]+", str(raw or ""))
    normalized, invalid = {}, []
    for value in values:
        if not str(value).strip():
            continue
        try:
            item = normalize_ipc(value, level)
            normalized.setdefault(item["normalized"], item)
        except ValueError:
            invalid.append(str(value))
    return sorted(normalized.values(), key=lambda item: item["normalized"]), invalid


def normalize_paper_type(value: Any) -> Tuple[str, bool]:
    raw = str(value or "").strip().lower()
    mapped = PAPER_TYPE_ALIASES.get(raw, raw)
    if mapped in PAPER_TYPES and mapped != "other":
        return mapped, False
    return "other", True


def apply_field_mapping(row: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
    """Map source column names to the canonical staging schema without dropping source data."""
    return {canonical: row.get(source) for canonical, source in mapping.items()}


class ResearchImportService:
    def __init__(self, repository: Optional[LibraryRepository] = None):
        self.repository = repository or LibraryRepository()

    def preview(
        self, kind: str, rows: Iterable[Dict[str, Any]], *, dataset_id: str,
        ipc_level: str = "main_group", ipc_edition: str = "",
        observation_cutoff: str = "", completeness: str = "complete",
        source_database: str = "", project_id: str = "",
    ) -> Dict[str, Any]:
        if kind not in {"patents", "reduced_edges", "papers", "ipc_mappings", "fusion_hypotheses"}:
            raise ValueError("不支持的研究导入类型")
        if completeness not in {"complete", "partial", "unknown", "not_applicable"}:
            raise ValueError("覆盖完整性状态无效")
        source_rows = list(rows)
        normalized, errors, warnings = [], [], []
        duplicate_source = 0
        duplicate_assignment_count = 0
        pair_count = 0
        seen = set()
        paper_type_counts = Counter()
        for index, row in enumerate(source_rows, start=2):
            source_row = int(row.get("_source_row") or index)
            try:
                if kind == "patents":
                    publication_number = str(row.get("publication_number") or "").strip()
                    if not publication_number:
                        raise ValueError("专利公开号为空")
                    year = int(row["application_year"])
                    raw_values = re.split(r"[,，;；|]+", str(row.get("ipc_codes") or ""))
                    assignments, invalid = parse_ipc_assignments(row.get("ipc_codes"), ipc_level)
                    duplicate_assignment_count += max(0, len([v for v in raw_values if v.strip()]) - len(assignments) - len(invalid))
                    if invalid:
                        raise ValueError("无法解析 IPC: %s" % ", ".join(invalid))
                    if not assignments:
                        raise ValueError("专利至少需要一个有效 IPC")
                    if publication_number in seen:
                        duplicate_source += 1
                        continue
                    seen.add(publication_number)
                    pair_count += len(list(itertools.combinations(assignments, 2)))
                    normalized.append({
                        "publication_number": publication_number, "application_year": year,
                        "title": str(row.get("title") or ""), "abstract": str(row.get("abstract") or ""),
                        "applicant_type": str(row.get("applicant_type") or ""),
                        "legal_status": str(row.get("legal_status") or ""),
                        "ipc_assignments": [{**item, "ipc_edition": str(row.get("ipc_edition") or ipc_edition)} for item in assignments],
                        "source_row": source_row,
                    })
                elif kind == "reduced_edges":
                    if row.get("cooccurrence_count") in (None, ""):
                        if row.get("probability") not in (None, ""):
                            raise ValueError("仅含概率的 IPC 对只能作为研究者假设导入")
                        raise ValueError("约简边缺少共现支持数")
                    missing = [field for field in STAGING_SCHEMAS["reduced_edges"]["required"]
                               if row.get(field) in (None, "")]
                    if missing:
                        raise ValueError("约简边缺少可复核字段: %s" % ", ".join(missing))
                    left = normalize_ipc(row.get("ipc1"), ipc_level)["normalized"]
                    right = normalize_ipc(row.get("ipc2"), ipc_level)["normalized"]
                    left, right = sorted((left, right))
                    if left == right:
                        raise ValueError("约简边不能连接同一 IPC")
                    item = {**row, "ipc1": left, "ipc2": right,
                            "year": int(row["year"]), "source_row": source_row,
                            "cooccurrence_count": int(row["cooccurrence_count"])}
                    for field in ("source_patent_count", "ipc1_count", "ipc2_count", "total_patent_count"):
                        item[field] = int(row[field]) if row.get(field) not in (None, "") else None
                    normalized.append(item)
                elif kind == "papers":
                    if not str(row.get("title") or "").strip():
                        raise ValueError("论文题名为空")
                    paper_type, needs_review = normalize_paper_type(row.get("paper_type"))
                    paper_type_counts[paper_type] += 1
                    if needs_review:
                        warnings.append({"row": source_row, "message": "论文类型已映射为 other，需显式审核"})
                    normalized.append({**row, "title": str(row["title"]).strip(),
                                       "year": int(row["year"]), "paper_type": paper_type,
                                       "paper_type_needs_review": needs_review,
                                       "paper_type_reviewed": bool(row.get("paper_type_reviewed")),
                                       "source_database": str(row.get("source_database") or source_database),
                                       "source_row": source_row})
                elif kind == "ipc_mappings":
                    parsed = normalize_ipc(row.get("ipc_code_raw"), ipc_level)
                    normalized.append({**row, "ipc_code_raw": parsed["raw"],
                                       "ipc_code_normalized": str(row.get("ipc_code_normalized") or parsed["normalized"]),
                                       "analysis_level": ipc_level, "source_row": source_row})
                else:
                    left = normalize_ipc(row.get("ipc1"), ipc_level)["normalized"]
                    right = normalize_ipc(row.get("ipc2"), ipc_level)["normalized"]
                    left, right = sorted((left, right))
                    probability = row.get("probability")
                    if probability is not None and not 0 <= float(probability) <= 1:
                        raise ValueError("陈述概率必须在 0-1 之间")
                    normalized.append({**row, "ipc1": left, "ipc2": right,
                                       "stated_probability": probability, "source_row": source_row})
            except (KeyError, TypeError, ValueError) as exc:
                errors.append({"row": source_row, "message": str(exc)})
        years = sorted({int(item["application_year"] if kind == "patents" else item["year"])
                        for item in normalized if ("application_year" in item or "year" in item)})
        if 2025 in years and completeness == "partial" and not observation_cutoff:
            errors.append({"row": 0, "message": "2025 年部分数据必须填写 observation_cutoff"})
        database_duplicates = 0
        if kind == "patents" and normalized:
            numbers = [item["publication_number"] for item in normalized]
            placeholders = ",".join("?" for _ in numbers)
            with self.repository.db.connect() as connection:
                database_duplicates = int(connection.execute(
                    "SELECT COUNT(*) FROM patents WHERE dataset_id=? AND publication_number IN (%s)" % placeholders,
                    [dataset_id, *numbers],
                ).fetchone()[0])
        return {"kind": kind, "dataset_id": dataset_id, "project_id": project_id,
                "ipc_level": ipc_level, "ipc_edition": ipc_edition,
                "observation_cutoff": observation_cutoff, "completeness": completeness,
                "source_count": len(source_rows), "valid_count": len(normalized),
                "invalid_count": len(errors), "duplicate_source_count": duplicate_source,
                "duplicate_assignment_count": duplicate_assignment_count,
                "duplicate_database_count": database_duplicates, "pair_count": pair_count,
                "year_coverage": years, "paper_type_coverage": dict(paper_type_counts),
                "rows": normalized, "errors": errors, "warnings": warnings}

    def commit(self, preview: Dict[str, Any], *, file_id: Optional[str] = None) -> Dict[str, Any]:
        if preview.get("errors"):
            raise ValueError("导入预览仍有错误，不能提交")
        kind, dataset_id, rows = preview["kind"], preview["dataset_id"], preview["rows"]
        if kind == "papers" and any(
            row.get("paper_type_needs_review") and not row.get("paper_type_reviewed")
            for row in rows
        ):
            raise ValueError("other 论文类型必须先完成显式审核")
        committed = 0
        duplicates_skipped = 0
        with self.repository.db.transaction() as connection:
            for row in rows:
                if kind == "patents":
                    exists = connection.execute(
                        "SELECT 1 FROM patents WHERE dataset_id=? AND publication_number=?",
                        (dataset_id, row["publication_number"]),
                    ).fetchone()
                    if exists:
                        duplicates_skipped += 1
                        continue
                    patent_id = _id("patent")
                    connection.execute(
                        """INSERT INTO patents(patent_id,dataset_id,publication_number,title,abstract,
                           application_year,applicant_type,legal_status,file_id,source_row)
                           VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (patent_id, dataset_id, row["publication_number"], row.get("title", ""),
                         row.get("abstract", ""), row["application_year"], row.get("applicant_type", ""),
                         row.get("legal_status", ""), file_id, row["source_row"]),
                    )
                    for assignment in row["ipc_assignments"]:
                        connection.execute(
                            """INSERT INTO patent_ipcs(assignment_id,patent_id,ipc_code_raw,
                               ipc_code_normalized,ipc_level,ipc_edition,mapping_status,mapping_rule_version)
                               VALUES (?,?,?,?,?,?,?,?)""",
                            (_id("assignment"), patent_id, assignment["raw"], assignment["normalized"],
                             preview["ipc_level"], assignment.get("ipc_edition", ""), "mapped", "ipc-main-group-v1"),
                        )
                elif kind == "reduced_edges":
                    connection.execute(
                        """INSERT INTO reduced_ipc_edges(reduced_edge_id,dataset_id,year,ipc1,ipc2,
                           cooccurrence_count,source_patent_count,ipc1_count,ipc2_count,total_patent_count,
                           normalization_method,denominator_json,source_row,review_status)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'pending')""",
                        (_id("reduced_edge"), dataset_id, row["year"], row["ipc1"], row["ipc2"],
                         row["cooccurrence_count"], row.get("source_patent_count"), row.get("ipc1_count"),
                         row.get("ipc2_count"), row.get("total_patent_count"),
                         str(row.get("normalization_method") or ""),
                         json.dumps({
                             "source_patent_count": row.get("source_patent_count"),
                             "ipc1_count": row.get("ipc1_count"),
                             "ipc2_count": row.get("ipc2_count"),
                             "total_patent_count": row.get("total_patent_count"),
                             "formula": row.get("normalization_formula"),
                         }, ensure_ascii=False, sort_keys=True), row["source_row"]),
                    )
                elif kind == "papers":
                    connection.execute(
                        """INSERT INTO papers(paper_id,dataset_id,title,authors,year,doi,keywords,abstract,
                           file_id,paper_type,source_database,publication_date,citation_count,citation_observed_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (_id("paper"), dataset_id, row["title"], str(row.get("authors") or ""), row["year"],
                         str(row.get("doi") or ""), str(row.get("keywords") or ""), str(row.get("abstract") or ""),
                         file_id, row["paper_type"], row.get("source_database", ""), row.get("publication_date"),
                         row.get("citation_count"), row.get("citation_observed_at")),
                    )
                elif kind == "ipc_mappings":
                    connection.execute(
                        """INSERT INTO ipc_code_mappings(mapping_id,ipc_code_raw,ipc_code_normalized,
                           analysis_level,source_edition,target_edition,rule_version,status,rationale)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        (_id("mapping"), row["ipc_code_raw"], row["ipc_code_normalized"], row["analysis_level"],
                         str(row.get("source_edition") or ""), str(row.get("target_edition") or ""),
                         str(row.get("rule_version") or "manual-v1"), str(row.get("status") or "suggested"),
                         str(row.get("rationale") or "")),
                    )
                else:
                    connection.execute(
                        """INSERT INTO researcher_fusion_hypotheses(hypothesis_id,project_id,dataset_id,
                           ipc1,ipc2,stated_probability,rationale,provenance_json) VALUES (?,?,?,?,?,?,?,?)""",
                        (_id("hypothesis"), preview.get("project_id") or None, dataset_id, row["ipc1"], row["ipc2"],
                         row.get("stated_probability"), str(row.get("rationale") or ""),
                         json.dumps({"source_row": row["source_row"]})),
                    )
                committed += 1
            for year in preview.get("year_coverage", []):
                source_kind = "patent" if kind == "patents" else kind.rstrip("s")
                connection.execute(
                    """INSERT INTO data_coverage(coverage_id,dataset_id,source_kind,year,
                       observation_cutoff,observed_count,completeness,researcher_notes,reviewed)
                       VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(dataset_id,source_kind,year) DO UPDATE SET
                       observation_cutoff=excluded.observation_cutoff,observed_count=excluded.observed_count,
                       completeness=excluded.completeness""",
                    (_id("coverage"), dataset_id, source_kind, year, preview.get("observation_cutoff", ""),
                     sum(1 for item in rows if int(item.get("application_year", item.get("year", -1))) == year),
                     preview.get("completeness", "unknown"), "", 0),
                )
        return {"kind": kind, "dataset_id": dataset_id, "committed": committed,
                "duplicates_skipped": duplicates_skipped}
