# -*- coding: utf-8 -*-
"""Persistence for bounded evidence packets and claim-centered deliberation."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from src.library.database import LibraryDatabase
from src.research.evolution_schemas import (
    Adjudication, DevelopmentClaim, EvolutionEvidencePacket, ReviewFinding,
)
from src.research.repository import canonical_checksum


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:16]}"


class ThesisRepository:
    def __init__(self, database: Optional[LibraryDatabase] = None):
        self.db = database or LibraryDatabase()

    @staticmethod
    def claim_version_id(job_id: str, claim_id: str, version: int) -> str:
        """Return the storage identity while keeping logical lineage job-agnostic."""
        return f"{job_id}:{claim_id}:v{version}"

    @staticmethod
    def logical_claim_version_id(claim_id: str, version: int) -> str:
        return f"{claim_id}:v{version}"

    @staticmethod
    def _packet_payload(packet: EvolutionEvidencePacket) -> Dict[str, Any]:
        payload = packet.model_dump()
        payload["checksum"] = ""
        return payload

    def create_packet(self, packet: EvolutionEvidencePacket) -> Dict[str, Any]:
        payload = self._packet_payload(packet)
        checksum_input = dict(payload)
        checksum_input.pop("checksum", None)
        checksum_input.pop("status", None)
        checksum = canonical_checksum(checksum_input)
        packet_version_id = f"{packet.packet_id}:v{packet.version}"
        payload["checksum"] = checksum
        validated = EvolutionEvidencePacket.model_validate(payload)
        rendered = json.dumps(validated.model_dump(), ensure_ascii=False, sort_keys=True)
        with self.db.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM evolution_evidence_packets WHERE checksum=?", (checksum,)
            ).fetchone()
            if existing:
                return self._packet_row(connection, dict(existing))
            identity = connection.execute(
                "SELECT checksum FROM evolution_evidence_packets WHERE packet_id=? AND version=?",
                (packet.packet_id, packet.version),
            ).fetchone()
            if identity:
                raise ValueError("同一证据包版本不可被不同内容覆盖")
            connection.execute(
                """INSERT INTO evolution_evidence_packets(
                    packet_version_id,packet_id,project_id,version,schema_version,
                    research_contract_version,baseline_year,cutoff_date,status,payload_json,checksum
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (packet_version_id, packet.packet_id, packet.project_id, packet.version,
                 packet.schema_version, packet.research_contract_version, packet.baseline_year,
                 packet.cutoff_date, packet.status, rendered, checksum),
            )
            for source in validated.sources:
                connection.execute(
                    """INSERT INTO evolution_evidence_sources(
                        packet_version_id,source_id,source_kind,locator_json) VALUES (?,?,?,?)""",
                    (packet_version_id, source.source_id, source.source_kind,
                     json.dumps(source.model_dump(), ensure_ascii=False, sort_keys=True)),
                )
            for record in validated.records:
                connection.execute(
                    """INSERT INTO evolution_evidence_records(
                        packet_version_id,evidence_id,evidence_kind,record_json) VALUES (?,?,?,?)""",
                    (packet_version_id, record.evidence_id, record.evidence_kind,
                     json.dumps(record.model_dump(), ensure_ascii=False, sort_keys=True)),
                )
            for attachment in validated.attachments:
                connection.execute(
                    """INSERT INTO evolution_evidence_attachments(
                        packet_version_id,attachment_id,mapping_state,checksum,attachment_json)
                       VALUES (?,?,?,?,?)""",
                    (packet_version_id, attachment.attachment_id, attachment.mapping_state,
                     attachment.checksum,
                     json.dumps(attachment.model_dump(), ensure_ascii=False, sort_keys=True)),
                )
            row = connection.execute(
                "SELECT * FROM evolution_evidence_packets WHERE packet_version_id=?",
                (packet_version_id,),
            ).fetchone()
            return self._packet_row(connection, dict(row))

    def transition_packet(self, packet_version_id: str, status: str) -> Dict[str, Any]:
        order = {"draft": 0, "reviewed": 1, "frozen": 2}
        if status not in order:
            raise ValueError("证据包状态无效")
        with self.db.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM evolution_evidence_packets WHERE packet_version_id=?",
                (packet_version_id,),
            ).fetchone()
            if not row:
                raise ValueError("证据包版本不存在")
            if order[status] < order[row["status"]]:
                raise ValueError("证据包状态不可回退；请创建新版本")
            reviewed = "reviewed_at=CURRENT_TIMESTAMP," if status in {"reviewed", "frozen"} else ""
            frozen = "frozen_at=CURRENT_TIMESTAMP," if status == "frozen" else ""
            connection.execute(
                f"UPDATE evolution_evidence_packets SET {reviewed}{frozen} status=? WHERE packet_version_id=?",
                (status, packet_version_id),
            )
            value = connection.execute(
                "SELECT * FROM evolution_evidence_packets WHERE packet_version_id=?",
                (packet_version_id,),
            ).fetchone()
            return self._packet_row(connection, dict(value))

    def get_packet(self, packet_id: str, version: Optional[int] = None) -> Optional[Dict[str, Any]]:
        with self.db.connect() as connection:
            if version is None:
                row = connection.execute(
                    "SELECT * FROM evolution_evidence_packets WHERE packet_id=? ORDER BY version DESC LIMIT 1",
                    (packet_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT * FROM evolution_evidence_packets WHERE packet_id=? AND version=?",
                    (packet_id, version),
                ).fetchone()
            return self._packet_row(connection, dict(row)) if row else None

    def get_packet_version(self, packet_version_id: str) -> Optional[Dict[str, Any]]:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM evolution_evidence_packets WHERE packet_version_id=?",
                (packet_version_id,),
            ).fetchone()
            return self._packet_row(connection, dict(row)) if row else None

    def list_packet_versions(self, packet_id: str) -> List[Dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM evolution_evidence_packets WHERE packet_id=? ORDER BY version DESC",
                (packet_id,),
            ).fetchall()
            return [self._packet_row(connection, dict(row), details=False) for row in rows]

    def _packet_row(self, connection, row: Dict[str, Any], details: bool = True) -> Dict[str, Any]:
        row["payload"] = json.loads(row.pop("payload_json"))
        row["payload"]["status"] = row["status"]
        row["payload"]["checksum"] = row["checksum"]
        if details:
            row["sources"] = [json.loads(item[0]) for item in connection.execute(
                "SELECT locator_json FROM evolution_evidence_sources WHERE packet_version_id=? ORDER BY source_id",
                (row["packet_version_id"],),
            ).fetchall()]
            row["records"] = [json.loads(item[0]) for item in connection.execute(
                "SELECT record_json FROM evolution_evidence_records WHERE packet_version_id=? ORDER BY evidence_id",
                (row["packet_version_id"],),
            ).fetchall()]
            row["attachments"] = [json.loads(item[0]) for item in connection.execute(
                "SELECT attachment_json FROM evolution_evidence_attachments WHERE packet_version_id=? ORDER BY attachment_id",
                (row["packet_version_id"],),
            ).fetchall()]
        return row

    def create_claim_version(self, job_id: str, packet_version_id: str,
                             claim: DevelopmentClaim) -> Dict[str, Any]:
        payload = claim.model_dump()
        checksum = canonical_checksum(payload)
        version_id = self.claim_version_id(job_id, claim.claim_id, claim.version)
        with self.db.transaction() as connection:
            packet = connection.execute(
                "SELECT status FROM evolution_evidence_packets WHERE packet_version_id=?",
                (packet_version_id,),
            ).fetchone()
            if not packet or packet["status"] != "frozen":
                raise ValueError("命题只能引用冻结证据包")
            existing = connection.execute(
                "SELECT * FROM development_claim_versions WHERE job_id=? AND claim_id=? AND version=?",
                (job_id, claim.claim_id, claim.version),
            ).fetchone()
            if existing:
                if existing["checksum"] != checksum:
                    raise ValueError("既有命题版本不可覆盖")
                return self._claim_row(dict(existing))
            if claim.version > 1:
                parent = connection.execute(
                    "SELECT claim_version_id FROM development_claim_versions WHERE job_id=? AND claim_id=? AND version=?",
                    (job_id, claim.claim_id, claim.version - 1),
                ).fetchone()
                expected_parent = self.logical_claim_version_id(claim.claim_id, claim.version - 1)
                if not parent or claim.parent_version_id != expected_parent:
                    raise ValueError("命题修订必须指向当前上一版本")
                stored_parent_version_id = parent[0]
            else:
                stored_parent_version_id = None
            connection.execute(
                """INSERT INTO development_claim_versions(
                    claim_version_id,job_id,packet_version_id,claim_id,version,parent_version_id,
                    object_ids_json,claim_type,support_level,status,claim_json,checksum
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (version_id, job_id, packet_version_id, claim.claim_id, claim.version,
                 stored_parent_version_id, json.dumps(claim.object_ids, ensure_ascii=False),
                 claim.claim_type, claim.support_level, claim.status,
                 json.dumps(payload, ensure_ascii=False, sort_keys=True), checksum),
            )
            row = connection.execute(
                "SELECT * FROM development_claim_versions WHERE claim_version_id=? AND job_id=?",
                (version_id, job_id),
            ).fetchone()
            return self._claim_row(dict(row))

    def get_claim_lineage(self, job_id: str, claim_id: str) -> List[Dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM development_claim_versions WHERE job_id=? AND claim_id=? ORDER BY version",
                (job_id, claim_id),
            ).fetchall()
        return [self._claim_row(dict(row)) for row in rows]

    @staticmethod
    def _claim_row(row: Dict[str, Any]) -> Dict[str, Any]:
        row["claim"] = json.loads(row.pop("claim_json"))
        row["object_ids"] = json.loads(row.pop("object_ids_json"))
        return row

    def save_findings(self, job_id: str, claim_version_id: str,
                      findings: Iterable[ReviewFinding]) -> List[Dict[str, Any]]:
        output = []
        with self.db.transaction() as connection:
            for finding in findings:
                payload = finding.model_dump()
                storage_finding_id = f"{job_id}:{finding.finding_id}"
                existing = connection.execute(
                    "SELECT finding_json FROM claim_review_findings WHERE finding_id=?",
                    (storage_finding_id,),
                ).fetchone()
                rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
                if existing and existing[0] != rendered:
                    raise ValueError("既有审查意见不可覆盖")
                connection.execute(
                    """INSERT OR IGNORE INTO claim_review_findings(
                        finding_id,job_id,claim_version_id,reviewer_role,check_kind,severity,status,finding_json
                    ) VALUES (?,?,?,?,?,?,?,?)""",
                    (storage_finding_id, job_id, claim_version_id, finding.reviewer_role,
                     finding.check_kind, finding.severity, finding.status, rendered),
                )
                output.append(payload)
        return output

    def close_finding(self, finding_id: str, closed_by_version_id: str,
                      job_id: str = "") -> None:
        with self.db.transaction() as connection:
            storage_finding_id = f"{job_id}:{finding_id}" if job_id else finding_id
            row = connection.execute(
                "SELECT finding_id FROM claim_review_findings WHERE finding_id=?",
                (storage_finding_id,),
            ).fetchone()
            if not row:
                raise ValueError("审查意见不存在")
            connection.execute(
                """UPDATE claim_review_findings SET status='closed',closed_by_version_id=?,
                   closed_at=CURRENT_TIMESTAMP WHERE finding_id=?""",
                (closed_by_version_id, storage_finding_id),
            )

    def save_adjudication(self, job_id: str, claim_version_id: str,
                          value: Adjudication) -> Dict[str, Any]:
        payload = value.model_dump()
        checksum = canonical_checksum(payload)
        storage_adjudication_id = f"{job_id}:{value.adjudication_id}"
        with self.db.transaction() as connection:
            existing = connection.execute(
                "SELECT adjudication_json,checksum FROM claim_adjudications WHERE adjudication_id=?",
                (storage_adjudication_id,),
            ).fetchone()
            if existing and existing["checksum"] != checksum:
                raise ValueError("既有裁决不可覆盖")
            connection.execute(
                """INSERT OR IGNORE INTO claim_adjudications(
                    adjudication_id,job_id,claim_version_id,decision,adjudication_json,checksum
                ) VALUES (?,?,?,?,?,?)""",
                (storage_adjudication_id, job_id, claim_version_id, value.decision,
                 json.dumps(payload, ensure_ascii=False, sort_keys=True), checksum),
            )
        return {**payload, "checksum": checksum}

    def set_claim_state(self, job_id: str, claim_id: str, claim_version_id: str,
                        status: str, details: Optional[Dict[str, Any]] = None) -> None:
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT INTO claim_terminal_states(job_id,claim_id,claim_version_id,status,details_json)
                   VALUES (?,?,?,?,?) ON CONFLICT(job_id,claim_id) DO UPDATE SET
                   claim_version_id=excluded.claim_version_id,status=excluded.status,
                   details_json=excluded.details_json,updated_at=CURRENT_TIMESTAMP""",
                (job_id, claim_id, claim_version_id, status,
                 json.dumps(details or {}, ensure_ascii=False, sort_keys=True)),
            )

    def job_claim_trace(self, job_id: str) -> Dict[str, Any]:
        with self.db.connect() as connection:
            claims = [self._claim_row(dict(row)) for row in connection.execute(
                "SELECT * FROM development_claim_versions WHERE job_id=? ORDER BY claim_id,version", (job_id,)
            ).fetchall()]
            findings = []
            for row in connection.execute(
                "SELECT finding_json,status,closed_by_version_id,closed_at FROM claim_review_findings "
                "WHERE job_id=? ORDER BY created_at,finding_id", (job_id,)
            ).fetchall():
                item = json.loads(row[0])
                item["status"] = row[1]
                item["closed_by_version_id"] = row[2]
                item["closed_at"] = row[3]
                findings.append(item)
            adjudications = [json.loads(row[0]) for row in connection.execute(
                "SELECT adjudication_json FROM claim_adjudications WHERE job_id=? ORDER BY created_at,adjudication_id", (job_id,)
            ).fetchall()]
            states = []
            for row in connection.execute(
                "SELECT * FROM claim_terminal_states WHERE job_id=? ORDER BY claim_id", (job_id,)
            ).fetchall():
                item = dict(row); item["details"] = json.loads(item.pop("details_json")); states.append(item)
            calls = []
            for row in connection.execute(
                "SELECT * FROM thesis_agent_call_traces WHERE job_id=? ORDER BY created_at,call_id",
                (job_id,),
            ).fetchall():
                item = dict(row)
                item["usage"] = json.loads(item.pop("usage_json"))
                item["error"] = json.loads(item.pop("error_json"))
                calls.append(item)
        return {"claims": claims, "findings": findings, "adjudications": adjudications,
                "states": states, "agent_calls": calls}

    def record_agent_call(self, job_id: str, role: str, input_payload: Dict[str, Any],
                          output_payload: Optional[Dict[str, Any]], status: str,
                          prompt_manifest_id: str = "", model_manifest_id: str = "",
                          claim_version_id: str = "", usage: Optional[Dict[str, Any]] = None,
                          error: Optional[Dict[str, Any]] = None) -> str:
        call_id = _id("call")
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT INTO thesis_agent_call_traces(
                    call_id,job_id,role,claim_version_id,prompt_manifest_id,model_manifest_id,
                    input_checksum,output_checksum,usage_json,status,error_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (call_id, job_id, role, claim_version_id or None,
                 prompt_manifest_id or None, model_manifest_id or None,
                 canonical_checksum(input_payload), canonical_checksum(output_payload) if output_payload else "",
                 json.dumps(usage or {}, sort_keys=True), status,
                 json.dumps(error or {}, ensure_ascii=False, sort_keys=True)),
            )
        return call_id
