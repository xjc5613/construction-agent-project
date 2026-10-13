# -*- coding: utf-8 -*-
"""Versioned structured contracts for evidence-constrained agent nodes."""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "agent-contract-v1"


class EvidenceClaim(ContractModel):
    claim: str = Field(min_length=1)
    evidence_ids: List[str] = Field(min_length=1)
    confidence: Literal["low", "medium", "high"]
    limitation: str = ""


class EvidenceAnalysis(ContractModel):
    analysis_kind: Literal["patent", "paper", "integrated"]
    claims: List[EvidenceClaim]
    conflicts: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class TechnologyConcept(ContractModel):
    concept_name: str = Field(min_length=1)
    ipc_pairs: List[str] = Field(min_length=1)
    mechanism: str = Field(min_length=1)
    evidence_ids: List[str] = Field(min_length=1)
    model_candidate_ids: List[str] = Field(default_factory=list)


class CriticFinding(ContractModel):
    severity: Literal["info", "warning", "blocking"]
    category: Literal["evidence", "causality", "uncertainty", "schema", "citation"]
    message: str = Field(min_length=1)
    target_id: str = ""
    remediation: str = ""


class ForecastMilestone(ContractModel):
    year: Literal[2030, 2035, 2040]
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    trl: Optional[int] = Field(None, ge=1, le=9)
    dependencies: List[str] = Field(default_factory=list)
    indicators: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(min_length=1)
    uncertainty: Literal["low", "medium", "high"] = "medium"


class ThemeForecast(ContractModel):
    theme_id: str
    theme_name: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    ipc_pairs: List[str] = Field(min_length=1)
    milestones: List[ForecastMilestone]
    limitations: List[str] = Field(default_factory=list)

    @field_validator("milestones")
    @classmethod
    def milestones_are_cumulative(cls, value):
        years = [item.year for item in value]
        if years != sorted(set(years)):
            raise ValueError("路线图年份必须唯一且递增")
        return value


class Scenario(ContractModel):
    name: Literal["baseline", "accelerated", "constrained"]
    assumptions: List[str] = Field(min_length=1)
    milestones: List[ForecastMilestone]


class ScenarioRoadmap(ContractModel):
    theme_id: str
    scenarios: List[Scenario]

    @model_validator(mode="after")
    def all_scenarios_present(self):
        if {item.name for item in self.scenarios} != {"baseline", "accelerated", "constrained"}:
            raise ValueError("必须包含基准、加速、受限三种情景")
        return self


class ThemeDossier(ContractModel):
    theme: ThemeForecast
    scenarios: ScenarioRoadmap
    evidence_analysis: EvidenceAnalysis
    critic_findings: List[CriticFinding]
    model_summary: Dict[str, object]
    review_status: Literal["pending", "approved", "edited", "rejected"]
    limitations: List[str] = Field(default_factory=list)
