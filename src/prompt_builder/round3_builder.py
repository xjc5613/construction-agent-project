# -*- coding:utf-8-*-
import json
from typing import List, Dict, Any
from config.settings import PROMPT_TEMPLATES_DIR
from src.utils.file_io import read_text

def _load_system() -> str:
    return read_text(PROMPT_TEMPLATES_DIR / "round3_system.txt") or ""

def _load_user_template() -> str:
    return read_text(PROMPT_TEMPLATES_DIR / "round3_user.txt") or ""

def build_round3_messages(round1_outputs: List[Dict[str, Any]], round2_output: Dict[str, str]) -> list:
    system = _load_system()
    time_snippets = []
    for out in round1_outputs:
        time_snippets.append(
            json.dumps({
                "topic_name": out.get("topic_name"),
                "bottlenecks_2030_2035": out.get("bottlenecks_2030_2035", []),
                "breakthroughs_by_2040": out.get("breakthroughs_by_2040", []),
                "ipc_inference": out.get("ipc_inference", []),
                "paper_inference": out.get("paper_inference", []),
                "evidence_synthesis": out.get("evidence_synthesis", []),
                "evidence_conflicts": out.get("evidence_conflicts", []),
                "evidence_ids": out.get("evidence_ids", []),
            }, ensure_ascii=False)
        )
    user = _load_user_template().format(
        new_paradigm_name=round2_output.get("new_paradigm_name", ""),
        new_paradigm_desc=round2_output.get("new_paradigm_description", ""),
        time_snippets="\n".join(time_snippets)
    )
    user += (
        "\n\n不得只使用每个主题的首条结论。每个路线节点必须标注 evidence_ids、"
        "confidence、assumptions 和 uncertainty_reason，并保留证据冲突。"
    )
    context = round1_outputs[0].get("_forecast_context", {}) if round1_outputs else {}
    if context:
        user += (
            "\n\n=== 项目预测合同 ===\n"
            + json.dumps(context, ensure_ascii=False)
            + "\n路线图只能输出 forecast_nodes 中的年份，不得补充目标年份之后的节点。"
        )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]
