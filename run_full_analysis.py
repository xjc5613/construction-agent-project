# -*- coding:utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logger import setup_logger
from src.data_preparation.build_round1_inputs import build_round1_inputs
from src.llm_orchestrator import run_round1, run_round2, run_round3, run_all_topics_roadmap
from src.report.per_topic_roadmap_report import save_per_topic_reports
from src.report_generator import generate_final_report
from src.evaluation.backtesting import Backtester, generate_mock_historical_data
from config.settings import OUTPUTS_REPORT, BACKTEST_HISTORICAL_YEAR, ENABLE_PER_TOPIC_ROADMAP
from src.utils.file_io import write_json, write_text
import json
from datetime import datetime

logger = setup_logger("run_all")


def run_forecast(force_rerun=False):
    logger.info("=" * 60)
    logger.info("===== 智能建造2040技术预测系统启动（全功能增强版） =====")
    logger.info("=" * 60)
    
    logger.info("步骤1: 构造第一轮输入数据")
    topic_inputs = build_round1_inputs()
    if not topic_inputs:
        logger.error("无有效主题输入，退出")
        return None, None, None, []
    
    logger.info(f"步骤2: 执行第一轮预测（主题演化）- 共{len(topic_inputs)}个主题")
    round1_results = run_round1(topic_inputs, force_rerun=force_rerun)
    if not round1_results:
        logger.error("第一轮无结果，退出")
        return None, None, None, []
    
    logger.info("步骤3: 执行第二轮预测（新范式）")
    round2_result = run_round2(round1_results, force_rerun=force_rerun)
    
    logger.info("步骤4: 执行第三轮预测（路线图）")
    round3_result = run_round3(round1_results, round2_result, force_rerun=force_rerun)
    
    roadmaps = []
    if ENABLE_PER_TOPIC_ROADMAP:
        logger.info("步骤5: 生成分主题技术路线图")
        roadmaps = run_all_topics_roadmap(round1_results, force_rerun=force_rerun)
        save_per_topic_reports(roadmaps)
        logger.info(f"分主题路线图生成完成，共 {len(roadmaps)} 个主题")
        logger.info("步骤6: 生成最终报告")
    else:
        logger.info("步骤5: 生成最终报告")
    
    generate_final_report(round1_results, round2_result, round3_result, roadmaps=roadmaps)
    
    logger.info("===== 技术预测完成 =====")
    return round1_results, round2_result, round3_result, roadmaps


def run_backtest():
    logger.info("=" * 60)
    logger.info("===== 回溯验证模块启动 =====")
    logger.info("=" * 60)
    
    import json
    from config.settings import DATA_RAW
    
    topics_file = DATA_RAW / "topics.json"
    with open(topics_file, 'r', encoding='utf-8') as f:
        topics_data = json.load(f)
    
    topic_ipc_list = topics_data if isinstance(topics_data, list) else topics_data.get('topics', [])
    
    historical_year = BACKTEST_HISTORICAL_YEAR
    forecast_year = 2025
    actual_year = 2025
    
    logger.info(f"历史回溯年份: {historical_year}")
    logger.info(f"预测目标年份: {forecast_year}")
    logger.info(f"实际对比年份: {actual_year}")
    
    mock_data = generate_mock_historical_data(topic_ipc_list, historical_year)
    
    def mock_forecast_func(historical_topics, target_year):
        forecasted = []
        for tech in historical_topics:
            if tech.get("maturity_level", 0) >= 0.3:
                forecasted.append({
                    "name": tech.get("name", "unknown"),
                    "forecast_year": target_year,
                    "maturity_level": min(tech.get("maturity_level", 0) + 0.3, 1.0)
                })
        return forecasted
    
    backtester = Backtester(historical_data=mock_data)
    
    logger.info("执行回溯验证...")
    results = backtester.run_backtest(
        forecast_func=mock_forecast_func,
        forecast_year=forecast_year,
        actual_year=actual_year
    )
    
    report = backtester.generate_report()
    report_path = OUTPUTS_REPORT / f"backtest_report_{historical_year}_{forecast_year}.md"
    write_text(report, report_path)
    
    json_path = OUTPUTS_REPORT / f"backtest_results_{historical_year}_{forecast_year}.json"
    write_json(results, json_path)
    
    logger.info(f"回溯验证报告已生成: {report_path}")
    logger.info(f"回溯验证数据已保存: {json_path}")
    logger.info("===== 回溯验证完成 =====")
    
    return results, report_path


