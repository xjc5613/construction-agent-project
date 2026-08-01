# -*- coding:utf-8 -*-
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List
from uuid import uuid4

from config.settings import DATA_RAW, PROMPT_TEMPLATES_DIR
from src.utils.api_client import LLMClient
from src.utils.file_io import read_json, read_text

from .storage import WorkbenchStorage

IPC_PATTERN = re.compile(r"([A-H]\d{2}[A-Z](?:[-－]?\d{1,4})?)")
PROB_PATTERN = re.compile(
    r"([A-H]\d{2}[A-Z])\s*(?:与|和|[-—])\s*([A-H]\d{2}[A-Z]).{0,24}?融合概率\s*[为:：]?\s*(0?\.\d+|1(?:\.0+)?)"
)
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[。！？；\n])")


def _clean_text(content: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]{2,}", " ", content)).strip()


def _sentences(content: str) -> List[str]:
    return [sentence.strip() for sentence in SENTENCE_SPLIT_PATTERN.split(content) if sentence.strip()]


def _load_seed_topics() -> List[Dict[str, Any]]:
    topics = read_json(DATA_RAW / "topics.json") or []
    pairs = read_json(DATA_RAW / "high_potential_pairs.json") or []
    pairs_by_topic = {item.get("topic_name"): item.get("pairs", []) for item in pairs}
    for topic in topics:
        topic["fusion_pairs"] = pairs_by_topic.get(topic.get("name"), [])
    return topics


def _evidence_sentences(content: str, terms: Iterable[str]) -> List[str]:
    lowered = [term.lower() for term in terms if term]
    matches = []
    for sentence in _sentences(content):
        if any(term in sentence.lower() for term in lowered):
            matches.append(sentence[:500])
    return matches[:3]


def _extract_ipc_evidence(content: str, document_id: str) -> List[Dict[str, str]]:
    evidence = []
    for sentence in _sentences(content):
        codes = IPC_PATTERN.findall(sentence)
        for code in dict.fromkeys(codes):
            evidence.append({
                "ipc": code,
                "trend": sentence[:500],
                "quote": sentence[:500],
                "document_id": document_id,
            })
    return sorted(evidence, key=lambda item: ("-" not in item["ipc"], item["ipc"]))


def _extract_pairs(content: str) -> List[Dict[str, Any]]:
    pairs = []
    for ipc1, ipc2, prob in PROB_PATTERN.findall(content):
        pairs.append({"ipc1": ipc1, "ipc2": ipc2, "prob": float(prob)})
    return pairs


def extract_topics_from_document(
    content: str, document_id: str, include_seed_topics: bool = True
) -> List[Dict[str, Any]]:
    """Build transparent candidate topics from seed topics and document evidence."""
    candidates: List[Dict[str, Any]] = []
    ipc_evidence = _extract_ipc_evidence(content, document_id)
    document_pairs = _extract_pairs(content)

    if include_seed_topics:
        for seed in _load_seed_topics():
            name = seed.get("name", "")
            keywords = seed.get("keywords", [])
            snippets = _evidence_sentences(content, [name, *keywords])
            seed_ipcs = set(IPC_PATTERN.findall(seed.get("ipc_trend", "")))
            relevant_ipcs = [
                item for item in ipc_evidence if item["ipc"].split("-")[0] in seed_ipcs
            ]
            relevant_ipcs.sort(key=lambda item: ("-" not in item["ipc"], item["ipc"]))
            if not snippets and not relevant_ipcs:
                continue
            evidence_score = min(100, len(snippets) * 28 + len(relevant_ipcs) * 18 + 18)
            candidates.append({
                "topic_id": f"topic_{uuid4().hex[:12]}",
                "topic_name": name,
                "keywords": keywords,
                "example": seed.get("example", ""),
                "ipc_evidence": relevant_ipcs or ipc_evidence[:3],
                "ipc_trend": seed.get("ipc_trend", ""),
                "fusion_pairs": seed.get("fusion_pairs", []) or document_pairs,
                "sample_abstracts": snippets,
                "operator_notes": "",
                "evidence_score": evidence_score,
                "requires_review": not bool(snippets or relevant_ipcs),
                "selected": True,
            })

    if not candidates and (ipc_evidence or content):
        candidates.append({
            "topic_id": f"topic_{uuid4().hex[:12]}",
            "topic_name": "待校准技术主题",
            "keywords": list(dict.fromkeys(IPC_PATTERN.findall(content)))[:5],
            "example": "",
            "ipc_evidence": ipc_evidence[:6],
            "ipc_trend": "从研究文档抽取，需人工补充技术趋势。",
            "fusion_pairs": document_pairs,
            "sample_abstracts": _sentences(content)[:3],
            "operator_notes": "",
            "evidence_score": 20 if ipc_evidence else 10,
            "requires_review": True,
            "selected": False,
        })
    return candidates


