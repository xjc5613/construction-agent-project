# -*- coding:utf-8-*-
import re
import json
from typing import Dict, Optional
from src.utils.logger import get_logger
from config.settings import ENABLE_REASONING_CHAIN
from src.output_parser.evidence_tagger import validate_reasoning_chain

logger = get_logger(__name__)


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
    return None


def parse_round2_output(raw_response: str) -> Optional[Dict[str, str]]:
    json_data = _extract_json(raw_response)
    if json_data and isinstance(json_data, dict):
        result = {}
        if "new_paradigm_name" in json_data:
            result["new_paradigm_name"] = str(json_data["new_paradigm_name"])
        elif "范式名称" in json_data:
            result["new_paradigm_name"] = str(json_data["范式名称"])
        
        if "new_paradigm_description" in json_data:
            result["new_paradigm_description"] = str(json_data["new_paradigm_description"])
        elif "范式描述" in json_data:
            result["new_paradigm_description"] = str(json_data["范式描述"])
        
        if ENABLE_REASONING_CHAIN:
            result["reasoning_chain"] = validate_reasoning_chain(
                json_data.get("reasoning_chain", [])
            )
        else:
            result["reasoning_chain"] = []
        
        if "new_paradigm_name" in result and "new_paradigm_description" in result:
            return result
    
    name_pattern = r'(?:新范式名称|范式名称)[:：]\s*(.+?)(?:\n|$)'
    desc_pattern = r'(?:范式描述|描述)[:：]\s*(.+?)(?=\n\n|\Z)'
    name_match = re.search(name_pattern, raw_response, re.IGNORECASE)
    desc_match = re.search(desc_pattern, raw_response, re.IGNORECASE | re.DOTALL)
    if name_match:
        name = name_match.group(1).strip()
    else:
        lines = raw_response.strip().split('\n')
        name = lines[0][:100] if lines else "未命名范式"
        logger.warning(f"未找到明确范式名称，使用首行: {name}")
    if desc_match:
        desc = desc_match.group(1).strip()
    else:
        desc = raw_response[:500]
        logger.warning("未找到明确范式描述，使用前500字符")
    
    result = {"new_paradigm_name": name, "new_paradigm_description": desc}
    if ENABLE_REASONING_CHAIN:
        result["reasoning_chain"] = []
    else:
        result["reasoning_chain"] = []
    
    return result