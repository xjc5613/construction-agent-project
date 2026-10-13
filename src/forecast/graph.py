# -*- coding: utf-8 -*-
"""Think-and-Execute forecast graph on LangGraph.

Pipeline:
  prepare -> execute(per-topic forecast) -> think(critic)
          ->[needs revision?] -> revise -> roadmap -> synthesize -> done

The critic loop runs at most once: if any finding is medium/high severity,
executor revises once using the critique, then proceeds to roadmap.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, TypedDict

from langgraph.graph import END, START, StateGraph

from . import prompts as P
from .llm import call_structured
from .schemas import (
    CriticFinding,
    Synthesis,
    TopicEvidence,
    TopicForecast,
    TopicRoadmap,
)


class ForecastState(TypedDict, total=False):
    job_id: str
    evidence: List[TopicEvidence]
    forecasts: List[TopicForecast]
    critiques: List[CriticFinding]
    revision_count: int
    roadmaps: List[TopicRoadmap]
    synthesis: Synthesis
    stage: str
    progress: float
    log: List[str]


def _emit(state: ForecastState, stage: str, progress: float, message: str) -> dict:
    return {"stage": stage, "progress": progress,
            "log": [*state.get("log", []), message]}


def node_prepare(state: ForecastState) -> dict:
    n = len(state.get("evidence", []))
    return _emit(state, "prepare", 0.05, f"载入 {n} 个技术主题证据，启动预测编排")


def node_execute(state: ForecastState) -> dict:
    evidence = state["evidence"]

    def one(ev: TopicEvidence) -> TopicForecast:
        user = P.FORECAST_USER_TEMPLATE.format(
            topic_name=ev.topic_name,
            keywords="、".join(ev.keywords),
            example=ev.example,
            ipc_trend=ev.ipc_trend or "（未提供）",
        )
        return call_structured(P.FORECAST_SYSTEM, user, TopicForecast)

    results = _parallel(one, evidence, desc="主题预测")
    update = _emit(state, "execute", 0.35, f"执行器完成 {len(results)} 个主题预测")
    update["forecasts"] = results
    return update


def node_think(state: ForecastState) -> dict:
    forecasts = state.get("forecasts", [])
    evidence_by_name = {e.topic_name: e for e in state.get("evidence", [])}

    def one(f: TopicForecast) -> CriticFinding:
        ev = evidence_by_name.get(f.topic_name, TopicEvidence(topic_name=f.topic_name))
        user = P.CRITIC_USER_TEMPLATE.format(
            topic_name=f.topic_name,
            ipc_trend=ev.ipc_trend,
            forecast_json=json.dumps(f.model_dump(), ensure_ascii=False, indent=2),
        )
        return call_structured(P.CRITIC_SYSTEM, user, CriticFinding)

    findings = _parallel(one, forecasts, desc="科学评审")
    update = _emit(state, "think", 0.5, f"评审完成，发现 {_blocking_count(findings)} 处需修正")
    update["critiques"] = findings
    return update


def node_revise(state: ForecastState) -> dict:
    forecasts = state.get("forecasts", [])
    critiques = state.get("critiques", [])
    advice = {c.topic_name: c for c in critiques}

    def one(f: TopicForecast) -> TopicForecast:
        finding = advice.get(f.topic_name)
        errors = [finding.revision_advice, *finding.issues] if finding else []
        ev = next((e for e in state.get("evidence", []) if e.topic_name == f.topic_name), None)
        user = P.FORECAST_USER_TEMPLATE.format(
            topic_name=f.topic_name,
            keywords="、".join(ev.keywords if ev else []),
            example=ev.example if ev else "",
            ipc_trend=ev.ipc_trend if ev else "",
        )
        return call_structured(
            P.FORECAST_SYSTEM, user, TopicForecast,
            correction_attempt=1, previous_errors=[e for e in errors if e],
        )

    revised = _parallel(one, forecasts, desc="修正预测")
    update = _emit(state, "revise", 0.6, "根据评审意见完成一轮修正")
    update["forecasts"] = revised
    update["revision_count"] = 1
    return update


def node_roadmap(state: ForecastState) -> dict:
    forecasts = state.get("forecasts", [])

    def one(f: TopicForecast) -> TopicRoadmap:
        user = P.ROADMAP_USER_TEMPLATE.format(
            topic_name=f.topic_name,
            forecast_json=json.dumps(f.model_dump(), ensure_ascii=False, indent=2),
        )
        return call_structured(P.ROADMAP_SYSTEM, user, TopicRoadmap)

    roadmaps = _parallel(one, forecasts, desc="路线图")
    update = _emit(state, "roadmap", 0.8, f"完成 {len(roadmaps)} 个主题的 2030/2035/2040 路线图")
    update["roadmaps"] = roadmaps
    return update


def node_synthesize(state: ForecastState) -> dict:
    forecasts = state.get("forecasts", [])
    summary = [
        {"topic": f.topic_name, "confidence": f.confidence,
         "breakthroughs": f.breakthroughs_by_2040,
         "uncertainty": f.uncertainty_notes}
        for f in forecasts
    ]
    user = P.SYNTHESIS_USER_TEMPLATE.format(
        forecasts_json=json.dumps(summary, ensure_ascii=False, indent=2)
    )
    synthesis = call_structured(P.SYNTHESIS_SYSTEM, user, Synthesis)
    update = _emit(state, "synthesize", 0.95, f"全局综合完成：{synthesis.new_paradigm_name}")
    update["synthesis"] = synthesis
    return update


def node_done(state: ForecastState) -> dict:
    return _emit(state, "done", 1.0, "预测完成")


def route_after_think(state: ForecastState) -> str:
    if state.get("revision_count", 0) >= 1:
        return "roadmap"
    return "revise" if _blocking_count(state.get("critiques", [])) > 0 else "roadmap"


def _blocking_count(critiques: List[CriticFinding]) -> int:
    return sum(1 for c in critiques if c.severity in ("medium", "high"))


def _parallel(fn, items, desc: str):
    if not items:
        return []
    results = [None] * len(items)
    with ThreadPoolExecutor(max_workers=min(5, len(items))) as pool:
        future_to_idx = {pool.submit(fn, item): i for i, item in enumerate(items)}
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()
    return [r for r in results if r is not None]


def build_graph():
    g = StateGraph(ForecastState)
    g.add_node("prepare", node_prepare)
    g.add_node("execute", node_execute)
    g.add_node("think", node_think)
    g.add_node("revise", node_revise)
    g.add_node("roadmap", node_roadmap)
    g.add_node("synthesize", node_synthesize)
    g.add_node("done", node_done)

    g.add_edge(START, "prepare")
    g.add_edge("prepare", "execute")
    g.add_edge("execute", "think")
    g.add_conditional_edges(
        "think", route_after_think,
        {"revise": "revise", "roadmap": "roadmap"},
    )
    g.add_edge("revise", "roadmap")
    g.add_edge("roadmap", "synthesize")
    g.add_edge("synthesize", "done")
    g.add_edge("done", END)
    return g.compile()


_compiled = None


def run_forecast(evidence: List[TopicEvidence], job_id: str) -> ForecastState:
    """Execute the full graph and return final state."""
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    initial: ForecastState = {
        "job_id": job_id, "evidence": evidence, "revision_count": 0,
        "stage": "start", "progress": 0.0, "log": [],
    }
    return _compiled.invoke(initial)
