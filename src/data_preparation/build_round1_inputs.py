# -*- coding:utf-8-*-
from typing import List, Dict, Any
from config.settings import DATA_PROCESSED
from src.utils.file_io import write_json
from src.utils.logger import get_logger
from .extract_from_chenke import load_topics, load_high_potential_pairs

logger = get_logger(__name__)

def build_round1_inputs() -> List[Dict[str, Any]]:
    topics = load_topics()
    all_pairs = load_high_potential_pairs()
    topic_to_pairs = {pair["topic_name"]: pair["pairs"] for pair in all_pairs}
    inputs = []
    for topic in topics:
        name = topic["name"]
        input_dict = {
            "topic_name": name,
            "keywords": topic.get("keywords", []),
            "example": topic.get("example", ""),
            "ipc_trend": topic.get("ipc_trend", ""),
            "fusion_pairs": topic_to_pairs.get(name, [])
        }
        inputs.append(input_dict)
        out_file = DATA_PROCESSED / "round1_inputs" / f"{name}.json"
        write_json(input_dict, out_file)
        logger.info(f"生成第一轮输入: {out_file}")
    return inputs