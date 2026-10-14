# -*- coding: utf-8 -*-
"""Controlled evaluation utilities for thesis forecasting workflows."""

from __future__ import annotations

import copy
import json
from typing import Any, Callable, Dict, Iterable, List, Optional

from src.research.evolution_schemas import EvaluationManifest, EvolutionEvidencePacket
from src.research.repository import canonical_checksum
from src.research.thesis_repository import ThesisRepository


REQUIRED_ARMS = ("single_agent", "five_role", "staged_reflection")
VALID_ABLATIONS = ("reverse_review", "engineering_review", "deterministic_validation", "local_rereview")


class ForecastMethodEvaluator:
    def __init__(self, repository: Optional[ThesisRepository] = None):
        self.repository = repository or ThesisRepository()

    def register(self, packet_version_id: str, manifest: EvaluationManifest) -> Dict[str, Any]:
        packet = self.repository.get_packet_version(packet_version_id)
        if not packet or packet["status"] != "frozen":
            raise ValueError("方法评价必须绑定冻结证据包")
        if manifest.packet_checksum != packet["checksum"]:
            raise ValueError("评价清单与证据包校验和不匹配")
        payload = manifest.model_dump()
        checksum = canonical_checksum(payload)
        with self.repository.db.transaction() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO forecast_method_evaluations(
                    evaluation_id,packet_version_id,manifest_json,manifest_checksum,status
                ) VALUES (?,?,?,?,?)""",
                (manifest.evaluation_id, packet_version_id,
                 json.dumps(payload, ensure_ascii=False, sort_keys=True), checksum, manifest.status),
            )
        return {"evaluation_id": manifest.evaluation_id, "status": manifest.status,
                "manifest_checksum": checksum}

    def run_paired(self, packet: EvolutionEvidencePacket, manifest: EvaluationManifest,
                   runners: Dict[str, Callable[[EvolutionEvidencePacket, Dict[str, Any]], Dict[str, Any]]],
                   ablation: str = "") -> Dict[str, Any]:
        missing = set(REQUIRED_ARMS) - set(runners)
        if missing:
            raise ValueError("缺少评价组：" + "、".join(sorted(missing)))
        if ablation and ablation not in VALID_ABLATIONS:
            raise ValueError("消融因素必须一次只选择一个预注册组件")
        outputs, failures = {}, {}
        base_context = {
            "packet_checksum": manifest.packet_checksum,
            "object_ids": manifest.object_ids,
            "base_model": manifest.base_model,
            "budgets": manifest.budgets,
            "revision_limit": manifest.revision_limit,
            "ablation": ablation,
        }
        for arm in REQUIRED_ARMS:
            try:
                outputs[arm] = runners[arm](packet.model_copy(deep=True), dict(base_context))
            except Exception as exc:
                failures[arm] = str(exc)
        return {"status": "completed" if outputs else "not_estimable",
                "outputs": outputs, "failures": failures,
                "metrics": self.metrics(outputs), "ablation": ablation or None}

    @staticmethod
    def metrics(outputs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        result = {}
        for arm, payload in outputs.items():
            claims = payload.get("claims", [])
            findings = payload.get("findings", [])
            states = payload.get("claim_states", {})
            total = len(claims)
            result[arm] = {
                "claim_count": total,
                "valid_reference_rate": ForecastMethodEvaluator._ratio(
                    sum(not item.get("reference_error") for item in claims), total),
                "numeric_fidelity_rate": ForecastMethodEvaluator._ratio(
                    sum(not item.get("numeric_error") for item in claims), total),
                "semantic_support_rate": ForecastMethodEvaluator._ratio(
                    sum(item.get("semantic_support") in {"whole", "partial"} for item in claims), total),
                "unsupported_extrapolation_count": sum(bool(item.get("unsupported_extrapolation")) for item in claims),
                "condition_complete_rate": ForecastMethodEvaluator._ratio(
                    sum(bool(item.get("enabling_conditions")) for item in claims
                        if item.get("claim_type") == "conditional_extrapolation"),
                    sum(item.get("claim_type") == "conditional_extrapolation" for item in claims)),
                "finding_resolution_rate": ForecastMethodEvaluator._ratio(
                    sum(item.get("status") == "closed" for item in findings), len(findings)),
                "coverage": {key: sum(value == key for value in states.values()) for key in (
                    "accepted", "downgraded", "deferred", "insufficient_evidence",
                    "revision_exhausted", "execution_failed")},
                "calls": payload.get("resource_cost", {}).get("calls"),
                "tokens": payload.get("resource_cost", {}).get("tokens"),
                "elapsed_seconds": payload.get("resource_cost", {}).get("elapsed_seconds"),
                "retries": payload.get("resource_cost", {}).get("retries"),
                "failures": payload.get("resource_cost", {}).get("failures"),
                "resource_cost": payload.get("resource_cost", {}),
            }
        return result

    @staticmethod
    def _ratio(numerator: int, denominator: int):
        return round(numerator / denominator, 4) if denominator else None

    @staticmethod
    def substantive_repeatability(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        if len(runs) < 2:
            return {"status": "not_estimable", "reason": "至少需要两次重复运行"}
        signatures = []
        for run in runs:
            signatures.append({
                item.get("claim_id"): canonical_checksum({
                    "objects": item.get("object_ids", []),
                    "type": item.get("claim_type"),
                    "evidence": sorted(item.get("evidence_ids", [])),
                    "conditions": sorted(item.get("enabling_conditions", [])),
                    "support": item.get("support_level"),
                    "gaps": sorted(item.get("unresolved_gaps", [])),
                }) for item in run.get("claims", [])
            })
        shared = set.intersection(*(set(item) for item in signatures)) if signatures else set()
        stable = sum(len({item[claim_id] for item in signatures}) == 1 for claim_id in shared)
        return {"status": "estimated", "shared_claims": len(shared), "stable_claims": stable,
                "substantive_stability": ForecastMethodEvaluator._ratio(stable, len(shared))}

    @staticmethod
    def perturb(packet: EvolutionEvidencePacket, kind: str, evidence_id: str = "") -> EvolutionEvidencePacket:
        value = packet.model_copy(deep=True)
        if kind == "reverse_order":
            value.records = list(reversed(value.records))
        elif kind == "deduplicate_sources":
            seen = set(); records = []
            for item in value.records:
                signature = tuple(sorted(item.source_ids))
                if signature not in seen:
                    records.append(item); seen.add(signature)
            value.records = records
        elif kind == "duplicate_same_source":
            if not value.records:
                raise ValueError("证据包中没有可复制的记录")
            duplicate = value.records[0].model_copy(
                update={"evidence_id": value.records[0].evidence_id + "-METHOD-DUPLICATE"})
            value.records = [*value.records, duplicate]
        elif kind == "remove_evidence":
            value.records = [item for item in value.records if item.evidence_id != evidence_id]
        elif kind == "shorten_summaries":
            value.records = [item.model_copy(update={"statement": item.statement[:120]}) for item in value.records]
        else:
            raise ValueError("不支持的扰动类型")
        value.status = "draft"
        value.checksum = ""
        value.validation_summary = {**value.validation_summary, "method_test": True,
                                    "perturbation": kind, "authentic_packet_unchanged": True}
        return value

    @staticmethod
    def blind_review_export(results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        items = []
        for index, (_, payload) in enumerate(sorted(results.items()), start=1):
            items.append({"condition_code": f"condition_{index:02d}",
                          "claims": copy.deepcopy(payload.get("claims", [])),
                          "annotation": None, "disagreement": None, "adjudication": None})
        return {"workflow_identity_hidden": True, "items": items,
                "rule": "工程评审模型输出不得作为其自身唯一真值标签"}

    @staticmethod
    def annotation_status(export: Dict[str, Any]) -> Dict[str, Any]:
        items = export.get("items", [])
        if not items:
            return {"status": "not_estimable", "reason": "没有可标注的命题"}
        annotated = [item for item in items if item.get("annotation") is not None]
        if len(annotated) < len(items):
            return {"status": "insufficient_annotation", "annotated": len(annotated),
                    "required": len(items)}
        return {"status": "completed", "annotated": len(annotated)}
