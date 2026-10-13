# -*- coding:utf-8 -*-
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator
from src.library.validation import validate_override_reason


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=500_000)
    source_type: Literal["text", "txt", "md", "json"] = "text"

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("文档内容不能为空")
        return value


class DocumentInfo(BaseModel):
    document_id: str
    title: str
    source_type: str
    content: str
    cleaned_content: str
    created_at: datetime


class IpcEvidence(BaseModel):
    ipc: str
    trend: str = ""
    quote: str = ""
    document_id: str


class FusionPair(BaseModel):
    ipc1: str = Field(min_length=1)
    ipc2: str = Field(min_length=1)
    prob: float = Field(ge=0, le=1)


class CandidateTopic(BaseModel):
    topic_id: str
    topic_name: str = Field(min_length=1, max_length=120)
    keywords: List[str] = Field(default_factory=list)
    example: str = ""
    ipc_evidence: List[IpcEvidence] = Field(default_factory=list)
    ipc_trend: str = ""
    fusion_pairs: List[FusionPair] = Field(default_factory=list)
    sample_abstracts: List[str] = Field(default_factory=list)
    operator_notes: str = ""
    evidence_score: float = Field(default=0, ge=0, le=100)
    requires_review: bool = False
    selected: bool = True


class TopicExtractionRequest(BaseModel):
    document_ids: List[str] = Field(min_length=1)
    seed_topics: Literal["use_existing", "none"] = "use_existing"
    extraction_mode: Literal["rules_only", "rules_then_llm"] = "rules_only"


class CandidateTopicCreate(BaseModel):
    topic_name: str = Field(min_length=1, max_length=120)
    keywords: List[str] = Field(default_factory=list)
    example: str = ""
    ipc_evidence: List[IpcEvidence] = Field(default_factory=list)
    ipc_trend: str = ""
    fusion_pairs: List[FusionPair] = Field(default_factory=list)
    sample_abstracts: List[str] = Field(default_factory=list)
    operator_notes: str = ""
    selected: bool = True


class CandidateTopicUpdate(BaseModel):
    topic_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    keywords: Optional[List[str]] = None
    example: Optional[str] = None
    ipc_evidence: Optional[List[IpcEvidence]] = None
    ipc_trend: Optional[str] = None
    fusion_pairs: Optional[List[FusionPair]] = None
    sample_abstracts: Optional[List[str]] = None
    operator_notes: Optional[str] = None
    evidence_score: Optional[float] = Field(default=None, ge=0, le=100)
    requires_review: Optional[bool] = None
    selected: Optional[bool] = None


class NormalizeTopicsRequest(BaseModel):
    topic_ids: Optional[List[str]] = None


class EvidenceGroundedTopicInput(BaseModel):
    """Unified topic contract consumed by all forecast rounds."""

    topic_id: str = ""
    topic_name: str = Field(min_length=1, max_length=120)
    keywords: List[str] = Field(default_factory=list)
    example: str = ""
    selected: bool = True
    ipc_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    ipc_trend: str = ""
    fusion_pairs: List[Dict[str, Any]] = Field(default_factory=list)
    sample_abstracts: List[str] = Field(default_factory=list)
    operator_notes: str = ""
    evidence_score: float = Field(default=0, ge=0, le=100)
    evidence_package: Dict[str, Any] = Field(default_factory=dict)
    technologies: List[Dict[str, Any]] = Field(default_factory=list)
    stage_analysis: List[Dict[str, Any]] = Field(default_factory=list)
    forecast_context: Dict[str, Any] = Field(default_factory=dict)


class ForecastOptions(BaseModel):
    enable_self_consistency: bool = False
    enable_multi_agent_debate: bool = False
    enable_multi_model: bool = False
    enable_reasoning_chain: bool = True
    enable_per_topic_roadmap: bool = True
    force_rerun: bool = False


