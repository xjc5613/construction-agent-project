# -*- coding:utf-8-*-
from datetime import datetime
from typing import List, Dict, Any
from config.settings import OUTPUTS_REPORT
from src.utils.file_io import write_text
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _get_confidence_level(confidence: float) -> str:
    if confidence >= 80:
        return "🟢 高置信"
    elif confidence >= 60:
        return "🟡 中置信"
    else:
        return "🔴 低置信"


def _get_confidence_label_cn(level: str) -> str:
    mapping = {
        "high": "高",
        "medium": "中",
        "low": "低"
    }
    return mapping.get(level, level)


def _get_impact_scope_cn(scope: str) -> str:
    mapping = {
        "global": "全局",
        "industry": "行业级",
        "local": "局部"
    }
    return mapping.get(scope, scope)


def _has_confidence_data(round1_outputs: List[Dict]) -> bool:
    for topic in round1_outputs:
        if "confidence" in topic:
            return True
    return False


def _has_evidence_data(round1_outputs: List[Dict]) -> bool:
    for topic in round1_outputs:
        if "overall_evidence_score" in topic:
            return True
    return False


def _has_reasoning_chain(round1_outputs: List[Dict], round2_output: Dict, round3_output: List[Dict]) -> bool:
    for topic in round1_outputs:
        chain = topic.get("reasoning_chain", [])
        if chain and isinstance(chain, list) and len(chain) > 0:
            return True
    if isinstance(round2_output, dict):
        chain = round2_output.get("reasoning_chain", [])
        if chain and isinstance(chain, list) and len(chain) > 0:
            return True
    if isinstance(round3_output, dict):
        chain = round3_output.get("reasoning_chain", [])
        if chain and isinstance(chain, list) and len(chain) > 0:
            return True
    return False


def _get_roadmap_items(round3_output: List[Dict]) -> List[Dict]:
    if isinstance(round3_output, list):
        return round3_output
    if isinstance(round3_output, dict):
        return round3_output.get("roadmap_items", [])
    return []


def _has_roadmap_enhanced(round3_output: List[Dict]) -> bool:
    items = _get_roadmap_items(round3_output)
    for item in items:
        if item.get("trl_level") is not None or item.get("uncertainty_level") or item.get("impact_scope"):
            return True
    return False


def _collect_low_confidence_items(round1_outputs: List[Dict]) -> List[Dict]:
    low_conf_items = []
    for topic in round1_outputs:
        topic_name = topic.get("topic_name", "未知主题")
        low_fields = topic.get("low_confidence_fields", [])
        if low_fields:
            field_confidences = topic.get("confidence_details", {})
            for field in low_fields:
                conf = field_confidences.get(field, 0.0)
                low_conf_items.append({
                    "topic": topic_name,
                    "field": field,
                    "confidence": conf
                })
    return low_conf_items


