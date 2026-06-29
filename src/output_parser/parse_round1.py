# -*- coding:utf-8-*-
import json
import re
from typing import List, Dict, Any, Optional
from src.utils.logger import get_logger
from src.utils.validator import validate_round1_output
from config.settings import ENABLE_REASONING_CHAIN
from src.output_parser.evidence_tagger import (
    validate_reasoning_chain,
    tag_items_with_evidence,
    _load_topics,
)

logger = get_logger(__name__)

FORBIDDEN_WORDS = [
    "量子计算", "神经形态硬件", "微胶囊", "形状记忆合金",
    "自修复混凝土", "联邦学习", "合成数据", "GDPR",
    "百万级参数空间", "20年疲劳寿命", "95%准确率"
]

def _extract_json(text: str) -> Optional[Dict]:
    if not text or not text.strip():
        return None

    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    code_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    match = re.search(code_pattern, text, re.IGNORECASE)
    if match:
        candidate = match.group(1).strip()
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            pass

    brace_balance = 0
    start_idx = -1
    for i, ch in enumerate(text):
        if ch == '{':
            if brace_balance == 0:
                start_idx = i
            brace_balance += 1
        elif ch == '}':
            brace_balance -= 1
            if brace_balance == 0 and start_idx != -1:
                candidate = text[start_idx:i + 1]
                try:
                    return json.loads(candidate)
                except (json.JSONDecodeError, ValueError):
                    pass
                start_idx = -1

    pattern = r'\{[^{}]*"topic_name"[^{}]*\}'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except (json.JSONDecodeError, ValueError):
            pass

    return None

def _fallback_parse(text: str, topic_name: str) -> Dict[str, Any]:
    result = {"topic_name": topic_name}

    bottleneck_patterns = [
        r'(?:瓶颈|bottlenecks?|技术瓶颈)\s*[:：]\s*([\s\S]*?)(?=\n\s*(?:\d+\s*[.、]?\s*)?(?:突破|breakthroughs?|深度融合|deep\s*fusion|融合场景|典型一天|typical\s*day)|\n\s*\n|\Z)',
        r'(?:bottlenecks_2030_2035)\s*[:：]\s*\[([\s\S]*?)\]',
        r'(?:瓶颈|bottlenecks?)\s*[-—]\s*([\s\S]*?)(?=\n\s*\n|\Z)',
    ]
    bottlenecks = []
    for pat in bottleneck_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            raw = match.group(1).strip()
            items = re.split(r'\n\s*[-*•]\s*|\n\s*\d+[.、]\s*|[,，;；]\s*', raw)
            items = [item.strip(" -•\t\"'") for item in items if item.strip()]
            if items:
                bottlenecks = items
                break
    result["bottlenecks_2030_2035"] = bottlenecks

    breakthrough_patterns = [
        r'(?:突破|breakthroughs?|技术突破)\s*[:：]\s*([\s\S]*?)(?=\n\s*(?:\d+\s*[.、]?\s*)?(?:深度融合|deep\s*fusion|融合场景|典型一天|typical\s*day)|\n\s*\n|\Z)',
        r'(?:breakthroughs_by_2040)\s*[:：]\s*\[([\s\S]*?)\]',
        r'(?:突破|breakthroughs?)\s*[-—]\s*([\s\S]*?)(?=\n\s*\n|\Z)',
    ]
    breakthroughs = []
    for pat in breakthrough_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            raw = match.group(1).strip()
            items = re.split(r'\n\s*[-*•]\s*|\n\s*\d+[.、]\s*|[,，;；]\s*', raw)
            items = [item.strip(" -•\t\"'") for item in items if item.strip()]
            if items:
                breakthroughs = items
                break
    result["breakthroughs_by_2040"] = breakthroughs

    fusion_topics_patterns = [
        r'(?:深度融合|deep\s*fusion\s*topics?|融合主题)\s*[:：]\s*([\s\S]*?)(?=\n\s*(?:\d+\s*[.、]?\s*)?(?:融合场景|典型一天|typical\s*day)|\n\s*\n|\Z)',
        r'(?:deep_fusion_topics)\s*[:：]\s*\[([\s\S]*?)\]',
    ]
    fusion_topics = []
    for pat in fusion_topics_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            raw = match.group(1).strip()
            items = re.split(r'\n\s*[-*•]\s*|\n\s*\d+[.、]\s*|[,，;；]\s*', raw)
            items = [item.strip(" -•\t\"'") for item in items if item.strip()]
            if items:
                fusion_topics = items[:2]
                break
    result["deep_fusion_topics"] = fusion_topics

    fusion_scenario_match = re.search(
        r'(?:融合场景|fusion_scenario|scenario)\s*[:：]\s*([\s\S]*?)(?=\n\s*(?:\d+\s*[.、]?\s*)?(?:典型一天|typical\s*day)|\n\s*\n|\Z)',
        text, re.IGNORECASE
    )
    if fusion_scenario_match:
        result["fusion_scenario"] = fusion_scenario_match.group(1).strip()
    else:
        result["fusion_scenario"] = ""

    typical_day_match = re.search(
        r'(?:典型一天|typical_day_2040|typical\s*day)\s*[:：]\s*([\s\S]*?)(?=\n\s*\n|\Z)',
        text, re.IGNORECASE
    )
    if typical_day_match:
        result["typical_day_2040"] = typical_day_match.group(1).strip()[:200]
    else:
        result["typical_day_2040"] = text[:200]

    return result

