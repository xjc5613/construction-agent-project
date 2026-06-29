# -*- coding:utf-8 -*-
import os
from datetime import datetime
from typing import List, Dict, Tuple
from pathlib import Path
from config.settings import OUTPUTS_REPORT, PER_TOPIC_ROADMAP_STAGES
from src.utils.file_io import write_text
from src.utils.logger import get_logger
from src.report.roadmap_charts import generate_all_charts, generate_all_topics_comparison

logger = get_logger(__name__)


def _get_uncertainty_cn(level: str) -> str:
    mapping = {"low": "低", "medium": "中", "high": "高"}
    return mapping.get(level, level)


def _get_trl_description(level: int) -> str:
    trl_defs = {
        1: "基础原理研究",
        2: "技术概念形成",
        3: "实验室原理验证",
        4: "组件级实验室验证",
        5: "相关环境验证",
        6: "原型系统演示验证",
        7: "实际环境系统演示",
        8: "实际运行与验证",
        9: "完全成熟与规模化应用"
    }
    return trl_defs.get(level, "未定义")


def _build_stage_tables(roadmap_data: Dict) -> str:
    lines = []
    roadmap = roadmap_data.get("roadmap", {})

    for year in PER_TOPIC_ROADMAP_STAGES:
        stage = roadmap.get(year, {})
        stage_desc = stage.get("stage_description", "")
        milestones = stage.get("milestones", [])

        if not milestones:
            continue

        lines.append(f"### {year}年\n")

        if stage_desc:
            lines.append(f"> **阶段定位**：{stage_desc}\n")

        lines.append("| 序号 | 里程碑 | 详细描述 | 关键技术 | TRL | 不确定性 | 前置依赖 |")
        lines.append("|------|--------|----------|----------|-----|----------|----------|")

        for idx, ms in enumerate(milestones, 1):
            name = ms.get("name", "-")
            description = ms.get("description", "-")
            key_techs = ms.get("key_technologies", [])
            key_techs_str = "、".join(key_techs) if isinstance(key_techs, list) else "-"
            trl = ms.get("trl_level")
            trl_str = f"{trl} ({_get_trl_description(trl)[:6]}…)" if trl is not None else "-"
            uncertainty = ms.get("uncertainty_level", "medium")
            unc_str = _get_uncertainty_cn(uncertainty)
            deps = ms.get("dependencies", [])
            deps_str = "、".join(deps) if isinstance(deps, list) and deps else "无"

            lines.append(f"| {idx} | **{name}** | {description} | {key_techs_str} | {trl_str} | {unc_str} | {deps_str} |")

        lines.append("")

    return "\n".join(lines)


def _build_metrics_summary(roadmap_data: Dict) -> str:
    lines = []
    roadmap = roadmap_data.get("roadmap", {})

    total_milestones = 0
    all_trls = []
    all_techs = set()
    uncertainty_counts = {"low": 0, "medium": 0, "high": 0}
    stage_details = {}

    for year in PER_TOPIC_ROADMAP_STAGES:
        stage = roadmap.get(year, {})
        milestones = stage.get("milestones", [])
        count = len(milestones)
        total_milestones += count
        stage_details[year] = count

        for ms in milestones:
            trl = ms.get("trl_level")
            if trl is not None:
                all_trls.append(trl)
            for t in ms.get("key_technologies", []):
                all_techs.add(t)
            unc = ms.get("uncertainty_level", "medium")
            uncertainty_counts[unc] = uncertainty_counts.get(unc, 0) + 1

    lines.append("### 核心指标总览\n")
    lines.append("| 指标 | 数值 | 说明 |")
    lines.append("|------|------|------|")
    lines.append(f"| 里程碑总数 | {total_milestones}个 | 覆盖4个时间阶段 |")
    lines.append(f"| 关键技术数 | {len(all_techs)}项 | 去重后统计 |")
    if all_trls:
        lines.append(f"| TRL跨度 | TRL {min(all_trls)} → TRL {max(all_trls)} | 从基础到成熟的发展路径 |")
        lines.append(f"| 平均TRL | {sum(all_trls)/len(all_trls):.1f} | 全阶段平均技术就绪水平 |")
    total_unc = sum(uncertainty_counts.values()) or 1
    lines.append(f"| 低不确定性占比 | {uncertainty_counts['low']/total_unc*100:.0f}% | 高置信度里程碑比例 |")
    lines.append("")

    lines.append("### 各阶段分布\n")
    lines.append("| 阶段 | 里程碑数 | 占比 | 主要特征 |")
    lines.append("|------|----------|------|----------|")
    stage_features = {
        "2025": "技术基础建立与现状梳理",
        "2030": "关键技术突破与原型验证",
        "2035": "系统集成与规模化应用",
        "2040": "成熟完善与范式革新"
    }
    for year in PER_TOPIC_ROADMAP_STAGES:
        count = stage_details.get(year, 0)
        pct = count / total_milestones * 100 if total_milestones > 0 else 0
        lines.append(f"| {year}年 | {count}个 | {pct:.0f}% | {stage_features.get(year, '')} |")
    lines.append("")

    return "\n".join(lines)


