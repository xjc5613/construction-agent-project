# -*- coding:utf-8-*-
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
        if out.get('bottlenecks_2030_2035'):
            time_snippets.append(f"主题 {out['topic_name']} 瓶颈: {out['bottlenecks_2030_2035'][0]}")
        if out.get('breakthroughs_by_2040'):
            time_snippets.append(f"主题 {out['topic_name']} 突破: {out['breakthroughs_by_2040'][0]}")
    user = _load_user_template().format(
        new_paradigm_name=round2_output.get("new_paradigm_name", ""),
        new_paradigm_desc=round2_output.get("new_paradigm_description", ""),
        time_snippets="\n".join(time_snippets)
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]