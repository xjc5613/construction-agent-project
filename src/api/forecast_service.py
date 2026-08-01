# -*- coding:utf-8 -*-
import hashlib
import json
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.llm_orchestrator import (
    run_all_topics_roadmap,
    run_round1,
    run_round2,
    run_round3,
)

from .asset_service import generate_job_assets
from .storage import WorkbenchStorage
from .topic_service import normalize_topic

_RUN_LOCK = threading.Lock()
STEP_NAMES = [
    "evidence_retrieval",
    "evidence_review",
    "snapshot",
    "quality_gate",
    "topic_normalization",
    "round1",
    "round2",
    "round3",
    "per_topic_roadmap",
    "report",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _initial_steps(evidence_mode: bool = False) -> List[Dict[str, str]]:
    evidence_steps = {"evidence_retrieval", "evidence_review", "snapshot", "quality_gate"}
    return [
        {
            "name": name,
            "status": "done" if evidence_mode and name in evidence_steps else (
                "skipped" if not evidence_mode and name in evidence_steps else "pending"
            ),
            "message": "证据快照已就绪" if evidence_mode and name in evidence_steps else "",
        }
        for name in STEP_NAMES
    ]


def _set_step(job: Dict[str, Any], name: str, status: str, message: str = "") -> None:
    for step in job["steps"]:
        if step["name"] == name:
            step["status"] = status
            step["message"] = message
            break
    completed = sum(step["status"] in {"done", "skipped"} for step in job["steps"])
    job["progress"] = completed / len(job["steps"])
    job["current_stage"] = name


def create_job(
    storage: WorkbenchStorage,
    topic_ids: List[str],
    options: Dict[str, Any],
    *,
    project_id: str = "",
    topic_snapshot: Optional[List[Dict[str, Any]]] = None,
    evidence_snapshot: Optional[Dict[str, Any]] = None,
    evidence_limited: bool = False,
    override_reason: str = "",
) -> Dict[str, Any]:
    job_id = f"forecast_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
    job = {
        "job_id": job_id,
        "status": "queued",
        "current_stage": "topic_normalization",
        "progress": 0.0,
        "steps": _initial_steps(evidence_snapshot is not None),
        "created_at": _utc_now(),
        "error": "",
        "topic_ids": topic_ids,
        "options": options,
        "project_id": project_id,
        "topic_snapshot": topic_snapshot or [],
        "evidence_limited": evidence_limited,
        "override_reason": override_reason,
        "evidence_snapshot_checksum": "",
    }
    storage.save_job(job_id, job)
    if evidence_snapshot is not None:
        rendered = json.dumps(evidence_snapshot, ensure_ascii=False, sort_keys=True)
        checksum = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
        evidence_snapshot["checksum"] = checksum
        storage.save_job_artifact(job_id, "evidence_snapshot.json", evidence_snapshot)
        job["evidence_snapshot_checksum"] = checksum
        storage.save_job(job_id, job)
    return job


def _build_result(
    job_id: str,
    topics: List[Dict[str, Any]],
    round1_results: List[Dict[str, Any]],
    round2_result: Dict[str, Any],
    round3_result: Any,
    roadmaps: List[Dict[str, Any]],
    job: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    job = job or {}
    fusion_evolution = []
    for topic in topics:
        for pair in topic.get("fusion_pairs", []):
            fusion_evolution.append({
                "topic": topic["topic_name"],
                "source": pair.get("ipc1"),
                "target": pair.get("ipc2"),
                "weight": pair.get("prob", 0),
            })
    confidences = [item.get("confidence") for item in round1_results if isinstance(item.get("confidence"), (int, float))]
    uncertainty_counts = {"low": 0, "medium": 0, "high": 0}
    for roadmap in roadmaps:
        for stage in roadmap.get("roadmap", {}).values():
            for milestone in stage.get("milestones", []):
                uncertainty = milestone.get("uncertainty_level", "medium")
                uncertainty_counts[uncertainty] = uncertainty_counts.get(uncertainty, 0) + 1
    chains = [
        {"topic_name": result.get("topic_name"), "reasoning_chain": result.get("reasoning_chain", [])}
        for result in round1_results
        if result.get("reasoning_chain")
    ]
    paradigm = round2_result.get("new_paradigm_name", "未形成稳定的新范式")
    conclusion = (
        f"基于{len(round1_results)}个技术主题的证据约束预测，"
        f"2030—2040年的重点是跨IPC技术融合、TRL提升和不确定性治理。"
        f"综合范式归纳为“{paradigm}”。"
    )
    return {
        "job_id": job_id,
        "time_nodes": ["2030", "2035", "2040"],
        "topics": topics,
        "round1_results": round1_results,
        "round2_result": round2_result,
        "round3_result": round3_result,
        "per_topic_roadmaps": roadmaps,
        "fusion_evolution": fusion_evolution,
        "confidence_summary": {
            "average": round(sum(confidences) / len(confidences), 2) if confidences else None,
            "available_topics": len(confidences),
        },
        "uncertainty_summary": uncertainty_counts,
        "reasoning_chain": chains,
        "academic_conclusion": conclusion,
        "asset_summary": {"count": 0, "failed_count": 0, "status": "pending"},
        "project_id": job.get("project_id", ""),
        "evidence_limited": bool(job.get("evidence_limited")),
        "override_reason": job.get("override_reason", ""),
        "evidence_snapshot_checksum": job.get("evidence_snapshot_checksum", ""),
        "stage_quality": {},
    }


def _build_charts(result: Dict[str, Any]) -> Dict[str, Any]:
    timeline, trl_series, heatmap, evidence_table = [], [], [], []
    ipc_trends, paper_year_counts, paper_keywords = [], {}, {}
    representative_papers, evidence_matrix, sankey_links = [], [], []
    round1_by_topic = {
        item.get("topic_name"): item for item in result.get("round1_results", [])
    }
    for roadmap in result["per_topic_roadmaps"]:
        topic_name = roadmap.get("topic_name", "")
        series = {"name": topic_name, "data": []}
        for year in ("2025", "2030", "2035", "2040"):
            milestones = roadmap.get("roadmap", {}).get(year, {}).get("milestones", [])
            trls = [item.get("trl_level") for item in milestones if isinstance(item.get("trl_level"), (int, float))]
            if year != "2025":
                timeline.append({
                    "topic": topic_name,
                    "year": year,
                    "milestones": [item.get("name", "") for item in milestones],
                })
            series["data"].append({"year": year, "value": round(sum(trls) / len(trls), 2) if trls else None})
            if year != "2025":
                levels = [item.get("uncertainty_level", "medium") for item in milestones]
                score = {"low": 1, "medium": 2, "high": 3}
                heatmap.append({
                    "topic": topic_name,
                    "year": year,
                    "value": round(sum(score.get(level, 2) for level in levels) / len(levels), 2) if levels else 2,
                })
        trl_series.append(series)
    for topic in result["topics"]:
        package = topic.get("evidence_package", {})
        active_items = [
            item for item in package.get("items", []) if not item.get("excluded")
        ]
        ipc_count = sum(item.get("evidence_type") == "ipc_metric" for item in active_items)
        paper_count = sum(item.get("evidence_type") == "paper" for item in active_items)
        conflicts = round1_by_topic.get(
            topic.get("topic_name", ""), {}
        ).get("evidence_conflicts", [])
        evidence_matrix.append({
            "topic": topic.get("topic_name", ""),
            "ipc_count": ipc_count,
            "paper_count": paper_count,
            "status": (
                "conflict" if conflicts
                else "convergent" if ipc_count and paper_count
                else "ipc_only" if ipc_count else "paper_only" if paper_count else "insufficient"
            ),
            "conflicts": conflicts,
        })
        for item in active_items:
            metadata = item.get("metadata", {})
            if item.get("evidence_type") == "ipc_metric":
                ipc_trends.append({
                    "topic": topic.get("topic_name", ""),
                    "ipc_code": metadata.get("ipc_code"),
                    "year": metadata.get("year"),
                    "patent_count": metadata.get("patent_count"),
                    "degree_centrality": metadata.get("degree_centrality"),
                    "betweenness_centrality": metadata.get("betweenness_centrality"),
                    "growth_rate": metadata.get("growth_rate"),
                    "evidence_id": item.get("evidence_id"),
                })
            elif item.get("evidence_type") == "paper":
                year = metadata.get("year")
                if year:
                    key = (topic.get("topic_name", ""), year)
                    paper_year_counts[key] = paper_year_counts.get(key, 0) + 1
                representative_papers.append({
                    "topic": topic.get("topic_name", ""),
                    "paper_id": item.get("source_id"),
                    "title": item.get("title", ""),
                    "year": year,
                    "evidence_id": item.get("evidence_id"),
                    "relevance": item.get("relevance", 0),
                })
                for keyword in str(metadata.get("keywords") or "").replace("；", ",").split(","):
                    keyword = keyword.strip()
                    if keyword:
                        key = (topic.get("topic_name", ""), keyword)
                        paper_keywords[key] = paper_keywords.get(key, 0) + 1
        for evidence in topic.get("ipc_evidence", []):
            evidence_table.append({
                "topic": topic.get("topic_name", ""),
                "ipc": evidence.get("ipc", ""),
                "quote": evidence.get("quote", ""),
                "document_id": evidence.get("document_id", ""),
            })
        for pair in topic.get("fusion_pairs", []):
            sankey_links.append({
                "source": pair.get("ipc1"), "target": pair.get("ipc2"),
                "value": pair.get("prob", pair.get("probability", 0)),
                "topic": topic.get("topic_name", ""),
            })
    return {
        "timeline": timeline,
        "trl_series": trl_series,
        "fusion_network": result["fusion_evolution"],
        "uncertainty_heatmap": heatmap,
        "evidence_table": evidence_table,
        "ipc_trends": ipc_trends,
        "paper_trends": [
            {"topic": topic, "year": year, "count": count}
            for (topic, year), count in sorted(paper_year_counts.items())
        ],
        "paper_directions": [
            {"topic": topic, "keyword": keyword, "count": count}
            for (topic, keyword), count in sorted(
                paper_keywords.items(), key=lambda item: item[1], reverse=True
            )
        ],
        "representative_papers": sorted(
            representative_papers, key=lambda item: item["relevance"], reverse=True
        )[:30],
        "evidence_matrix": evidence_matrix,
        "fusion_sankey": sankey_links,
    }


def _build_markdown(result: Dict[str, Any]) -> str:
    dataset_versions = sorted({
        f"{item.get('metadata', {}).get('dataset_name', item.get('dataset_id', '未知数据集'))}"
        f"@{item.get('metadata', {}).get('dataset_version', 'unknown')}"
        for topic in result.get("topics", [])
        for item in topic.get("evidence_package", {}).get("items", [])
        if item.get("dataset_id") and not item.get("excluded")
    })
    lines = [
        "# 智能建造技术预测工作台报告",
        "",
        "## 摘要",
        result["academic_conclusion"],
        "",
        "## 数据来源",
        "本报告基于研究文档中的技术主题、IPC分类号、融合关系和人工校准信息生成。",
        f"- 数据集版本：{', '.join(dataset_versions) if dataset_versions else '未登记'}",
        f"- 证据快照：`{result.get('evidence_snapshot_checksum') or 'legacy-input'}`",
        f"- 证据截止与限制：{'证据受限，' + result.get('override_reason', '') if result.get('evidence_limited') else '通过完整性门槛'}",
        "",
        "## 方法说明",
        "系统复用现有三轮预测、分主题路线图、置信度和推理链条机制；2025年仅作基线，重点预测2030、2035、2040三个节点。",
        "",
        "## 技术主题预测",
    ]
    for item in result["round1_results"]:
        lines.append(f"### {item.get('topic_name', '未命名主题')}")
        for bottleneck in item.get("bottlenecks_2030_2035", []):
            lines.append(f"- 2030-2035瓶颈：{bottleneck}")
        for breakthrough in item.get("breakthroughs_by_2040", []):
            lines.append(f"- 2040突破：{breakthrough}")
        evidence_ids = item.get("evidence_ids", [])
        if evidence_ids:
            lines.append(f"- 证据引用：{', '.join(evidence_ids)}")
        for conflict in item.get("evidence_conflicts", []):
            lines.append(f"- 证据冲突：{conflict}")
    lines.extend(["", "## 技术融合变化"])
    for edge in result["fusion_evolution"]:
        lines.append(f"- {edge['topic']}：{edge['source']} → {edge['target']}（融合权重 {edge['weight']}）")
    lines.extend([
        "",
        "## 不确定性分析",
        str(result["uncertainty_summary"]),
        "",
        "## 结论",
        result["academic_conclusion"],
        "",
        "## 局限性",
        "预测结果受输入研究文档覆盖范围、IPC网络质量和大语言模型输出稳定性影响，应结合专家评审与后续回溯验证使用。",
        "",
        "## 阶段质量",
        str(result.get("stage_quality", {})),
        "",
        "## 图表索引",
        "交互式图表数据见 charts.json；主题级 PNG 资产见 assets.json。",
    ])
    return "\n".join(lines) + "\n"


@contextmanager
def _job_runner_configuration(job_dir, options: Dict[str, Any]):
    """Redirect runner caches and apply job-level options for one serialized job."""
    import src.llm_orchestrator.per_topic_roadmap_runner as roadmap_runner
    import src.llm_orchestrator.round1_runner as round1_runner
    import src.llm_orchestrator.round2_runner as round2_runner
    import src.llm_orchestrator.round3_runner as round3_runner
    import src.output_parser.parse_round1 as parse_round1
    import src.output_parser.parse_round2 as parse_round2
    import src.output_parser.parse_round3 as parse_round3

    runner_modules = [round1_runner, round2_runner, round3_runner, roadmap_runner]
    parser_modules = [parse_round1, parse_round2, parse_round3]
    original_values = []
    original_reasoning = [(module, module.ENABLE_REASONING_CHAIN) for module in parser_modules]
    raw_dir = job_dir / "raw"
    parsed_dir = job_dir / "parsed"
    raw_dir.mkdir(parents=True, exist_ok=True)
    parsed_dir.mkdir(parents=True, exist_ok=True)
    for module in runner_modules:
        original_values.append((
            module,
            module.OUTPUTS_RAW if hasattr(module, "OUTPUTS_RAW") else None,
            module.OUTPUTS_PARSED,
            module.ENABLE_SELF_CONSISTENCY,
            module.ENABLE_MULTI_AGENT_DEBATE,
            module.ENABLE_MULTI_MODEL,
        ))
        if hasattr(module, "OUTPUTS_RAW"):
            module.OUTPUTS_RAW = raw_dir
        module.OUTPUTS_PARSED = parsed_dir
        module.ENABLE_SELF_CONSISTENCY = options.get("enable_self_consistency", False)
        module.ENABLE_MULTI_AGENT_DEBATE = options.get("enable_multi_agent_debate", False)
        module.ENABLE_MULTI_MODEL = options.get("enable_multi_model", False)
    for module in parser_modules:
        module.ENABLE_REASONING_CHAIN = options.get("enable_reasoning_chain", True)
    try:
        yield
    finally:
        for module, raw_output, parsed_output, self_consistency, debate, multi_model in original_values:
            if raw_output is not None:
                module.OUTPUTS_RAW = raw_output
            module.OUTPUTS_PARSED = parsed_output
            module.ENABLE_SELF_CONSISTENCY = self_consistency
            module.ENABLE_MULTI_AGENT_DEBATE = debate
            module.ENABLE_MULTI_MODEL = multi_model
        for module, reasoning_chain in original_reasoning:
            module.ENABLE_REASONING_CHAIN = reasoning_chain


def run_forecast_job(storage: WorkbenchStorage, job_id: str) -> None:
    """Run a job under a process lock because existing runners use module-level paths."""
    with _RUN_LOCK:
        job = storage.get_job(job_id)
        if not job:
            return
        try:
            job["status"] = "running"
            _set_step(job, "topic_normalization", "running")
            storage.save_job(job_id, job)
            if job.get("project_id"):
                from src.library import LibraryRepository
                LibraryRepository().update_forecast_job_status(job_id, "running")
            if job.get("topic_snapshot"):
                topics = [
                    topic for topic in job["topic_snapshot"]
                    if topic.get("topic_id") in job["topic_ids"] and topic.get("selected", True)
                ]
            else:
                topics_by_id = {topic["topic_id"]: topic for topic in storage.list_topics()}
                topics = [
                    topics_by_id[topic_id] for topic_id in job["topic_ids"]
                    if topic_id in topics_by_id and topics_by_id[topic_id].get("selected")
                ]
            if not topics:
                raise ValueError("没有可用于预测的已选技术主题")
            inputs = [normalize_topic(topic) for topic in topics]
            storage.save_job_artifact(job_id, "round1_inputs.json", inputs)
            _set_step(job, "topic_normalization", "done")

            options = job["options"]
            with _job_runner_configuration(storage.job_dir(job_id), options):
                _set_step(job, "round1", "running")
                storage.save_job(job_id, job)
                round1_results = run_round1(inputs, force_rerun=options.get("force_rerun", False))
                if not round1_results:
                    raise ValueError("Round 1 未产生任何有效主题结果，任务已停止")
                _set_step(job, "round1", "done", f"完成 {len(round1_results)}/{len(inputs)} 个主题")

                _set_step(job, "round2", "running")
                storage.save_job(job_id, job)
                round2_result = run_round2(round1_results, force_rerun=options.get("force_rerun", False))
                _set_step(job, "round2", "done")

                _set_step(job, "round3", "running")
                storage.save_job(job_id, job)
                round3_result = run_round3(round1_results, round2_result, force_rerun=options.get("force_rerun", False))
                _set_step(job, "round3", "done")

                roadmaps: List[Dict[str, Any]] = []
                if options.get("enable_per_topic_roadmap", True):
                    _set_step(job, "per_topic_roadmap", "running")
                    storage.save_job(job_id, job)
                    roadmaps = run_all_topics_roadmap(round1_results, force_rerun=options.get("force_rerun", False))
                    _set_step(job, "per_topic_roadmap", "done")
                else:
                    _set_step(job, "per_topic_roadmap", "skipped")

            _set_step(job, "report", "running")
            result = _build_result(
                job_id, topics, round1_results, round2_result, round3_result, roadmaps, job
            )
            fallback_topics = [
                roadmap.get("topic_name", "") for roadmap in roadmaps
                if roadmap.get("is_fallback")
            ]
            result["stage_quality"] = {
                "round1": "complete" if len(round1_results) == len(inputs) else "partial",
                "round2": "complete" if round2_result else "missing",
                "round3": "complete" if round3_result else "missing",
                "roadmaps": "fallback" if fallback_topics else (
                    "complete" if len(roadmaps) == len(round1_results) else "partial"
                ),
                "fallback_topics": fallback_topics,
            }
            charts = _build_charts(result)
            markdown = _build_markdown(result)
            topic_ids_by_name = {
                topic.get("topic_name", ""): topic.get("topic_id", "")
                for topic in topics
            }
            asset_index = generate_job_assets(
                job_id, storage.job_dir(job_id), roadmaps, topic_ids_by_name
            )
            result["asset_summary"] = {
                "count": len(asset_index["assets"]),
                "failed_count": len(asset_index["failed_assets"]),
                "status": "partial" if asset_index["failed_assets"] else "ready",
            }
            result["stage_quality"]["assets"] = (
                "failed" if asset_index["failed_assets"] and not asset_index["assets"]
                else "partial" if asset_index["failed_assets"] else "complete"
            )
            storage.save_job_artifact(job_id, "result.json", result)
            storage.save_job_artifact(job_id, "charts.json", charts)
            storage.save_job_artifact(job_id, "assets.json", asset_index)
            (storage.job_dir(job_id) / "report.md").write_text(markdown, encoding="utf-8")
            _set_step(job, "report", "done")

            failed = (
                len(round1_results) < len(inputs)
                or not round2_result
                or not round3_result
                or len(roadmaps) < len(round1_results)
                or bool(fallback_topics)
            )
            job["status"] = "partial_failed" if failed else "completed"
            job["current_stage"] = "completed"
            storage.save_job(job_id, job)
            if job.get("project_id"):
                from src.library import LibraryRepository
                repository = LibraryRepository()
                repository.update_forecast_job_status(job_id, job["status"])
                repository.update_project_status(
                    job["project_id"], "completed" if not failed else "partial_failed"
                )
        except Exception as exc:
            job["status"] = "failed"
            job["error"] = str(exc)
            _set_step(job, job.get("current_stage", "topic_normalization"), "failed", str(exc))
            storage.save_job(job_id, job)
            if job.get("project_id"):
                from src.library import LibraryRepository
                repository = LibraryRepository()
                repository.update_forecast_job_status(job_id, "failed")
                repository.update_project_status(job["project_id"], "failed")
