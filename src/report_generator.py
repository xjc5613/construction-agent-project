# -*- coding:utf-8-*-
from datetime import datetime
from typing import List, Dict, Any
from config.settings import OUTPUTS_REPORT
from src.utils.file_io import write_text
from src.utils.logger import get_logger

logger = get_logger(__name__)

def generate_final_report(round1_outputs: List[Dict], round2_output: Dict, round3_output: List[Dict]) -> None:
    lines = []
    lines.append("# 智能建造2040技术趋势预测报告\n")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append("## 1. 技术主题演化预测\n")
    for topic in round1_outputs:
        lines.append(f"### {topic['topic_name']}\n")
        lines.append(f"- **2030-2035年瓶颈**: {', '.join(topic.get('bottlenecks_2030_2035', []))}\n")
        lines.append(f"- **至2040年突破**: {', '.join(topic.get('breakthroughs_by_2040', []))}\n")
        lines.append(f"- **深度融合主题**: {', '.join(topic.get('deep_fusion_topics', []))}\n")
        lines.append(f"- **融合场景**: {topic.get('fusion_scenario', '')}\n")
        lines.append(f"- **典型一天**: {topic.get('typical_day_2040', '')}\n\n")
    lines.append("## 2. 智能建造新范式\n")
    lines.append(f"**范式名称**: {round2_output.get('new_paradigm_name', '未定义')}\n\n")
    lines.append(f"**描述**: {round2_output.get('new_paradigm_description', '')}\n\n")
    lines.append("## 3. 技术路线图\n")
    lines.append("| 年份 | 类别 | 描述 |\n")
    lines.append("|------|------|------|\n")
    for item in round3_output:
        lines.append(f"| {item['year']} | {item['category']} | {item['description']} |\n")
    content = "\n".join(lines)
    out_path = OUTPUTS_REPORT / "forecast_report.md"
    write_text(content, out_path)
    logger.info(f"报告已生成: {out_path}")