# -*- coding:utf-8 -*-
import json
import os
from datetime import datetime
from typing import List, Dict, Tuple, Any
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


def _collect_topic_metrics(roadmap_data: Dict) -> Dict[str, Any]:
    roadmap = roadmap_data.get("roadmap", {})
    stage_counts = {}
    stage_avg_trl = {}
    stage_tech_counts = {}
    all_trls = []
    all_techs = []
    uncertainty_counts = {"low": 0, "medium": 0, "high": 0}

    for year in PER_TOPIC_ROADMAP_STAGES:
        milestones = roadmap.get(year, {}).get("milestones", [])
        stage_counts[year] = len(milestones)
        trls = [ms.get("trl_level") for ms in milestones if isinstance(ms.get("trl_level"), (int, float))]
        stage_avg_trl[year] = sum(trls) / len(trls) if trls else 0
        techs = []
        for ms in milestones:
            techs.extend(ms.get("key_technologies", []) or [])
            unc = ms.get("uncertainty_level", "medium")
            uncertainty_counts[unc] = uncertainty_counts.get(unc, 0) + 1
        stage_tech_counts[year] = len(set(techs))
        all_trls.extend(trls)
        all_techs.extend(techs)

    tech_freq = {}
    for tech in all_techs:
        tech_freq[tech] = tech_freq.get(tech, 0) + 1

    total_milestones = sum(stage_counts.values())
    total_unc = sum(uncertainty_counts.values()) or 1
    uncertainty_pct = {
        level: uncertainty_counts.get(level, 0) / total_unc * 100
        for level in ["low", "medium", "high"]
    }

    return {
        "total_milestones": total_milestones,
        "tech_count": len(set(all_techs)),
        "stage_counts": stage_counts,
        "stage_avg_trl": stage_avg_trl,
        "stage_tech_counts": stage_tech_counts,
        "trl_min": min(all_trls) if all_trls else 0,
        "trl_max": max(all_trls) if all_trls else 0,
        "trl_avg": sum(all_trls) / len(all_trls) if all_trls else 0,
        "uncertainty_counts": uncertainty_counts,
        "uncertainty_pct": uncertainty_pct,
        "top_techs": sorted(tech_freq.items(), key=lambda item: (-item[1], item[0]))[:8],
    }


