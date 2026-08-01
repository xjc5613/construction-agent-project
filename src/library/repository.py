# -*- coding: utf-8 -*-
import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from .database import LibraryDatabase


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:16]}"


def _dict(row) -> Optional[Dict[str, Any]]:
    return dict(row) if row is not None else None


class LibraryRepository:
    def __init__(self, database: Optional[LibraryDatabase] = None):
        self.db = database or LibraryDatabase()

    def create_dataset(
        self, kind: str, name: str, version: str, description: str = "", checksum: str = ""
    ) -> Dict[str, Any]:
        dataset_id = _id("dataset")
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT INTO datasets(dataset_id,kind,name,version,description,checksum)
                   VALUES (?,?,?,?,?,?)""",
                (dataset_id, kind, name.strip(), version.strip(), description, checksum),
            )
            return dict(connection.execute(
                "SELECT * FROM datasets WHERE dataset_id=?", (dataset_id,)
            ).fetchone())

    def list_datasets(self, kind: str = "") -> List[Dict[str, Any]]:
        with self.db.connect() as connection:
            if kind:
                rows = connection.execute(
                    "SELECT * FROM datasets WHERE kind=? ORDER BY imported_at DESC", (kind,)
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM datasets ORDER BY imported_at DESC"
                ).fetchall()
            return [dict(row) for row in rows]

    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        with self.db.connect() as connection:
            return _dict(connection.execute(
                "SELECT * FROM datasets WHERE dataset_id=?", (dataset_id,)
            ).fetchone())

    def update_dataset_status(self, dataset_id: str, status: str) -> Optional[Dict[str, Any]]:
        with self.db.transaction() as connection:
            connection.execute(
                "UPDATE datasets SET status=? WHERE dataset_id=?", (status, dataset_id)
            )
            return _dict(connection.execute(
                "SELECT * FROM datasets WHERE dataset_id=?", (dataset_id,)
            ).fetchone())

    def find_file_by_checksum(self, checksum: str) -> Optional[Dict[str, Any]]:
        with self.db.connect() as connection:
            return _dict(connection.execute(
                "SELECT * FROM source_files WHERE checksum=?", (checksum,)
            ).fetchone())

    def create_source_file(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        file_id = payload.get("file_id") or _id("file")
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT INTO source_files(
                    file_id,dataset_id,filename,media_type,checksum,stored_path,size_bytes,
                    parse_status,text_coverage,parse_error
                ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    file_id, payload.get("dataset_id"), payload["filename"],
                    payload["media_type"], payload["checksum"], payload["stored_path"],
                    payload["size_bytes"], payload.get("parse_status", "pending"),
                    payload.get("text_coverage", 0), payload.get("parse_error", ""),
                ),
            )
            return dict(connection.execute(
                "SELECT * FROM source_files WHERE file_id=?", (file_id,)
            ).fetchone())

    def create_import(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        import_id = payload.get("import_id") or _id("import")
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT INTO imports(import_id,dataset_id,file_id,kind,status,mapping_json,preview_json,error_json)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    import_id, payload.get("dataset_id"), payload["file_id"], payload["kind"],
                    payload.get("status", "preview"),
                    json.dumps(payload.get("mapping", {}), ensure_ascii=False),
                    json.dumps(payload.get("preview", {}), ensure_ascii=False),
                    json.dumps(payload.get("errors", []), ensure_ascii=False),
                ),
            )
        return self.get_import(import_id)

    def get_import(self, import_id: str) -> Optional[Dict[str, Any]]:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM imports WHERE import_id=?", (import_id,)
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            for key in ("mapping_json", "preview_json", "error_json"):
                result[key.removesuffix("_json")] = json.loads(result.pop(key))
            return result

    def update_import(self, import_id: str, status: str, dataset_id: str = "") -> None:
        with self.db.transaction() as connection:
            if dataset_id:
                connection.execute(
                    "UPDATE imports SET status=?,dataset_id=? WHERE import_id=?",
                    (status, dataset_id, import_id),
                )
            else:
                connection.execute(
                    "UPDATE imports SET status=? WHERE import_id=?", (status, import_id)
                )

    def upsert_ipc_metrics(self, dataset_id: str, rows: Iterable[Dict[str, Any]]) -> int:
        count = 0
        with self.db.transaction() as connection:
            for row in rows:
                connection.execute(
                    """INSERT INTO ipc_metrics(
                        metric_id,dataset_id,ipc_code,year,patent_count,degree_centrality,
                        betweenness_centrality,growth_rate,source_row
                    ) VALUES (?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(dataset_id,ipc_code,year) DO UPDATE SET
                        patent_count=excluded.patent_count,
                        degree_centrality=excluded.degree_centrality,
                        betweenness_centrality=excluded.betweenness_centrality,
                        growth_rate=excluded.growth_rate,
                        source_row=excluded.source_row""",
                    (
                        _id("ipc"), dataset_id, row["ipc_code"], row["year"],
                        row.get("patent_count"), row.get("degree_centrality"),
                        row.get("betweenness_centrality"), row.get("growth_rate"),
                        row.get("source_row"),
                    ),
                )
                count += 1
        return count

    def upsert_ipc_fusions(self, dataset_id: str, rows: Iterable[Dict[str, Any]]) -> int:
        count = 0
        with self.db.transaction() as connection:
            for row in rows:
                connection.execute(
                    """INSERT INTO ipc_fusions(fusion_id,dataset_id,ipc1,ipc2,year,probability,source_row)
                       VALUES (?,?,?,?,?,?,?)
                       ON CONFLICT(dataset_id,ipc1,ipc2,year) DO UPDATE SET
                           probability=excluded.probability,source_row=excluded.source_row""",
                    (
                        _id("fusion"), dataset_id, row["ipc1"], row["ipc2"],
                        row.get("year"), row["probability"], row.get("source_row"),
                    ),
                )
                count += 1
        return count

    def ipc_series(
        self, codes: Iterable[str] = (), start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        clauses, values = ["d.status='published'"], []
        codes = [code for code in codes if code]
        if codes:
            clauses.append(f"m.ipc_code IN ({','.join('?' for _ in codes)})")
            values.extend(codes)
        if start_year is not None:
            clauses.append("m.year>=?")
            values.append(start_year)
        if end_year is not None:
            clauses.append("m.year<=?")
            values.append(end_year)
        query = f"""SELECT m.*,d.name dataset_name,d.version dataset_version
                    FROM ipc_metrics m JOIN datasets d ON d.dataset_id=m.dataset_id
                    WHERE {' AND '.join(clauses)} ORDER BY m.ipc_code,m.year"""
        with self.db.connect() as connection:
            return [dict(row) for row in connection.execute(query, values).fetchall()]

    def ipc_fusions(self, codes: Iterable[str] = ()) -> List[Dict[str, Any]]:
        codes = [code for code in codes if code]
        query = """SELECT f.*,d.name dataset_name,d.version dataset_version
                   FROM ipc_fusions f JOIN datasets d ON d.dataset_id=f.dataset_id
                   WHERE d.status='published'"""
        values: List[Any] = []
        if codes:
            query += f" AND (f.ipc1 IN ({','.join('?' for _ in codes)}) OR f.ipc2 IN ({','.join('?' for _ in codes)}))"
            values.extend(codes)
            values.extend(codes)
        query += " ORDER BY f.probability DESC"
        with self.db.connect() as connection:
            return [dict(row) for row in connection.execute(query, values).fetchall()]

    def add_paper(self, dataset_id: str, paper: Dict[str, Any], chunks: Iterable[Dict[str, Any]] = ()) -> Dict[str, Any]:
        paper_id = paper.get("paper_id") or _id("paper")
        chunks = list(chunks)
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT INTO papers(paper_id,dataset_id,title,authors,year,doi,keywords,abstract,file_id)
                   VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(dataset_id,title,year) DO UPDATE SET
                     authors=excluded.authors,doi=excluded.doi,keywords=excluded.keywords,
                     abstract=excluded.abstract,file_id=COALESCE(excluded.file_id,papers.file_id)""",
                (
                    paper_id, dataset_id, paper["title"], paper.get("authors", ""),
                    paper.get("year"), paper.get("doi", ""), paper.get("keywords", ""),
                    paper.get("abstract", ""), paper.get("file_id"),
                ),
            )
            existing = connection.execute(
                "SELECT paper_id FROM papers WHERE dataset_id=? AND title=? AND year IS ?",
                (dataset_id, paper["title"], paper.get("year")),
            ).fetchone()
            paper_id = existing["paper_id"]
            for index, chunk in enumerate(chunks):
                connection.execute(
                    """INSERT OR REPLACE INTO paper_chunks(
                        chunk_id,paper_id,section,ordinal,page_number,content
                    ) VALUES (?,?,?,?,?,?)""",
                    (
                        chunk.get("chunk_id") or _id("chunk"), paper_id,
                        chunk.get("section", ""), chunk.get("ordinal", index),
                        chunk.get("page_number"), chunk["content"],
                    ),
                )
            full_text = "\n".join(chunk["content"] for chunk in chunks)
            connection.execute("DELETE FROM paper_fts WHERE paper_id=?", (paper_id,))
            connection.execute(
                "INSERT INTO paper_fts(paper_id,title,abstract,keywords,content) VALUES (?,?,?,?,?)",
                (
                    paper_id, paper["title"], paper.get("abstract", ""),
                    paper.get("keywords", ""), full_text,
                ),
            )
            return dict(connection.execute(
                "SELECT * FROM papers WHERE paper_id=?", (paper_id,)
            ).fetchone())

    def search_papers(self, query: str = "", limit: int = 20, end_year: Optional[int] = None) -> List[Dict[str, Any]]:
        with self.db.connect() as connection:
            if query.strip():
                terms = [term.replace('"', "") for term in query.split() if term]
                match = " OR ".join(f'"{term}"' for term in terms)
                sql = """SELECT p.*,d.name dataset_name,d.version dataset_version,
                                snippet(paper_fts,4,'<mark>','</mark>','…',16) snippet,
                                bm25(paper_fts) rank
                         FROM paper_fts JOIN papers p ON p.paper_id=paper_fts.paper_id
                         JOIN datasets d ON d.dataset_id=p.dataset_id
                         WHERE paper_fts MATCH ? AND d.status='published'"""
                values: List[Any] = [match]
                if end_year is not None:
                    sql += " AND (p.year IS NULL OR p.year<=?)"
                    values.append(end_year)
                sql += " ORDER BY rank LIMIT ?"
                values.append(limit)
                try:
                    matched = [dict(row) for row in connection.execute(sql, values).fetchall()]
                    if matched:
                        return matched
                except Exception:
                    pass
            like = f"%{query}%"
            sql = """SELECT p.*,d.name dataset_name,d.version dataset_version,p.abstract snippet,0 rank
                     FROM papers p JOIN datasets d ON d.dataset_id=p.dataset_id
                     WHERE d.status='published' AND (?='' OR p.title LIKE ? OR p.abstract LIKE ? OR p.keywords LIKE ?)"""
            values = [query, like, like, like]
            if end_year is not None:
                sql += " AND (p.year IS NULL OR p.year<=?)"
                values.append(end_year)
            sql += " ORDER BY p.year DESC LIMIT ?"
            values.append(limit)
            return [dict(row) for row in connection.execute(sql, values).fetchall()]

    def get_paper(self, paper_id: str) -> Optional[Dict[str, Any]]:
        with self.db.connect() as connection:
            paper = _dict(connection.execute(
                "SELECT * FROM papers WHERE paper_id=?", (paper_id,)
            ).fetchone())
            if paper:
                paper["chunks"] = [dict(row) for row in connection.execute(
                    "SELECT * FROM paper_chunks WHERE paper_id=? ORDER BY ordinal", (paper_id,)
                ).fetchall()]
            return paper

    def create_project(self, name: str, description: str = "", project_id: str = "") -> Dict[str, Any]:
        project_id = project_id or _id("project")
        with self.db.transaction() as connection:
            connection.execute(
                "INSERT INTO projects(project_id,name,description) VALUES (?,?,?)",
                (project_id, name.strip(), description),
            )
            return dict(connection.execute(
                "SELECT * FROM projects WHERE project_id=?", (project_id,)
            ).fetchone())

    def list_projects(self) -> List[Dict[str, Any]]:
        with self.db.connect() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM projects ORDER BY updated_at DESC"
            ).fetchall()]

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        with self.db.connect() as connection:
            return _dict(connection.execute(
                "SELECT * FROM projects WHERE project_id=?", (project_id,)
            ).fetchone())

    def update_project_status(
        self, project_id: str, status: str
    ) -> Optional[Dict[str, Any]]:
        with self.db.transaction() as connection:
            connection.execute(
                "UPDATE projects SET status=?,updated_at=? WHERE project_id=?",
                (status, datetime.now(timezone.utc).isoformat(), project_id),
            )
        return self.get_project(project_id)

    def add_material(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        material_id = payload.get("material_id") or _id("material")
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT INTO project_materials(
                    material_id,project_id,title,source_type,original_filename,checksum,
                    content,cleaned_content,stored_path,parse_status,parse_metadata_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    material_id, payload["project_id"], payload["title"], payload["source_type"],
                    payload.get("original_filename", ""), payload["checksum"],
                    payload["content"], payload["cleaned_content"], payload.get("stored_path", ""),
                    payload.get("parse_status", "ready"),
                    json.dumps(payload.get("parse_metadata", {}), ensure_ascii=False),
                ),
            )
        return self.get_material(material_id)

    def get_material(self, material_id: str) -> Optional[Dict[str, Any]]:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM project_materials WHERE material_id=?", (material_id,)
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            result["parse_metadata"] = json.loads(result.pop("parse_metadata_json"))
            return result

    def list_materials(self, project_id: str) -> List[Dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM project_materials WHERE project_id=? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def save_topic(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        topic_id = payload.get("topic_id") or _id("topic")
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT INTO project_topics(
                    topic_id,project_id,topic_name,description,keywords_json,evidence_json,
                    fusion_pairs_json,operator_notes,evidence_score,requires_review,selected,status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    topic_id, payload["project_id"], payload["topic_name"],
                    payload.get("description", ""),
                    json.dumps(payload.get("keywords", []), ensure_ascii=False),
                    json.dumps(payload.get("evidence", []), ensure_ascii=False),
                    json.dumps(payload.get("fusion_pairs", []), ensure_ascii=False),
                    payload.get("operator_notes", ""), payload.get("evidence_score", 0),
                    int(payload.get("requires_review", True)), int(payload.get("selected", True)),
                    payload.get("status", "candidate"),
                ),
            )
        return self.get_topic(topic_id)

    @staticmethod
    def _decode_topic(row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        result = dict(row)
        result["keywords"] = json.loads(result.pop("keywords_json"))
        result["evidence"] = json.loads(result.pop("evidence_json"))
        result["fusion_pairs"] = json.loads(result.pop("fusion_pairs_json"))
        result["requires_review"] = bool(result["requires_review"])
        result["selected"] = bool(result["selected"])
        return result

    def get_topic(self, topic_id: str) -> Optional[Dict[str, Any]]:
        with self.db.connect() as connection:
            return self._decode_topic(connection.execute(
                "SELECT * FROM project_topics WHERE topic_id=?", (topic_id,)
            ).fetchone())

    def list_topics(self, project_id: str, include_deleted: bool = False) -> List[Dict[str, Any]]:
        query = "SELECT * FROM project_topics WHERE project_id=?"
        if not include_deleted:
            query += " AND status NOT IN ('deleted','merged')"
        query += " ORDER BY created_at"
        with self.db.connect() as connection:
            return [self._decode_topic(row) for row in connection.execute(
                query, (project_id,)
            ).fetchall()]

    def update_topic(self, topic_id: str, changes: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        allowed = {
            "topic_name", "description", "operator_notes", "evidence_score",
            "requires_review", "selected", "status", "merged_into",
        }
        fields, values = [], []
        for key, value in changes.items():
            column = {"keywords": "keywords_json", "evidence": "evidence_json", "fusion_pairs": "fusion_pairs_json"}.get(key, key)
            if key in {"keywords", "evidence", "fusion_pairs"}:
                value = json.dumps(value, ensure_ascii=False)
            elif key in {"requires_review", "selected"}:
                value = int(bool(value))
            elif key not in allowed:
                continue
            fields.append(f"{column}=?")
            values.append(value)
        if not fields:
            return self.get_topic(topic_id)
        fields.append("updated_at=?")
        values.append(datetime.now(timezone.utc).isoformat())
        values.append(topic_id)
        with self.db.transaction() as connection:
            connection.execute(
                f"UPDATE project_topics SET {','.join(fields)} WHERE topic_id=?", values
            )
        return self.get_topic(topic_id)

    def create_evidence_package(
        self, project_id: str, topic_id: str, query: Dict[str, Any],
        quality: Dict[str, Any], items: Iterable[Dict[str, Any]],
        operator_notes: str = "",
    ) -> Dict[str, Any]:
        package_id = _id("package")
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT INTO evidence_packages(
                    package_id,project_id,topic_id,query_json,quality_json,operator_notes
                ) VALUES (?,?,?,?,?,?)""",
                (
                    package_id, project_id, topic_id,
                    json.dumps(query, ensure_ascii=False), json.dumps(quality, ensure_ascii=False),
                    operator_notes,
                ),
            )
            for item in items:
                connection.execute(
                    """INSERT INTO evidence_items(
                        item_id,evidence_id,package_id,evidence_type,source_id,dataset_id,title,
                        content,metadata_json,relevance,excluded,exclusion_reason
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        f"{package_id}:{item['evidence_id']}",
                        item["evidence_id"], package_id,
                        item["evidence_type"], item["source_id"],
                        item.get("dataset_id"), item.get("title", ""), item.get("content", ""),
                        json.dumps(item.get("metadata", {}), ensure_ascii=False),
                        item.get("relevance", 0), int(item.get("excluded", False)),
                        item.get("exclusion_reason", ""),
                    ),
                )
        return self.get_evidence_package(package_id)

    def get_evidence_package(self, package_id: str) -> Optional[Dict[str, Any]]:
        with self.db.connect() as connection:
            package = connection.execute(
                "SELECT * FROM evidence_packages WHERE package_id=?", (package_id,)
            ).fetchone()
            if not package:
                return None
            result = dict(package)
            result["query"] = json.loads(result.pop("query_json"))
            result["quality"] = json.loads(result.pop("quality_json"))
            result["items"] = []
            for row in connection.execute(
                "SELECT * FROM evidence_items WHERE package_id=? ORDER BY evidence_type,relevance DESC",
                (package_id,),
            ).fetchall():
                item = dict(row)
                item["metadata"] = json.loads(item.pop("metadata_json"))
                item["excluded"] = bool(item["excluded"])
                result["items"].append(item)
            return result

    def latest_package_for_topic(self, topic_id: str) -> Optional[Dict[str, Any]]:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT package_id FROM evidence_packages WHERE topic_id=? ORDER BY created_at DESC LIMIT 1",
                (topic_id,),
            ).fetchone()
        return self.get_evidence_package(row["package_id"]) if row else None

    def update_evidence_item(
        self, evidence_id: str, excluded: bool, reason: str = "",
        package_id: str = "",
    ) -> None:
        with self.db.transaction() as connection:
            if package_id:
                connection.execute(
                    """UPDATE evidence_items SET excluded=?,exclusion_reason=?
                       WHERE evidence_id=? AND package_id=?""",
                    (int(excluded), reason, evidence_id, package_id),
                )
            else:
                connection.execute(
                    "UPDATE evidence_items SET excluded=?,exclusion_reason=? WHERE evidence_id=?",
                    (int(excluded), reason, evidence_id),
                )

    def freeze_package(self, package_id: str, checksum: str) -> None:
        with self.db.transaction() as connection:
            connection.execute(
                "UPDATE evidence_packages SET status='frozen',checksum=?,frozen_at=? WHERE package_id=?",
                (checksum, datetime.now(timezone.utc).isoformat(), package_id),
            )

    def register_forecast_job(
        self, job_id: str, project_id: str, snapshot_path: str,
        topics: List[Dict[str, Any]], evidence_limited: bool, override_reason: str
    ) -> None:
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO forecast_jobs(
                    job_id,project_id,evidence_snapshot_path,topic_snapshot_json,
                    evidence_limited,override_reason
                ) VALUES (?,?,?,?,?,?)""",
                (
                    job_id, project_id, snapshot_path,
                    json.dumps(topics, ensure_ascii=False),
                    int(evidence_limited), override_reason,
                ),
            )

    def update_forecast_job_status(self, job_id: str, status: str) -> None:
        with self.db.transaction() as connection:
            connection.execute(
                "UPDATE forecast_jobs SET status=? WHERE job_id=?",
                (status, job_id),
            )