def generate_single_topic_report(roadmap_data: Dict, chart_paths: Dict[str, str] = None) -> str:
    topic_name = roadmap_data.get("topic_name", "未知主题")
    roadmap = roadmap_data.get("roadmap", {})
    chart_paths = chart_paths or {}

    lines = []

    lines.append(f"# {topic_name} - 技术发展路线图\n")

    confidence = roadmap_data.get("confidence")
    if confidence is not None:
        lines.append(f"> **预测置信度**：{confidence:.1f} / 100\n")

    lines.append("## 一、可视化图表\n")

    lines.append("### 1.1 时间轴路线图\n")
    if chart_paths.get("timeline"):
        rel_path = os.path.relpath(chart_paths["timeline"], OUTPUTS_REPORT)
        lines.append(f"![时间轴路线图]({rel_path})\n")
    lines.append("> 气泡大小表示TRL等级（技术成熟度），颜色标记不确定性等级。\n")

    lines.append("### 1.2 TRL发展趋势\n")
    if chart_paths.get("trl_curve"):
        rel_path = os.path.relpath(chart_paths["trl_curve"], OUTPUTS_REPORT)
        lines.append(f"![TRL发展曲线]({rel_path})\n")
    lines.append("> 展示各阶段技术就绪水平的变化趋势与分布范围。\n")

    lines.append("### 1.3 技术依赖关系图\n")
    if chart_paths.get("dependency"):
        rel_path = os.path.relpath(chart_paths["dependency"], OUTPUTS_REPORT)
        lines.append(f"![技术依赖关系图]({rel_path})\n")
    lines.append("> 箭头表示技术依赖方向，节点大小与TRL成正比。\n")

    lines.append("### 1.4 综合能力雷达图\n")
    if chart_paths.get("radar"):
        rel_path = os.path.relpath(chart_paths["radar"], OUTPUTS_REPORT)
        lines.append(f"![综合能力雷达图]({rel_path})\n")
    lines.append("> 六维评估：技术成熟度、里程碑密度、技术多样性、确定性、应用广度、创新程度。\n")

    lines.append("## 二、核心指标\n")
    metrics = _build_metrics_summary(roadmap_data)
    lines.append(metrics)

    lines.append("## 三、分阶段详细里程碑\n")
    tables = _build_stage_tables(roadmap_data)
    lines.append(tables)

    return "\n".join(lines)