def _build_topic_section(topic: Dict, has_confidence: bool, has_evidence: bool) -> List[str]:
    lines = []
    topic_name = topic.get("topic_name", "未知主题")
    title = f"### {topic_name}"

    if has_confidence and "confidence" in topic:
        conf = topic["confidence"]
        level = _get_confidence_level(conf)
        title += f"  {level} ({conf:.1f}%)"

    lines.append(title + "\n")

    if has_evidence and "overall_evidence_score" in topic:
        score = topic["overall_evidence_score"]
        lines.append(f"- **依据充分度**: {score:.1f}/100\n")

    low_fields = topic.get("low_confidence_fields", []) if has_confidence else []

    bottlenecks = topic.get("bottlenecks_2030_2035", [])
    if bottlenecks:
        bottleneck_line = "- **2030-2035年瓶颈**: "
        items = []
        tagged = topic.get("bottlenecks_2030_2035_tagged")
        if tagged and isinstance(tagged, list):
            for i, item in enumerate(tagged):
                text = item.get("text", str(item)) if isinstance(item, dict) else str(item)
                marker = " ⚠️" if low_fields and "bottlenecks_2030_2035" in low_fields else ""
                items.append(f"{text}{marker}")
        else:
            for b in bottlenecks:
                text = b if isinstance(b, str) else str(b)
                marker = " ⚠️" if low_fields and "bottlenecks_2030_2035" in low_fields else ""
                items.append(f"{text}{marker}")
        bottleneck_line += ", ".join(items)
        lines.append(bottleneck_line + "\n")

    breakthroughs = topic.get("breakthroughs_by_2040", [])
    if breakthroughs:
        breakthrough_line = "- **至2040年突破**: "
        items = []
        tagged = topic.get("breakthroughs_by_2040_tagged")
        if tagged and isinstance(tagged, list):
            for item in tagged:
                text = item.get("text", str(item)) if isinstance(item, dict) else str(item)
                marker = " ⚠️" if low_fields and "breakthroughs_by_2040" in low_fields else ""
                items.append(f"{text}{marker}")
        else:
            for b in breakthroughs:
                text = b if isinstance(b, str) else str(b)
                marker = " ⚠️" if low_fields and "breakthroughs_by_2040" in low_fields else ""
                items.append(f"{text}{marker}")
        breakthrough_line += ", ".join(items)
        lines.append(breakthrough_line + "\n")

    fusion_topics = topic.get("deep_fusion_topics", [])
    if fusion_topics:
        marker = " ⚠️" if low_fields and "deep_fusion_topics" in low_fields else ""
        lines.append(f"- **深度融合主题**: {', '.join(str(x) for x in fusion_topics)}{marker}\n")

    fusion_scenario = topic.get("fusion_scenario", "")
    if fusion_scenario:
        marker = " ⚠️" if low_fields and "fusion_scenario" in low_fields else ""
        lines.append(f"- **融合场景**: {fusion_scenario}{marker}\n")

    typical_day = topic.get("typical_day_2040", "")
    if typical_day:
        marker = " ⚠️" if low_fields and "typical_day_2040" in low_fields else ""
        lines.append(f"- **典型一天**: {typical_day}{marker}\n")

    if has_confidence and low_fields:
        lines.append(f"- **高不确定性项**: {', '.join(low_fields)}\n")

    return lines


def _build_uncertainty_section(round1_outputs: List[Dict], has_confidence: bool) -> List[str]:
    lines = []
    lines.append("## 4. 不确定性分析\n")

    low_conf_items = _collect_low_confidence_items(round1_outputs) if has_confidence else []

    if low_conf_items:
        lines.append("### 4.1 低置信度项汇总\n")
        lines.append("| 主题 | 字段 | 置信度 |\n")
        lines.append("|------|------|--------|\n")
        for item in sorted(low_conf_items, key=lambda x: x["confidence"]):
            lines.append(f"| {item['topic']} | {item['field']} | {item['confidence']:.1f}% |\n")
        lines.append("")
    else:
        lines.append("### 4.1 低置信度项汇总\n")
        lines.append("本次预测未检测到显著低置信度项。\n")

    lines.append("### 4.2 关键假设与不确定因素\n")
    lines.append("1. **技术发展速度假设**：预测基于当前技术发展趋势的外推，实际技术突破可能因基础研究进展而加速或延迟\n")
    lines.append("2. **政策环境假设**：假设行业政策整体保持支持态势，政策重大变化可能影响技术发展路径\n")
    lines.append("3. **市场需求假设**：基于当前行业痛点和需求趋势预测，市场结构变化可能改变技术优先级\n")
    lines.append("4. **供应链因素**：关键材料、芯片等供应链稳定性可能影响技术落地速度\n")
    lines.append("5. **人才供给假设**：假设行业人才培养能够跟上技术发展需求\n")
    lines.append("")

    lines.append("### 4.3 预测方法局限性\n")
    lines.append("1. **数据局限性**：预测主要基于专利数据和专家知识，数据覆盖范围和质量可能影响准确性\n")
    lines.append("2. **模型局限性**：大语言模型可能存在知识截止日期限制和幻觉风险\n")
    lines.append("3. **维度局限性**：主要从技术维度分析，对社会、经济、环境等外部因素考虑有限\n")
    lines.append("4. **时间跨度**：预测至2040年，时间跨度较长，不确定性随时间递增\n")
    lines.append("5. **黑天鹅事件**：无法预测可能彻底改变行业格局的重大突发事件\n")
    lines.append("")

    return lines


