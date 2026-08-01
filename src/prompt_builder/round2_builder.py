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
- IPC推断: {out.get('ipc_inference', [])}
- 论文方向推断: {out.get('paper_inference', [])}
- 双证据综合: {out.get('evidence_synthesis', [])}
- 证据冲突: {out.get('evidence_conflicts', [])}
- 证据引用: {out.get('evidence_ids', [])}
"""
        summaries.append(summary)
    user = _load_user_template().format(round1_summaries="\n".join(summaries))
    user += (
        "\n\n范式归纳必须保留 evidence_synthesis、evidence_conflicts 和 evidence_ids，"
        "明确哪些主题的 IPC 与论文证据收敛或冲突。"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]
