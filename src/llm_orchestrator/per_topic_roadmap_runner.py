# -*- coding:utf-8 -*-
import re
from typing import List, Dict, Any
from config.settings import (
    OUTPUTS_PARSED,
    ENABLE_SELF_CONSISTENCY, SELF_CONSISTENCY_SAMPLES,
    SELF_CONSISTENCY_TEMPERATURE_MIN, SELF_CONSISTENCY_TEMPERATURE_MAX,
    CONFIDENCE_THRESHOLD,
    ENABLE_MULTI_MODEL, MULTI_MODEL_LIST, MULTI_MODEL_STRATEGY,
    ENABLE_MULTI_AGENT_DEBATE, DEBATE_ROUNDS, DEBATE_AGENTS
)
from src.utils.api_client import LLMClient, MultiModelClient
from src.utils.logger import get_logger
from src.utils.file_io import write_json, read_json
from src.prompt_builder import build_per_topic_roadmap_messages
from src.output_parser import parse_per_topic_roadmap_output
from .self_consistency import SelfConsistencyEngine
from .ensemble import EnsembleEngine
from .debate import DebateEngine

logger = get_logger(__name__)


def _safe_filename(name: str) -> str:
    if not name:
        return "unnamed"
    safe = re.sub(r'[\\/:*?"<>|\s]+', '_', name)
    safe = safe.strip('._')
    return safe or "unnamed"


def _run_single_roadmap(client, topic_data: Dict[str, Any]) -> Dict[str, Any]:
    msgs = build_per_topic_roadmap_messages(topic_data)
    resp = client.chat_completion(msgs)
    if not resp:
        logger.error("单主题路线图 API 失败")
        return {}
    topic_name = topic_data.get("topic_name", topic_data.get("topic", ""))
    parsed = parse_per_topic_roadmap_output(resp, topic_name)
    if parsed and parsed.get("roadmap"):
        return parsed
    return {}


def _run_self_consistency_roadmap(client, topic_data: Dict[str, Any]) -> Dict[str, Any]:
    msgs = build_per_topic_roadmap_messages(topic_data)
    topic_name = topic_data.get("topic_name", topic_data.get("topic", ""))
    engine = SelfConsistencyEngine(
        llm_client=client,
        num_samples=SELF_CONSISTENCY_SAMPLES,
        temp_min=SELF_CONSISTENCY_TEMPERATURE_MIN,
        temp_max=SELF_CONSISTENCY_TEMPERATURE_MAX,
        confidence_threshold=CONFIDENCE_THRESHOLD
    )
    result = engine.run(msgs, parse_per_topic_roadmap_output, parser_args=(topic_name,))
    if not result.get("success"):
        logger.error("单主题路线图自洽性验证全部失败")
        return {}
    return result


def _run_debate_roadmap(client, topic_data: Dict[str, Any]) -> Dict[str, Any]:
    msgs = build_per_topic_roadmap_messages(topic_data)
    topic_name = topic_data.get("topic_name", topic_data.get("topic", ""))
    initial_resp = client.chat_completion(msgs)
    if not initial_resp:
        logger.error("单主题路线图初始预测失败，无法启动辩论")
        return {}
    initial_parsed = parse_per_topic_roadmap_output(initial_resp, topic_name)
    if not initial_parsed or not initial_parsed.get("roadmap"):
        logger.error("单主题路线图初始结果解析失败，无法启动辩论")
        return {}

    context_info = f"主题名称：{topic_name}\n关键信息：瓶颈 {len(topic_data.get('bottlenecks_2030_2035', []))} 项，突破 {len(topic_data.get('breakthroughs_by_2040', []))} 项"
    engine = DebateEngine(
        llm_client=client,
        agents=DEBATE_AGENTS,
        num_rounds=DEBATE_ROUNDS,
        confidence_threshold=CONFIDENCE_THRESHOLD
    )
    result = engine.run(
        initial_messages=msgs,
        initial_result=initial_parsed,
        parser_func=parse_per_topic_roadmap_output,
        parser_args=(topic_name,),
        context_info=context_info
    )
    if not result.get("debate_info", {}).get("success"):
        logger.error("单主题路线图辩论失败")
        return {}
    return result