def _build_methodology_section() -> List[str]:
    lines = []
    lines.append("## 5. 方法说明\n")

    lines.append("### 5.1 预测方法论\n")
    lines.append("本系统采用多轮迭代的技术预测方法，结合定性与定量分析：\n")
    lines.append("1. **第一轮（主题演化预测）**：针对每个技术主题，分析2030-2035年发展瓶颈和2040年技术突破方向\n")
    lines.append("2. **第二轮（新范式识别）**：基于第一轮结果，综合提炼智能建造领域的新范式\n")
    lines.append("3. **第三轮（技术路线图）**：结合前两轮结果，生成分阶段技术发展路线图\n")
    lines.append("")

    lines.append("### 5.2 置信度评估方式\n")
    lines.append("系统通过多种机制评估预测置信度：\n")
    lines.append("1. **自洽性验证**：对同一问题进行多次采样，通过结果一致性计算置信度\n")
    lines.append("2. **多模型集成**：不同模型预测结果的一致性反映置信度水平\n")
    lines.append("3. **多Agent辩论**：多角色专家评审与辩论，提升结果可靠性\n")
    lines.append("4. **字段级置信度**：对每个预测字段单独计算置信度，识别高不确定性项\n")
    lines.append("")
    lines.append("置信度等级划分：\n")
    lines.append("- 🟢 **高置信 (≥80%)**：预测结果一致性高，可靠性强\n")
    lines.append("- 🟡 **中置信 (60%-79%)**：预测结果基本一致，存在一定不确定性\n")
    lines.append("- 🔴 **低置信 (<60%)**：预测结果分歧较大，需谨慎参考\n")
    lines.append("")

    lines.append("### 5.3 技术工具与数据来源\n")
    lines.append("**技术工具**：\n")
    lines.append("- 大语言模型 API（DeepSeek 等）\n")
    lines.append("- 自洽性验证引擎\n")
    lines.append("- 多模型集成框架\n")
    lines.append("- 多Agent辩论系统\n")
    lines.append("- 证据标注与推理链条追踪\n")
    lines.append("")
    lines.append("**数据来源**：\n")
    lines.append("- 专利数据（IPC分类号、度中心度、中介中心度等网络分析指标）\n")
    lines.append("- 技术主题融合对分析\n")
    lines.append("- 领域专家知识\n")
    lines.append("- 学术文献摘要\n")
    lines.append("")

    return lines


def _build_roadmap_section(round3_output: List[Dict], has_enhanced: bool) -> List[str]:
    lines = []
    lines.append("## 3. 技术路线图\n")

    items = _get_roadmap_items(round3_output)

    if not items:
        lines.append("（暂无路线图数据）\n")
        return lines

    if has_enhanced:
        header = "| 年份 | 类别 | 描述 | TRL | 影响范围 | 不确定性 |"
        separator = "|------|------|------|-----|----------|----------|"
        lines.append(header + "\n")
        lines.append(separator + "\n")
        for item in items:
            year = item.get("year", "")
            category = item.get("category", "")
            description = item.get("description", "")
            trl = item.get("trl_level", "-")
            if trl is None:
                trl = "-"
            scope = item.get("impact_scope")
            scope_display = _get_impact_scope_cn(scope) if scope else "-"
            uncertainty = item.get("uncertainty_level")
            unc_display = _get_confidence_label_cn(uncertainty) if uncertainty else "-"
            lines.append(f"| {year} | {category} | {description} | {trl} | {scope_display} | {unc_display} |\n")
    else:
        lines.append("| 年份 | 类别 | 描述 |\n")
        lines.append("|------|------|------|\n")
        for item in items:
            year = item.get("year", "")
            category = item.get("category", "")
            description = item.get("description", "")
            lines.append(f"| {year} | {category} | {description} |\n")

    lines.append("")
    return lines


