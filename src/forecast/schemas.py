# -*- coding: utf-8 -*-
"""Structured output schemas for the think-and-execute forecast graph."""
from typing import Dict, List, Literal

from pydantic import BaseModel, Field

Uncertainty = Literal["low", "medium", "high"]


class TopicEvidence(BaseModel):
    """Immutable evidence packet for one construction-technology topic."""

    topic_name: str
    keywords: List[str] = Field(default_factory=list)
    example: str = ""
    ipc_trend: str = ""


class TopicForecast(BaseModel):
    """Executor output: one topic's mid/long-term forecast."""

    topic_name: str
    drivers: List[str] = Field(
        default_factory=list, description="2025-2040 年推动该技术的主要力量"
    )
    bottlenecks_2030_2035: List[str] = Field(
        default_factory=list, description="2030-2035 年间的关键瓶颈"
    )
    breakthroughs_by_2040: List[str] = Field(
        default_factory=list, description="到 2040 年可能实现的突破"
    )
    enabling_technologies: List[str] = Field(
        default_factory=list, description="支撑该技术突破的使能技术"
    )
    confidence: float = Field(
        ge=0, le=100, description="综合证据后给出的置信度 0-100"
    )
    uncertainty_notes: str = Field(default="", description="主要不确定性与边界条件")


class CriticFinding(BaseModel):
    """Thinker output: scientific review of an executor forecast."""

    topic_name: str
    issues: List[str] = Field(
        default_factory=list, description="过度断言、证据缺口或逻辑问题"
    )
    severity: Literal["low", "medium", "high"] = "low"
    revision_advice: str = ""


class RoadmapMilestone(BaseModel):
    name: str
    trl_level: int = Field(ge=1, le=9, description="技术成熟度等级 1-9")
    uncertainty_level: Uncertainty = "medium"
    note: str = ""


class TopicRoadmap(BaseModel):
    """Per-topic phased roadmap at 2030 / 2035 / 2040."""

    topic_name: str
    stages: Dict[str, List[RoadmapMilestone]] = Field(
        description="键为 '2030'/'2035'/'2040'，值为该阶段里程碑"
    )
    terminal_trl: float = Field(ge=1, le=9, description="2040 年平均 TRL")


class Synthesis(BaseModel):
    """Global synthesis across all topics."""

    new_paradigm_name: str
    new_paradigm_description: str
    cross_topic_fusions: List[str] = Field(default_factory=list)
    grand_challenges: List[str] = Field(default_factory=list)
    conclusion: str = ""
