# -*- coding: utf-8 -*-
"""Inventory or add a reviewed Chapter 4 evidence draft without rewriting legacy data."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.library import LibraryDatabase
from src.research.evidence_packets import EvidencePacketService
from src.research.thesis_repository import ThesisRepository


def inventory(repository: ThesisRepository) -> dict:
    with repository.db.connect() as connection:
        jobs = [dict(row) for row in connection.execute(
            "SELECT job_id,status,job_mode,research_contract_version FROM forecast_jobs ORDER BY job_id"
        ).fetchall()]
        packets = [dict(row) for row in connection.execute(
            "SELECT packet_version_id,project_id,status,checksum FROM evolution_evidence_packets "
            "ORDER BY packet_version_id"
        ).fetchall()]
        missing = [dict(row) for row in connection.execute(
            """SELECT packet_version_id FROM evolution_evidence_packets p
               WHERE NOT EXISTS (
                 SELECT 1 FROM evolution_evidence_attachments a
                 WHERE a.packet_version_id=p.packet_version_id
               ) ORDER BY packet_version_id"""
        ).fetchall()]
    return {
        "legacy_jobs": [item for item in jobs if item["job_mode"] == "legacy_read_only"],
        "discovery_jobs": [item for item in jobs if item["job_mode"] == "ipc_fusion_discovery"],
        "thesis_jobs": [item for item in jobs if item["job_mode"] == "thesis_evolution_forecast"],
        "packets": packets,
        "missing_optional_mapping_attachments": missing,
        "requires_researcher_review": [item["packet_version_id"] for item in packets
                                        if item["status"] == "draft"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Chapter 4 evidence packet migration")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--input", type=Path, help="Chapter 4 JSON draft")
    parser.add_argument("--project-id")
    parser.add_argument("--packet-id", default="")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--reviewed-confirmation", action="store_true",
                        help="Confirm a researcher reviewed the input before additive import")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    repository = ThesisRepository(LibraryDatabase(args.db))
    report = {
        "schema_version": "evolution-migration-report-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "apply" if args.apply else "dry_run",
        "before": inventory(repository),
        "created": None,
    }
    if args.input:
        if not args.project_id:
            parser.error("--input requires --project-id")
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        service = EvidencePacketService(repository)
        draft = service.import_draft(payload, args.project_id, args.packet_id)
        report["candidate"] = {
            "packet_id": draft.packet_id,
            "version": draft.version,
            "validation_summary": draft.validation_summary,
            "optional_attachments": [item.model_dump() for item in draft.attachments],
        }
        if args.apply:
            if not args.reviewed_confirmation:
                parser.error("--apply requires --reviewed-confirmation")
            created = repository.create_packet(draft)
            report["created"] = {
                "packet_version_id": created["packet_version_id"],
                "checksum": created["checksum"],
                "status": created["status"],
            }
            report["rollback"] = {
                "policy": "Only an unreferenced draft may be removed; reviewed/frozen packets are immutable.",
                "packet_version_id": created["packet_version_id"],
            }
    elif args.apply:
        parser.error("--apply requires --input")
    report["after"] = inventory(repository)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.report:
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