def _run_multi_model_roadmap(multi_client, topic_data: Dict[str, Any]) -> Dict[str, Any]:
    msgs = build_per_topic_roadmap_messages(topic_data)
    topic_name = topic_data.get("topic_name", topic_data.get("topic", ""))
    engine = EnsembleEngine(
        multi_model_client=multi_client,
        parser_func=parse_per_topic_roadmap_output,
        strategy=MULTI_MODEL_STRATEGY,
        confidence_threshold=CONFIDENCE_THRESHOLD
    )
    result = engine.run(msgs, parser_args=(topic_name,))
    if not result.get("success"):
        logger.error("单主题路线图多模型集成都失败")
        return {}
    return result


def _extract_roadmap_data(result: Dict[str, Any], topic_name: str = "") -> Dict[str, Any]:
    if not result:
        return {}
    if "roadmap" in result:
        return result
    if "final_result" in result:
        final = result["final_result"]
        if isinstance(final, dict) and "roadmap" in final:
            return final
    if "consensus_result" in result:
        cons = result["consensus_result"]
        if isinstance(cons, dict) and "roadmap" in cons:
            return cons
    if "result" in result:
        res = result["result"]
        if isinstance(res, dict) and "roadmap" in res:
            return res
    if "debate_info" in result:
        di = result["debate_info"]
        if isinstance(di, dict):
            final_ans = di.get("final_answer") or di.get("consensus")
            if isinstance(final_ans, dict) and "roadmap" in final_ans:
                return final_ans
    for key in ("best_result", "top_result", "selected_result"):
        if key in result:
            val = result[key]
            if isinstance(val, dict) and "roadmap" in val:
                return val
    return {}


def _fill_missing_stages(roadmap_data: Dict[str, Any], topic_name: str = "") -> Dict[str, Any]:
    from config.settings import PER_TOPIC_ROADMAP_STAGES

    if not roadmap_data or "roadmap" not in roadmap_data:
        roadmap_data = {"topic_name": topic_name, "roadmap": {}}

    roadmap = roadmap_data.get("roadmap", {})
    filled_stages = {}
    prev_milestones = []

    for stage in PER_TOPIC_ROADMAP_STAGES:
        if stage in roadmap and roadmap[stage] and roadmap[stage].get("milestones"):
            filled_stages[stage] = roadmap[stage]
            prev_milestones = roadmap[stage].get("milestones", [])
        else:
            if prev_milestones:
                desc = f"基于前一阶段技术持续优化，推动{topic_name}向更深层次发展"
            else:
                desc = f"{topic_name}技术基础建设与初步应用阶段"
            filled_stages[stage] = {
                "stage_description": desc,
                "milestones": [
                    {
                        "name": f"{stage}年持续优化",
                        "description": desc,
                        "key_technologies": ["持续优化", "技术迭代"],
                        "trl_level": min(9, 2 + PER_TOPIC_ROADMAP_STAGES.index(stage) * 2),
                        "dependencies": [f"前序阶段技术基础"],
                        "uncertainty_level": "medium"
                    }
                ]
            }
            if prev_milestones:
                filled_stages[stage]["milestones"][0]["dependencies"] = [
                    m.get("name", "") for m in prev_milestones[:2]
                ]

    roadmap_data["roadmap"] = filled_stages
    if not roadmap_data.get("topic_name"):
        roadmap_data["topic_name"] = topic_name

    return roadmap_data