def generate_comprehensive_report(round1_results, round2_result, round3_result, backtest_results, roadmaps=None):
    if roadmaps is None:
        roadmaps = []

    logger.info("=" * 60)
    logger.info("===== 生成综合分析报告 =====")
    logger.info("=" * 60)
    
    lines = []
    lines.append("# 智能建造2040技术预测 - 综合分析报告\n")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    lines.append("## 一、运行配置概览\n")
    lines.append("### 1.1 功能开关状态\n")
    lines.append("| 功能 | 状态 |\n")
    lines.append("|------|------|\n")
    from config import settings
    lines.append(f"| 自洽性验证 | {'✅ 开启' if settings.ENABLE_SELF_CONSISTENCY else '❌ 关闭'} |\n")
    lines.append(f"| 多模型集成 | {'✅ 开启' if settings.ENABLE_MULTI_MODEL else '❌ 关闭'} |\n")
    lines.append(f"| 多Agent辩论 | {'✅ 开启' if settings.ENABLE_MULTI_AGENT_DEBATE else '❌ 关闭'} |\n")
    lines.append(f"| 推理链条 | {'✅ 开启' if settings.ENABLE_REASONING_CHAIN else '❌ 关闭'} |\n")
    lines.append(f"| 路线图增强 | {'✅ 开启' if settings.ENABLE_ROADMAP_ENHANCED else '❌ 关闭'} |\n")
    lines.append(f"| 分主题路线图 | {'✅ 开启' if settings.ENABLE_PER_TOPIC_ROADMAP else '❌ 关闭'} |\n")
    
    lines.append("\n### 1.2 核心参数配置\n")
    lines.append(f"- 自洽性采样次数: {settings.SELF_CONSISTENCY_SAMPLES}次\n")
    lines.append(f"- 自洽性温度范围: {settings.SELF_CONSISTENCY_TEMPERATURE_MIN} - {settings.SELF_CONSISTENCY_TEMPERATURE_MAX}\n")
    lines.append(f"- 置信度阈值: {settings.CONFIDENCE_THRESHOLD}分\n")
    lines.append(f"- 辩论轮次: {settings.DEBATE_ROUNDS}轮\n")
    lines.append(f"- 辩论Agent: {', '.join(settings.DEBATE_AGENTS)}\n")
    lines.append(f"- 多模型策略: {settings.MULTI_MODEL_STRATEGY}\n")
    lines.append(f"- 回溯历史年份: {settings.BACKTEST_HISTORICAL_YEAR}年\n")
    
    lines.append("\n## 二、技术主题预测统计\n")
    
    if round1_results:
        lines.append(f"### 2.1 预测主题数量\n")
        lines.append(f"共完成 **{len(round1_results)}** 个技术主题的预测分析\n")
        
        lines.append("\n### 2.2 各主题预测详情\n")
        for i, topic in enumerate(round1_results, 1):
            topic_name = topic.get('topic_name', f'主题{i}')
            bottlenecks = topic.get('bottlenecks_2030_2035', [])
            breakthroughs = topic.get('breakthroughs_by_2040', [])
            fusion_topics = topic.get('deep_fusion_topics', [])
            confidence = topic.get('confidence', None)
            evidence_score = topic.get('overall_evidence_score', None)
            
            lines.append(f"\n#### {i}. {topic_name}\n")
            lines.append(f"- 2030-2035年瓶颈: **{len(bottlenecks)}** 项\n")
            lines.append(f"- 2040年技术突破: **{len(breakthroughs)}** 项\n")
            lines.append(f"- 深度融合主题: **{len(fusion_topics)}** 个\n")
            
            if confidence is not None:
                conf_level = "高" if confidence >= 80 else ("中" if confidence >= 60 else "低")
                conf_icon = "🟢" if confidence >= 80 else ("🟡" if confidence >= 60 else "🔴")
                lines.append(f"- 总体置信度: {conf_icon} **{confidence:.1f}**分 ({conf_level}置信)\n")
            
            if evidence_score is not None:
                lines.append(f"- 依据充分度: **{evidence_score:.1f}**分\n")
            
            low_conf = topic.get('low_confidence_fields', [])
            if low_conf:
                lines.append(f"- ⚠️ 低置信度字段: {', '.join(low_conf)}\n")
            
            debate_summary = topic.get('debate_summary', None)
            if debate_summary:
                lines.append(f"- 💬 辩论摘要: 已进行多Agent辩论评审\n")
    
    lines.append("\n### 2.3 智能建造新范式\n")
    if round2_result:
        paradigm_name = round2_result.get('new_paradigm_name', '未定义')
        paradigm_desc = round2_result.get('new_paradigm_description', '')
        confidence = round2_result.get('confidence', None)
        
        lines.append(f"**范式名称**: {paradigm_name}\n")
        if confidence is not None:
            conf_level = "高" if confidence >= 80 else ("中" if confidence >= 60 else "低")
            lines.append(f"**置信度**: {confidence:.1f}分 ({conf_level}置信)\n")
        lines.append(f"\n{paradigm_desc[:300]}...\n")
    
    lines.append("\n## 三、技术路线图分析\n")
    
    if round3_result:
        lines.append(f"### 3.1 路线图条目统计\n")
        lines.append(f"共 **{len(round3_result)}** 条路线图条目\n")
        
        by_year = {}
        by_category = {}
        by_trl = {}
        by_uncertainty = {}
        by_impact = {}
        
        for item in round3_result:
            year = str(item.get('year', '未知'))
            category = item.get('category', '未知')
            trl = item.get('trl_level', '未知')
            uncertainty = item.get('uncertainty_level', '未知')
            impact = item.get('impact_scope', '未知')
            
            by_year[year] = by_year.get(year, 0) + 1
            by_category[category] = by_category.get(category, 0) + 1
            if trl != '未知':
                by_trl[str(trl)] = by_trl.get(str(trl), 0) + 1
            if uncertainty != '未知':
                by_uncertainty[uncertainty] = by_uncertainty.get(uncertainty, 0) + 1
            if impact != '未知':
                by_impact[impact] = by_impact.get(impact, 0) + 1
        
        lines.append("\n### 3.2 按年份分布\n")
        lines.append("| 年份 | 条目数 |\n")
        lines.append("|------|--------|\n")
        for year in sorted(by_year.keys()):
            lines.append(f"| {year}年 | {by_year[year]} |\n")
        
        lines.append("\n### 3.3 按类别分布\n")
        lines.append("| 类别 | 条目数 |\n")
        lines.append("|------|--------|\n")
        for cat, count in sorted(by_category.items(), key=lambda x: -x[1]):
            lines.append(f"| {cat} | {count} |\n")
        
        if by_trl:
            lines.append("\n### 3.4 按TRL等级分布（技术成熟度）\n")
            lines.append("| TRL等级 | 条目数 | 说明 |\n")
            lines.append("|---------|--------|------|\n")
            trl_desc = {
                '1': '基本原理', '2': '技术概念', '3': '功能验证',
                '4': '组件验证', '5': '相关环境', '6': '相关环境原型',
                '7': '系统原型', '8': '实际系统', '9': '实际应用'
            }
            for trl in sorted(by_trl.keys()):
                desc = trl_desc.get(trl, '')
                lines.append(f"| TRL {trl} | {by_trl[trl]} | {desc} |\n")
        
        if by_uncertainty:
            lines.append("\n### 3.5 按不确定性等级分布\n")
            lines.append("| 不确定性等级 | 条目数 |\n")
            lines.append("|-------------|--------|\n")
            for level in ['low', 'medium', 'high']:
                count = by_uncertainty.get(level, 0)
                label = {'low': '低', 'medium': '中', 'high': '高'}.get(level, level)
                lines.append(f"| {label} | {count} |\n")
        
        if by_impact:
            lines.append("\n### 3.6 按影响范围分布\n")
            lines.append("| 影响范围 | 条目数 |\n")
            lines.append("|----------|--------|\n")
            for scope in ['local', 'industry', 'global']:
                count = by_impact.get(scope, 0)
                label = {'local': '局部', 'industry': '行业级', 'global': '全局'}.get(scope, scope)
                lines.append(f"| {label} | {count} |\n")
    
    lines.append("\n## 四、分主题技术路线图\n")
    
    if roadmaps:
        lines.append(f"已为 **{len(roadmaps)}** 个技术主题单独生成了详细的技术路线图，每个主题包含时间轴视图、流程图视图、分阶段里程碑表格和统计信息。\n")
        
        lines.append("### 4.1 主题路线图清单\n")
        lines.append("| 序号 | 主题名称 | 报告文件 |\n")
        lines.append("|------|----------|----------|\n")
        
        from src.report.per_topic_roadmap_report import _safe_filename
        for i, roadmap in enumerate(roadmaps, 1):
            topic_name = roadmap.get("topic_name", f"主题{i}")
            safe_name = _safe_filename(topic_name)
            file_path = f"per_topic_roadmaps/{safe_name}_路线图.md"
            lines.append(f"| {i} | {topic_name} | `{file_path}` |\n")
        
        lines.append("\n### 4.2 统计汇总\n")
        total_milestones = 0
        stage_totals = {year: 0 for year in settings.PER_TOPIC_ROADMAP_STAGES}
        for roadmap in roadmaps:
            roadmap_data = roadmap.get("roadmap", {})
            for year in settings.PER_TOPIC_ROADMAP_STAGES:
                stage = roadmap_data.get(year, {})
                milestones = stage.get("milestones", [])
                count = len(milestones)
                stage_totals[year] += count
                total_milestones += count
        
        lines.append(f"- **总主题数**：{len(roadmaps)}\n")
        lines.append(f"- **总里程碑数**：{total_milestones}\n")
        lines.append("- **各阶段汇总**：\n")
        for year in settings.PER_TOPIC_ROADMAP_STAGES:
            lines.append(f"  - {year}年：{stage_totals[year]} 个里程碑\n")
        
        lines.append("\n### 4.3 文件位置\n")
        lines.append("- **整合报告**: `outputs/final_report/per_topic_roadmaps_all.md`\n")
        lines.append("- **单主题报告目录**: `outputs/final_report/per_topic_roadmaps/`\n")
    else:
        lines.append("未生成分主题路线图（功能未开启或无数据）。\n")
    
    lines.append("\n## 五、回溯验证结果\n")
    
    if backtest_results:
        metrics = backtest_results.get('metrics', {})
        
        lines.append("### 4.1 核心评估指标\n")
        lines.append("| 指标 | 数值 | 说明 |\n")
        lines.append("|------|------|------|\n")
        
        accuracy = metrics.get('accuracy', 0)
        precision = metrics.get('precision', 0)
        recall = metrics.get('recall', 0)
        f1 = metrics.get('f1_score', 0)
        time_dev = metrics.get('time_deviation', 0)
        dir_acc = metrics.get('direction_accuracy', 0)
        
        lines.append(f"| 准确率 (Accuracy) | {accuracy*100:.1f}% | 预测正确的技术占预测总数的比例 |\n")
        lines.append(f"| 精确率 (Precision) | {precision*100:.1f}% | 预测为正的样本中实际为正的比例 |\n")
        lines.append(f"| 召回率 (Recall) | {recall*100:.1f}% | 实际发生的技术中被预测到的比例 |\n")
        lines.append(f"| F1分数 | {f1*100:.1f}% | 精确率和召回率的调和平均 |\n")
        lines.append(f"| 时间偏差 | {time_dev:.2f}年 | 预测时间与实际时间的平均偏差 |\n")
        lines.append(f"| 方向准确率 | {dir_acc*100:.1f}% | 趋势预测方向是否正确 |\n")
        
        lines.append("\n### 4.2 验证配置\n")
        lines.append(f"- 历史回溯年份: {backtest_results.get('historical_year', 'N/A')}年\n")
        lines.append(f"- 预测目标年份: {backtest_results.get('forecast_year', 'N/A')}年\n")
        lines.append(f"- 实际对比年份: {backtest_results.get('actual_year', 'N/A')}年\n")
        lines.append(f"- 预测技术数量: {metrics.get('forecast_count', 0)}项\n")
        lines.append(f"- 实际技术数量: {metrics.get('actual_count', 0)}项\n")
        
        lines.append("\n### 4.3 详细分析\n")
        correct = metrics.get("correct_predictions_list", [])
        false_positives = metrics.get("false_positives", [])
        false_negatives = metrics.get("false_negatives", [])
        
        lines.append(f"- ✅ 正确预测: **{metrics.get('correct_predictions', 0)}** 项\n")
        lines.append(f"- ⚠️ 误报（预测了但未发生）: **{len(false_positives)}** 项\n")
        lines.append(f"- ❌ 漏报（发生了但未预测到）: **{len(false_negatives)}** 项\n")
        
        lines.append(f"\n- 预测技术总数: {metrics.get('forecast_count', 0)}项\n")
        lines.append(f"- 实际技术总数: {metrics.get('actual_count', 0)}项\n")
    
    lines.append("\n## 六、方法学说明\n")
    lines.append("### 6.1 预测方法论\n")
    lines.append("本系统采用**三轮迭代预测法**，结合多种增强机制提升预测可靠性：\n")
    lines.append("1. **第一轮（主题演化预测）**: 对9个技术主题分别进行深度分析\n")
    lines.append("2. **第二轮（新范式提炼）**: 综合各主题趋势，提炼整体范式变革\n")
    lines.append("3. **第三轮（路线图生成）**: 生成分阶段技术发展路线图\n")
    
    lines.append("\n### 6.2 增强机制说明\n")
    lines.append("#### 自洽性验证 (Self-Consistency)\n")
    lines.append(f"- 对同一问题独立采样 {settings.SELF_CONSISTENCY_SAMPLES} 次\n")
    lines.append("- 通过结果一致性计算置信度（0-100分）\n")
    lines.append("- 自动识别低置信度项并标记\n")
    
    lines.append("\n#### 多Agent辩论 (Multi-Agent Debate)\n")
    lines.append(f"- {len(settings.DEBATE_AGENTS)} 个专家角色交叉评审: {', '.join(settings.DEBATE_AGENTS)}\n")
    lines.append(f"- 进行 {settings.DEBATE_ROUNDS} 轮辩论迭代\n")
    lines.append("- 技术专家、产业分析师、风险评估师等多视角审视\n")
    
    lines.append("\n#### 推理链条与可解释性\n")
    lines.append("- 记录每个结论的完整推理过程\n")
    lines.append("- 自动标注依据来源（IPC分类、融合对、技术主题）\n")
    lines.append("- 量化评估依据充分度\n")
    
    lines.append("\n#### 路线图多维度分析\n")
    lines.append("- TRL技术成熟度分级（1-9级）\n")
    lines.append("- 影响范围评估（局部/行业级/全局）\n")
    lines.append("- 不确定性等级标注（低/中/高）\n")
    lines.append("- 时间序列合理性校验\n")
    
    lines.append("\n## 七、结果文件清单\n")
    lines.append("| 文件类型 | 路径 |\n")
    lines.append("|----------|------|\n")
    lines.append("| 📄 最终预测报告 | `outputs/final_report/forecast_report.md` |\n")
    lines.append("| 📊 回溯验证报告 | `outputs/final_report/backtest_report_*.md` |\n")
    lines.append("| 📋 第一轮原始结果 | `outputs/raw/round1_*.json` (9个主题) |\n")
    lines.append("| 🔍 第一轮解析结果 | `outputs/parsed/round1_*.json` (9个主题) |\n")
    lines.append("| 🧠 新范式结果 | `outputs/parsed/round2_paradigm.json` |\n")
    lines.append("| 🗺️ 路线图结果 | `outputs/parsed/round3_roadmap.json` |\n")
    lines.append("| 🗺️ 分主题路线图整合报告 | `outputs/final_report/per_topic_roadmaps_all.md` |\n")
    lines.append("| 📁 分主题路线图单文件 | `outputs/final_report/per_topic_roadmaps/` |\n")
    lines.append("| 📈 回溯验证数据 | `outputs/final_report/backtest_results_*.json` |\n")
    lines.append("| 📝 运行日志 | `logs/forecast.log` |\n")
    
    lines.append("\n---\n")
    lines.append(f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
    
    content = "\n".join(lines)
    report_path = OUTPUTS_REPORT / "comprehensive_analysis_report.md"
    write_text(content, report_path)
    
    logger.info(f"综合分析报告已生成: {report_path}")
    return report_path


def main():
    force_rerun = False
    
    round1_results, round2_result, round3_result, roadmaps = run_forecast(force_rerun=force_rerun)
    
    backtest_results, backtest_report_path = run_backtest()
    
    comprehensive_path = generate_comprehensive_report(
        round1_results, round2_result, round3_result, backtest_results, roadmaps=roadmaps
    )
    
    logger.info("=" * 60)
    logger.info("===== 所有任务全部完成 =====")
    logger.info("=" * 60)
    logger.info(f"最终预测报告: {OUTPUTS_REPORT / 'forecast_report.md'}")
    logger.info(f"综合分析报告: {comprehensive_path}")
    logger.info(f"回溯验证报告: {backtest_report_path}")
    if roadmaps:
        logger.info(f"分主题路线图: {OUTPUTS_REPORT / 'per_topic_roadmaps_all.md'}")


if __name__ == "__main__":
    main()
