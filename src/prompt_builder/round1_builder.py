# -*- coding:utf-8-*-
import json
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
    abstracts = topic_input.get("sample_abstracts") or load_abstracts_for_topic(topic_input["topic_name"])
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
    if topic_input.get("evidence_package"):
        evidence_context = {
            "quality": topic_input.get("evidence_quality", {}),
            "ipc_evidence": topic_input.get("ipc_evidence_records", []),
            "paper_evidence": topic_input.get("paper_evidence_records", []),
            "material_evidence": topic_input.get("material_evidence_records", []),
        }
        user += (
            "\n\n=== 结构化证据包（只读）===\n"
            + json.dumps(evidence_context, ensure_ascii=False)
            + "\n\n请额外输出 ipc_inference、paper_inference、evidence_synthesis、"
              "evidence_conflicts 字段。每项核心结论必须包含 evidence_ids、"
              "confidence、assumptions、uncertainty_reason；不得生成证据包中不存在的统计值。"
        )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]
