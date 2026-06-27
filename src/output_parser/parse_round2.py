# -*- coding:utf-8-*-
import re
from typing import Dict, Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)

def parse_round2_output(raw_response: str) -> Optional[Dict[str, str]]:
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
    return {"new_paradigm_name": name, "new_paradigm_description": desc}