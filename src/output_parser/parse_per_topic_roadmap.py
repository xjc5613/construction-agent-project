# -*- coding:utf-8-*-
import re
import json
from typing import Dict, Any, Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
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

    brace_start = text.find('{')
    brace_end = text.rfind('}')
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        candidate = text[brace_start:brace_end + 1]
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            pass

    return None


def _normalize_stage_data(stage_data: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(stage_data, dict):
        return None

    stage_description = stage_data.get("stage_description") or stage_data.get("阶段描述") or ""
    milestones_raw = stage_data.get("milestones") or stage_data.get("里程碑") or []

    if not isinstance(milestones_raw, list):
        milestones_raw = []

    milestones = []
    for ms in milestones_raw:
        if not isinstance(ms, dict):
            continue
        milestone = {
            "name": ms.get("name") or ms.get("名称") or "",
            "description": ms.get("description") or ms.get("描述") or "",
            "key_technologies": ms.get("key_technologies") or ms.get("关键技术") or [],
            "trl_level": ms.get("trl_level") or ms.get("TRL等级") or ms.get("技术就绪水平"),
            "dependencies": ms.get("dependencies") or ms.get("依赖") or [],
            "uncertainty_level": ms.get("uncertainty_level") or ms.get("不确定性等级") or "medium"
        }

        if isinstance(milestone["trl_level"], str):
            try:
                milestone["trl_level"] = int(milestone["trl_level"])
            except (ValueError, TypeError):
                milestone["trl_level"] = None

        if milestone["trl_level"] is not None and not (1 <= milestone["trl_level"] <= 9):
            milestone["trl_level"] = None

        if not isinstance(milestone["key_technologies"], list):
            milestone["key_technologies"] = []

        if not isinstance(milestone["dependencies"], list):
            milestone["dependencies"] = []

        if milestone["uncertainty_level"] not in ("low", "medium", "high"):
            unc_map = {"低": "low", "中": "medium", "高": "high"}
            milestone["uncertainty_level"] = unc_map.get(milestone["uncertainty_level"], "medium")

        if milestone["name"] and milestone["description"]:
            milestones.append(milestone)

    return {
        "stage_description": str(stage_description),
        "milestones": milestones
    }


def parse_per_topic_roadmap_output(raw_text: str, topic_name: str = "") -> Dict[str, Any]:
    result = {
        "topic_name": topic_name,
        "roadmap": {}
    }

    if not raw_text or not raw_text.strip():
        logger.warning("输入为空，未提取到路线图数据")
        return result

    data = _extract_json_from_text(raw_text)
    if data is None:
        logger.warning("未能从输入中解析出JSON对象")
        return result

    roadmap_data = None
    for key in ["roadmap", "技术路线图", "timeline", "路线图", "stages", "phases"]:
        if key in data and isinstance(data[key], (dict, list)):
            roadmap_data = data[key]
            break

    if roadmap_data is None and isinstance(data, dict):
        stage_keys = ["2025", "2030", "2035", "2040"]
        if any(k in data for k in stage_keys):
            roadmap_data = data

    if roadmap_data is None and isinstance(data, list):
        if len(data) > 0 and isinstance(data[0], dict):
            roadmap_data = data

    if isinstance(roadmap_data, list):
        stage_order = ["2025", "2030", "2035", "2040"]
        mapped = {}
        for i, stage_item in enumerate(roadmap_data[:4]):
            if i < len(stage_order):
                mapped[stage_order[i]] = stage_item
            else:
                mapped[f"stage_{i}"] = stage_item
        if mapped:
            roadmap_data = mapped

    if not isinstance(roadmap_data, dict):
        logger.warning("未找到路线图数据结构")
        return result

    if roadmap_data is None:
        logger.warning("未找到路线图数据结构")
        return result

    roadmap = {}
    stage_order = ["2025", "2030", "2035", "2040"]

    for year in stage_order:
        if year in roadmap_data:
            normalized = _normalize_stage_data(roadmap_data[year])
            if normalized:
                roadmap[year] = normalized

    if not roadmap:
        logger.warning("未能解析出任何有效阶段数据")
        return result

    result["roadmap"] = roadmap
    logger.info(f"成功解析路线图，包含 {len(roadmap)} 个阶段")
    return result