def _extract_json_object(content: str) -> Dict[str, Any]:
    try:
        return json.loads(content)
    except (TypeError, ValueError):
        pass
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content or "", re.IGNORECASE)
    if match:
        try:
            return json.loads(match.group(1))
        except ValueError:
            return {}
    return {}


def refine_topics_with_llm(candidates: List[Dict[str, Any]], content: str) -> List[Dict[str, Any]]:
    """Optionally let the configured LLM refine candidate labels without losing evidence."""
    template_path = PROMPT_TEMPLATES_DIR / "topic_extraction_user.txt"
    template = read_text(template_path) or ""
    if not template:
        return candidates
    try:
        client = LLMClient()
        prompt = template.format(
            candidates=json.dumps(candidates, ensure_ascii=False),
            document=content[:12000],
        )
        response = client.chat_completion([
            {"role": "system", "content": "你是技术预测研究助理，只能基于给定证据校正候选主题。"},
            {"role": "user", "content": prompt},
        ])
        payload = _extract_json_object(response or "")
        refinements = payload.get("topics", [])
        if not isinstance(refinements, list):
            return candidates
        by_id = {topic["topic_id"]: topic for topic in candidates}
        for refined in refinements:
            topic_id = refined.get("topic_id")
            original = by_id.get(topic_id)
            if not original:
                continue
            original["topic_name"] = str(refined.get("topic_name") or original["topic_name"])
            keywords = refined.get("keywords")
            if isinstance(keywords, list):
                original["keywords"] = [str(item) for item in keywords[:12]]
            original["requires_review"] = bool(refined.get("requires_review", False))
        return candidates
    except Exception:
        return candidates


def persist_extracted_topics(
    storage: WorkbenchStorage, topics: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    existing = {topic["topic_id"]: topic for topic in storage.list_topics()}
    existing.update({topic["topic_id"]: topic for topic in topics})
    result = list(existing.values())
    storage.save_topics(result)
    return result


def normalize_topic(topic: Dict[str, Any]) -> Dict[str, Any]:
    evidence = topic.get("ipc_evidence", [])
    evidence_trends = [
        f"{item.get('ipc', '')}：{item.get('trend') or item.get('quote', '')}"
        for item in evidence
    ]
    abstracts = topic.get("sample_abstracts", [])
    evidence_package = topic.get("evidence_package", {})
    active_items = [
        item for item in evidence_package.get("items", [])
        if not item.get("excluded")
    ]
    evidence_ids = [item.get("evidence_id") for item in active_items if item.get("evidence_id")]
    return {
        "topic_name": topic["topic_name"],
        "keywords": topic.get("keywords", []),
        "example": topic.get("example", ""),
        "ipc_trend": topic.get("ipc_trend") or "\n".join(evidence_trends),
        "fusion_pairs": topic.get("fusion_pairs", []),
        "sample_abstracts": "\n".join(abstracts),
        "operator_notes": topic.get("operator_notes", ""),
        "evidence_package": evidence_package,
        "evidence_ids": evidence_ids,
        "ipc_evidence_records": [
            item for item in active_items
            if item.get("evidence_type") in {"ipc_metric", "ipc_fusion"}
        ],
        "paper_evidence_records": [
            item for item in active_items if item.get("evidence_type") == "paper"
        ],
        "material_evidence_records": [
            item for item in active_items if item.get("evidence_type") == "material"
        ],
        "evidence_quality": evidence_package.get("quality", {}),
    }