class ForecastJobCreate(BaseModel):
    topic_ids: List[str] = Field(min_length=1)
    time_nodes: List[Literal["2030", "2035", "2040"]] = Field(
        default_factory=lambda: ["2030", "2035", "2040"]
    )
    options: ForecastOptions = Field(default_factory=ForecastOptions)

    @field_validator("time_nodes")
    @classmethod
    def validate_time_nodes(cls, value: List[str]) -> List[str]:
        ordered = [year for year in ("2030", "2035", "2040") if year in value]
        if not ordered or len(ordered) != len(set(value)):
            raise ValueError("预测节点必须是非重复的2030、2035、2040")
        return ordered


class ProjectForecastJobCreate(ForecastJobCreate):
    override_evidence_gate: bool = False
    override_reason: str = Field(default="", max_length=500)
    idempotency_key: str = Field(default="", max_length=120)
    confirmation_token: str = ""
    parent_job_id: Optional[str] = None

    @field_validator("override_reason")
    @classmethod
    def validate_override_reason(cls, value: str) -> str:
        return validate_override_reason(value)


class ReadinessRequirement(BaseModel):
    id: str
    label: str
    actual: Any
    required: Any
    passed: bool
    blocking: bool = True
    overrideable: bool = True
    weight: int = Field(ge=0, le=100)
    remediation: str = ""


class EvidenceReadiness(BaseModel):
    contract_version: int
    score: int = Field(ge=0, le=100)
    sufficient: bool
    state: Literal["ready", "blocked", "override_required"]
    requirements: List[ReadinessRequirement] = Field(default_factory=list)
    missing: List[str] = Field(default_factory=list)
    missing_periods: List[str] = Field(default_factory=list)
    ipc_record_count: int = 0
    year_count: int = 0
    paper_count: int = 0
    paper_fragment_count: int = 0
    data_cutoff: Optional[int] = None


class WorkflowStepReadiness(BaseModel):
    id: Literal["overview", "materials", "topics-evidence", "forecast", "results"]
    label: str
    state: Literal["hidden", "blocked", "available", "completed"]
    visible: bool = True
    route: str
    blocking_reasons: List[str] = Field(default_factory=list)
    remediation: List[str] = Field(default_factory=list)


class RecommendedWorkflowAction(BaseModel):
    step_id: str
    label: str
    route: str


class PaginatedRecords(BaseModel):
    items: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class JobActionCommit(BaseModel):
    confirmation_token: str = Field(min_length=1)
    payload: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(default="", max_length=120)


class ForecastStep(BaseModel):
    name: str
    status: Literal["pending", "running", "done", "failed", "skipped"]
    message: str = ""


class ForecastJobStatus(BaseModel):
    job_id: str
    status: Literal[
        "queued", "running", "cancelling", "cancelled",
        "completed", "partial_failed", "failed",
    ]
    current_stage: str
    progress: float = Field(ge=0, le=1)
    steps: List[ForecastStep]
    created_at: datetime
    error: str = ""


class ForecastResult(BaseModel):
    job_id: str
    time_nodes: List[str]
    topics: List[Dict[str, Any]]
    round1_results: List[Dict[str, Any]]
    round2_result: Dict[str, Any]
    round3_result: Any
    per_topic_roadmaps: List[Dict[str, Any]]
    fusion_evolution: List[Dict[str, Any]]
    confidence_summary: Dict[str, Any]
    uncertainty_summary: Dict[str, Any]
    reasoning_chain: List[Dict[str, Any]]
    academic_conclusion: str
    asset_summary: Dict[str, Any] = Field(default_factory=dict)
    project_id: str = ""
    evidence_limited: bool = False
    override_reason: str = ""
    evidence_snapshot_checksum: str = ""
    stage_quality: Dict[str, Any] = Field(default_factory=dict)
    baseline_year: int = 2025
    target_year: int = 2040
    taxonomy: Dict[str, Any] = Field(default_factory=dict)
    historical_periods: List[str] = Field(default_factory=list)
    stage_analysis: List[Dict[str, Any]] = Field(default_factory=list)