def _run_with_fallback(client, topic_data: Dict[str, Any]) -> Dict[str, Any]:
    topic_name = topic_data.get("topic_name", topic_data.get("topic", ""))

    if ENABLE_MULTI_AGENT_DEBATE:
        logger.info(f"  尝试模式: 多Agent辩论")
        result = _run_debate_roadmap(client, topic_data)
        extracted = _extract_roadmap_data(result, topic_name)
        if extracted and extracted.get("roadmap"):
            logger.info(f"  多Agent辩论模式成功")
            if "debate_info" in result:
                extracted["debate_info"] = result["debate_info"]
            if "confidence" in result:
                extracted["confidence"] = result["confidence"]
            return _fill_missing_stages(extracted, topic_name)
        logger.warning(f"  多Agent辩论模式失败，降级到自洽性验证")

    if ENABLE_SELF_CONSISTENCY:
        logger.info(f"  尝试模式: 自洽性验证")
        result = _run_self_consistency_roadmap(client, topic_data)
        extracted = _extract_roadmap_data(result, topic_name)
        if extracted and extracted.get("roadmap"):
            logger.info(f"  自洽性验证模式成功")
            if "confidence" in result:
                extracted["confidence"] = result["confidence"]
            if "vote_scores" in result:
                extracted["vote_scores"] = result["vote_scores"]
            return _fill_missing_stages(extracted, topic_name)
        logger.warning(f"  自洽性验证模式失败，降级到单模型")

    logger.info(f"  使用模式: 单模型")
    for attempt in range(2):
        result = _run_single_roadmap(client, topic_data)
        if result and result.get("roadmap"):
            logger.info(f"  单模型模式成功（第{attempt + 1}次尝试）")
            return _fill_missing_stages(result, topic_name)
        if attempt == 0:
            logger.warning(f"  单模型第1次失败，重试...")

    logger.error(f"  所有模式均失败，使用兜底数据")
    fallback = _fill_missing_stages({}, topic_name)
    fallback["is_fallback"] = True
    return fallback


def run_per_topic_roadmap(topic_data: Dict[str, Any], force_rerun: bool = False) -> Dict[str, Any]:
    topic_name = topic_data.get("topic_name", topic_data.get("topic", ""))
    safe_name = _safe_filename(topic_name)
    parsed_path = OUTPUTS_PARSED / f"per_topic_roadmap_{safe_name}.json"

    if not force_rerun and parsed_path.exists():
        logger.info(f"加载缓存单主题路线图: {topic_name}")
        cached = read_json(parsed_path)
        if cached:
            return cached

    logger.info(f"开始生成单主题路线图: {topic_name}")

    use_multi_model = ENABLE_MULTI_MODEL and bool(MULTI_MODEL_LIST)

    if use_multi_model:
        multi_client = MultiModelClient(
            model_configs=MULTI_MODEL_LIST,
            strategy=MULTI_MODEL_STRATEGY
        )
        result = _run_multi_model_roadmap(multi_client, topic_data)
        parsed = _extract_roadmap_data(result, topic_name)
        if not parsed or not parsed.get("roadmap"):
            logger.warning(f"多模型集成失败，降级到单模型")
            client = LLMClient()
            parsed = _run_with_fallback(client, topic_data)
    else:
        client = LLMClient()
        parsed = _run_with_fallback(client, topic_data)

    if parsed:
        write_json(parsed, parsed_path)
        logger.info(f"单主题路线图生成完成: {topic_name}")
        return parsed
    logger.error(f"单主题路线图生成失败: {topic_name}")
    return {}


def run_all_topics_roadmap(round1_results: List[Dict[str, Any]], force_rerun: bool = False) -> List[Dict[str, Any]]:
    all_roadmaps = []
    total = len(round1_results)

    logger.info(f"开始批量生成主题路线图，共 {total} 个主题")

    for idx, topic_data in enumerate(round1_results):
        topic_name = topic_data.get("topic_name", topic_data.get("topic", f"主题_{idx + 1}"))
        logger.info(f"[{idx + 1}/{total}] 开始处理主题: {topic_name}")

        try:
            roadmap = run_per_topic_roadmap(topic_data, force_rerun=force_rerun)
            if roadmap:
                all_roadmaps.append(roadmap)
                logger.info(f"[{idx + 1}/{total}] 主题完成: {topic_name}")
            else:
                logger.warning(f"[{idx + 1}/{total}] 主题生成结果为空: {topic_name}")
        except Exception as e:
            logger.error(f"[{idx + 1}/{total}] 主题处理异常: {topic_name}, 错误: {e}")
            continue

    logger.info(f"批量生成完成，成功 {len(all_roadmaps)}/{total} 个主题")

    output_path = OUTPUTS_PARSED / "per_topic_roadmaps_all.json"
    write_json(all_roadmaps, output_path)

    return all_roadmaps
