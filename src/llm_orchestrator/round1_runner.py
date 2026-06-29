# -*- coding:utf-8 -*-
from typing import List, Dict, Any
from config.settings import (
    OUTPUTS_RAW, OUTPUTS_PARSED,
    ENABLE_SELF_CONSISTENCY, SELF_CONSISTENCY_SAMPLES,
    SELF_CONSISTENCY_TEMPERATURE_MIN, SELF_CONSISTENCY_TEMPERATURE_MAX,
    CONFIDENCE_THRESHOLD,
    ENABLE_MULTI_MODEL, MULTI_MODEL_LIST, MULTI_MODEL_STRATEGY,
    ENABLE_MULTI_AGENT_DEBATE, DEBATE_ROUNDS, DEBATE_AGENTS
)
from src.utils.api_client import LLMClient, MultiModelClient
from src.utils.logger import get_logger
from src.utils.file_io import write_json, read_json
from src.prompt_builder import build_round1_messages
from src.output_parser import parse_round1_output
from .self_consistency import SelfConsistencyEngine
from .ensemble import EnsembleEngine
from .debate import DebateEngine

logger = get_logger(__name__)


def _run_single_round1(client, inp: Dict[str, Any]) -> Dict[str, Any]:
    name = inp["topic_name"]
    msgs = build_round1_messages(inp)
    resp = client.chat_completion(msgs)
    if not resp:
        logger.error(f"主题 {name} API 失败")
        return None
    parsed = parse_round1_output(resp, name)
    if parsed:
        logger.info(f"完成: {name}")
        return parsed
    else:
        logger.error(f"解析失败: {name}")
        return None


def _run_self_consistency_round1(client, inp: Dict[str, Any]) -> Dict[str, Any]:
    name = inp["topic_name"]
    msgs = build_round1_messages(inp)
    engine = SelfConsistencyEngine(
        llm_client=client,
        num_samples=SELF_CONSISTENCY_SAMPLES,
        temp_min=SELF_CONSISTENCY_TEMPERATURE_MIN,
        temp_max=SELF_CONSISTENCY_TEMPERATURE_MAX,
        confidence_threshold=CONFIDENCE_THRESHOLD
    )
    result = engine.run(msgs, parse_round1_output, parser_args=(name,))
    if not result.get("success"):
        logger.error(f"主题 {name} 自洽性验证全部失败")
        return None
    return result


def _run_multi_model_round1(multi_client, inp: Dict[str, Any]) -> Dict[str, Any]:
    name = inp["topic_name"]
    msgs = build_round1_messages(inp)
    engine = EnsembleEngine(
        multi_model_client=multi_client,
        parser_func=parse_round1_output,
        strategy=MULTI_MODEL_STRATEGY,
        confidence_threshold=CONFIDENCE_THRESHOLD
    )
    result = engine.run(msgs, parser_args=(name,))
    if not result.get("success"):
        logger.error(f"主题 {name} 多模型集成都失败")
        return None
    return result


def _run_debate_round1(client, inp: Dict[str, Any]) -> Dict[str, Any]:
    name = inp["topic_name"]
    msgs = build_round1_messages(inp)
    initial_resp = client.chat_completion(msgs)
    if not initial_resp:
        logger.error(f"主题 {name} 初始预测失败，无法启动辩论")
        return None
    initial_parsed = parse_round1_output(initial_resp, name)
    if not initial_parsed:
        logger.error(f"主题 {name} 初始结果解析失败，无法启动辩论")
        return None

    context_info = f"主题名称：{inp.get('topic_name', '')}\n关键词：{', '.join(inp.get('keywords', []))}"
    engine = DebateEngine(
        llm_client=client,
        agents=DEBATE_AGENTS,
        num_rounds=DEBATE_ROUNDS,
        confidence_threshold=CONFIDENCE_THRESHOLD
    )
    result = engine.run(
        initial_messages=msgs,
        initial_result=initial_parsed,
        parser_func=parse_round1_output,
        parser_args=(name,),
        context_info=context_info
    )
    if not result.get("debate_info", {}).get("success"):
        logger.error(f"主题 {name} 辩论失败")
        return None
    return result


def run_round1(topic_inputs: List[Dict[str, Any]], force_rerun: bool = False) -> List[Dict[str, Any]]:
    use_multi_model = ENABLE_MULTI_MODEL and bool(MULTI_MODEL_LIST)

    if use_multi_model:
        multi_client = MultiModelClient(
            model_configs=MULTI_MODEL_LIST,
            strategy=MULTI_MODEL_STRATEGY
        )
    else:
        client = LLMClient()

    results = []
    for inp in topic_inputs:
        name = inp["topic_name"]
        raw_path = OUTPUTS_RAW / f"round1_{name}.json"
        parsed_path = OUTPUTS_PARSED / f"round1_{name}.json"
        if not force_rerun and parsed_path.exists():
            logger.info(f"加载缓存: {name}")
            cached = read_json(parsed_path)
            if cached:
                results.append(cached)
                continue
        logger.info(f"处理主题: {name}")

        if use_multi_model:
            parsed = _run_multi_model_round1(multi_client, inp)
        elif ENABLE_MULTI_AGENT_DEBATE:
            parsed = _run_debate_round1(client, inp)
        elif ENABLE_SELF_CONSISTENCY:
            parsed = _run_self_consistency_round1(client, inp)
        else:
            parsed = _run_single_round1(client, inp)

        if parsed:
            write_json(parsed, parsed_path)
            results.append(parsed)
    logger.info(f"第一轮完成: {len(results)}/{len(topic_inputs)}")
    return results