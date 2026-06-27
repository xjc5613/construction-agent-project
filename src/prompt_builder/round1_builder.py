# -*- coding:utf-8-*-
from pathlib import Path
from typing import Dict, Any
from config.settings import PROMPT_TEMPLATES_DIR
from src.utils.file_io import read_text
from src.data_preparation.sample_abstracts import load_abstracts_for_topic

def _load_system() -> str:
    return read_text(PROMPT_TEMPLATES_DIR / "round1_system.txt") or ""

def _load_user_template() -> str:
    return read_text(PROMPT_TEMPLATES_DIR / "round1_user.txt") or ""

def build_round1_messages(topic_input: Dict[str, Any]) -> list:
    system = _load_system()
    abstracts = load_abstracts_for_topic(topic_input["topic_name"])
    fusion_str = ""
    for p in topic_input.get("fusion_pairs", []):
        fusion_str += f"- {p['ipc1']} 与 {p['ipc2']} (概率: {p.get('prob', 0.0)})\n"
    user = _load_user_template().format(
        topic_name=topic_input["topic_name"],
        keywords=", ".join(topic_input.get("keywords", [])),
        example=topic_input.get("example", ""),
        ipc_trend=topic_input.get("ipc_trend", ""),
        fusion_pairs=fusion_str,
        sample_abstracts=abstracts if abstracts else "（无额外示例）"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]