def parse_round1_output(raw_response: str, topic_name: str) -> Optional[Dict[str, Any]]:
    data = _extract_json(raw_response)
    if data is None:
        logger.error(f"主题 {topic_name} 响应中未找到有效 JSON，使用兜底解析")
        result = _fallback_parse(raw_response, topic_name)
        return _enhance_with_evidence(result, topic_name)
    if "topic_name" not in data:
        data["topic_name"] = topic_name
    for key in ["bottlenecks_2030_2035", "breakthroughs_by_2040", "deep_fusion_topics"]:
        if key not in data or not isinstance(data[key], list):
            data[key] = []
    data.setdefault("fusion_scenario", "")
    data.setdefault("typical_day_2040", "")
    
    if ENABLE_REASONING_CHAIN:
        raw_reasoning = data.get("reasoning_chain", [])
        data["reasoning_chain"] = validate_reasoning_chain(raw_reasoning)
    else:
        data["reasoning_chain"] = []
    
    data["breakthroughs_by_2040"] = filter_unrealistic_breakthroughs(data["breakthroughs_by_2040"])
    data["bottlenecks_2030_2035"] = filter_unrealistic_breakthroughs(data["bottlenecks_2030_2035"])
    
    data = _enhance_with_evidence(data, topic_name)
    
    if not validate_round1_output(data):
        logger.warning(f"主题 {topic_name} 格式不完全符合 schema，但已强制使用")
    return data


def _enhance_with_evidence(data: Dict[str, Any], topic_name: str) -> Dict[str, Any]:
    if not ENABLE_REASONING_CHAIN:
        return data
    
    try:
        topics = _load_topics()
        all_topic_names = [t.get("name", "") for t in topics]
        topic_context = {
            "topic_name": topic_name,
            "all_topic_names": all_topic_names
        }
        
        bottlenecks = data.get("bottlenecks_2030_2035", [])
        if bottlenecks and isinstance(bottlenecks[0], str):
            data["bottlenecks_2030_2035_tagged"] = tag_items_with_evidence(bottlenecks, topic_context)
        
        breakthroughs = data.get("breakthroughs_by_2040", [])
        if breakthroughs and isinstance(breakthroughs[0], str):
            data["breakthroughs_by_2040_tagged"] = tag_items_with_evidence(breakthroughs, topic_context)
        
        bottleneck_scores = [item.get("evidence_score", 0.0) 
                            for item in data.get("bottlenecks_2030_2035_tagged", [])]
        breakthrough_scores = [item.get("evidence_score", 0.0) 
                              for item in data.get("breakthroughs_by_2040_tagged", [])]
        
        all_scores = bottleneck_scores + breakthrough_scores
        if all_scores:
            data["overall_evidence_score"] = sum(all_scores) / len(all_scores)
        else:
            data["overall_evidence_score"] = 0.0
            
    except Exception as e:
        logger.warning(f"证据标注增强失败: {e}")
    
    return data

def filter_unrealistic_breakthroughs(breakthroughs: List[str]) -> List[str]:
    filtered = []
    for b in breakthroughs:
        if any(word in b for word in FORBIDDEN_WORDS):
            continue
        filtered.append(b)
    return filtered
