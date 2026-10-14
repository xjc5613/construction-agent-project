# -*- coding: utf-8 -*-
import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from .constants import (
    BASELINE_YEAR,
    COMPATIBLE_HISTORICAL_PERIODS,
    COMPATIBLE_PERIOD_LABELS,
    HISTORICAL_PERIODS,
    LEGACY_HISTORICAL_PERIODS,
    PERIOD_LABELS,
    PUBLIC_DATASET_KINDS,
    TARGET_YEARS,
)
from .database import LibraryDatabase
from src.research.contracts import (
    CURRENT_RESEARCH_CONTRACT_VERSION,
    contract_for_record,
    get_research_contract,
)
from .validation import validate_dataset_version, validate_project_name


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:16]}"


def _dict(row) -> Optional[Dict[str, Any]]:
    return dict(row) if row is not None else None


class LibraryRepository:
    def __init__(self, database: Optional[LibraryDatabase] = None):
        self.db = database or LibraryDatabase()

    def create_dataset(
        self, kind: str, name: str, version: str, description: str = "",
        checksum: str = "", *, technology_node_id: str = "",
        period_code: str = "", public_kind: str = "",
        research_contract_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        version = validate_dataset_version(version)
        dataset_id = _id("dataset")
        if research_contract_version is None:
            research_contract_version = (
                2 if period_code in LEGACY_HISTORICAL_PERIODS
                else CURRENT_RESEARCH_CONTRACT_VERSION
            )
        contract = get_research_contract(research_contract_version)
        technology = None
        if technology_node_id:
            from .technology import TechnologyRepository
            technology = TechnologyRepository(self.db).get(technology_node_id)
            if (
                not technology or technology["level"] != 3
                or technology.get("effective_status") != "active"
            ):
                raise ValueError("数据集必须绑定有效启用的三级技术")
        with self.db.transaction() as connection:
            if technology_node_id:
                public_kind = public_kind or kind
                if public_kind not in PUBLIC_DATASET_KINDS:
                    raise ValueError("数据类型必须是 IPC、论文或综合数据")
                contract.validate_period(period_code)
                internal_kind = {
                    "ipc": "ipc_metrics", "paper": "papers",
                    "integrated": "mixed",
                }[public_kind]
                name = (
                    f"{technology['name']} · {COMPATIBLE_PERIOD_LABELS[period_code]} · "
                    f"{ {'ipc':'IPC','paper':'论文','integrated':'综合数据'}[public_kind] }"
                )
                kind = internal_kind
            connection.execute(
                """INSERT INTO datasets(
                    dataset_id,kind,name,version,description,checksum,public_kind,
                    technology_node_id,period_code,migration_status,
                    research_contract_version
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    dataset_id, kind, name.strip(), version, description,
                    checksum, public_kind, technology_node_id or None,
                    period_code or None, "mapped" if technology_node_id else "legacy",
                    research_contract_version,
                ),
            )
        return self.get_dataset(dataset_id)

    def generated_dataset_version(
        self, technology_node_id: str, period_code: str, public_kind: str,
    ) -> str:
        prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
        with self.db.connect() as connection:
            rows = connection.execute(
                """SELECT version FROM datasets
                   WHERE technology_node_id=? AND period_code=? AND public_kind=?
                   AND version LIKE ?""",
                (technology_node_id, period_code, public_kind, f"{prefix}.%"),
            ).fetchall()
        used = {
            int(row["version"].rsplit(".", 1)[-1])
            for row in rows
            if row["version"].rsplit(".", 1)[-1].isdigit()
        }
        sequence = 1
        while sequence in used:
            sequence += 1
        return f"{prefix}.{sequence}"

    def list_datasets(
        self, kind: str = "", technology_node_id: str = "",
        period_code: str = "", status: str = "", scope_node_id: str = "",
        lifecycle_status: str = "", migration_status: str = "",
    ) -> List[Dict[str, Any]]:
        clauses, values = ["1=1"], []
        if kind:
            clauses.append("(d.public_kind=? OR (d.public_kind='' AND d.kind=?))")
            values.extend([kind, kind])
        if technology_node_id:
            clauses.append("d.technology_node_id=?")
            values.append(technology_node_id)
        if scope_node_id:
            from .technology import TechnologyRepository
            scoped_ids = [
                item["node_id"] for item in TechnologyRepository(self.db).descendants(
                    scope_node_id, level=3, active_only=False
                )
            ]
            if not scoped_ids:
                return []
            clauses.append(
                f"d.technology_node_id IN ({','.join('?' for _ in scoped_ids)})"
            )
            values.extend(scoped_ids)
        if period_code:
            clauses.append("d.period_code=?")
            values.append(period_code)
        if status:
            clauses.append("d.status=?")
            values.append(status)
        if lifecycle_status:
            clauses.append("d.lifecycle_status=?")
            values.append(lifecycle_status)
        if migration_status:
            clauses.append("d.migration_status=?")
            values.append(migration_status)
        with self.db.connect() as connection:
            rows = connection.execute(
                f"""SELECT d.*,n.name technology_name
                    FROM datasets d
                    LEFT JOIN technology_nodes n ON n.node_id=d.technology_node_id
                    WHERE {' AND '.join(clauses)}
                    ORDER BY d.imported_at DESC""",
                values,
            ).fetchall()
            return [dict(row) for row in rows]

    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        with self.db.connect() as connection:
            row = connection.execute(
                """SELECT d.*,n.name technology_name
                   FROM datasets d LEFT JOIN technology_nodes n
                   ON n.node_id=d.technology_node_id WHERE d.dataset_id=?""",
                (dataset_id,),
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            result["components"] = [dict(item) for item in connection.execute(
                """SELECT i.import_id,i.component_kind,i.status,s.filename,
                          s.parse_status,s.content_role
                   FROM imports i JOIN source_files s ON s.file_id=i.file_id
                   WHERE i.dataset_id=? ORDER BY i.created_at""",
                (dataset_id,),
            ).fetchall()]
        if result.get("technology_node_id"):
            from .technology import TechnologyRepository
            node = TechnologyRepository(self.db).get(result["technology_node_id"])
            result["technology_path"] = node.get("path_text", "") if node else ""
        return result

    def update_dataset_status(self, dataset_id: str, status: str) -> Optional[Dict[str, Any]]:
        current = self.get_dataset(dataset_id)
        if not current:
            return None
        if status == "published":
            if (
                current.get("migration_status") != "mapped"
                or not current.get("technology_node_id")
                or not current.get("period_code")
            ):
                raise ValueError("发布前必须完成技术、阶段和数据类型映射")
            from .technology import TechnologyRepository
            technology = TechnologyRepository(self.db).get(
                current["technology_node_id"]
            )
            if not technology or technology.get("effective_status") != "active":
                raise ValueError("发布数据集绑定的技术已停用")
        with self.db.transaction() as connection:
            dataset = connection.execute(
                "SELECT * FROM datasets WHERE dataset_id=?", (dataset_id,)
            ).fetchone()
            if status == "published":
                kinds = {
                    row["component_kind"]
                    for row in connection.execute(
                        """SELECT component_kind FROM imports
                           WHERE dataset_id=? AND status='committed'""",
                        (dataset_id,),
                    ).fetchall()
                }
                counts = {
                    "ipc": int(connection.execute(
                        """SELECT
                             (SELECT COUNT(*) FROM ipc_metrics WHERE dataset_id=?)
                             + (SELECT COUNT(*) FROM ipc_fusions WHERE dataset_id=?)
                           value""",
                        (dataset_id, dataset_id),
                    ).fetchone()["value"]),
                    "paper": int(connection.execute(
                        "SELECT COUNT(*) value FROM papers WHERE dataset_id=?",
                        (dataset_id,),
                    ).fetchone()["value"]),
                }
                if dataset["public_kind"] == "ipc" and not counts["ipc"]:
                    raise ValueError("IPC 数据集没有有效记录")
                if dataset["public_kind"] == "paper" and not counts["paper"]:
                    raise ValueError("论文数据集没有有效记录")
                if (
                    dataset["public_kind"] == "integrated"
                    and (
                        not ({"ipc_metrics", "ipc_fusions"} & kinds)
                        or "papers" not in kinds
                        or not counts["ipc"] or not counts["paper"]
                    )
                ):
                    raise ValueError("综合数据发布前必须包含有效 IPC 和论文组成")
            connection.execute(
                "UPDATE datasets SET status=?,updated_at=? WHERE dataset_id=?",
                (status, datetime.now(timezone.utc).isoformat(), dataset_id),
            )
        return self.get_dataset(dataset_id)

    def dataset_reference_impact(self, dataset_id: str) -> Dict[str, Any]:
        with self.db.connect() as connection:
            row = connection.execute(
                """SELECT
                    (SELECT COUNT(*) FROM source_files WHERE dataset_id=?) files,
                    (SELECT COUNT(*) FROM imports WHERE dataset_id=? AND status='committed') committed_imports,
                    (SELECT COUNT(*) FROM ipc_metrics WHERE dataset_id=?) ipc_metrics,
                    (SELECT COUNT(*) FROM ipc_fusions WHERE dataset_id=?) ipc_fusions,
                    (SELECT COUNT(*) FROM papers WHERE dataset_id=?) papers,
                    (SELECT COUNT(*) FROM evidence_items WHERE dataset_id=?) evidence_items""",
                (dataset_id,) * 6,
            ).fetchone()
        result = dict(row)
        result["referenced"] = any(result.values())
        return result

    def set_dataset_lifecycle(self, dataset_id: str, status: str) -> Optional[Dict[str, Any]]:
        if status not in {"active", "deprecated"}:
            raise ValueError("数据集生命周期状态无效")
        now = datetime.now(timezone.utc).isoformat()
        current = self.get_dataset(dataset_id)
        if not current:
            return None
        with self.db.transaction() as connection:
            connection.execute(
                """UPDATE datasets SET lifecycle_status=?,status=?,deprecated_at=?,updated_at=?
                   WHERE dataset_id=?""",
                (
                    status,
                    "inactive" if status == "deprecated" else "published",
                    now if status == "deprecated" else None,
                    now, dataset_id,
                ),
            )
        return self.get_dataset(dataset_id)

    def delete_dataset_draft(self, dataset_id: str) -> bool:
        dataset = self.get_dataset(dataset_id)
        if not dataset:
            return False
        if dataset["status"] != "draft":
            raise ValueError("仅草稿数据集可永久删除")
        impact = self.dataset_reference_impact(dataset_id)
        if impact["referenced"]:
            raise ValueError("数据集已有记录或引用，只能废弃不能删除")
        with self.db.transaction() as connection:
            connection.execute("DELETE FROM datasets WHERE dataset_id=?", (dataset_id,))
        return True

    def classify_legacy_dataset(
        self, dataset_id: str, technology_node_id: str,
        period_code: str, public_kind: str,
    ) -> Dict[str, Any]:
        if public_kind not in PUBLIC_DATASET_KINDS:
            raise ValueError("数据类型必须是 IPC、论文或综合数据")
        if period_code not in COMPATIBLE_HISTORICAL_PERIODS:
            raise ValueError("历史阶段无效")
        start, end = COMPATIBLE_HISTORICAL_PERIODS[period_code]
        from .technology import TechnologyRepository
        technology = TechnologyRepository(self.db).get(technology_node_id)
        if (
            not technology or technology["level"] != 3
            or technology.get("effective_status") != "active"
        ):
            raise ValueError("必须选择有效启用的三级技术")
        with self.db.transaction() as connection:
            dataset = connection.execute(
                "SELECT * FROM datasets WHERE dataset_id=?", (dataset_id,)
            ).fetchone()
            if not dataset:
                raise ValueError("数据集不存在")
            years = []
            for table in ("ipc_metrics", "ipc_fusions", "papers"):
                years.extend(
                    int(row["year"]) for row in connection.execute(
                        f"""SELECT year FROM {table}
                            WHERE dataset_id=? AND year IS NOT NULL""",
                        (dataset_id,),
                    ).fetchall()
                )
            outside = sorted({year for year in years if year < start or year > end})
            if outside:
                connection.execute(
                    "UPDATE datasets SET migration_status='needs_split' WHERE dataset_id=?",
                    (dataset_id,),
                )
                raise ValueError(
                    f"数据包含阶段外年份 {outside}，需先拆分后再校准"
                )
            name = (
                f"{technology['name']} · {COMPATIBLE_PERIOD_LABELS[period_code]} · "
                f"{ {'ipc':'IPC','paper':'论文','integrated':'综合数据'}[public_kind] }"
            )
            connection.execute(
                """UPDATE datasets SET technology_node_id=?,period_code=?,
                   public_kind=?,name=?,migration_status='mapped'
                   WHERE dataset_id=?""",
                (
                    technology_node_id, period_code, public_kind,
                    name, dataset_id,
                ),
            )
        return self.get_dataset(dataset_id)

    def split_legacy_dataset(
        self, dataset_id: str, technology_node_id: str, public_kind: str,
    ) -> List[Dict[str, Any]]:
        source = self.get_dataset(dataset_id)
        if not source:
            raise ValueError("数据集不存在")
        if public_kind not in PUBLIC_DATASET_KINDS:
            raise ValueError("数据类型必须是 IPC、论文或综合数据")
        from .technology import TechnologyRepository
        technology = TechnologyRepository(self.db).get(technology_node_id)
        if (
            not technology or technology["level"] != 3
            or technology.get("effective_status") != "active"
        ):
            raise ValueError("必须选择有效启用的三级技术")

        def period_for(year: Optional[int]) -> str:
            if year is None:
                raise ValueError("跨阶段拆分要求每条记录包含年份")
            for code, (start, end) in HISTORICAL_PERIODS.items():
                if start <= int(year) <= end:
                    return code
            raise ValueError(f"年份 {year} 不属于支持的历史阶段")

        grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        with self.db.connect() as connection:
            for table, key in (
                ("ipc_metrics", "ipc"), ("ipc_fusions", "fusions"),
                ("papers", "papers"),
            ):
                for row in connection.execute(
                    f"SELECT * FROM {table} WHERE dataset_id=?",
                    (dataset_id,),
                ).fetchall():
                    item = dict(row)
                    grouped.setdefault(period_for(item.get("year")), {
                        "ipc": [], "fusions": [], "papers": [],
                    })[key].append(item)
            source_imports = [
                self.get_import(row["import_id"])
                for row in connection.execute(
                    "SELECT import_id FROM imports WHERE dataset_id=?",
                    (dataset_id,),
                ).fetchall()
            ]
        if len(grouped) < 2:
            raise ValueError("数据没有跨越多个历史阶段，无需拆分")

        results = []
        for period, records in sorted(grouped.items()):
            version = self.generated_dataset_version(
                technology_node_id, period, public_kind
            )
            target = self.create_dataset(
                public_kind, "", version,
                description=f"由旧数据集 {dataset_id} 拆分",
                technology_node_id=technology_node_id,
                period_code=period, public_kind=public_kind,
            )
            target_id = target["dataset_id"]
            self.upsert_ipc_metrics(target_id, [
                {
                    key: value for key, value in item.items()
                    if key not in {"metric_id", "dataset_id"}
                }
                for item in records["ipc"]
            ])
            self.upsert_ipc_fusions(target_id, [
                {
                    key: value for key, value in item.items()
                    if key not in {"fusion_id", "dataset_id"}
                }
                for item in records["fusions"]
            ])
            for paper in records["papers"]:
                with self.db.connect() as connection:
                    chunks = [
                        dict(row) for row in connection.execute(
                            """SELECT section,ordinal,page_number,content
                               FROM paper_chunks WHERE paper_id=? ORDER BY ordinal""",
                            (paper["paper_id"],),
                        ).fetchall()
                    ]
                payload = {
                    key: value for key, value in paper.items()
                    if key not in {"paper_id", "dataset_id", "created_at"}
                }
                self.add_paper(target_id, payload, chunks)
            for item in source_imports:
                if not item:
                    continue
                imported = self.create_import({
                    "dataset_id": target_id,
                    "file_id": item["file_id"],
                    "kind": item["kind"],
                    "component_kind": item["component_kind"],
                    "mapping": item.get("mapping", {}),
                    "preview": item.get("preview", {}),
                    "errors": item.get("errors", []),
                    "status": "committed",
                })
                self.update_import(imported["import_id"], "committed", target_id)
            with self.db.transaction() as connection:
                connection.execute(
                    "UPDATE datasets SET lineage_json=? WHERE dataset_id=?",
                    (
                        json.dumps({
                            "source_dataset_id": dataset_id,
                            "operation": "legacy-period-split",
                            "period_code": period,
                        }, ensure_ascii=False),
                        target_id,
                    ),
                )
            results.append(self.get_dataset(target_id))
        with self.db.transaction() as connection:
            connection.execute(
                "UPDATE datasets SET migration_status='needs_split' WHERE dataset_id=?",
                (dataset_id,),
            )
        return results

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
                    parse_status,text_coverage,parse_error,content_role
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    file_id, payload.get("dataset_id"), payload["filename"],
                    payload["media_type"], payload["checksum"], payload["stored_path"],
                    payload["size_bytes"], payload.get("parse_status", "pending"),
                    payload.get("text_coverage", 0), payload.get("parse_error", ""),
                    payload.get("content_role", ""),
                ),
            )
            return dict(connection.execute(
                "SELECT * FROM source_files WHERE file_id=?", (file_id,)
            ).fetchone())

    def create_import(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        import_id = payload.get("import_id") or _id("import")
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT INTO imports(
                    import_id,dataset_id,file_id,kind,status,mapping_json,
                    preview_json,error_json,component_kind
                ) VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    import_id, payload.get("dataset_id"), payload["file_id"], payload["kind"],
                    payload.get("status", "preview"),
                    json.dumps(payload.get("mapping", {}), ensure_ascii=False),
                    json.dumps(payload.get("preview", {}), ensure_ascii=False),
                    json.dumps(payload.get("errors", []), ensure_ascii=False),
                    payload.get("component_kind", payload["kind"]),
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
        end_year: Optional[int] = None, *,
        dataset_ids: Optional[Iterable[str]] = None,
        limit: Optional[int] = None, offset: int = 0,
    ) -> List[Dict[str, Any]]:
        clauses, values = ["d.status='published'"], []
        if dataset_ids is not None:
            dataset_ids = list(dict.fromkeys(dataset_ids))
            if not dataset_ids:
                return []
            clauses.append(
                f"m.dataset_id IN ({','.join('?' for _ in dataset_ids)})"
            )
            values.extend(dataset_ids)
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
        query = f"""SELECT m.*,d.name dataset_name,d.version dataset_version,
                           d.technology_node_id,
                           d.period_code,d.public_kind,d.migration_status,
                           n.name technology_name,s.filename source_filename,
                           s.parse_status source_parse_status
                    FROM ipc_metrics m JOIN datasets d ON d.dataset_id=m.dataset_id
                    LEFT JOIN technology_nodes n ON n.node_id=d.technology_node_id
                    LEFT JOIN source_files s ON s.file_id=(
                        SELECT i.file_id FROM imports i
                        WHERE i.dataset_id=d.dataset_id
                        ORDER BY i.created_at LIMIT 1
                    )
                    WHERE {' AND '.join(clauses)}
                    ORDER BY m.ipc_code,m.year"""
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            values.extend([limit, max(0, offset)])
        with self.db.connect() as connection:
            items = [dict(row) for row in connection.execute(query, values).fetchall()]
        from .technology import TechnologyRepository
        technologies = TechnologyRepository(self.db)
        for item in items:
            node = technologies.get(item.get("technology_node_id")) if item.get("technology_node_id") else None
            item["technology_path"] = node.get("path_text", "") if node else ""
        return items

    def ipc_fusions(
        self, codes: Iterable[str] = (), *,
        dataset_ids: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        codes = [code for code in codes if code]
        query = """SELECT f.*,d.name dataset_name,d.version dataset_version
                   FROM ipc_fusions f JOIN datasets d ON d.dataset_id=f.dataset_id
                   WHERE d.status='published'"""
        values: List[Any] = []
        if dataset_ids is not None:
            dataset_ids = list(dict.fromkeys(dataset_ids))
            if not dataset_ids:
                return []
            query += f" AND f.dataset_id IN ({','.join('?' for _ in dataset_ids)})"
            values.extend(dataset_ids)
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
                """INSERT INTO papers(
                       paper_id,dataset_id,title,authors,year,doi,keywords,abstract,file_id,
                       paper_type,source_database,publication_date,citation_count,
                       citation_observed_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(dataset_id,title,year) DO UPDATE SET
                     authors=excluded.authors,doi=excluded.doi,keywords=excluded.keywords,
                     abstract=excluded.abstract,file_id=COALESCE(excluded.file_id,papers.file_id),
                     paper_type=excluded.paper_type,source_database=excluded.source_database,
                     publication_date=excluded.publication_date,
                     citation_count=excluded.citation_count,
                     citation_observed_at=excluded.citation_observed_at""",
                (
                    paper_id, dataset_id, paper["title"], paper.get("authors", ""),
                    paper.get("year"), paper.get("doi", ""), paper.get("keywords", ""),
                    paper.get("abstract", ""), paper.get("file_id"),
                    paper.get("paper_type", "unknown"),
                    paper.get("source_database", ""),
                    paper.get("publication_date"), paper.get("citation_count"),
                    paper.get("citation_observed_at"),
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

    def search_papers(
        self, query: str = "", limit: int = 20,
        end_year: Optional[int] = None, *,
        start_year: Optional[int] = None,
        dataset_ids: Optional[Iterable[str]] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        clauses = ["d.status='published'"]
        values: List[Any] = []
        if dataset_ids is not None:
            dataset_ids = list(dict.fromkeys(dataset_ids))
            if not dataset_ids:
                return []
            clauses.append(
                f"p.dataset_id IN ({','.join('?' for _ in dataset_ids)})"
            )
            values.extend(dataset_ids)
        if query.strip():
            like = f"%{query.strip()}%"
            clauses.append(
                "(p.title LIKE ? OR p.abstract LIKE ? OR p.keywords LIKE ? OR p.authors LIKE ?)"
            )
            values.extend([like, like, like, like])
        if start_year is not None:
            clauses.append("(p.year IS NULL OR p.year>=?)")
            values.append(start_year)
        if end_year is not None:
            clauses.append("(p.year IS NULL OR p.year<=?)")
            values.append(end_year)
        sql = f"""SELECT p.*,d.name dataset_name,d.version dataset_version,
                         d.technology_node_id,
                         d.period_code,d.public_kind,d.migration_status,
                         n.name technology_name,s.filename source_filename,
                         s.parse_status source_parse_status,
                         p.abstract snippet,0 rank
                  FROM papers p JOIN datasets d ON d.dataset_id=p.dataset_id
                  LEFT JOIN technology_nodes n ON n.node_id=d.technology_node_id
                  LEFT JOIN source_files s ON s.file_id=p.file_id
                  WHERE {' AND '.join(clauses)}
                  ORDER BY p.year DESC,p.title LIMIT ? OFFSET ?"""
        values.extend([limit, max(0, offset)])
        with self.db.connect() as connection:
            items = [dict(row) for row in connection.execute(sql, values).fetchall()]
        from .technology import TechnologyRepository
        technologies = TechnologyRepository(self.db)
        for item in items:
            node = technologies.get(item.get("technology_node_id")) if item.get("technology_node_id") else None
            item["technology_path"] = node.get("path_text", "") if node else ""
        return items

    def get_paper(self, paper_id: str) -> Optional[Dict[str, Any]]:
        with self.db.connect() as connection:
            paper = _dict(connection.execute(
                """SELECT p.*,d.name dataset_name,d.version dataset_version,
                          d.period_code,d.technology_node_id,n.name technology_name,
                          s.filename source_filename,s.parse_status source_parse_status
                   FROM papers p JOIN datasets d ON d.dataset_id=p.dataset_id
                   LEFT JOIN technology_nodes n ON n.node_id=d.technology_node_id
                   LEFT JOIN source_files s ON s.file_id=p.file_id
                   WHERE p.paper_id=?""",
                (paper_id,),
            ).fetchone())
            if paper:
                paper["chunks"] = [dict(row) for row in connection.execute(
                    "SELECT * FROM paper_chunks WHERE paper_id=? ORDER BY ordinal", (paper_id,)
                ).fetchall()]
        if paper and paper.get("technology_node_id"):
            from .technology import TechnologyRepository
            node = TechnologyRepository(self.db).get(paper["technology_node_id"])
            paper["technology_path"] = node.get("path_text", "") if node else ""
        return paper

    def _record_dataset_ids(
        self, *, scope_node_id: str = "", dataset_id: str = "",
        period_code: str = "", public_kind: str = "",
        include_ineligible: bool = False,
    ) -> List[str]:
        clauses, values = ["1=1"], []
        if dataset_id:
            clauses.append("d.dataset_id=?")
            values.append(dataset_id)
        if scope_node_id:
            from .technology import TechnologyRepository
            leaf_ids = [
                item["node_id"] for item in TechnologyRepository(self.db).descendants(
                    scope_node_id, level=3, active_only=not include_ineligible
                )
            ]
            if not leaf_ids:
                return []
            clauses.append(
                f"d.technology_node_id IN ({','.join('?' for _ in leaf_ids)})"
            )
            values.extend(leaf_ids)
        if period_code:
            clauses.append("d.period_code=?")
            values.append(period_code)
        if public_kind:
            clauses.append("d.public_kind=?")
            values.append(public_kind)
        if not include_ineligible:
            clauses.extend([
                "d.status='published'",
                "d.lifecycle_status='active'",
                "d.migration_status='mapped'",
            ])
        with self.db.connect() as connection:
            return [
                row["dataset_id"] for row in connection.execute(
                    f"""SELECT d.dataset_id FROM datasets d
                        WHERE {' AND '.join(clauses)}""",
                    values,
                ).fetchall()
            ]

    def paper_page(
        self, *, query: str = "", scope_node_id: str = "",
        dataset_id: str = "", period_code: str = "",
        start_year: Optional[int] = None, end_year: Optional[int] = None,
        page: int = 1, page_size: int = 20,
        include_ineligible: bool = False,
    ) -> Dict[str, Any]:
        dataset_ids = self._record_dataset_ids(
            scope_node_id=scope_node_id, dataset_id=dataset_id,
            period_code=period_code, public_kind="paper",
            include_ineligible=include_ineligible,
        )
        if include_ineligible:
            dataset_ids += [
                item for item in self._record_dataset_ids(
                    scope_node_id=scope_node_id, dataset_id=dataset_id,
                    period_code=period_code, public_kind="integrated",
                    include_ineligible=True,
                ) if item not in dataset_ids
            ]
        else:
            dataset_ids += [
                item for item in self._record_dataset_ids(
                    scope_node_id=scope_node_id, dataset_id=dataset_id,
                    period_code=period_code, public_kind="integrated",
                ) if item not in dataset_ids
            ]
        if not dataset_ids:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        items = self.search_papers(
            query, page_size, end_year, start_year=start_year,
            dataset_ids=dataset_ids, offset=(page - 1) * page_size,
        )
        placeholders = ",".join("?" for _ in dataset_ids)
        clauses = [f"dataset_id IN ({placeholders})"]
        values: List[Any] = list(dataset_ids)
        if query.strip():
            like = f"%{query.strip()}%"
            clauses.append(
                "(title LIKE ? OR abstract LIKE ? OR keywords LIKE ? OR authors LIKE ?)"
            )
            values.extend([like, like, like, like])
        if start_year is not None:
            clauses.append("(year IS NULL OR year>=?)")
            values.append(start_year)
        if end_year is not None:
            clauses.append("(year IS NULL OR year<=?)")
            values.append(end_year)
        with self.db.connect() as connection:
            total = int(connection.execute(
                f"SELECT COUNT(*) value FROM papers WHERE {' AND '.join(clauses)}",
                values,
            ).fetchone()["value"])
        return {
            "items": items, "total": total,
            "page": page, "page_size": page_size,
        }

    def ipc_page(
        self, *, codes: Iterable[str] = (), scope_node_id: str = "",
        dataset_id: str = "", period_code: str = "",
        start_year: Optional[int] = None, end_year: Optional[int] = None,
        page: int = 1, page_size: int = 20,
        include_ineligible: bool = False,
    ) -> Dict[str, Any]:
        dataset_ids = self._record_dataset_ids(
            scope_node_id=scope_node_id, dataset_id=dataset_id,
            period_code=period_code, public_kind="ipc",
            include_ineligible=include_ineligible,
        )
        dataset_ids += [
            item for item in self._record_dataset_ids(
                scope_node_id=scope_node_id, dataset_id=dataset_id,
                period_code=period_code, public_kind="integrated",
                include_ineligible=include_ineligible,
            ) if item not in dataset_ids
        ]
        if not dataset_ids:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        normalized_codes = [item for item in codes if item]
        items = self.ipc_series(
            normalized_codes, start_year, end_year, dataset_ids=dataset_ids,
            limit=page_size, offset=(page - 1) * page_size,
        )
        placeholders = ",".join("?" for _ in dataset_ids)
        clauses = [f"dataset_id IN ({placeholders})"]
        values: List[Any] = list(dataset_ids)
        if normalized_codes:
            clauses.append(
                f"ipc_code IN ({','.join('?' for _ in normalized_codes)})"
            )
            values.extend(normalized_codes)
        if start_year is not None:
            clauses.append("year>=?")
            values.append(start_year)
        if end_year is not None:
            clauses.append("year<=?")
            values.append(end_year)
        with self.db.connect() as connection:
            total = int(connection.execute(
                f"SELECT COUNT(*) value FROM ipc_metrics WHERE {' AND '.join(clauses)}",
                values,
            ).fetchone()["value"])
        return {
            "items": items, "total": total,
            "page": page, "page_size": page_size,
        }

    def library_files(
        self, *, scope_node_id: str = "", include_ineligible: bool = False,
    ) -> List[Dict[str, Any]]:
        dataset_ids = self._record_dataset_ids(
            scope_node_id=scope_node_id,
            include_ineligible=include_ineligible,
        )
        if not dataset_ids:
            return []
        placeholders = ",".join("?" for _ in dataset_ids)
        with self.db.connect() as connection:
            return [dict(row) for row in connection.execute(
                f"""SELECT s.*,d.name dataset_name,d.version dataset_version,
                           d.period_code,d.public_kind,d.migration_status,
                           n.name technology_name
                    FROM source_files s JOIN imports i ON i.file_id=s.file_id
                    JOIN datasets d ON d.dataset_id=i.dataset_id
                    LEFT JOIN technology_nodes n ON n.node_id=d.technology_node_id
                    WHERE i.dataset_id IN ({placeholders})
                    ORDER BY s.created_at DESC""",
                dataset_ids,
            ).fetchall()]

    def list_imports(
        self, *, scope_node_id: str = "", include_ineligible: bool = False,
    ) -> List[Dict[str, Any]]:
        dataset_ids = self._record_dataset_ids(
            scope_node_id=scope_node_id,
            include_ineligible=include_ineligible,
        )
        if not dataset_ids:
            return []
        placeholders = ",".join("?" for _ in dataset_ids)
        with self.db.connect() as connection:
            rows = connection.execute(
                f"""SELECT i.*,s.filename,s.parse_status,d.name dataset_name,
                           d.version dataset_version,d.period_code,d.public_kind,
                           d.migration_status,d.lifecycle_status
                    FROM imports i JOIN source_files s ON s.file_id=i.file_id
                    JOIN datasets d ON d.dataset_id=i.dataset_id
                    WHERE i.dataset_id IN ({placeholders})
                    ORDER BY i.created_at DESC""",
                dataset_ids,
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            for key in ("mapping_json", "preview_json", "error_json"):
                item[key.removesuffix("_json")] = json.loads(item.pop(key))
            item["eligible"] = bool(
                item["migration_status"] == "mapped"
                and item["lifecycle_status"] == "active"
                and item["status"] == "committed"
            )
            results.append(item)
        return results

    def create_project(
        self, name: str = "", description: str = "", project_id: str = "",
        *, technology_node_id: str = "", target_year: int = 2040,
        baseline_year: int = BASELINE_YEAR,
        research_contract_version: int = CURRENT_RESEARCH_CONTRACT_VERSION,
    ) -> Dict[str, Any]:
        project_id = project_id or _id("project")
        contract = get_research_contract(research_contract_version)
        technology = None
        if technology_node_id:
            from .technology import TechnologyRepository
            technology = TechnologyRepository(self.db).get(technology_node_id)
            if (
                not technology or technology["level"] != 1
                or technology.get("effective_status") != "active"
            ):
                raise ValueError("预测项目必须绑定有效启用的一级技术")
        with self.db.transaction() as connection:
            scope_version = 0
            legacy_mode = 1
            if technology_node_id:
                if research_contract_version != CURRENT_RESEARCH_CONTRACT_VERSION:
                    raise ValueError("新预测项目必须使用研究合同 v3")
                contract.derive_forecast_nodes(target_year)
                contract.validate_baseline(baseline_year)
                default_name = f"{technology['name']}-{target_year}技术预测"
                name = f"{default_name}-{name.strip()}" if name.strip() else default_name
                scope_version = int(technology["taxonomy_version"])
                legacy_mode = 0
            elif not name.strip():
                raise ValueError("项目名称不能为空")
            if name.strip():
                name = validate_project_name(name)
            connection.execute(
                """INSERT INTO projects(
                    project_id,name,description,technology_node_id,baseline_year,
                    target_year,scope_version,legacy_mode,research_contract_version
                ) VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    project_id, name.strip(), description,
                    technology_node_id or None,
                    baseline_year if technology_node_id else 2025,
                    target_year, scope_version, legacy_mode,
                    research_contract_version if technology_node_id else 2,
                ),
            )
        return self.get_project(project_id)

    def list_projects(self, include_archived: bool = False) -> List[Dict[str, Any]]:
        with self.db.connect() as connection:
            where = "" if include_archived else "WHERE p.lifecycle_status='active'"
            rows = connection.execute(
                f"""SELECT p.*,n.name technology_name
                   FROM projects p LEFT JOIN technology_nodes n
                   ON n.node_id=p.technology_node_id
                   {where}
                   ORDER BY p.updated_at DESC"""
            ).fetchall()
            return [self._decode_project(dict(row)) for row in rows]

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        with self.db.connect() as connection:
            row = connection.execute(
                """SELECT p.*,n.name technology_name
                   FROM projects p LEFT JOIN technology_nodes n
                   ON n.node_id=p.technology_node_id WHERE p.project_id=?""",
                (project_id,),
            ).fetchone()
            return self._decode_project(dict(row)) if row else None

    @staticmethod
    def _decode_project(project: Dict[str, Any]) -> Dict[str, Any]:
        project["legacy_mode"] = bool(project.get("legacy_mode", 1))
        contract = contract_for_record(project)
        project["research_contract_version"] = contract.version
        project["research_contract"] = contract.to_dict()
        project["historical_periods"] = list(contract.periods)
        project["forecast_nodes"] = contract.derive_forecast_nodes(
            int(project.get("target_year") or 2040)
        )
        return project

    def update_project_status(
        self, project_id: str, status: str
    ) -> Optional[Dict[str, Any]]:
        with self.db.transaction() as connection:
            connection.execute(
                "UPDATE projects SET status=?,updated_at=? WHERE project_id=?",
                (status, datetime.now(timezone.utc).isoformat(), project_id),
            )
        return self.get_project(project_id)

    def update_project(self, project_id: str, changes: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        allowed = {"name", "description"}
        fields, values = [], []
        for key, value in changes.items():
            if key not in allowed:
                continue
            value = str(value).strip() if key == "name" else str(value)
            if key == "name" and not value:
                raise ValueError("项目名称不能为空")
            fields.append(f"{key}=?")
            values.append(value)
        if not fields:
            return self.get_project(project_id)
        fields.append("updated_at=?")
        values.extend([datetime.now(timezone.utc).isoformat(), project_id])
        with self.db.transaction() as connection:
            connection.execute(
                f"UPDATE projects SET {','.join(fields)} WHERE project_id=?", values
            )
        return self.get_project(project_id)

    def project_reference_impact(self, project_id: str) -> Dict[str, Any]:
        with self.db.connect() as connection:
            row = connection.execute(
                """SELECT
                    (SELECT COUNT(*) FROM project_materials WHERE project_id=?) materials,
                    (SELECT COUNT(*) FROM project_topics WHERE project_id=?) topics,
                    (SELECT COUNT(*) FROM evidence_packages WHERE project_id=?) evidence_packages,
                    (SELECT COUNT(*) FROM forecast_jobs WHERE project_id=?) jobs""",
                (project_id, project_id, project_id, project_id),
            ).fetchone()
        return dict(row)

    def set_project_lifecycle(self, project_id: str, status: str) -> Optional[Dict[str, Any]]:
        if status not in {"active", "archived"}:
            raise ValueError("项目生命周期状态无效")
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as connection:
            connection.execute(
                """UPDATE projects SET lifecycle_status=?,archived_at=?,updated_at=?
                   WHERE project_id=?""",
                (status, now if status == "archived" else None, now, project_id),
            )
        return self.get_project(project_id)

    def add_material(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        material_id = payload.get("material_id") or _id("material")
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT INTO project_materials(
                    material_id,project_id,title,source_type,original_filename,checksum,
                    content,cleaned_content,stored_path,parse_status,parse_metadata_json,
                    analysis_kind,review_status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    material_id, payload["project_id"], payload["title"], payload["source_type"],
                    payload.get("original_filename", ""), payload["checksum"],
                    payload["content"], payload["cleaned_content"], payload.get("stored_path", ""),
                    payload.get("parse_status", "ready"),
                    json.dumps(payload.get("parse_metadata", {}), ensure_ascii=False),
                    payload.get("analysis_kind", "integrated_analysis"),
                    payload.get("review_status", "ready"),
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

    def list_materials(self, project_id: str, include_inactive: bool = False) -> List[Dict[str, Any]]:
        with self.db.connect() as connection:
            lifecycle = "" if include_inactive else "AND lifecycle_status='active'"
            rows = connection.execute(
                f"""SELECT * FROM project_materials WHERE project_id=? {lifecycle}
                    ORDER BY created_at DESC""",
                (project_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def material_reference_impact(self, material_id: str) -> Dict[str, Any]:
        pattern = f'%"material_id": "{material_id}"%'
        compact_pattern = f'%"material_id":"{material_id}"%'
        with self.db.connect() as connection:
            frozen = connection.execute(
                """SELECT COUNT(*) value FROM forecast_jobs
                   WHERE topic_snapshot_json LIKE ? OR topic_snapshot_json LIKE ?""",
                (pattern, compact_pattern),
            ).fetchone()["value"]
        return {"frozen_jobs": frozen, "referenced": bool(frozen)}

    def update_material(self, material_id: str, changes: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        impact = self.material_reference_impact(material_id)
        if impact["referenced"] and any(key in changes for key in ("content", "cleaned_content")):
            raise ValueError("材料已被预测快照引用，不能修改正文")
        allowed = {"title", "content", "cleaned_content", "analysis_kind", "review_status"}
        fields, values = [], []
        for key, value in changes.items():
            if key in allowed:
                fields.append(f"{key}=?")
                values.append(value)
        if not fields:
            return self.get_material(material_id)
        fields.append("updated_at=?")
        values.extend([datetime.now(timezone.utc).isoformat(), material_id])
        with self.db.transaction() as connection:
            connection.execute(
                f"UPDATE project_materials SET {','.join(fields)} WHERE material_id=?",
                values,
            )
        return self.get_material(material_id)

    def set_material_lifecycle(self, material_id: str, status: str) -> Optional[Dict[str, Any]]:
        if status not in {"active", "inactive"}:
            raise ValueError("材料生命周期状态无效")
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as connection:
            connection.execute(
                """UPDATE project_materials
                   SET lifecycle_status=?,deactivated_at=?,updated_at=? WHERE material_id=?""",
                (status, now if status == "inactive" else None, now, material_id),
            )
        return self.get_material(material_id)

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
        if payload.get("technologies"):
            self.set_topic_technologies(topic_id, payload["technologies"])
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
            topic = self._decode_topic(connection.execute(
                "SELECT * FROM project_topics WHERE topic_id=?", (topic_id,)
            ).fetchone())
            if topic:
                topic["technologies"] = self.get_topic_technologies(topic_id)
            return topic

    def list_topics(self, project_id: str, include_deleted: bool = False) -> List[Dict[str, Any]]:
        query = "SELECT * FROM project_topics WHERE project_id=?"
        if not include_deleted:
            query += " AND status NOT IN ('deleted','merged')"
        query += " ORDER BY created_at"
        with self.db.connect() as connection:
            topics = [
                self._decode_topic(row) for row in connection.execute(
                    query, (project_id,)
                ).fetchall()
            ]
            for topic in topics:
                topic["technologies"] = self.get_topic_technologies(topic["topic_id"])
            return topics

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

    def topic_reference_impact(self, topic_id: str) -> Dict[str, Any]:
        pattern = f'%"topic_id": "{topic_id}"%'
        compact = f'%"topic_id":"{topic_id}"%'
        with self.db.connect() as connection:
            row = connection.execute(
                """SELECT
                    (SELECT COUNT(*) FROM evidence_packages WHERE topic_id=?) evidence_packages,
                    (SELECT COUNT(*) FROM forecast_jobs
                     WHERE topic_snapshot_json LIKE ? OR topic_snapshot_json LIKE ?) jobs""",
                (topic_id, pattern, compact),
            ).fetchone()
        return dict(row)

    def set_topic_technologies(
        self, topic_id: str, technologies: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        if not technologies:
            raise ValueError("主题至少需要关联一个三级技术")
        primary_count = sum(bool(item.get("is_primary")) for item in technologies)
        if primary_count != 1:
            raise ValueError("主题必须且只能设置一个主技术")
        with self.db.connect() as connection:
            topic_row = connection.execute(
                """SELECT t.topic_id,p.technology_node_id,p.legacy_mode
                   FROM project_topics t JOIN projects p ON p.project_id=t.project_id
                   WHERE t.topic_id=?""",
                (topic_id,),
            ).fetchone()
        if not topic_row:
            raise ValueError("项目主题不存在")
        node_ids = list(dict.fromkeys(
            item["technology_node_id"] for item in technologies
        ))
        from .technology import TechnologyRepository
        technology_repository = TechnologyRepository(self.db)
        if topic_row["technology_node_id"]:
            allowed = {
                item["node_id"] for item in technology_repository.descendants(
                    topic_row["technology_node_id"], level=3, active_only=True
                )
            }
        else:
            allowed = {
                item["node_id"] for item in technology_repository.list_nodes(
                    level=3, status="active"
                )
            }
        invalid = [item for item in node_ids if item not in allowed]
        if invalid:
            raise ValueError(
                "主题技术不在项目范围或已停用：" + "、".join(invalid)
            )
        with self.db.transaction() as connection:
            connection.execute(
                "DELETE FROM project_topic_technologies WHERE topic_id=?", (topic_id,)
            )
            for item in technologies:
                connection.execute(
                    """INSERT INTO project_topic_technologies(
                        topic_id,technology_node_id,is_primary,relevance,source
                    ) VALUES (?,?,?,?,?)""",
                    (
                        topic_id, item["technology_node_id"],
                        int(bool(item.get("is_primary"))),
                        float(item.get("relevance", 1)),
                        item.get("source", "manual"),
                    ),
                )
        return self.get_topic_technologies(topic_id)

    def get_topic_technologies(self, topic_id: str) -> List[Dict[str, Any]]:
        with self.db.connect() as connection:
            items = [dict(row) for row in connection.execute(
                """SELECT pt.*,n.name,n.level,n.status
                   FROM project_topic_technologies pt
                   JOIN technology_nodes n ON n.node_id=pt.technology_node_id
                   WHERE pt.topic_id=? ORDER BY pt.is_primary DESC,n.name""",
                (topic_id,),
            ).fetchall()]
        from .technology import TechnologyRepository
        technologies = TechnologyRepository(self.db)
        for item in items:
            node = technologies.get(item["technology_node_id"])
            item["effective_status"] = (
                node.get("effective_status", "inactive") if node else "inactive"
            )
            item["path_text"] = node.get("path_text", "") if node else ""
        return items

    def project_technology_scope(self, project_id: str) -> Dict[str, Any]:
        project = self.get_project(project_id)
        if not project:
            raise ValueError("预测项目不存在")
        if not project.get("technology_node_id"):
            return {
                "legacy_mode": True, "root": None, "nodes": [],
                "baseline_year": project["baseline_year"],
                "target_year": project["target_year"],
                "forecast_nodes": project["forecast_nodes"],
                "research_contract": project["research_contract"],
            }
        from .technology import TechnologyRepository
        snapshot = TechnologyRepository(self.db).snapshot(
            project["technology_node_id"]
        )
        return {
            **snapshot,
            "legacy_mode": False,
            "baseline_year": project["baseline_year"],
            "target_year": project["target_year"],
            "forecast_nodes": project["forecast_nodes"],
            "research_contract": project["research_contract"],
        }

    def refresh_project_scope(self, project_id: str) -> Dict[str, Any]:
        scope = self.project_technology_scope(project_id)
        if scope.get("legacy_mode"):
            raise ValueError("历史项目不能刷新技术范围")
        with self.db.transaction() as connection:
            connection.execute(
                "UPDATE projects SET scope_version=?,updated_at=? WHERE project_id=?",
                (
                    scope["taxonomy_version"],
                    datetime.now(timezone.utc).isoformat(), project_id,
                ),
            )
        return self.project_technology_scope(project_id)

    def dataset_coverage(self, root_node_id: str) -> Dict[str, Any]:
        from .eligibility import DatasetEligibilityResolver
        project = {
            "project_id": f"scope:{root_node_id}",
            "technology_node_id": root_node_id,
            "legacy_mode": False,
        }
        resolved = DatasetEligibilityResolver(self).resolve(project)
        periods = resolved["coverage"]["periods"]
        missing = [
            f"{PERIOD_LABELS[period]} 缺少基础证据"
            for period in resolved["coverage"]["missing_periods"]
        ]
        return {
            "root_node_id": root_node_id, "periods": periods,
            "leaf_count": len(resolved["technology_ids"]), "missing": missing,
            "complete": not missing,
            "eligible_dataset_ids": resolved["eligible_dataset_ids"],
            "excluded_datasets": resolved["excluded_datasets"],
            "scope_checksum": resolved["scope_checksum"],
        }

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
            target_package = package_id
            if not target_package:
                row = connection.execute(
                    """SELECT package_id FROM evidence_items
                       WHERE evidence_id=? ORDER BY rowid DESC LIMIT 1""",
                    (evidence_id,),
                ).fetchone()
                target_package = row["package_id"] if row else ""
            package = connection.execute(
                "SELECT status FROM evidence_packages WHERE package_id=?",
                (target_package,),
            ).fetchone()
            if package and package["status"] == "frozen":
                raise ValueError("冻结证据包不可修改，请重新检索形成新证据包")
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
        topics: List[Dict[str, Any]], evidence_limited: bool, override_reason: str,
        *, baseline_year: int = 2025, target_year: int = 2040,
        forecast_nodes: Optional[List[int]] = None,
        research_contract_version: int = CURRENT_RESEARCH_CONTRACT_VERSION,
        taxonomy_snapshot: Optional[Dict[str, Any]] = None,
        request_checksum: str = "", idempotency_key: Optional[str] = None,
        parent_job_id: Optional[str] = None, options: Optional[Dict[str, Any]] = None,
        request: Optional[Dict[str, Any]] = None, snapshot_checksum: str = "",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT INTO forecast_jobs(
                    job_id,project_id,evidence_snapshot_path,topic_snapshot_json,
                    evidence_limited,override_reason,baseline_year,target_year,
                    forecast_nodes_json,taxonomy_snapshot_json,request_checksum,
                    idempotency_key,parent_job_id,options_json,request_json,
                    snapshot_checksum,updated_at,research_contract_version
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(job_id) DO UPDATE SET
                    evidence_snapshot_path=excluded.evidence_snapshot_path,
                    topic_snapshot_json=excluded.topic_snapshot_json,
                    evidence_limited=excluded.evidence_limited,
                    override_reason=excluded.override_reason,
                    baseline_year=excluded.baseline_year,
                    target_year=excluded.target_year,
                    forecast_nodes_json=excluded.forecast_nodes_json,
                    taxonomy_snapshot_json=excluded.taxonomy_snapshot_json,
                    request_checksum=excluded.request_checksum,
                    options_json=excluded.options_json,
                    request_json=excluded.request_json,
                    snapshot_checksum=excluded.snapshot_checksum,
                    research_contract_version=excluded.research_contract_version,
                    artifact_health='ready',updated_at=excluded.updated_at""",
                (
                    job_id, project_id, snapshot_path,
                    json.dumps(topics, ensure_ascii=False),
                    int(evidence_limited), override_reason,
                    baseline_year, target_year,
                    json.dumps(
                        forecast_nodes or [2030, 2035, 2040],
                        ensure_ascii=False,
                    ),
                    json.dumps(taxonomy_snapshot or {}, ensure_ascii=False),
                    request_checksum, idempotency_key, parent_job_id,
                    json.dumps(options or {}, ensure_ascii=False),
                    json.dumps(request or {}, ensure_ascii=False),
                    snapshot_checksum, now, research_contract_version,
                ),
            )

    def reserve_forecast_job(
        self, job_id: str, project_id: str, *, request_checksum: str,
        idempotency_key: str, parent_job_id: Optional[str] = None,
        request: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT INTO forecast_jobs(
                    job_id,project_id,status,request_checksum,idempotency_key,
                    parent_job_id,request_json,options_json,created_at,updated_at,
                    artifact_health,current_stage
                ) VALUES (?,?,?,?,?,?,?,?,?,?, 'initializing','queued')""",
                (
                    job_id, project_id, "queued", request_checksum,
                    idempotency_key, parent_job_id,
                    json.dumps(request or {}, ensure_ascii=False, sort_keys=True),
                    json.dumps(options or {}, ensure_ascii=False, sort_keys=True),
                    now, now,
                ),
            )
        return self.get_forecast_job(job_id)

    def update_forecast_job_status(
        self, job_id: str, status: str, *, progress: Optional[float] = None,
        current_stage: str = "", error_code: str = "", error_message: str = "",
        artifact_health: str = "",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        fields, values = ["status=?", "updated_at=?"], [status, now]
        if progress is not None:
            fields.append("progress=?")
            values.append(max(0, min(1, progress)))
        if current_stage:
            fields.append("current_stage=?")
            values.append(current_stage)
        if error_code:
            fields.append("error_code=?")
            values.append(error_code)
        if error_message:
            fields.append("error_message=?")
            values.append(error_message)
        if artifact_health:
            fields.append("artifact_health=?")
            values.append(artifact_health)
        if status == "running":
            fields.append("started_at=COALESCE(started_at,?)")
            values.append(now)
        if status in {"completed", "partial_failed", "failed", "cancelled"}:
            fields.append("completed_at=?")
            values.append(now)
        values.append(job_id)
        with self.db.transaction() as connection:
            connection.execute(
                f"UPDATE forecast_jobs SET {','.join(fields)} WHERE job_id=?", values,
            )

    @staticmethod
    def _decode_forecast_job(row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        result = dict(row)
        for source, target, fallback in (
            ("topic_snapshot_json", "topics", []),
            ("forecast_nodes_json", "forecast_nodes", []),
            ("taxonomy_snapshot_json", "taxonomy", {}),
            ("options_json", "options", {}),
            ("request_json", "request", {}),
            ("run_manifest_json", "run_manifest", {}),
        ):
            try:
                result[target] = json.loads(result.pop(source))
            except (TypeError, json.JSONDecodeError):
                result[target] = fallback
        result["evidence_limited"] = bool(result.get("evidence_limited"))
        contract = contract_for_record(result)
        result["research_contract_version"] = contract.version
        result["research_contract"] = contract.to_dict()
        if not result.get("forecast_nodes"):
            result["forecast_nodes"] = contract.derive_forecast_nodes(
                int(result.get("target_year") or 2040)
            )
        return result

    def get_forecast_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM forecast_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
        return self._decode_forecast_job(row)

    def list_forecast_jobs(self, project_id: str) -> List[Dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM forecast_jobs WHERE project_id=?
                   ORDER BY created_at DESC,job_id DESC""",
                (project_id,),
            ).fetchall()
        return [self._decode_forecast_job(row) for row in rows]

    def get_active_forecast_job(self, project_id: str) -> Optional[Dict[str, Any]]:
        with self.db.connect() as connection:
            row = connection.execute(
                """SELECT * FROM forecast_jobs WHERE project_id=?
                   AND status IN ('queued','running','cancelling')
                   ORDER BY created_at DESC LIMIT 1""",
                (project_id,),
            ).fetchone()
        return self._decode_forecast_job(row)

    def get_forecast_job_by_idempotency(self, key: str) -> Optional[Dict[str, Any]]:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM forecast_jobs WHERE idempotency_key=?", (key,)
            ).fetchone()
        return self._decode_forecast_job(row)

    def request_forecast_cancellation(self, job_id: str) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as connection:
            row = connection.execute(
                "SELECT status FROM forecast_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if not row:
                return None
            if row["status"] not in {"queued", "running", "cancelling"}:
                raise ValueError("终态任务不能取消")
            connection.execute(
                """UPDATE forecast_jobs SET status='cancelling',cancel_requested_at=?,
                   updated_at=? WHERE job_id=?""",
                (now, now, job_id),
            )
        return self.get_forecast_job(job_id)
