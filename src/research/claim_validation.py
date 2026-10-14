# -*- coding: utf-8 -*-
"""Deterministic and semantic-boundary validation for development claims."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Set

from src.research.evolution_schemas import DevelopmentClaim, EvolutionEvidencePacket, ReviewFinding
from src.research.repository import canonical_checksum


def _finding(claim: DevelopmentClaim, check_kind: str, category: str, severity: str,
             message: str, evidence_ids=None, remediation="") -> ReviewFinding:
    payload = {
        "claim": claim.claim_id, "version": claim.version, "check": check_kind,
        "category": category, "message": message, "evidence": evidence_ids or [],
    }
    return ReviewFinding(
        finding_id="finding_" + canonical_checksum(payload)[:16],
        claim_id=claim.claim_id, claim_version=claim.version,
        reviewer_role="deterministic", check_kind=check_kind, category=category,
        severity=severity, evidence_ids=list(evidence_ids or []), message=message,
        remediation=remediation,
    )


class ReferenceValidator:
    def validate(self, claim: DevelopmentClaim, packet: EvolutionEvidencePacket) -> List[ReviewFinding]:
        findings = []
        object_ids = {item.object_id for item in packet.objects}
        evidence = {item.evidence_id: item for item in packet.records}
        unknown_objects = set(claim.object_ids) - object_ids
        unknown_evidence = set(claim.evidence_ids) - set(evidence)
        if unknown_objects:
            findings.append(_finding(
                claim, "reference", "object_identity", "blocking",
                "命题引用了冻结证据包之外的对象：" + "、".join(sorted(unknown_objects)),
                remediation="删除越界对象或创建并冻结新的证据包版本。",
            ))
        if unknown_evidence:
            findings.append(_finding(
                claim, "reference", "evidence_identity", "blocking",
                "命题引用了冻结证据包之外的证据：" + "、".join(sorted(unknown_evidence)),
                remediation="仅使用本次冻结证据ID。",
            ))
        for evidence_id in set(claim.evidence_ids) & set(evidence):
            record = evidence[evidence_id]
            if record.object_ids and not set(claim.object_ids) & set(record.object_ids):
                findings.append(_finding(
                    claim, "reference", "object_evidence_scope", "warning",
                    f"证据{evidence_id}未映射到该命题对象。", [evidence_id],
                    "补充映射依据或更换证据。",
                ))
            if not record.source_ids:
                findings.append(_finding(
                    claim, "reference", "source_locator", "blocking",
                    f"证据{evidence_id}缺少来源定位。", [evidence_id], "补充来源注册记录。",
                ))
        for assertion in claim.reference_assertions:
            record = evidence.get(assertion.evidence_id)
            if not record:
                continue
            mismatches = []
            if assertion.expected_stage and record.stage != assertion.expected_stage:
                mismatches.append(f"阶段应为{record.stage}")
            if assertion.expected_ipc and assertion.expected_ipc not in record.ipc_codes:
                mismatches.append("未包含所声明IPC")
            if assertion.expected_source_id and assertion.expected_source_id not in record.source_ids:
                mismatches.append("来源位置不匹配")
            if assertion.expected_cutoff_date and assertion.expected_cutoff_date != packet.cutoff_date:
                mismatches.append(f"证据包截止日期为{packet.cutoff_date}")
            if mismatches:
                findings.append(_finding(
                    claim, "reference", "reference_metadata_mismatch", "blocking",
                    f"{assertion.evidence_id}引用元数据不一致：" + "；".join(mismatches),
                    [assertion.evidence_id], "按冻结证据记录修正阶段、IPC、来源或日期。",
                ))
        return findings


class NumericClaimValidator:
    NUMBER = re.compile(r"(?<![A-Za-z0-9])(?P<number>\d+(?:\.\d+)?)(?![A-Za-z0-9])")

    def validate(self, claim: DevelopmentClaim, packet: EvolutionEvidencePacket,
                 numeric_assertions: Optional[List[Dict[str, Any]]] = None) -> List[ReviewFinding]:
        findings = []
        records = {item.evidence_id: item for item in packet.records}
        cited = [records[item] for item in claim.evidence_ids if item in records]
        allowed: Set[float] = set()
        for record in cited:
            for value in record.values.values():
                if value is not None:
                    allowed.add(round(float(value), 10))
        allowed.update({2025.0, 2030.0, 2035.0, 2040.0})
        for match in self.NUMBER.finditer(claim.statement):
            value = round(float(match.group("number")), 10)
            if value not in allowed:
                findings.append(_finding(
                    claim, "numeric", "unverified_numeric_value", "blocking",
                    f"命题数值{match.group('number')}无法在所引结构化证据中核对。",
                    claim.evidence_ids, "删除该数值、补充结构化来源或明确标为未核验。",
                ))
        assertions = numeric_assertions
        if assertions is None:
            assertions = [item.model_dump() for item in claim.numeric_assertions]
        for item in assertions:
            evidence_id, metric = item.get("evidence_id"), item.get("metric")
            record = records.get(evidence_id)
            if not record or metric not in record.values:
                findings.append(_finding(
                    claim, "numeric", "unknown_metric", "blocking",
                    f"数值断言引用的指标不存在：{evidence_id}/{metric}", [evidence_id] if evidence_id else [],
                ))
                continue
            expected, actual = record.values[metric], item.get("value")
            if expected is None or actual is None or abs(float(expected) - float(actual)) > 1e-9:
                findings.append(_finding(
                    claim, "numeric", "numeric_mismatch", "blocking",
                    f"{evidence_id}的{metric}应为{expected}，命题记录为{actual}。", [evidence_id],
                    "按冻结记录修正数值和指标方向。",
                ))
            expected_unit = record.units.get(metric, "")
            if item.get("unit") and item["unit"] != expected_unit:
                findings.append(_finding(
                    claim, "numeric", "unit_mismatch", "blocking",
                    f"{evidence_id}的{metric}单位应为{expected_unit or '未标注'}。", [evidence_id],
                    "使用冻结记录中的单位或明确记录未标注单位。",
                ))
            if item.get("stage") and item["stage"] != record.stage:
                findings.append(_finding(
                    claim, "numeric", "numeric_stage_mismatch", "blocking",
                    f"{evidence_id}的指标阶段应为{record.stage}。", [evidence_id],
                ))
            if item.get("object_id") and item["object_id"] not in record.object_ids:
                findings.append(_finding(
                    claim, "numeric", "numeric_object_mismatch", "blocking",
                    f"{evidence_id}未归属于对象{item['object_id']}。", [evidence_id],
                ))
        return self._dedupe(findings)

    @staticmethod
    def _dedupe(values: List[ReviewFinding]) -> List[ReviewFinding]:
        return list({item.finding_id: item for item in values}.values())


class InferenceBoundaryValidator:
    PERFORMANCE = re.compile(r"(效率|生产率|性能提升|成本降低|安全性提高|质量提高|工程效益)")
    DYNAMIC = re.compile(r"(加速融合|持续增长|增长率|动态增强|演化速度)")
    MATURITY = re.compile(r"(成熟|产业化|规模化应用|TRL|技术成熟度)", re.I)
    LIFECYCLE = re.compile(r"(进入成长期|进入成熟期|进入衰退期|主题生命周期)")
    OBSERVED = re.compile(r"(已经实现|已形成|已证明|实测|实际提高)")

    def validate(self, claim: DevelopmentClaim, packet: EvolutionEvidencePacket) -> List[ReviewFinding]:
        findings = []
        records = {item.evidence_id: item for item in packet.records}
        cited = [records[item] for item in claim.evidence_ids if item in records]
        kinds = {item.evidence_kind for item in cited}
        mapping_bases = {item.mapping_basis for item in cited}
        if "network_observation" in kinds and self.PERFORMANCE.search(claim.statement):
            findings.append(_finding(
                claim, "inference_boundary", "network_to_performance", "blocking",
                "网络结构指标不能直接证明工程性能或效益提升。", claim.evidence_ids,
                "改为结构观察，或补充试验/应用证据。",
            ))
        if "semantic_relation" in kinds and self.DYNAMIC.search(claim.statement):
            findings.append(_finding(
                claim, "inference_boundary", "static_to_dynamic", "blocking",
                "静态语义关系不能直接证明动态增长或融合速度。", claim.evidence_ids,
                "降级为功能联系假设，或补充分阶段动态证据。",
            ))
        if kinds <= {"theme_fact", "network_observation", "semantic_relation", "method_metric"} \
                and self.MATURITY.search(claim.statement):
            findings.append(_finding(
                claim, "inference_boundary", "patent_to_maturity", "blocking",
                "主题、专利网络或聚类记录不足以确认工程成熟度。", claim.evidence_ids,
                "删除成熟度判断或补充试验、示范、部署证据。",
            ))
        if "functional_only" in mapping_bases and re.search(r"(该主题的专利|主题增长率|主题中心度)", claim.statement):
            findings.append(_finding(
                claim, "inference_boundary", "ipc_to_theme", "blocking",
                "功能对应不能表述为已核验的IPC—专利—主题样本归属。", claim.evidence_ids,
                "保留功能对应前提，或引用已提供并核验的逐文档映射。",
            ))
        if self.LIFECYCLE.search(claim.statement) and not any(
                item.evidence_kind == "engineering_source"
                or bool(item.model_provenance.get("lifecycle_method")) for item in cited):
            findings.append(_finding(
                claim, "inference_boundary", "domain_to_topic_lifecycle", "blocking",
                "IPC领域变化或功能联系不能直接确认论文主题的生命周期。",
                claim.evidence_ids, "提供明确的主题生命周期方法与证据，否则改为有限的结构观察。",
            ))
        if claim.claim_type == "target_scenario" and self.OBSERVED.search(claim.statement):
            findings.append(_finding(
                claim, "inference_boundary", "scenario_to_observation", "blocking",
                "目标情景被表述为已经观测或实现的事实。", claim.evidence_ids,
                "使用条件性目标表达并列出进入条件。",
            ))
        if claim.claim_type == "conditional_extrapolation" and not claim.enabling_conditions:
            findings.append(_finding(
                claim, "inference_boundary", "missing_conditions", "warning",
                "条件外推没有列出实现条件。", claim.evidence_ids, "补充与命题相关的前置条件。",
            ))
        return findings


class ClaimValidationSuite:
    def __init__(self):
        self.reference = ReferenceValidator()
        self.numeric = NumericClaimValidator()
        self.boundary = InferenceBoundaryValidator()

    def validate(self, claim: DevelopmentClaim, packet: EvolutionEvidencePacket,
                 numeric_assertions: Optional[List[Dict[str, Any]]] = None) -> List[ReviewFinding]:
        values = [
            *self.reference.validate(claim, packet),
            *self.numeric.validate(claim, packet, numeric_assertions),
            *self.boundary.validate(claim, packet),
        ]
        return list({item.finding_id: item for item in values}.values())

    @staticmethod
    def support_level(claim: DevelopmentClaim, findings: Iterable[ReviewFinding]) -> str:
        findings = list(findings)
        if claim.claim_type == "insufficient_evidence" or not claim.evidence_ids:
            return "insufficient_evidence"
        if any(item.severity == "blocking" and item.status != "closed" for item in findings):
            return "insufficient_evidence"
        if claim.claim_type == "historical_observation" and not findings:
            return "direct_support"
        if claim.claim_type == "target_scenario":
            return "exploratory_scenario"
        return "conditional_support"