def _build_reasoning_chain_appendix(round1_outputs: List[Dict], round2_output: Dict, round3_output: List[Dict]) -> List[str]:
    lines = []
    lines.append("## 附录：推理链条\n")
    lines.append("> 以下为关键结论的推理过程，点击展开详情。\n")
    lines.append("")

    lines.append("### A.1 主题演化预测推理链条\n")
    lines.append("")

    has_any_chain = False
    for topic in round1_outputs:
        topic_name = topic.get("topic_name", "未知主题")
        chain = topic.get("reasoning_chain", [])
        if chain and isinstance(chain, list) and len(chain) > 0:
            has_any_chain = True
            lines.append(f"#### {topic_name}\n")
            for step in chain:
                if isinstance(step, dict):
                    step_num = step.get("step", "")
                    evidence = step.get("input_evidence", "")
                    reasoning = step.get("reasoning", "")
                    conclusion = step.get("conclusion", "")
                    lines.append(f"**步骤{step_num}**\n")
                    if evidence:
                        lines.append(f"- 输入证据：{evidence}\n")
                    if reasoning:
                        lines.append(f"- 推理过程：{reasoning}\n")
                    if conclusion:
                        lines.append(f"- 结论：{conclusion}\n")
                    lines.append("")

    if not has_any_chain:
        lines.append("（暂无详细推理链条）\n")

    lines.append("### A.2 核心依据来源\n")
    lines.append("")
    for topic in round1_outputs:
        topic_name = topic.get("topic_name", "未知主题")
        evidence_score = topic.get("overall_evidence_score")
        bottlenecks_tagged = topic.get("bottlenecks_2030_2035_tagged", [])
        breakthroughs_tagged = topic.get("breakthroughs_by_2040_tagged", [])

        if evidence_score is not None or (bottlenecks_tagged and breakthroughs_tagged):
            lines.append(f"#### {topic_name}\n")
            if evidence_score is not None:
                lines.append(f"- 整体依据充分度：{evidence_score:.1f}/100\n")

            all_tagged = []
            if isinstance(bottlenecks_tagged, list):
                all_tagged.extend([("瓶颈", item) for item in bottlenecks_tagged])
            if isinstance(breakthroughs_tagged, list):
                all_tagged.extend([("突破", item) for item in breakthroughs_tagged])

            for category, item in all_tagged:
                if isinstance(item, dict):
                    text = item.get("text", "")
                    sources = item.get("evidence_sources", [])
                    score = item.get("evidence_score", 0)
                    if sources:
                        source_strs = []
                        for src in sources:
                            if isinstance(src, dict):
                                src_type = src.get("type", "")
                                src_val = src.get("value", "")
                                source_strs.append(f"{src_type}:{src_val}")
                        lines.append(f"- [{category}] {text}\n")
                        lines.append(f"  - 依据来源：{', '.join(source_strs)}\n")
                        lines.append(f"  - 证据评分：{score:.1f}/100\n")
            lines.append("")

    return lines


def _build_per_topic_roadmap_section(roadmaps: List[Dict]) -> List[str]:
    lines = []
    lines.append("## 6. 分主题技术路线图\n")

    if not roadmaps:
        lines.append("（未生成分主题路线图）\n")
        return lines

    lines.append(f"已为 **{len(roadmaps)}** 个技术主题单独生成了详细的技术路线图，每个主题包含：\n")
    lines.append("- 时间轴视图（Mermaid timeline）\n")
    lines.append("- 流程图视图（Mermaid flowchart，含依赖关系）\n")
    lines.append("- 分阶段详细里程碑表格\n")
    lines.append("- 统计信息汇总\n")
    lines.append("")

    lines.append("### 6.1 主题路线图清单\n")
    lines.append("| 序号 | 主题名称 | 报告文件 |\n")
    lines.append("|------|----------|----------|\n")

    from src.report.per_topic_roadmap_report import _safe_filename
    for i, roadmap in enumerate(roadmaps, 1):
        topic_name = roadmap.get("topic_name", f"主题{i}")
        safe_name = _safe_filename(topic_name)
        file_path = f"per_topic_roadmaps/{safe_name}_路线图.md"
        lines.append(f"| {i} | {topic_name} | `{file_path}` |\n")

    lines.append("")
    lines.append("### 6.2 文件位置\n")
    lines.append("- **整合报告**: `outputs/final_report/per_topic_roadmaps_all.md`\n")
    lines.append("- **单主题报告目录**: `outputs/final_report/per_topic_roadmaps/`\n")
    lines.append("")

    return lines


