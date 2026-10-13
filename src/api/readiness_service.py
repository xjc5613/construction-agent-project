# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from src.library import DatasetEligibilityResolver, LibraryRepository
from src.library.constants import HISTORICAL_PERIODS, PERIOD_LABELS


class ReadinessService:
    CONTRACT_VERSION = 3

    def __init__(self, repository: Optional[LibraryRepository] = None):
        self.repository = repository or LibraryRepository()

    @staticmethod
    def _requirement(
        identifier: str, label: str, actual: Any, required: Any, passed: bool,
        weight: int, remediation: str, *, overrideable: bool = True,
    ) -> Dict[str, Any]:
        return {
            "id": identifier, "label": label, "actual": actual,
            "required": required, "passed": passed, "blocking": True,
            "overrideable": overrideable, "weight": weight,
            "remediation": "" if passed else remediation,
        }

    def evaluate_evidence_items(
        self, project: Dict[str, Any], topic: Dict[str, Any],
        items: Iterable[Dict[str, Any]],
    ) -> Dict[str, Any]:
        active = [item for item in items if not item.get("excluded")]
        ipc = [item for item in active if item.get("evidence_type") == "ipc_metric"]
        papers = [item for item in active if item.get("evidence_type") == "paper"]
        years = {
            item.get("metadata", {}).get("year")
            for item in ipc if item.get("metadata", {}).get("year") is not None
        }
        paper_ids = {item.get("source_id") for item in papers if item.get("source_id")}
        fragments = sum(bool(str(item.get("content") or "").strip()) for item in papers)
        technology_ids = [
            item["technology_node_id"] for item in topic.get("technologies", [])
            if item.get("technology_node_id")
        ]
        scope = (
            DatasetEligibilityResolver(self.repository).resolve(
                project, technology_ids
            )
            if technology_ids else {
                "eligible_dataset_ids": [], "eligible_datasets": [],
                "scope_checksum": "",
            }
        )
        covered_periods = {
            dataset.get("period_code")
            for dataset in scope["eligible_datasets"]
        }
        required_periods = set(HISTORICAL_PERIODS)
        periods_passed = bool(project.get("legacy_mode")) or required_periods <= covered_periods
        requirements = [
            self._requirement(
                "ipc_record_count", "IPC时间序列", len(ipc), 1, len(ipc) >= 1, 15,
                "导入并发布相关 IPC 指标，或调整主题 IPC 关键词",
            ),
            self._requirement(
                "ipc_year_count", "IPC年份覆盖", len(years), 3, len(years) >= 3, 20,
                "补充至少覆盖3个年份的 IPC 数据",
            ),
            self._requirement(
                "paper_count", "相关论文", len(paper_ids), 2, len(paper_ids) >= 2, 20,
                "补充论文数据或调整检索范围",
            ),
            self._requirement(
                "paper_fragment_count", "论文证据片段", fragments, 3,
                fragments >= 3, 20, "补充至少3个非空论文证据片段",
            ),
            self._requirement(
                "historical_periods", "历史阶段覆盖",
                sorted(covered_periods), sorted(required_periods), periods_passed, 25,
                "补充历史阶段：" + "、".join(
                    PERIOD_LABELS[item] for item in sorted(required_periods - covered_periods)
                ),
            ),
        ]
        score = sum(item["weight"] for item in requirements if item["passed"])
        sufficient = all(item["passed"] for item in requirements)
        missing = [item["label"] for item in requirements if not item["passed"]]
        return {
            "contract_version": self.CONTRACT_VERSION,
            "score": score, "sufficient": sufficient,
            "state": "ready" if sufficient else "override_required",
            "requirements": requirements, "missing": missing,
            "missing_periods": sorted(required_periods - covered_periods)
            if not project.get("legacy_mode") else [],
            "ipc_record_count": len(ipc), "year_count": len(years),
            "paper_count": len(paper_ids), "paper_fragment_count": fragments,
            "data_cutoff": max(years) if years else None,
            "eligible_dataset_ids": scope["eligible_dataset_ids"],
            "scope_checksum": scope["scope_checksum"],
        }

    def topic_readiness(
        self, project_id: str, topic_id: str,
        package: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        project = self.repository.get_project(project_id)
        topic = self.repository.get_topic(topic_id)
        if not project or not topic or topic.get("project_id") != project_id:
            raise ValueError("项目主题不存在")
        structural = []
        if topic.get("status") not in {"confirmed", "evidence_ready"} or topic.get("requires_review"):
            structural.append("主题尚未确认")
        technologies = topic.get("technologies", [])
        if not technologies or sum(bool(item.get("is_primary")) for item in technologies) != 1:
            structural.append("主题缺少唯一主技术")
        if technologies:
            try:
                eligibility = DatasetEligibilityResolver(
                    self.repository
                ).resolve_for_topic(project_id, topic)
            except ValueError as exc:
                structural.append(str(exc))
                eligibility = {
                    "eligible_dataset_ids": [], "coverage": {
                        "missing_periods": list(HISTORICAL_PERIODS),
                        "complete": False,
                    }, "scope_checksum": "",
                }
        else:
            eligibility = {
                "eligible_dataset_ids": [], "coverage": {
                    "missing_periods": list(HISTORICAL_PERIODS),
                    "complete": False,
                }, "scope_checksum": "",
            }
        package = package or self.repository.latest_package_for_topic(topic_id)
        if not package:
            structural.append("尚未检索证据")
            quality = {
                "contract_version": self.CONTRACT_VERSION, "score": 0,
                "sufficient": False, "state": "blocked", "requirements": [],
                "missing": ["尚未检索证据"], "missing_periods": [],
                "ipc_record_count": 0, "year_count": 0, "paper_count": 0,
                "paper_fragment_count": 0, "data_cutoff": None,
            }
        else:
            quality = self.evaluate_evidence_items(project, topic, package["items"])
        return {
            "topic_id": topic_id, "topic_name": topic.get("topic_name", topic_id),
            "package_id": package.get("package_id") if package else None,
            "structural_blockers": structural, "quality": quality,
            "can_start": not structural and quality["sufficient"],
            "can_override": not structural and not quality["sufficient"],
            "eligibility": {
                "eligible_dataset_ids": eligibility["eligible_dataset_ids"],
                "eligible_dataset_count": len(eligibility["eligible_dataset_ids"]),
                "coverage": eligibility["coverage"],
                "scope_checksum": eligibility["scope_checksum"],
            },
        }

    def project_readiness(
        self, project_id: str, topic_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        project = self.repository.get_project(project_id)
        if not project:
            raise ValueError("预测项目不存在")
        all_topics = self.repository.list_topics(project_id)
        selected = [
            topic for topic in all_topics
            if (not topic_ids or topic["topic_id"] in topic_ids) and topic.get("selected", True)
        ]
        topic_results = [
            self.topic_readiness(project_id, topic["topic_id"]) for topic in selected
        ]
        structural = [
            f"{item['topic_name']}: {reason}"
            for item in topic_results for reason in item["structural_blockers"]
        ]
        if project.get("lifecycle_status") == "archived":
            structural.append("归档项目不能创建新的预测任务")
        if not selected:
            structural.append("没有已选择的技术主题")
        override_reasons = [
            f"{item['topic_name']}: {requirement['label']}"
            for item in topic_results
            for requirement in item["quality"].get("requirements", [])
            if not requirement["passed"]
        ]
        active_job = self.repository.get_active_forecast_job(project_id)
        if active_job:
            structural.append(f"项目已有活动任务 {active_job['job_id']}")

        materials = self.repository.list_materials(project_id)
        confirmed = [
            topic for topic in all_topics
            if topic.get("status") in {"confirmed", "evidence_ready"}
            and not topic.get("requires_review")
        ]
        all_evidence_ready = bool(confirmed) and all(
            self.topic_readiness(project_id, topic["topic_id"])["quality"]["sufficient"]
            for topic in confirmed
        )
        terminal_jobs = [
            job for job in self.repository.list_forecast_jobs(project_id)
            if job["status"] in {"completed", "partial_failed"}
        ]
        all_jobs = self.repository.list_forecast_jobs(project_id)
        progress_checks = [
            (10, bool(project.get("technology_node_id")) or bool(project.get("legacy_mode"))),
            (20, bool(materials)), (20, bool(confirmed)),
            (30, all_evidence_ready), (20, bool(active_job or terminal_jobs)),
        ]
        progress = sum(weight for weight, passed in progress_checks if passed)
        current_stage = (
            "completed" if terminal_jobs else "forecasting" if active_job
            else "ready_to_forecast" if all_evidence_ready
            else "evidence_review" if confirmed else "topics_review" if materials
            else "material_ready" if project.get("technology_node_id") else "draft"
        )
        can_override = bool(topic_results) and not structural and bool(override_reasons)
        can_start = bool(topic_results) and not structural and not override_reasons
        archived = project.get("lifecycle_status") == "archived"
        has_package = any(item.get("package_id") for item in topic_results)
        steps = [
            self._step(
                "overview", "项目概览", "available",
                f"/projects/{project_id}/overview",
            ),
            self._step(
                "materials", "研究材料",
                "completed" if materials else "available",
                f"/projects/{project_id}/materials",
                ["归档项目为只读"] if archived else [],
            ),
            self._step(
                "topics-evidence", "主题与证据",
                "completed" if has_package and confirmed else (
                    "available" if materials else "blocked"
                ),
                f"/projects/{project_id}/topics-evidence",
                [] if materials else ["请先添加研究材料"],
            ),
            self._step(
                "forecast", "预测运行",
                "completed" if terminal_jobs else (
                    "available" if can_start or can_override or active_job else "blocked"
                ),
                f"/projects/{project_id}/forecast",
                [] if can_start or can_override or active_job else (
                    structural + override_reasons
                ),
            ),
            self._step(
                "results", "结果与历史",
                "available" if all_jobs else "hidden",
                f"/projects/{project_id}/results",
                [] if all_jobs else ["尚无预测任务"],
                visible=bool(all_jobs),
            ),
        ]
        if archived:
            for step in steps:
                if step["id"] not in {"overview", "results"}:
                    step["state"] = "blocked"
                    step["blocking_reasons"] = ["归档项目仅支持查看历史结果"]
        if active_job or all_jobs:
            recommended = {
                "step_id": "results", "label": "查看预测进度与结果",
                "route": f"/projects/{project_id}/results",
            }
        elif not materials:
            recommended = {
                "step_id": "materials", "label": "添加研究材料",
                "route": f"/projects/{project_id}/materials",
            }
        elif not confirmed or not has_package:
            recommended = {
                "step_id": "topics-evidence", "label": "校准主题与检索证据",
                "route": f"/projects/{project_id}/topics-evidence",
            }
        else:
            recommended = {
                "step_id": "forecast", "label": "配置并启动预测",
                "route": f"/projects/{project_id}/forecast",
            }
        coverage = (
            self.repository.dataset_coverage(project["technology_node_id"])
            if project.get("technology_node_id") else {
                "complete": False, "missing": ["历史项目未绑定技术目录"],
                "periods": {},
            }
        )
        contract_version = int(project.get("research_contract_version") or 2)
        if contract_version == 3:
            with self.repository.db.connect() as connection:
                design_confirmed = bool(connection.execute(
                    """SELECT 1 FROM research_designs WHERE project_id=? AND status='confirmed'
                       ORDER BY version DESC LIMIT 1""", (project_id,)
                ).fetchone())
                network_completed = bool(connection.execute(
                    "SELECT 1 FROM network_runs WHERE project_id=? AND status='completed' LIMIT 1",
                    (project_id,),
                ).fetchone())
                model_completed = bool(connection.execute(
                    """SELECT 1 FROM model_runs m JOIN feature_runs f ON f.feature_run_id=m.feature_run_id
                       JOIN network_runs n ON n.network_run_id=f.network_run_id
                       WHERE n.project_id=? AND m.status='completed' LIMIT 1""", (project_id,)
                ).fetchone())
                export_completed = bool(connection.execute(
                    "SELECT 1 FROM export_manifests WHERE project_id=? AND status='completed' LIMIT 1",
                    (project_id,),
                ).fetchone())
                graph_row = connection.execute(
                    """SELECT g.status,g.current_node,g.thread_id,g.job_id FROM graph_threads g
                       JOIN forecast_jobs j ON j.job_id=g.job_id WHERE j.project_id=?
                       ORDER BY g.updated_at DESC LIMIT 1""", (project_id,)
                ).fetchone()
            data_ready = bool(coverage.get("complete") or any(
                values.get("patent_records") or values.get("reduced_edge_records")
                for values in coverage.get("periods", {}).values()
            ))
            themes_ready = bool(confirmed)
            checks = [design_confirmed, data_ready, network_completed,
                      model_completed, themes_ready, export_completed]
            definitions = [
                ("research-design", "研究设计", "/research-design", [], "确认研究问题与方法参数"),
                ("data-quality", "数据质量", "/data-quality", ["请先确认研究设计"], "检查覆盖度、映射与论文类型"),
                ("network-evolution", "网络演化", "/network-evolution", ["数据质量尚未达到建网条件"], "构建年度及三时期 IPC 网络"),
                ("fusion-forecast", "融合预测", "/fusion-forecast", ["请先完成网络构建与历史验证"], "训练、校准并审核融合候选"),
                ("technology-themes", "技术主题", "/technology-themes", ["请先审核融合候选"], "综合专利与论文证据形成技术主题"),
                ("roadmap-report", "路线图与报告", "/roadmap-report", ["请先确认技术主题与发布门"], "生成路线图、图件与研究包"),
            ]
            v3_steps = []
            for index, (identifier, label, route, blockers, remediation) in enumerate(definitions):
                passed = checks[index]
                prerequisite = all(checks[:index])
                state = "completed" if passed else "available" if prerequisite else "blocked"
                v3_steps.append({
                    "id": identifier, "label": label, "state": state,
                    "route": f"/projects/{project_id}{route}", "visible": True,
                    "blocking_reasons": [] if prerequisite else blockers,
                    "remediation": "" if passed else remediation,
                })
            next_index = next((i for i, passed in enumerate(checks) if not passed), 5)
            next_step = v3_steps[next_index]
            steps = v3_steps
            recommended = {"step_id": next_step["id"], "label": next_step["remediation"],
                           "route": next_step["route"]}
            progress = round(sum(checks) / len(checks) * 100)
            current_stage = next_step["id"] if not all(checks) else "completed"
        return {
            "contract_version": self.CONTRACT_VERSION if contract_version == 3 else 2,
            "research_contract_version": contract_version, "project_id": project_id,
            "progress_percent": progress, "current_stage": current_stage,
            "topics": topic_results,
            "steps": steps,
            "recommended_action": recommended,
            "coverage": coverage,
            "lifecycle_status": project.get("lifecycle_status", "active"),
            "graph_checkpoint": dict(graph_row) if contract_version == 3 and graph_row else None,
            "evidence": {
                "score": round(sum(item["quality"]["score"] for item in topic_results) / len(topic_results))
                if topic_results else 0,
                "sufficient": bool(topic_results) and not override_reasons,
                "state": "ready" if topic_results and not override_reasons else (
                    "blocked" if structural else "override_required"
                ),
            },
            "forecast": {
                "can_start": can_start, "can_override": can_override,
                "blocking_reasons": structural,
                "override_reasons": override_reasons,
                "active_job_id": active_job["job_id"] if active_job else None,
            },
        }

    @staticmethod
    def _step(
        identifier: str, label: str, state: str, route: str,
        blocking_reasons: Optional[List[str]] = None, *, visible: bool = True,
    ) -> Dict[str, Any]:
        reasons = list(dict.fromkeys(blocking_reasons or []))
        return {
            "id": identifier,
            "label": label,
            "state": state,
            "visible": visible,
            "route": route,
            "blocking_reasons": reasons,
            "remediation": reasons,
        }
