# -*- coding:utf-8-*-
from jsonschema import validate, ValidationError
from typing import Dict, Any
from .logger import get_logger

logger = get_logger(__name__)

ROUND1_SCHEMA = {
    "type": "object",
    "properties": {
        "topic_name": {"type": "string"},
        "bottlenecks_2030_2035": {"type": "array", "items": {"type": "string"}},
        "breakthroughs_by_2040": {"type": "array", "items": {"type": "string"}},
        "deep_fusion_topics": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 2},
        "fusion_scenario": {"type": "string"},
        "typical_day_2040": {"type": "string", "maxLength": 200}
    },
    "required": ["topic_name", "bottlenecks_2030_2035", "breakthroughs_by_2040",
                 "deep_fusion_topics", "fusion_scenario", "typical_day_2040"]
}

def validate_round1_output(data: Dict[str, Any]) -> bool:
    try:
        validate(instance=data, schema=ROUND1_SCHEMA)
        return True
    except ValidationError as e:
        logger.error(f"格式校验失败: {e.message}")
        return False