# -*- coding:utf-8-*-
from typing import Dict, Any, List
from config.settings import PROMPT_TEMPLATES_DIR
from src.utils.file_io import read_text


def _load_system() -> str:
    return read_text(PROMPT_TEMPLATES_DIR / "per_topic_roadmap_system.txt") or ""


def _load_user_template() -> str:
    return read_text(PROMPT_TEMPLATES_DIR / "per_topic_roadmap_user.txt") or ""


def _format_list(items: List[str]) -> str:
    if not items:
        return "无"
    return "\n".join([f"- {item}" for item in items])


def build_per_topic_roadmap_messages(topic_data: Dict[str, Any]) -> list:
    system = _load_system()

    topic_name = topic_data.get("topic_name", topic_data.get("topic", ""))
    bottlenecks = topic_data.get("bottlenecks_2030_2035", [])
    breakthroughs = topic_data.get("breakthroughs_by_2040", [])
    fusion_topics = topic_data.get("deep_fusion_topics", [])
    fusion_scenario = topic_data.get("fusion_scenario", "")
    typical_day = topic_data.get("typical_day_2040", "")

    user = _load_user_template().format(
        topic_name=topic_name,
        bottlenecks=_format_list(bottlenecks),
        breakthroughs=_format_list(breakthroughs),
        fusion_topics=_format_list(fusion_topics),
        fusion_scenario=fusion_scenario if fusion_scenario else "无",
        typical_day=typical_day if typical_day else "无"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]
