# -*- coding: utf-8 -*-
"""Versioned research-design and frozen evidence-snapshot services."""

import json
from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.library import DatasetEligibilityResolver, LibraryRepository
from src.research.contracts import get_research_contract
from src.research.repository import canonical_checksum


def _id(prefix: str) -> str:
    return "%s_%s" % (prefix, uuid4().hex[:16])


class ResearchDesignService:
    def __init__(self, repository: Optional[LibraryRepository] = None):
        self.repository = repository or LibraryRepository()

    @staticmethod
    def _decode(row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        result = dict(row)
        result["paper_types"] = json.loads(result.pop("paper_types_json"))
        result["parameters"] = json.loads(result.pop("parameters_json"))
        return result

    def create_version(self, project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        project = self.repository.get_project(project_id)
        if not project or project.get("legacy_mode"):
            raise ValueError("仅 v3 项目可创建研究设计")
        contract = get_research_contract(project["research_contract_version"])
        cutoff = str(payload.get("data_cutoff") or contract.default_cutoff)
        canonical = {
            "research_question": str(payload.get("research_question") or "").strip(),
            "paper_types": sorted(set(payload.get("paper_types") or ["journal_article", "conference_paper"])),
            "ipc_analysis_level": payload.get("ipc_analysis_level", "main_group"),
            "candidate_target": payload.get("candidate_target", "both"),
            "data_cutoff": cutoff,
            "completeness_policy": payload.get("completeness_policy", "include_partial_with_sensitivity"),
            "parameters": payload.get("parameters") or {},
        }
        if not canonical["research_question"]:
            raise ValueError("研究问题不能为空")
        if canonical["ipc_analysis_level"] not in {"subclass", "main_group", "subgroup"}:
            raise ValueError("IPC 分析层级无效")
        if canonical["candidate_target"] not in {"emergence", "strengthening", "both"}:
            raise ValueError("候选目标无效")
        checksum = canonical_checksum(canonical)
        with self.repository.db.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM research_designs WHERE project_id=? AND checksum=?",
                (project_id, checksum),
            ).fetchone()
            if existing:
                return self._decode(existing)
            version = int(connection.execute(
                "SELECT COALESCE(MAX(version),0)+1 FROM research_designs WHERE project_id=?",
                (project_id,),
            ).fetchone()[0])
            design_id = _id("design")
            connection.execute(
                """INSERT INTO research_designs(
                       design_id,project_id,version,research_contract_version,research_question,
                       paper_types_json,ipc_analysis_level,candidate_target,data_cutoff,
                       completeness_policy,parameters_json,status,checksum
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'draft',?)""",
                (design_id, project_id, version, contract.version, canonical["research_question"],
                 json.dumps(canonical["paper_types"], ensure_ascii=False),
                 canonical["ipc_analysis_level"], canonical["candidate_target"], cutoff,
                 canonical["completeness_policy"],
                 json.dumps(canonical["parameters"], ensure_ascii=False, sort_keys=True), checksum),
            )
            row = connection.execute(
                "SELECT * FROM research_designs WHERE design_id=?", (design_id,)
            ).fetchone()
        return self._decode(row)

    def list_versions(self, project_id: str) -> List[Dict[str, Any]]:
        with self.repository.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM research_designs WHERE project_id=? ORDER BY version DESC",
                (project_id,),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def confirm(self, project_id: str, design_id: str) -> Dict[str, Any]:
        with self.repository.db.transaction() as connection:
            design = connection.execute(
                "SELECT * FROM research_designs WHERE design_id=? AND project_id=?",
                (design_id, project_id),
            ).fetchone()
            if not design:
                raise ValueError("研究设计不存在")
            previous = connection.execute(
                "SELECT active_research_design_id FROM projects WHERE project_id=?",
                (project_id,),
            ).fetchone()[0]
            connection.execute(
                """UPDATE research_designs SET status='confirmed',confirmed_at=CURRENT_TIMESTAMP
                   WHERE design_id=?""", (design_id,),
            )
            connection.execute(
                "UPDATE projects SET active_research_design_id=?,updated_at=CURRENT_TIMESTAMP WHERE project_id=?",
                (design_id, project_id),
            )
            if previous and previous != design_id:
                self._mark_stale(connection, project_id)
            row = connection.execute(
                "SELECT * FROM research_designs WHERE design_id=?", (design_id,)
            ).fetchone()
        result = self._decode(row)
        result["stale_artifacts"] = self.stale_artifacts(project_id)
        return result

    @staticmethod
    def _mark_stale(connection, project_id: str) -> None:
        connection.execute("UPDATE network_runs SET status='stale' WHERE project_id=? AND status='completed'", (project_id,))
        connection.execute(
            """UPDATE model_runs SET status='stale' WHERE model_run_id IN (
               SELECT m.model_run_id FROM model_runs m JOIN feature_runs f ON f.feature_run_id=m.feature_run_id
               JOIN network_runs n ON n.network_run_id=f.network_run_id WHERE n.project_id=?)""", (project_id,)
        )
        connection.execute(
            """UPDATE graph_threads SET status='stale' WHERE job_id IN
               (SELECT job_id FROM forecast_jobs WHERE project_id=?)""", (project_id,)
        )
        connection.execute("UPDATE export_manifests SET status='stale' WHERE project_id=?", (project_id,))

    def stale_artifacts(self, project_id: str) -> Dict[str, int]:
        with self.repository.db.connect() as connection:
            return {
                "network_runs": int(connection.execute(
                    "SELECT COUNT(*) FROM network_runs WHERE project_id=? AND status='stale'", (project_id,)
                ).fetchone()[0]),
                "graph_threads": int(connection.execute(
                    """SELECT COUNT(*) FROM graph_threads WHERE status='stale' AND job_id IN
                       (SELECT job_id FROM forecast_jobs WHERE project_id=?)""", (project_id,)
                ).fetchone()[0]),
                "exports": int(connection.execute(
                    "SELECT COUNT(*) FROM export_manifests WHERE project_id=? AND status='stale'", (project_id,)
                ).fetchone()[0]),
            }

    def freeze_snapshot(self, project_id: str, dataset_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        project = self.repository.get_project(project_id)
        if not project:
            raise ValueError("预测项目不存在")
        design_id = project.get("active_research_design_id")
        with self.repository.db.connect() as connection:
            design_row = connection.execute(
                "SELECT * FROM research_designs WHERE design_id=?", (design_id,)
            ).fetchone() if design_id else None
        if not design_row or design_row["status"] != "confirmed":
            raise ValueError("必须先确认研究设计")
        design = self._decode(design_row)
        scope = DatasetEligibilityResolver(self.repository).resolve(
            project, requested_dataset_ids=dataset_ids
        )
        selected = scope["selected_dataset_ids"]
        if not selected:
            raise ValueError("没有符合范围的可冻结数据")
        placeholders = ",".join("?" for _ in selected)
        with self.repository.db.connect() as connection:
            source_files = [dict(row) for row in connection.execute(
                "SELECT file_id,dataset_id,checksum,filename FROM source_files WHERE dataset_id IN (%s) ORDER BY file_id" % placeholders,
                selected,
            ).fetchall()]
            patent_ids = [row[0] for row in connection.execute(
                "SELECT patent_id FROM patents WHERE dataset_id IN (%s) ORDER BY patent_id" % placeholders, selected
            ).fetchall()]
            paper_ids = [row[0] for row in connection.execute(
                "SELECT paper_id FROM papers WHERE dataset_id IN (%s) ORDER BY paper_id" % placeholders, selected
            ).fetchall()]
            coverage = [dict(row) for row in connection.execute(
                "SELECT * FROM data_coverage WHERE dataset_id IN (%s) ORDER BY dataset_id,year" % placeholders, selected
            ).fetchall()]
            mappings = [dict(row) for row in connection.execute(
                "SELECT * FROM ipc_code_mappings WHERE status='confirmed' ORDER BY mapping_id"
            ).fetchall()]
        snapshot = {
            "snapshot_schema_version": 3,
            "project_id": project_id,
            "research_contract": project["research_contract"],
            "design": design,
            "scope": scope,
            "dataset_ids": selected,
            "source_files": source_files,
            "record_ids": {"patents": patent_ids, "papers": paper_ids},
            "coverage": coverage,
            "ipc_mappings": mappings,
        }
        snapshot["checksum"] = canonical_checksum(snapshot)
        return snapshot
