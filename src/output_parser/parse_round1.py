# -*- coding:utf-8-*-
import json
import re
from typing import List, Dict, Any, Optional
from src.utils.logger import get_logger
from src.utils.validator import validate_round1_output

logger = get_logger(__name__)

FORBIDDEN_WORDS = [
    "量子计算", "神经形态硬件", "微胶囊", "形状记忆合金",
    "自修复混凝土", "联邦学习", "合成数据", "GDPR",
    "百万级参数空间", "20年疲劳寿命", "95%准确率"
]

def _extract_json(text: str) -> Optional[Dict]:
    try:
        return json.loads(text)
    except:
        pass
    pattern = r'\{[^{}]*"topic_name"[^{}]*\}'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass
    code_pattern = r'```json\s*(\{.*?\})\s*```'
    match = re.search(code_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            pass
    return None

def _fallback_parse(text: str, topic_name: str) -> Dict[str, Any]:
    result = {"topic_name": topic_name}
    bottleneck_match = re.search(r'(?:瓶颈|bottlenecks)[:：]\s*(.+?)(?=\n\s*\n|\Z)', text, re.IGNORECASE | re.DOTALL)
    if bottleneck_match:
        result["bottlenecks_2030_2035"] = [bottleneck_match.group(1).strip()]
    else:
        result["bottlenecks_2030_2035"] = []
    result["breakthroughs_by_2040"] = []
    result["deep_fusion_topics"] = []
    result["fusion_scenario"] = ""
    result["typical_day_2040"] = text[:200]
    return result

def parse_round1_output(raw_response: str, topic_name: str) -> Optional[Dict[str, Any]]:
    data = _extract_json(raw_response)
    if data is None:
        logger.error(f"主题 {topic_name} 响应中未找到有效 JSON，使用兜底解析")
        return _fallback_parse(raw_response, topic_name)
    if "topic_name" not in data:
        data["topic_name"] = topic_name
    for key in ["bottlenecks_2030_2035", "breakthroughs_by_2040", "deep_fusion_topics"]:
        if key not in data or not isinstance(data[key], list):
            data[key] = []
    data.setdefault("fusion_scenario", "")
    data.setdefault("typical_day_2040", "")
    filter_unrealistic_breakthroughs(data)
    if not validate_round1_output(data):
        logger.warning(f"主题 {topic_name} 格式不完全符合 schema，但已强制使用")
    return data

def filter_unrealistic_breakthroughs(breakthroughs: List[str]) -> List[str]:
    filtered = []
    for b in breakthroughs:
        if any(word in b for word in FORBIDDEN_WORDS):
            continue  # 或替换为“（依据不足，已自动过滤）”
        filtered.append(b)
    return filtered