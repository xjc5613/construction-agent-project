# -*- coding: utf-8 -*-
import hashlib
import json
import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional

from src.ingestion.service import calculate_ipc_trends
from src.library import LibraryRepository

IPC_PATTERN = re.compile(r"\b[A-H]\d{2}[A-Z](?:[-－]?\d{1,4})?\b", re.IGNORECASE)


def stable_evidence_id(evidence_type: str, source_id: str, locator: str = "") -> str:
    material = f"{evidence_type}:{source_id}:{locator}".encode("utf-8")
    return f"evidence_{hashlib.sha256(material).hexdigest()[:20]}"


class EvidenceRetrievalService:
    def __init__(self, repository: Optional[LibraryRepository] = None):
        self.repository = repository or LibraryRepository()

    @staticmethod
    def _topic_codes(topic: Dict[str, Any]) -> List[str]:
        values = [topic.get("topic_name", ""), *topic.get("keywords", [])]
        for evidence in topic.get("evidence", []):
            values.extend([
                str(evidence.get("ipc", "")), str(evidence.get("content", "")),
                str(evidence.get("quote", "")),
            ])
        return sorted({
            match.upper().replace("－", "-").split("-")[0]
            for value in values for match in IPC_PATTERN.findall(value)
        })

    def retrieve(
        self, project_id: str, topic_id: str, start_year: int = 2000,
        end_year: int = 2025, paper_limit: int = 20,
        dataset_ids: Optional[List[str]] = None,
        min_relevance: float = 0,
        operator_notes: str = "",
    ) -> Dict[str, Any]:
        topic = self.repository.get_topic(topic_id)
        if not topic or topic["project_id"] != project_id:
            raise ValueError("项目主题不存在")
        if topic["requires_review"] or topic["status"] not in {"confirmed", "evidence_ready"}:
            raise ValueError("主题尚未确认")
        codes = self._topic_codes(topic)
        dataset_ids = [item for item in (dataset_ids or []) if item]
        ipc_rows = self.repository.ipc_series(codes, start_year, end_year)
        if not ipc_rows and codes:
            # Imported metrics can use subclass codes while material only mentions main class.
            with self.repository.db.connect() as connection:
                clauses = " OR ".join("m.ipc_code LIKE ?" for _ in codes)
                values = [f"{code}%" for code in codes] + [start_year, end_year]
                rows = connection.execute(
                    f"""SELECT m.*,d.name dataset_name,d.version dataset_version
                        FROM ipc_metrics m JOIN datasets d ON d.dataset_id=m.dataset_id
                        WHERE d.status='published' AND ({clauses}) AND m.year>=? AND m.year<=?
                        ORDER BY m.ipc_code,m.year""",
                    values,
                ).fetchall()
                ipc_rows = [dict(row) for row in rows]
        fusion_rows = self.repository.ipc_fusions(codes)
        if dataset_ids:
            ipc_rows = [
                row for row in ipc_rows if row["dataset_id"] in dataset_ids
            ]
            fusion_rows = [
                row for row in fusion_rows if row["dataset_id"] in dataset_ids
            ]
        search_terms = [topic["topic_name"], *topic.get("keywords", [])]
        papers_by_id: Dict[str, Dict[str, Any]] = {}
        for term in [term for term in search_terms if term][:8]:
            for paper in self.repository.search_papers(term, paper_limit, end_year):
                if dataset_ids and paper["dataset_id"] not in dataset_ids:
                    continue
                current = papers_by_id.get(paper["paper_id"])
                score = self._paper_score(paper, search_terms, end_year)
                if score >= min_relevance and (
                    not current or score > current["relevance"]
                ):
                    paper["relevance"] = score
                    papers_by_id[paper["paper_id"]] = paper
        papers = sorted(papers_by_id.values(), key=lambda item: item["relevance"], reverse=True)[:paper_limit]

        items: List[Dict[str, Any]] = []
        for row in ipc_rows:
            source_id = row["metric_id"]
            items.append({
                "evidence_id": stable_evidence_id("ipc_metric", source_id),
                "evidence_type": "ipc_metric", "source_id": source_id,
                "dataset_id": row["dataset_id"],
                "title": f"{row['ipc_code']} · {row['year']}",
                "content": self._ipc_content(row),
                "metadata": row, "relevance": 1.0,
            })
        for row in fusion_rows[:30]:
            source_id = row["fusion_id"]
            items.append({
                "evidence_id": stable_evidence_id("ipc_fusion", source_id),
                "evidence_type": "ipc_fusion", "source_id": source_id,
                "dataset_id": row["dataset_id"],
                "title": f"{row['ipc1']} × {row['ipc2']}",
                "content": f"融合概率 {row['probability']}",
                "metadata": row, "relevance": float(row["probability"]),
            })
        for paper in papers:
            source_id = paper["paper_id"]
            items.append({
                "evidence_id": stable_evidence_id("paper", source_id),
                "evidence_type": "paper", "source_id": source_id,
                "dataset_id": paper["dataset_id"], "title": paper["title"],
                "content": (paper.get("snippet") or paper.get("abstract") or "")[:1200],
                "metadata": {
                    "authors": paper.get("authors"), "year": paper.get("year"),
                    "doi": paper.get("doi"), "keywords": paper.get("keywords"),
                    "dataset_name": paper.get("dataset_name"),
                    "dataset_version": paper.get("dataset_version"),
                },
                "relevance": paper["relevance"],
            })
        for index, evidence in enumerate(topic.get("evidence", [])):
            source_id = evidence.get("material_id") or f"{topic_id}:{index}"
            items.append({
                "evidence_id": stable_evidence_id("material", source_id, str(index)),
                "evidence_type": "material", "source_id": source_id,
                "title": evidence.get("title", "项目材料"),
                "content": evidence.get("content") or evidence.get("quote", ""),
                "metadata": evidence, "relevance": 1.0,
            })

        quality = self._quality(ipc_rows, papers, items)
        query = {
            "codes": codes, "terms": search_terms, "start_year": start_year,
            "end_year": end_year, "paper_limit": paper_limit,
            "dataset_ids": dataset_ids, "min_relevance": min_relevance,
        }
        package = self.repository.create_evidence_package(
            project_id, topic_id, query, quality, items, operator_notes
        )
        self.repository.update_topic(
            topic_id, {"status": "evidence_ready" if quality["sufficient"] else "confirmed"}
        )
        return package

    @staticmethod
    def _ipc_content(row: Dict[str, Any]) -> str:
        parts = [f"{row['ipc_code']} 在 {row['year']} 年"]
        for key, label in (
            ("patent_count", "专利量"), ("degree_centrality", "度中心度"),
            ("betweenness_centrality", "中介中心度"), ("growth_rate", "增长率"),
        ):
            if row.get(key) is not None:
                parts.append(f"{label}={row[key]}")
        return "，".join(parts)

    @staticmethod
    def _paper_score(paper: Dict[str, Any], terms: Iterable[str], end_year: int) -> float:
        haystack = " ".join([
            str(paper.get("title", "")), str(paper.get("abstract", "")),
            str(paper.get("keywords", "")), str(paper.get("snippet", "")),
        ]).lower()
        matches = sum(1 for term in terms if term and str(term).lower() in haystack)
        freshness = 0
        if paper.get("year"):
            freshness = max(0, 1 - (end_year - int(paper["year"])) / 20)
        return round(min(1.0, 0.2 + matches * 0.18 + freshness * 0.2), 4)

    @staticmethod
    def _quality(
        ipc_rows: List[Dict[str, Any]], papers: List[Dict[str, Any]],
        items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        years = sorted({row["year"] for row in ipc_rows})
        paper_fragments = sum(bool(item.get("content")) for item in items if item["evidence_type"] == "paper")
        missing = []
        if not ipc_rows:
            missing.append("至少1条IPC时间序列")
        if len(years) < 3:
            missing.append("IPC数据至少覆盖3个年份")
        if len(papers) < 2:
            missing.append("至少2篇相关论文")
        if paper_fragments < 3:
            missing.append("至少3个论文证据片段")
        score = min(100, len(ipc_rows) * 4 + len(years) * 8 + len(papers) * 10 + paper_fragments * 5)
        return {
            "score": score, "sufficient": not missing, "missing": missing,
            "ipc_record_count": len(ipc_rows), "year_count": len(years),
            "paper_count": len(papers), "paper_fragment_count": paper_fragments,
            "data_cutoff": max(years) if years else None,
            "ipc_trends": calculate_ipc_trends(ipc_rows) if ipc_rows else {},
        }

    def update_item(
        self, evidence_id: str, excluded: bool, reason: str = "",
        project_id: str = "",
    ) -> None:
        evidence = self.resolve_evidence(evidence_id, project_id)
        if not evidence:
            raise ValueError("证据不存在")
        self.repository.update_evidence_item(
            evidence_id, excluded, reason, evidence["package_id"]
        )

    def resolve_evidence(
        self, evidence_id: str, project_id: str = ""
    ) -> Optional[Dict[str, Any]]:
        with self.repository.db.connect() as connection:
            query = (
                """SELECT e.*,p.project_id,p.topic_id,d.name dataset_name,d.version dataset_version
                   FROM evidence_items e JOIN evidence_packages p ON p.package_id=e.package_id
                   LEFT JOIN datasets d ON d.dataset_id=e.dataset_id
                   WHERE e.evidence_id=?"""
            )
            values = [evidence_id]
            if project_id:
                query += " AND p.project_id=?"
                values.append(project_id)
            query += " ORDER BY p.created_at DESC,p.rowid DESC LIMIT 1"
            row = connection.execute(query, values).fetchone()
            if not row:
                return None
            result = dict(row)
            result["metadata"] = json.loads(result.pop("metadata_json"))
            result["excluded"] = bool(result["excluded"])
            return result
