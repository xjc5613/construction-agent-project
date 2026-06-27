# -*- coding:utf-8-*-
from typing import List, Dict, Any
from config.settings import PROMPT_TEMPLATES_DIR
from src.utils.file_io import read_text

def _load_system() -> str:
    return read_text(PROMPT_TEMPLATES_DIR / "round2_system.txt") or ""

def _load_user_template() -> str:
    return read_text(PROMPT_TEMPLATES_DIR / "round2_user.txt") or ""

def build_round2_messages(round1_outputs: List[Dict[str, Any]]) -> list:
    system = _load_system()
    summaries = []
    for out in round1_outputs:
        summary = f"""
## 主题：{out.get('topic_name')}
- 瓶颈（2030-2035）: {', '.join(out.get('bottlenecks_2030_2035', []))}
- 突破（至2040）: {', '.join(out.get('breakthroughs_by_2040', []))}
- 深度融合主题: {', '.join(out.get('deep_fusion_topics', []))}
- 融合场景: {out.get('fusion_scenario', '')}
- 典型一天: {out.get('typical_day_2040', '')}
"""
        summaries.append(summary)
    user = _load_user_template().format(round1_summaries="\n".join(summaries))
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]