def _load_backtest_results() -> List[Dict]:
    results = []
    for path in sorted(OUTPUTS_REPORT.glob("backtest_results_*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                results.append(json.load(f))
        except Exception as e:
            logger.warning(f"读取回测结果失败: {path}, 错误: {e}")
    return results


def _topic_backtest_rows(topic_name: str, backtest_results: List[Dict]) -> List[Dict]:
    rows = []
    for result in backtest_results or []:
        metrics = result.get("metrics", {})
        for detail in result.get("details", []):
            if detail.get("name") == topic_name:
                rows.append({
                    "historical_year": result.get("historical_year"),
                    "forecast_year": result.get("forecast_year"),
                    "actual_year": result.get("actual_year"),
                    "in_forecast": detail.get("in_forecast"),
                    "in_actual": detail.get("in_actual"),
                    "time_deviation": detail.get("time_deviation"),
                    "direction_correct": detail.get("direction_correct"),
                    "global_precision": metrics.get("precision"),
                    "global_recall": metrics.get("recall"),
                    "global_f1": metrics.get("f1_score"),
                })
    return rows


def _format_pct(value: float) -> str:
    return f"{value:.1f}%"


def generate_topic_analysis_file(roadmap_data: Dict,
                                 chart_paths: Dict[str, str] = None,
                                 backtest_results: List[Dict] = None) -> str:
    topic_name = roadmap_data.get("topic_name", "未知主题")
    chart_paths = chart_paths or {}
    metrics = _collect_topic_metrics(roadmap_data)
    backtest_rows = _topic_backtest_rows(topic_name, backtest_results or [])
    link_base = Path(chart_paths["description"]).parent if chart_paths.get("description") else OUTPUTS_REPORT

    dominant_stage = max(metrics["stage_counts"].items(), key=lambda item: item[1])[0] if metrics["stage_counts"] else "-"
    terminal_stage = PER_TOPIC_ROADMAP_STAGES[-1]
    terminal_trl = metrics["stage_avg_trl"].get(terminal_stage, 0)
    top_techs = "、".join([tech for tech, _ in metrics["top_techs"][:5]]) or "未识别出稳定高频技术项"
    low_pct = metrics["uncertainty_pct"].get("low", 0)
    high_pct = metrics["uncertainty_pct"].get("high", 0)

    lines = []
    lines.append(f"# {topic_name}：图表、指标与评估结果解读\n")
    lines.append("## 摘要\n")
    lines.append(
        f"本文件基于分阶段技术路线图、图表输出和历史回测结果，对“{topic_name}”的技术演化特征进行解释。"
        f"该主题共识别出 {metrics['total_milestones']} 个里程碑和 {metrics['tech_count']} 项去重关键技术，"
        f"TRL 水平由 {metrics['trl_min']:.0f} 提升至 {metrics['trl_max']:.0f}，全阶段平均 TRL 为 {metrics['trl_avg']:.2f}。"
        f"低不确定性里程碑占比为 {_format_pct(low_pct)}，高不确定性里程碑占比为 {_format_pct(high_pct)}。"
    )
    lines.append("")

    lines.append("## 图表解读\n")
    if chart_paths.get("combined"):
        rel_path = os.path.relpath(chart_paths["combined"], link_base)
        lines.append(f"![综合分析图]({rel_path})\n")
    lines.append(
        "综合分析图从 TRL 发展、里程碑阶段分布、内容复杂度和不确定性结构四个维度刻画该主题。"
        f"结果显示，{dominant_stage} 年阶段包含的里程碑数量最多，说明该阶段承担了较集中的技术推进任务。"
        f"从 TRL 轨迹看，平均成熟度呈阶段性上升，至 {terminal_stage} 年达到 {terminal_trl:.2f}，"
        "表明路线图假定该方向将从概念验证和原型验证逐步进入系统化应用阶段。"
    )
    lines.append("")

    if chart_paths.get("timeline"):
        rel_path = os.path.relpath(chart_paths["timeline"], link_base)
        lines.append(f"![时间轴路线图]({rel_path})\n")
    lines.append(
        "时间轴图将单个里程碑映射到技术就绪度坐标上，适合观察阶段内任务的成熟度差异。"
        "若同一阶段内部存在多个 TRL 层级，说明该阶段并非单一线性推进，而是由基础能力、系统集成和应用验证并行构成。"
        "圆点的不确定性标识进一步揭示了需要持续跟踪的风险位置。"
    )
    lines.append("")

    if chart_paths.get("radar"):
        rel_path = os.path.relpath(chart_paths["radar"], link_base)
        lines.append(f"![综合能力雷达图]({rel_path})\n")
    lines.append(
        "综合能力雷达图用于比较各阶段在成熟度、里程碑密度、技术多样性、确定性、应用范围和创新程度上的相对表现。"
        f"该主题的核心技术集包括：{top_techs}。"
        "若后期阶段在技术多样性和创新程度上同步扩张，则意味着路线图不仅预测成熟度提升，也预测技术组合复杂度增加。"
    )
    lines.append("")

    lines.append("## 量化指标\n")
    lines.append("| 指标 | 数值 | 学术化解释 |")
    lines.append("|------|------|------------|")
    lines.append(f"| 里程碑总数 | {metrics['total_milestones']} | 反映路线图的任务颗粒度和阶段分解深度。 |")
    lines.append(f"| 去重关键技术数 | {metrics['tech_count']} | 表征该主题涉及的技术组合宽度。 |")
    lines.append(f"| TRL跨度 | {metrics['trl_min']:.0f}–{metrics['trl_max']:.0f} | 表明技术从早期验证到成熟应用的覆盖范围。 |")
    lines.append(f"| 平均TRL | {metrics['trl_avg']:.2f} | 衡量全周期技术成熟度的整体水平。 |")
    lines.append(f"| 低不确定性占比 | {_format_pct(low_pct)} | 代表较高置信度、路径相对清晰的里程碑比例。 |")
    lines.append(f"| 高不确定性占比 | {_format_pct(high_pct)} | 代表需要验证、政策或工程条件约束较强的里程碑比例。 |")
    lines.append("")

    lines.append("## 分阶段结果\n")
    lines.append("| 阶段 | 里程碑数 | 平均TRL | 技术多样性 | 解释 |")
    lines.append("|------|----------|---------|------------|------|")
    for year in PER_TOPIC_ROADMAP_STAGES:
        count = metrics["stage_counts"].get(year, 0)
        avg_trl = metrics["stage_avg_trl"].get(year, 0)
        tech_count = metrics["stage_tech_counts"].get(year, 0)
        if year == "2025":
            note = "以基础能力建设、工具链集成和初步验证为主。"
        elif year == "2030":
            note = "重点转向关键模块突破和原型系统验证。"
        elif year == "2035":
            note = "强调跨系统集成、工程化验证和规模化试点。"
        else:
            note = "面向成熟应用、范式转变和产业级扩散。"
        lines.append(f"| {year} | {count} | {avg_trl:.2f} | {tech_count} | {note} |")
    lines.append("")

    lines.append("## 回测评估结果\n")
    if backtest_rows:
        lines.append("| 历史基准 | 预测年 | 实际年 | 是否预测命中 | 是否实际出现 | 时间偏差 | 全局Precision | 全局Recall | 全局F1 |")
        lines.append("|----------|--------|--------|--------------|--------------|----------|----------------|------------|--------|")
        for row in backtest_rows:
            lines.append(
                f"| {row['historical_year']} | {row['forecast_year']} | {row['actual_year']} | "
                f"{'是' if row['in_forecast'] else '否'} | {'是' if row['in_actual'] else '否'} | "
                f"{row['time_deviation']} | {row['global_precision']:.4f} | {row['global_recall']:.4f} | {row['global_f1']:.4f} |"
            )
        lines.append("")
        lines.append(
            "从回测角度看，该主题的命中状态应与全局 precision、recall 和 F1-score 联合解释。"
            "单主题命中说明模型能够识别该方向的存在性，但时间偏差反映了技术扩散节奏与预测窗口之间的差异。"
            "因此，本文将其视为方向有效性和时序校准能力的共同证据，而非单一准确率指标。"
        )
    else:
        lines.append("当前未检索到该主题对应的回测条目，因此本节仅保留路线图内部指标解释。")
    lines.append("")

    lines.append("## 结论\n")
    lines.append(
        f"总体而言，“{topic_name}”呈现出由低TRL基础能力向高TRL系统应用推进的演化路径。"
        f"其关键判断依据包括：TRL 均值的阶段性提升、{metrics['tech_count']} 项关键技术构成的组合复杂度、"
        f"以及不确定性结构中低风险里程碑占比 {_format_pct(low_pct)}。"
        "后续研究可进一步结合专利、论文、标准和工程项目数据，对高不确定性里程碑进行外部证据校准。"
    )

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

    lines.append("### 1.1 综合分析图\n")
    if chart_paths.get("combined"):
        rel_path = os.path.relpath(chart_paths["combined"], OUTPUTS_REPORT)
        lines.append(f"![综合分析图]({rel_path})\n")
    lines.append("> 四面板分析：TRL发展趋势、里程碑分布、内容分析、不确定性构成。\n")

    lines.append("### 1.2 时间轴路线图\n")
    if chart_paths.get("timeline"):
        rel_path = os.path.relpath(chart_paths["timeline"], OUTPUTS_REPORT)
        lines.append(f"![时间轴路线图]({rel_path})\n")
    lines.append("> 横向条形图展示各里程碑的TRL发展路径，颜色标记阶段，圆点标记不确定性。\n")

    lines.append("### 1.3 综合能力雷达图\n")
    if chart_paths.get("radar"):
        rel_path = os.path.relpath(chart_paths["radar"], OUTPUTS_REPORT)
        lines.append(f"![综合能力雷达图]({rel_path})\n")
    lines.append("> 六维评估：TRL等级、里程碑密度、技术多样性、确定性、应用广度、创新程度。\n")

    if chart_paths.get("description"):
        rel_path = os.path.relpath(chart_paths["description"], OUTPUTS_REPORT)
        lines.append(f"> 图表与指标的论文式解读见：[{topic_name} 图表指标解读]({rel_path})。\n")

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
    trl_distribution = {}
    uncertainty_distribution = {"low": 0, "medium": 0, "high": 0}
    tech_topic_distribution = {}
    dependency_graph = {}

    for roadmap in all_roadmaps:
        topic_name = roadmap.get("topic_name", "")
        roadmap_data = roadmap.get("roadmap", {})
        
        for year in PER_TOPIC_ROADMAP_STAGES:
            stage = roadmap_data.get(year, {})
            milestones = stage.get("milestones", [])
            count = len(milestones)
            stage_totals[year] += count
            total_milestones += count
            
            for ms in milestones:
                ms_name = ms.get("name", "")
                trl = ms.get("trl_level")
                unc = ms.get("uncertainty_level", "medium")
                techs = ms.get("key_technologies", [])
                deps = ms.get("dependencies", [])
                
                if trl:
                    trl_distribution[trl] = trl_distribution.get(trl, 0) + 1
                uncertainty_distribution[unc] = uncertainty_distribution.get(unc, 0) + 1
                
                for t in techs:
                    all_techs.add(t)
                    if t not in tech_topic_distribution:
                        tech_topic_distribution[t] = set()
                    tech_topic_distribution[t].add(topic_name)
                
                if ms_name not in dependency_graph:
                    dependency_graph[ms_name] = {"deps": deps, "topic": topic_name, "year": year}

    lines.append("## 执行摘要\n")
    lines.append(f"- **分析主题数**：{total_topics} 个技术领域\n")
    lines.append(f"- **里程碑总数**：{total_milestones} 项\n")
    lines.append(f"- **关键技术数**：{len(all_techs)} 项（去重）\n")
    lines.append(f"- **时间跨度**：2025年 → 2040年（15年）\n")
    avg_trl = sum(k * v for k, v in trl_distribution.items()) / sum(trl_distribution.values()) if trl_distribution else 0
    lines.append(f"- **平均TRL等级**：{avg_trl:.1f}\n")
    low_unc_pct = uncertainty_distribution["low"] / sum(uncertainty_distribution.values()) * 100 if uncertainty_distribution else 0
    lines.append(f"- **低不确定性占比**：{low_unc_pct:.1f}%\n")
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

    lines.append("### TRL等级分布\n")
    lines.append("| TRL等级 | 里程碑数 | 占比 | TRL描述 |")
    lines.append("|---------|----------|------|---------|")
    for trl in sorted(trl_distribution.keys()):
        count = trl_distribution[trl]
        pct = count / total_milestones * 100 if total_milestones > 0 else 0
        desc = _get_trl_description(trl)
        lines.append(f"| TRL {trl} | {count} | {pct:.1f}% | {desc} |")
    lines.append("")

    lines.append("### 不确定性分布\n")
    lines.append("| 不确定性 | 里程碑数 | 占比 | 含义 |")
    lines.append("|----------|----------|------|------|")
    unc_meanings = {
        "low": "技术路径清晰，风险可控",
        "medium": "存在一定不确定性，需持续跟踪",
        "high": "技术方向不明，风险较高"
    }
    for level in ["low", "medium", "high"]:
        count = uncertainty_distribution.get(level, 0)
        pct = count / total_milestones * 100 if total_milestones > 0 else 0
        lines.append(f"| {_get_uncertainty_cn(level)} | {count} | {pct:.1f}% | {unc_meanings.get(level, '')} |")
    lines.append("")

    lines.append("### 技术跨主题分布（高频技术）\n")
    shared_techs = [(t, len(topics)) for t, topics in tech_topic_distribution.items() if len(topics) >= 2]
    shared_techs.sort(key=lambda x: x[1], reverse=True)
    lines.append("| 关键技术 | 涉及主题数 | 涉及主题 |")
    lines.append("|----------|------------|----------|")
    for tech, count in shared_techs[:10]:
        topics = ", ".join(tech_topic_distribution[tech])
        lines.append(f"| {tech} | {count} | {topics} |")
    lines.append("")

    lines.append("### 主题索引\n")
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
    analysis_dir = per_topic_dir / "analysis"
    per_topic_dir.mkdir(parents=True, exist_ok=True)
    chart_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir.mkdir(parents=True, exist_ok=True)

    single_paths = []
    all_chart_paths = {}
    backtest_results = _load_backtest_results()

    logger.info(f"开始生成路线图图表，共 {len(all_roadmaps)} 个主题")

    for roadmap in all_roadmaps:
        topic_name = roadmap.get("topic_name", "未知主题")
        safe_name = _safe_filename(topic_name)

        chart_paths = generate_all_charts(roadmap, str(per_topic_dir))

        analysis_path = analysis_dir / f"{safe_name}_图表指标解读.md"
        chart_paths["description"] = str(analysis_path)
        all_chart_paths[topic_name] = chart_paths

        analysis_content = generate_topic_analysis_file(roadmap, chart_paths, backtest_results)
        write_text(analysis_content, analysis_path)
        logger.info(f"图表指标解读文件已生成: {analysis_path}")

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
