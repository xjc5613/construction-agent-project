# -*- coding:utf-8-*-
import re
from typing import List, Dict
from src.utils.logger import get_logger

logger = get_logger(__name__)

def parse_round3_output(raw_response: str) -> List[Dict[str, any]]:
    items = []
    pattern = r'(2030|2035|2040)[\s:：]*[-–—]?\s*(.+)'
    lines = raw_response.split('\n')
    for line in lines:
        match = re.search(pattern, line)
        if match:
            year = int(match.group(1))
            desc = match.group(2).strip()
            if "技术" in desc or "研发" in desc:
                cat = "技术里程碑"
            elif "产品" in desc or "应用" in desc:
                cat = "产品里程碑"
            else:
                cat = "其他"
            items.append({"year": year, "category": cat, "description": desc})
    if not items:
        logger.warning("未提取到路线图条目")
    return items