def generate_all_topics_report(all_roadmaps: List[Dict],
                                all_chart_paths: Dict[str, Dict[str, str]] = None,
                                comparison_chart: str = None) -> str:
    all_chart_paths = all_chart_paths or {}
    lines = []

    lines.append("# 智能建造2040 - 分主题技术路线图总报告\n")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    total_topics = len(all_roadmaps)
    total_milestones = 0
    all_techs = set()
    stage_totals = {year: 0 for year in PER_TOPIC_ROADMAP_STAGES}

    for roadmap in all_roadmaps:
        roadmap_data = roadmap.get("roadmap", {})
        for year in PER_TOPIC_ROADMAP_STAGES:
            stage = roadmap_data.get(year, {})
            milestones = stage.get("milestones", [])
            count = len(milestones)
            stage_totals[year] += count
            total_milestones += count
            for ms in milestones:
                for t in ms.get("key_technologies", []):
                    all_techs.add(t)

    lines.append("## 执行摘要\n")
    lines.append(f"- **分析主题数**：{total_topics} 个技术领域\n")
    lines.append(f"- **里程碑总数**：{total_milestones} 项\n")
    lines.append(f"- **关键技术数**：{len(all_techs)} 项（去重）\n")
    lines.append(f"- **时间跨度**：2025年 → 2040年（15年）\n")
    lines.append("")

    lines.append("## 综合对比分析\n")
    if comparison_chart:
        rel_path = os.path.relpath(comparison_chart, OUTPUTS_REPORT)
        lines.append(f"![综合对比图]({rel_path})\n")
    lines.append("> 四维度对比：TRL发展、里程碑分布、技术多样性、不确定性构成。\n")

    lines.append("### 各阶段里程碑分布\n")
    lines.append("| 阶段 | 里程碑数 | 占比 | 典型特征 |")
    lines.append("|------|----------|------|----------|")
    features = {
        "2025": "现状基础与技术积累",
        "2030": "关键技术突破期",
        "2035": "系统集成与规模化",
        "2040": "成熟应用与范式转变"
    }
    for year in PER_TOPIC_ROADMAP_STAGES:
        count = stage_totals[year]
        pct = count / total_milestones * 100 if total_milestones > 0 else 0
        lines.append(f"| {year}年 | {count} | {pct:.1f}% | {features.get(year, '')} |")
    lines.append("")

    lines.append("## 主题索引\n")
    for i, roadmap in enumerate(all_roadmaps, 1):
        topic_name = roadmap.get("topic_name", "未知主题")
        anchor = topic_name.replace(" ", "-")
        roadmap_data = roadmap.get("roadmap", {})
        ms_count = sum(len(roadmap_data.get(y, {}).get("milestones", [])) for y in PER_TOPIC_ROADMAP_STAGES)
        lines.append(f"{i}. [{topic_name}](#{anchor}) — {ms_count}个里程碑\n")
    lines.append("")

    lines.append("---\n")

    for idx, roadmap in enumerate(all_roadmaps):
        topic_name = roadmap.get("topic_name", "未知主题")
        chart_dict = all_chart_paths.get(topic_name, {})
        topic_report = generate_single_topic_report(roadmap, chart_dict)
        lines.append(topic_report)
        lines.append("\n---\n")

    return "\n".join(lines)


def _safe_filename(name: str) -> str:
    if not name:
        return "unnamed"
    result = name
    for ch in '/\\:*?"<>| ':
        result = result.replace(ch, "_")
    result = result.strip("_")
    if not result:
        return "unnamed"
    return result


def save_per_topic_reports(all_roadmaps: List[Dict]) -> Tuple[str, List[str]]:
    per_topic_dir = OUTPUTS_REPORT / "per_topic_roadmaps"
    chart_dir = per_topic_dir / "charts"
    per_topic_dir.mkdir(parents=True, exist_ok=True)
    chart_dir.mkdir(parents=True, exist_ok=True)

    single_paths = []
    all_chart_paths = {}

    logger.info(f"开始生成路线图图表，共 {len(all_roadmaps)} 个主题")

    for roadmap in all_roadmaps:
        topic_name = roadmap.get("topic_name", "未知主题")
        safe_name = _safe_filename(topic_name)

        chart_paths = generate_all_charts(roadmap, str(per_topic_dir))
        all_chart_paths[topic_name] = chart_paths

        report_content = generate_single_topic_report(roadmap, chart_paths)
        file_path = per_topic_dir / f"{safe_name}_路线图.md"
        write_text(report_content, file_path)
        single_paths.append(str(file_path))
        logger.info(f"单主题报告已生成: {file_path}")

    comparison_path = str(chart_dir / "00_综合对比图.png")
    try:
        generate_all_topics_comparison(all_roadmaps, comparison_path)
    except Exception as e:
        logger.warning(f"生成综合对比图失败: {e}")
        comparison_path = None

    all_report_content = generate_all_topics_report(all_roadmaps, all_chart_paths, comparison_path)
    all_report_path = OUTPUTS_REPORT / "per_topic_roadmaps_all.md"
    write_text(all_report_content, all_report_path)
    logger.info(f"整合报告已生成: {all_report_path}")

    return str(all_report_path), single_paths
