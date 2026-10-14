# -*- coding: utf-8 -*-
"""Contracts for bounded Chapter 4 evidence and Chapter 5 claim deliberation."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


EvidenceKind = Literal[
    "theme_fact", "network_observation", "semantic_relation", "method_metric",
    "engineering_source", "derived_model_evidence",
]
MappingState = Literal[
    "supplied_verified", "supplied_unverified", "reported_but_not_supplied", "unavailable",
]
MappingBasis = Literal[
    "verified_document_mapping", "reported_mapping", "functional_only", "not_applicable", "unknown",
]
ClaimType = Literal[
    "historical_observation", "conditional_extrapolation", "target_scenario", "insufficient_evidence",
]
SupportLevel = Literal[
    "direct_support", "conditional_support", "exploratory_scenario", "insufficient_evidence",
]
ClaimStatus = Literal[
    "proposed", "under_review", "accepted", "revision_required", "downgraded", "deferred",
    "revision_exhausted", "insufficient_evidence", "execution_failed", "cancelled",
]
JobMode = Literal["thesis_evolution_forecast", "ipc_fusion_discovery", "legacy_read_only"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceLocator(StrictModel):
    source_id: str = Field(min_length=1)
    source_kind: Literal["table", "figure", "paragraph", "file", "artifact"]
    title: str = ""
    locator: str = Field(min_length=1)
    file_path: str = ""
    checksum: str = ""
    notes: str = ""


class ThesisObject(StrictModel):
    object_id: str
    object_kind: Literal["theme", "candidate"]
    name: str = Field(min_length=1)
    definition: str = Field(min_length=1)
    keywords: List[str] = Field(default_factory=list)
    typical_technologies: List[str] = Field(default_factory=list)
    representative_patent_ids: List[str] = Field(default_factory=list)
    lifecycle_status: Optional[str] = None
    lifecycle_availability_note: str = ""

    @model_validator(mode="after")
    def identity_matches_kind(self):
        expected = r"T0[1-9]" if self.object_kind == "theme" else r"C0[1-6]"
        if not re.fullmatch(expected, self.object_id):
            raise ValueError("主题必须使用T01-T09，候选必须使用C01-C06")
        return self


class EvidenceRecord(StrictModel):
    evidence_id: str = Field(min_length=1)
    evidence_kind: EvidenceKind
    object_ids: List[str] = Field(default_factory=list)
    statement: str = Field(min_length=1)
    stage: Optional[Literal["2010_2014", "2015_2019", "2020_2025"]] = None
    ipc_codes: List[str] = Field(default_factory=list)
    values: Dict[str, Optional[float]] = Field(default_factory=dict)
    units: Dict[str, str] = Field(default_factory=dict)
    source_ids: List[str] = Field(min_length=1)
    mapping_basis: MappingBasis = "unknown"
    relation_type: str = ""
    limitations: List[str] = Field(default_factory=list)
    supports: List[str] = Field(default_factory=list)
    does_not_support: List[str] = Field(default_factory=list)
    availability_note: str = ""
    model_provenance: Dict[str, Any] = Field(default_factory=dict)
    reviewed: bool = False

    @model_validator(mode="after")
    def discovery_requires_review_and_provenance(self):
        if self.evidence_kind == "derived_model_evidence":
            if not self.reviewed or not self.model_provenance:
                raise ValueError("派生模型证据必须经过审核并保留模型来源")
            if not self.object_ids:
                raise ValueError("派生模型证据必须显式映射论文对象")
        return self


class TraceabilityAttachment(StrictModel):
    attachment_id: str = Field(min_length=1)
    mapping_state: MappingState
    filename: str = ""
    checksum: str = ""
    row_count: Optional[int] = Field(None, ge=0)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    notes: str = ""

    @model_validator(mode="after")
    def supplied_has_content(self):
        if self.mapping_state.startswith("supplied_") and not (self.rows or self.filename):
            raise ValueError("已提供的映射附件必须包含文件或映射行")
        return self


class EvolutionEvidencePacket(StrictModel):
    schema_version: str = "evolution-evidence-packet-v1"
    packet_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    research_contract_version: Literal[3] = 3
    baseline_year: Literal[2025] = 2025
    cutoff_date: str = "2025-10-01"
    status: Literal["draft", "reviewed", "frozen"] = "draft"
    objects: List[ThesisObject]
    sources: List[SourceLocator]
    records: List[EvidenceRecord]
    attachments: List[TraceabilityAttachment] = Field(default_factory=list)
    validation_summary: Dict[str, Any] = Field(default_factory=dict)
    checksum: str = ""

    @model_validator(mode="after")
    def validate_references(self):
        object_ids = [item.object_id for item in self.objects]
        if len(object_ids) != len(set(object_ids)):
            raise ValueError("论文对象ID不能重复")
        evidence_ids = [item.evidence_id for item in self.records]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("同一证据包内证据ID不能重复")
        source_ids = {item.source_id for item in self.sources}
        object_set = set(object_ids)
        for record in self.records:
            if not set(record.object_ids) <= object_set:
                raise ValueError("证据记录引用了证据包之外的论文对象")
            if not set(record.source_ids) <= source_ids:
                raise ValueError("证据记录引用了未注册来源")
        themes = {item.object_id for item in self.objects if item.object_kind == "theme"}
        if themes and themes != {f"T{i:02d}" for i in range(1, 10)}:
            raise ValueError("包含主题时必须完整保留T01-T09")
        return self


class EvolutionObservation(StrictModel):
    observation_id: str
    object_ids: List[str] = Field(min_length=1)
    statement: str = Field(min_length=1)
    evidence_ids: List[str] = Field(min_length=1)
    missing_fields: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class EvolutionSummary(StrictModel):
    object_id: str
    observations: List[EvolutionObservation] = Field(default_factory=list)
    missingness: List[str] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)


class EvolutionSummaryBatch(StrictModel):
    summaries: List[EvolutionSummary]


class EvidenceReferenceAssertion(StrictModel):
    evidence_id: str
    expected_stage: Optional[str] = None
    expected_ipc: Optional[str] = None
    expected_source_id: Optional[str] = None
    expected_cutoff_date: Optional[str] = None


class NumericAssertion(StrictModel):
    evidence_id: str
    metric: str
    value: Optional[float] = None
    unit: str = ""
    object_id: str = ""
    stage: Optional[str] = None


class DevelopmentClaim(StrictModel):
    schema_version: str = "development-claim-v1"
    claim_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    parent_version_id: Optional[str] = None
    object_ids: List[str] = Field(min_length=1)
    claim_type: ClaimType
    target_period: Literal["historical", "2026_2030", "2031_2035", "2036_2040", "cross_period"]
    scenario: str = "baseline"
    statement: str = Field(min_length=1)
    evidence_ids: List[str] = Field(default_factory=list)
    reference_assertions: List[EvidenceReferenceAssertion] = Field(default_factory=list)
    numeric_assertions: List[NumericAssertion] = Field(default_factory=list)
    reasoning_bridge: str = ""
    assumptions: List[str] = Field(default_factory=list)
    enabling_conditions: List[str] = Field(default_factory=list)
    validation_requirements: List[str] = Field(default_factory=list)
    competing_explanations: List[str] = Field(default_factory=list)
    uncertainty_sources: List[str] = Field(default_factory=list)
    support_level: SupportLevel
    support_reason: str = Field(min_length=1)
    unresolved_gaps: List[str] = Field(default_factory=list)
    status: ClaimStatus = "proposed"
    change_reason: str = ""

    @model_validator(mode="after")
    def align_type_and_support(self):
        if self.claim_type == "historical_observation" and self.target_period != "historical":
            raise ValueError("历史观察必须使用historical时段")
        if self.claim_type == "insufficient_evidence":
            if self.support_level != "insufficient_evidence" or self.evidence_ids:
                raise ValueError("证据不足命题不得伪装成有据结论")
        if self.claim_type != "insufficient_evidence" and not self.evidence_ids:
            raise ValueError("非证据不足命题必须引用冻结证据")
        if self.version > 1 and not self.parent_version_id:
            raise ValueError("修订版本必须指向上一版本")
        return self


class DevelopmentClaimBatch(StrictModel):
    claims: List[DevelopmentClaim]


class ReviewFinding(StrictModel):
    finding_id: str
    claim_id: str
    claim_version: int = Field(ge=1)
    reviewer_role: Literal["deterministic", "reverse_reviewer", "engineering_reviewer", "semantic_reviewer"]
    check_kind: str
    category: str
    severity: Literal["info", "warning", "blocking"]
    evidence_ids: List[str] = Field(default_factory=list)
    message: str = Field(min_length=1)
    remediation: str = ""
    semantic_support: Optional[Literal["whole", "partial", "contradictory", "indeterminate"]] = None
    status: Literal["open", "closed", "retained"] = "open"
    closed_by_version: Optional[int] = None


class ReviewFindingBatch(StrictModel):
    findings: List[ReviewFinding]


class Adjudication(StrictModel):
    adjudication_id: str
    claim_id: str
    claim_version: int = Field(ge=1)
    decision: Literal["accept", "revise", "downgrade", "defer"]
    finding_ids: List[str] = Field(default_factory=list)
    resolved_finding_ids: List[str] = Field(default_factory=list)
    unresolved_finding_ids: List[str] = Field(default_factory=list)
    resulting_support_level: SupportLevel
    reason: str = Field(min_length=1)
    required_changes: List[str] = Field(default_factory=list)


class AdjudicationBatch(StrictModel):
    adjudications: List[Adjudication]


class RoadmapMilestone(StrictModel):
    milestone_id: str
    object_id: str
    period: Literal["2026_2030", "2031_2035", "2036_2040"]
    capability: str = Field(min_length=1)
    claim_version_ids: List[str] = Field(min_length=1)
    prerequisites: List[str] = Field(default_factory=list)
    entry_conditions: List[str] = Field(default_factory=list)
    validation_indicators: List[str] = Field(default_factory=list)
    scenario_assumptions: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(min_length=1)
    retained_objections: List[str] = Field(default_factory=list)
    trl: Optional[int] = Field(None, ge=1, le=9)
    trl_scale: str = ""
    trl_evidence_ids: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def trl_requires_evidence(self):
        if self.trl is not None and (not self.trl_scale or not self.trl_evidence_ids):
            raise ValueError("TRL必须包含量表和成熟度证据")
        return self


class RoadmapBatch(StrictModel):
    milestones: List[RoadmapMilestone]


class CrossThemeRelation(StrictModel):
    relation_id: str
    source_object_id: str
    target_object_id: str
    relation_basis: Literal[
        "network_observation", "static_semantic_relation", "reviewed_model_evidence",
        "engineering_functional_hypothesis",
    ]
    statement: str
    evidence_ids: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class CrossThemeSynthesis(StrictModel):
    relations: List[CrossThemeRelation] = Field(default_factory=list)
    summary: str = ""
    unresolved_gaps: List[str] = Field(default_factory=list)


class ClaimRunSummary(StrictModel):
    total: int = 0
    accepted: int = 0
    downgraded: int = 0
    deferred: int = 0
    insufficient_evidence: int = 0
    revision_exhausted: int = 0
    execution_failed: int = 0
    cancelled: int = 0


class ObjectTask(StrictModel):
    object_id: str
    status: Literal["pending", "completed", "execution_failed"] = "pending"
    error: str = ""


class EvaluationManifest(StrictModel):
    schema_version: str = "forecast-method-evaluation-v1"
    evaluation_id: str
    packet_checksum: str
    object_ids: List[str]
    base_model: Dict[str, Any]
    prompt_versions: Dict[str, str]
    budgets: Dict[str, Any]
    revision_limit: int = Field(ge=0)
    repeats: int = Field(ge=1)
    annotation_rules: Dict[str, Any]
    metrics: List[str]
    status: Literal["not_run", "running", "completed", "not_estimable", "insufficient_annotation"] = "not_run"


class ThesisJobRequest(StrictModel):
    mode: JobMode = "thesis_evolution_forecast"
    packet_id: str = ""
    packet_version: Optional[int] = None
    revision_limit: int = Field(2, ge=0, le=10)
    compute_concurrency: int = Field(4, ge=1, le=16)
    run_budget: Dict[str, Any] = Field(default_factory=dict)
    model_options: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def thesis_requires_packet(self):
        if self.mode == "thesis_evolution_forecast" and not self.packet_id:
            raise ValueError("论文研判模式必须指定冻结证据包")
        return self
