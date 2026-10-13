# -*- coding: utf-8 -*-
"""Transactional persistence for v3 scientific evidence and immutable artifacts."""

import hashlib
import json
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from src.library.database import LibraryDatabase


def _id(prefix: str) -> str:
    return "%s_%s" % (prefix, uuid4().hex[:16])


def canonical_checksum(value: Any) -> str:
    rendered = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


class ResearchRepository:
    def __init__(self, database: Optional[LibraryDatabase] = None):
        self.db = database or LibraryDatabase()

    def add_patent_with_ipcs(
        self, patent: Dict[str, Any], assignments: Iterable[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Atomically store a canonical patent and its normalized IPC assignments."""
        patent_id = patent.get("patent_id") or _id("patent")
        rows = list(assignments)
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT INTO patents(
                       patent_id,dataset_id,publication_number,title,abstract,
                       application_year,applicant_type,legal_status,file_id,source_row
                   ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    patent_id, patent["dataset_id"], patent["publication_number"],
                    patent.get("title", ""), patent.get("abstract", ""),
                    int(patent["application_year"]), patent.get("applicant_type", ""),
                    patent.get("legal_status", ""), patent.get("file_id"),
                    patent.get("source_row"),
                ),
            )
            for assignment in rows:
                connection.execute(
                    """INSERT INTO patent_ipcs(
                           assignment_id,patent_id,ipc_code_raw,ipc_code_normalized,
                           ipc_level,ipc_edition,mapping_status,mapping_rule_version
                       ) VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        assignment.get("assignment_id") or _id("assignment"), patent_id,
                        assignment["ipc_code_raw"], assignment["ipc_code_normalized"],
                        assignment.get("ipc_level", "main_group"),
                        assignment.get("ipc_edition", ""),
                        assignment.get("mapping_status", "mapped"),
                        assignment.get("mapping_rule_version", "ipc-main-group-v1"),
                    ),
                )
        return self.get_patent(patent_id)

    def get_patent(self, patent_id: str) -> Optional[Dict[str, Any]]:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM patents WHERE patent_id=?", (patent_id,)
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            result["ipc_assignments"] = [dict(item) for item in connection.execute(
                "SELECT * FROM patent_ipcs WHERE patent_id=? ORDER BY ipc_code_normalized",
                (patent_id,),
            ).fetchall()]
            return result

    def save_ipc_mapping(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        mapping_id = payload.get("mapping_id") or _id("mapping")
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT INTO ipc_code_mappings(
                       mapping_id,ipc_code_raw,ipc_code_normalized,analysis_level,
                       source_edition,target_edition,rule_version,status,rationale
                   ) VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    mapping_id, payload["ipc_code_raw"], payload["ipc_code_normalized"],
                    payload["analysis_level"], payload.get("source_edition", ""),
                    payload.get("target_edition", ""), payload["rule_version"],
                    payload.get("status", "confirmed"), payload.get("rationale", ""),
                ),
            )
        return self.get_mapping(mapping_id)

    def get_mapping(self, mapping_id: str) -> Optional[Dict[str, Any]]:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM ipc_code_mappings WHERE mapping_id=?", (mapping_id,)
            ).fetchone()
        return dict(row) if row else None

    def upsert_coverage(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        coverage_id = payload.get("coverage_id") or _id("coverage")
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT INTO data_coverage(
                       coverage_id,dataset_id,source_kind,year,observation_cutoff,
                       expected_count,observed_count,completeness,researcher_notes,reviewed
                   ) VALUES (?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(dataset_id,source_kind,year) DO UPDATE SET
                       observation_cutoff=excluded.observation_cutoff,
                       expected_count=excluded.expected_count,
                       observed_count=excluded.observed_count,
                       completeness=excluded.completeness,
                       researcher_notes=excluded.researcher_notes,
                       reviewed=excluded.reviewed,
                       updated_at=CURRENT_TIMESTAMP""",
                (
                    coverage_id, payload["dataset_id"], payload["source_kind"],
                    int(payload["year"]), payload.get("observation_cutoff", ""),
                    payload.get("expected_count"), payload.get("observed_count"),
                    payload.get("completeness", "unknown"),
                    payload.get("researcher_notes", ""), int(bool(payload.get("reviewed"))),
                ),
            )
            row = connection.execute(
                """SELECT * FROM data_coverage
                   WHERE dataset_id=? AND source_kind=? AND year=?""",
                (payload["dataset_id"], payload["source_kind"], int(payload["year"])),
            ).fetchone()
        return dict(row)

    def create_network_run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return an existing content-addressed run instead of duplicating it."""
        input_checksum = payload.get("input_checksum") or canonical_checksum(
            payload.get("input", payload)
        )
        algorithm_version = payload["algorithm_version"]
        with self.db.transaction() as connection:
            existing = connection.execute(
                """SELECT * FROM network_runs
                   WHERE input_checksum=? AND algorithm_version=?""",
                (input_checksum, algorithm_version),
            ).fetchone()
            if existing:
                return self._decode_json(dict(existing), ("parameters_json",))
            run_id = payload.get("network_run_id") or _id("network")
            connection.execute(
                """INSERT INTO network_runs(
                       network_run_id,project_id,snapshot_checksum,
                       research_contract_version,algorithm_version,parameters_json,
                       input_checksum,evidence_grade,random_seed
                   ) VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    run_id, payload.get("project_id"), payload["snapshot_checksum"],
                    int(payload.get("research_contract_version", 3)), algorithm_version,
                    json.dumps(payload.get("parameters", {}), ensure_ascii=False, sort_keys=True),
                    input_checksum, payload.get("evidence_grade", "canonical"),
                    int(payload.get("random_seed", 0)),
                ),
            )
            row = connection.execute(
                "SELECT * FROM network_runs WHERE network_run_id=?", (run_id,)
            ).fetchone()
        return self._decode_json(dict(row), ("parameters_json",))

    def complete_network_run(self, run_id: str, result_checksum: str) -> Dict[str, Any]:
        with self.db.transaction() as connection:
            row = connection.execute(
                "SELECT status,result_checksum FROM network_runs WHERE network_run_id=?",
                (run_id,),
            ).fetchone()
            if not row:
                raise ValueError("网络运行不存在")
            if row["status"] == "completed" and row["result_checksum"] != result_checksum:
                raise ValueError("已完成的科学运行不可变")
            connection.execute(
                """UPDATE network_runs SET status='completed',result_checksum=?,
                   completed_at=CURRENT_TIMESTAMP WHERE network_run_id=?""",
                (result_checksum, run_id),
            )
            result = connection.execute(
                "SELECT * FROM network_runs WHERE network_run_id=?", (run_id,)
            ).fetchone()
        return self._decode_json(dict(result), ("parameters_json",))

    @staticmethod
    def _decode_json(value: Dict[str, Any], fields: Iterable[str]) -> Dict[str, Any]:
        for field in fields:
            value[field[:-5] if field.endswith("_json") else field] = json.loads(
                value.pop(field)
            )
        return value
