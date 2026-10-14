# -*- coding: utf-8 -*-
"""Build and version the bounded Chapter 4 evolution-evidence packet."""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from src.research.evolution_schemas import (
    EvidenceRecord, EvolutionEvidencePacket, SourceLocator, ThesisObject,
    TraceabilityAttachment,
)
from src.research.repository import canonical_checksum
from src.research.thesis_repository import ThesisRepository


EVIDENCE_KIND_BY_PREFIX = {
    "Q": "theme_fact",
    "N": "network_observation",
    "H": "semantic_relation",
    "M": "method_metric",
}


class EvidencePacketService:
    def __init__(self, repository: Optional[ThesisRepository] = None):
        self.repository = repository or ThesisRepository()

    @staticmethod
    def normalize_source(value: Dict[str, Any], fallback_id: str = "") -> SourceLocator:
        kind = str(value.get("source_kind") or value.get("kind") or "paragraph").lower()
        aliases = {"表": "table", "图": "figure", "段落": "paragraph", "文件": "file"}
        kind = aliases.get(kind, kind)
        if kind not in {"table", "figure", "paragraph", "file", "artifact"}:
            kind = "paragraph"
        locator = value.get("locator") or value.get("location") or value.get("source_location")
        if not locator:
            locator = value.get("title") or fallback_id or "未提供具体定位"
        return SourceLocator(
            source_id=str(value.get("source_id") or fallback_id or f"source_{uuid4().hex[:10]}"),
            source_kind=kind,
            title=str(value.get("title") or ""),
            locator=str(locator),
            file_path=str(value.get("file_path") or value.get("path") or ""),
            checksum=str(value.get("checksum") or ""),
            notes=str(value.get("notes") or ""),
        )

    @staticmethod
    def normalize_object(value: Dict[str, Any], fallback_kind: str = "theme") -> ThesisObject:
        object_id = str(value.get("object_id") or value.get("theme_id") or value.get("candidate_id") or "")
        object_kind = value.get("object_kind") or ("candidate" if object_id.startswith("C") else fallback_kind)
        return ThesisObject(
            object_id=object_id,
            object_kind=object_kind,
            name=str(value.get("name") or value.get("theme_name") or value.get("title") or ""),
            definition=str(value.get("definition") or value.get("description") or value.get("technical_meaning") or ""),
            keywords=list(value.get("keywords") or value.get("representative_words") or []),
            typical_technologies=list(value.get("typical_technologies") or value.get("examples") or []),
            representative_patent_ids=list(value.get("representative_patent_ids") or []),
            lifecycle_status=value.get("lifecycle_status"),
            lifecycle_availability_note=str(value.get("lifecycle_availability_note") or ""),
        )

    @staticmethod
    def infer_kind(evidence_id: str, supplied: str = "") -> str:
        if supplied:
            return supplied
        prefix = re.match(r"[A-Za-z]+", evidence_id)
        key = prefix.group(0)[0].upper() if prefix else ""
        return EVIDENCE_KIND_BY_PREFIX.get(key, "engineering_source")

    def import_draft(self, payload: Dict[str, Any], project_id: str,
                     packet_id: str = "", version: Optional[int] = None) -> EvolutionEvidencePacket:
        """Normalize a user draft without turning null into zero or inventing optional data."""
        source_values = list(payload.get("sources") or [])
        record_values = list(payload.get("records") or payload.get("evidence_records") or [])
        source_by_id: Dict[str, SourceLocator] = {}
        for raw in source_values:
            source = self.normalize_source(raw)
            source_by_id[source.source_id] = source

        objects: List[ThesisObject] = []
        for raw in list(payload.get("objects") or payload.get("themes") or []):
            objects.append(self.normalize_object(raw, "theme"))
        for raw in list(payload.get("candidates") or []):
            objects.append(self.normalize_object(raw, "candidate"))

        records: List[EvidenceRecord] = []
        for index, raw in enumerate(record_values, start=1):
            evidence_id = str(raw.get("evidence_id") or raw.get("id") or f"E{index:03d}")
            source_ids = list(raw.get("source_ids") or [])
            if not source_ids:
                embedded = raw.get("source") or raw.get("source_location")
                if isinstance(embedded, dict):
                    source = self.normalize_source(embedded, f"src_{evidence_id}")
                else:
                    source = self.normalize_source(
                        {"locator": embedded or "未提供具体定位", "source_kind": "paragraph"},
                        f"src_{evidence_id}",
                    )
                source_by_id[source.source_id] = source
                source_ids = [source.source_id]
            values = copy.deepcopy(raw.get("values") or raw.get("metrics") or {})
            # Deliberately retain None. Missing or null never becomes 0.
            records.append(EvidenceRecord(
                evidence_id=evidence_id,
                evidence_kind=self.infer_kind(evidence_id, str(raw.get("evidence_kind") or "")),
                object_ids=list(raw.get("object_ids") or ([raw["object_id"]] if raw.get("object_id") else [])),
                statement=str(raw.get("statement") or raw.get("description") or raw.get("claim") or ""),
                stage=raw.get("stage"),
                ipc_codes=list(raw.get("ipc_codes") or ([raw["ipc_code"]] if raw.get("ipc_code") else [])),
                values=values,
                units=dict(raw.get("units") or {}),
                source_ids=source_ids,
                mapping_basis=raw.get("mapping_basis", "unknown"),
                relation_type=str(raw.get("relation_type") or ""),
                limitations=list(raw.get("limitations") or []),
                supports=list(raw.get("supports") or []),
                does_not_support=list(raw.get("does_not_support") or []),
                availability_note=str(raw.get("availability_note") or ""),
                model_provenance=dict(raw.get("model_provenance") or {}),
                reviewed=bool(raw.get("reviewed", False)),
            ))

        attachments = []
        for raw in list(payload.get("attachments") or []):
            attachments.append(TraceabilityAttachment.model_validate(raw))
        mapping = payload.get("ipc_patent_topic_mapping")
        if mapping:
            mapping = dict(mapping)
            mapping.setdefault("attachment_id", "ipc-patent-topic-mapping")
            attachments.append(TraceabilityAttachment.model_validate(mapping))
        elif payload.get("mapping_reported_count"):
            attachments.append(TraceabilityAttachment(
                attachment_id="ipc-patent-topic-mapping",
                mapping_state="reported_but_not_supplied",
                row_count=int(payload["mapping_reported_count"]),
                notes="论文报告已完成映射，但当前证据包未提供逐行表。",
            ))

        packet_id = packet_id or str(payload.get("packet_id") or f"packet_{uuid4().hex[:12]}")
        if version is None:
            latest = self.repository.get_packet(packet_id)
            version = int(latest["version"]) + 1 if latest else int(payload.get("version") or 1)
        packet = EvolutionEvidencePacket(
            packet_id=packet_id,
            project_id=project_id,
            version=version,
            status=payload.get("status", "draft"),
            objects=objects,
            sources=sorted(source_by_id.values(), key=lambda item: item.source_id),
            records=records,
            attachments=attachments,
            validation_summary=self.validation_summary(objects, records, attachments),
        )
        return packet

    @staticmethod
    def validation_summary(objects: Iterable[ThesisObject], records: Iterable[EvidenceRecord],
                           attachments: Iterable[TraceabilityAttachment]) -> Dict[str, Any]:
        objects, records, attachments = list(objects), list(records), list(attachments)
        object_ids = {item.object_id for item in objects}
        covered = {identifier for item in records for identifier in item.object_ids}
        mapping_states = sorted({item.mapping_state for item in attachments})
        return {
            "object_count": len(objects),
            "theme_count": sum(item.object_kind == "theme" for item in objects),
            "candidate_count": sum(item.object_kind == "candidate" for item in objects),
            "evidence_count": len(records),
            "objects_without_records": sorted(object_ids - covered),
            "mapping_states": mapping_states,
            "optional_missing_is_blocking": False,
        }

    def create_from_draft(self, payload: Dict[str, Any], project_id: str,
                          packet_id: str = "") -> Dict[str, Any]:
        return self.repository.create_packet(self.import_draft(payload, project_id, packet_id))

    def review(self, packet_version_id: str) -> Dict[str, Any]:
        return self.repository.transition_packet(packet_version_id, "reviewed")

    def freeze(self, packet_version_id: str) -> Dict[str, Any]:
        packet = self.repository.get_packet_version(packet_version_id)
        if not packet or packet["status"] not in {"reviewed", "frozen"}:
            raise ValueError("证据包必须先完成人工审阅")
        return self.repository.transition_packet(packet_version_id, "frozen")

    def diff(self, left_version_id: str, right_version_id: str) -> Dict[str, Any]:
        left = self.repository.get_packet_version(left_version_id)
        right = self.repository.get_packet_version(right_version_id)
        if not left or not right:
            raise ValueError("证据包版本不存在")
        left_records = {item["evidence_id"]: item for item in left["records"]}
        right_records = {item["evidence_id"]: item for item in right["records"]}
        shared = set(left_records) & set(right_records)
        return {
            "left_checksum": left["checksum"], "right_checksum": right["checksum"],
            "added": sorted(set(right_records) - set(left_records)),
            "removed": sorted(set(left_records) - set(right_records)),
            "changed": sorted(key for key in shared
                              if canonical_checksum(left_records[key]) != canonical_checksum(right_records[key])),
        }

    def import_reviewed_discovery(self, packet_id: str, discovery: Dict[str, Any],
                                  object_ids: List[str], reviewer: str,
                                  source_locator: Dict[str, Any]) -> Dict[str, Any]:
        latest = self.repository.get_packet(packet_id)
        if not latest or latest["status"] != "frozen":
            raise ValueError("只能向已有冻结证据包派生新版本")
        if not discovery.get("reviewed") or not reviewer.strip():
            raise ValueError("融合发现必须经过明确人工审阅")
        payload = copy.deepcopy(latest["payload"])
        payload["status"] = "draft"
        payload["checksum"] = ""
        payload["version"] = latest["version"] + 1
        payload["sources"] = list(payload.get("sources") or [])
        source = self.normalize_source(source_locator, f"discovery_{discovery.get('candidate_id','candidate')}")
        payload["sources"].append(source.model_dump())
        payload["records"] = list(payload.get("records") or [])
        payload["records"].append(EvidenceRecord(
            evidence_id=str(discovery.get("evidence_id") or f"D-{discovery.get('candidate_id','candidate')}"),
            evidence_kind="derived_model_evidence", object_ids=object_ids,
            statement=str(discovery.get("statement") or "经审核的IPC融合模型候选"),
            source_ids=[source.source_id], mapping_basis="functional_only",
            limitations=list(discovery.get("limitations") or []),
            supports=list(discovery.get("supports") or []),
            does_not_support=list(discovery.get("does_not_support") or ["不能自动改写论文主题"]),
            model_provenance={**dict(discovery.get("model_provenance") or {}), "reviewer": reviewer},
            reviewed=True,
        ).model_dump())
        packet = EvolutionEvidencePacket.model_validate(payload)
        packet.validation_summary = self.validation_summary(packet.objects, packet.records, packet.attachments)
        return self.repository.create_packet(packet)