def generate_final_report(round1_outputs: List[Dict], round2_output: Dict, round3_output: List[Dict], roadmaps: List[Dict] = None) -> None:
    if roadmaps is None:
        roadmaps = []

    has_confidence = _has_confidence_data(round1_outputs)
    has_evidence = _has_evidence_data(round1_outputs)
    has_reasoning = _has_reasoning_chain(round1_outputs, round2_output, round3_output)
    has_roadmap_enhanced = _has_roadmap_enhanced(round3_output)
    has_per_topic_roadmap = len(roadmaps) > 0

    lines = []
    lines.append("# 智能建造2040技术趋势预测报告\n")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    if has_confidence:
        high_count = sum(1 for t in round1_outputs if t.get("confidence", 0) >= 80)
        mid_count = sum(1 for t in round1_outputs if 60 <= t.get("confidence", 0) < 80)
        low_count = sum(1 for t in round1_outputs if t.get("confidence", 0) < 60 and "confidence" in t)
        lines.append(f"置信度概览：🟢 高置信 {high_count} 个主题 | 🟡 中置信 {mid_count} 个主题 | 🔴 低置信 {low_count} 个主题\n")

    lines.append("## 1. 技术主题演化预测\n")
    for topic in round1_outputs:
        topic_lines = _build_topic_section(topic, has_confidence, has_evidence)
        lines.extend(topic_lines)

    lines.append("## 2. 智能建造新范式\n")
    if isinstance(round2_output, dict):
        paradigm_name = round2_output.get("new_paradigm_name", round2_output.get("paradigm_name", "未定义"))
        paradigm_desc = round2_output.get("new_paradigm_description", round2_output.get("description", ""))
        lines.append(f"**范式名称**: {paradigm_name}\n\n")
        lines.append(f"**描述**: {paradigm_desc}\n\n")
    else:
        lines.append(f"**范式名称**: {round2_output.get('new_paradigm_name', '未定义') if isinstance(round2_output, dict) else '未定义'}\n\n")

    roadmap_lines = _build_roadmap_section(round3_output, has_roadmap_enhanced)
    lines.extend(roadmap_lines)

    if has_confidence or has_evidence:
        uncertainty_lines = _build_uncertainty_section(round1_outputs, has_confidence)
        lines.extend(uncertainty_lines)
    else:
        lines.append("## 4. 不确定性分析\n")
        lines.append("### 4.2 关键假设与不确定因素\n")
        lines.append("1. **技术发展速度假设**：预测基于当前技术发展趋势的外推，实际技术突破可能因基础研究进展而加速或延迟\n")
        lines.append("2. **政策环境假设**：假设行业政策整体保持支持态势，政策重大变化可能影响技术发展路径\n")
        lines.append("3. **市场需求假设**：基于当前行业痛点和需求趋势预测，市场结构变化可能改变技术优先级\n")
        lines.append("4. **供应链因素**：关键材料、芯片等供应链稳定性可能影响技术落地速度\n")
        lines.append("5. **人才供给假设**：假设行业人才培养能够跟上技术发展需求\n")
        lines.append("")
        lines.append("### 4.3 预测方法局限性\n")
        lines.append("1. **数据局限性**：预测主要基于专利数据和专家知识，数据覆盖范围和质量可能影响准确性\n")
        lines.append("2. **模型局限性**：大语言模型可能存在知识截止日期限制和幻觉风险\n")
        lines.append("3. **维度局限性**：主要从技术维度分析，对社会、经济、环境等外部因素考虑有限\n")
        lines.append("4. **时间跨度**：预测至2040年，时间跨度较长，不确定性随时间递增\n")
        lines.append("5. **黑天鹅事件**：无法预测可能彻底改变行业格局的重大突发事件\n")
        lines.append("")

    methodology_lines = _build_methodology_section()
    lines.extend(methodology_lines)

    if has_per_topic_roadmap:
        per_topic_lines = _build_per_topic_roadmap_section(roadmaps)
        lines.extend(per_topic_lines)

    if has_reasoning or has_evidence:
        appendix_lines = _build_reasoning_chain_appendix(round1_outputs, round2_output, round3_output)
        lines.extend(appendix_lines)

    content = "\n".join(lines)
    out_path = OUTPUTS_REPORT / "forecast_report.md"
    write_text(content, out_path)
    logger.info(f"报告已生成: {out_path}")
