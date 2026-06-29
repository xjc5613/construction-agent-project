# -*- coding:utf-8-*-
import re
import json
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from src.utils.logger import get_logger
from config.settings import DATA_RAW, ENABLE_REASONING_CHAIN

logger = get_logger(__name__)

IPC_PATTERN = re.compile(r'(?<![A-Z0-9])([A-Z]\d{2}[A-Z])(?:[-\s]\d{3})?(?![A-Z0-9])')
FUSION_PROB_PATTERN = re.compile(r'([A-Z]\d{2}[A-Z])\s*(?:与|和|\+|&|/)\s*([A-Z]\d{2}[A-Z]).*?(\d+\.\d+)')
EVIDENCE_BRACKET_PATTERN = re.compile(r'[（(](?:依据|根据|基于)[：:]?\s*([^）)]+)[）)]')


def _load_topics() -> List[Dict[str, Any]]:
    topics_path = DATA_RAW / "topics.json"
    if topics_path.exists():
        with open(topics_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _load_high_potential_pairs() -> List[Dict[str, Any]]:
    pairs_path = DATA_RAW / "high_potential_pairs.json"
    if pairs_path.exists():
        with open(pairs_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def extract_ipc_codes(text: str) -> List[str]:
    if not text:
        return []
    matches = IPC_PATTERN.findall(text)
    seen = set()
    result = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result


def extract_fusion_pairs(text: str) -> List[Dict[str, Any]]:
    if not text:
        return []
    pairs = []
    bracket_matches = EVIDENCE_BRACKET_PATTERN.findall(text)
    for bracket_text in bracket_matches:
        prob_matches = FUSION_PROB_PATTERN.findall(bracket_text)
        for ipc1, ipc2, prob in prob_matches:
            pairs.append({
                "ipc1": ipc1,
                "ipc2": ipc2,
                "probability": float(prob),
                "source": "direct_annotation"
            })
    return pairs


def extract_topic_mentions(text: str, topic_names: List[str]) -> List[str]:
    if not text or not topic_names:
        return []
    mentioned = []
    for name in topic_names:
        if name and name in text:
            mentioned.append(name)
    return mentioned


def identify_evidence_sources(item_text: str, topic_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    if not ENABLE_REASONING_CHAIN:
        return []
    
    sources = []
    topic_context = topic_context or {}
    
    ipc_codes = extract_ipc_codes(item_text)
    for ipc in ipc_codes:
        sources.append({
            "type": "ipc_class",
            "value": ipc,
            "quality": "direct" if ipc in item_text else "indirect"
        })
    
    fusion_pairs = extract_fusion_pairs(item_text)
    for pair in fusion_pairs:
        sources.append({
            "type": "fusion_pair",
            "value": f"{pair['ipc1']}-{pair['ipc2']}",
            "probability": pair["probability"],
            "quality": pair["source"]
        })
    
    topic_names = topic_context.get("all_topic_names", [])
    mentioned_topics = extract_topic_mentions(item_text, topic_names)
    for topic in mentioned_topics:
        sources.append({
            "type": "topic_name",
            "value": topic,
            "quality": "direct"
        })
    
    bracket_evidence = EVIDENCE_BRACKET_PATTERN.findall(item_text)
    for ev in bracket_evidence:
        if not any(ev in s.get("value", "") for s in sources):
            sources.append({
                "type": "explicit_annotation",
                "value": ev.strip(),
                "quality": "direct"
            })
    
    return sources


def tag_items_with_evidence(items: List[str], topic_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    if not ENABLE_REASONING_CHAIN:
        return [{"text": item, "evidence_sources": [], "evidence_score": 0.0} for item in items]
    
    tagged = []
    for item in items:
        evidence_sources = identify_evidence_sources(item, topic_context)
        evidence_score = calculate_evidence_score(item, evidence_sources)
        tagged.append({
            "text": item,
            "evidence_sources": evidence_sources,
            "evidence_score": evidence_score
        })
    return tagged


def calculate_evidence_score(item_text: str, evidence_sources: List[Dict[str, Any]]) -> float:
    if not evidence_sources:
        return 0.0
    
    score = 0.0
    direct_weight = 15.0
    indirect_weight = 5.0
    
    type_weights = {
        "ipc_class": 1.0,
        "fusion_pair": 1.5,
        "topic_name": 0.8,
        "explicit_annotation": 2.0
    }
    
    has_ipc = False
    has_fusion = False
    has_topic = False
    has_explicit = False
    
    for src in evidence_sources:
        src_type = src.get("type", "unknown")
        quality = src.get("quality", "indirect")
        weight = direct_weight if quality == "direct" else indirect_weight
        type_weight = type_weights.get(src_type, 1.0)
        contribution = weight * type_weight
        
        if src_type == "ipc_class":
            if not has_ipc:
                score += contribution
                has_ipc = True
            else:
                score += contribution * 0.5
        elif src_type == "fusion_pair":
            if not has_fusion:
                score += contribution
                has_fusion = True
            prob = src.get("probability", 0.5)
            score += prob * 10.0
        elif src_type == "topic_name":
            if not has_topic:
                score += contribution
                has_topic = True
        elif src_type == "explicit_annotation":
            if not has_explicit:
                score += contribution
                has_explicit = True
    
    if len(evidence_sources) >= 3:
        score += 10.0
    elif len(evidence_sources) >= 2:
        score += 5.0
    
    return min(score, 100.0)


def validate_reasoning_chain(reasoning_chain: Any) -> List[Dict[str, Any]]:
    if not ENABLE_REASONING_CHAIN:
        return []
    
    if not isinstance(reasoning_chain, list):
        return []
    
    valid_chain = []
    for step in reasoning_chain:
        if not isinstance(step, dict):
            continue
        if "step" not in step or "conclusion" not in step:
            continue
        valid_step = {
            "step": step.get("step"),
            "input_evidence": step.get("input_evidence", ""),
            "reasoning": step.get("reasoning", ""),
            "conclusion": step.get("conclusion", "")
        }
        valid_chain.append(valid_step)
    
    return valid_chain
