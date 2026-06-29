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
from src.prompt_builder import build_round2_messages
from src.output_parser import parse_round2_output
from .self_consistency import SelfConsistencyEngine
from .ensemble import EnsembleEngine
from .debate import DebateEngine

logger = get_logger(__name__)


def _run_single_round2(client, round1_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
    msgs = build_round2_messages(round1_outputs)
    resp = client.chat_completion(msgs)
    if not resp:
        logger.error("第二轮 API 失败")
        return {}
    parsed = parse_round2_output(resp)
    if parsed:
        return parsed
    return {}


def _run_self_consistency_round2(client, round1_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
    msgs = build_round2_messages(round1_outputs)
    engine = SelfConsistencyEngine(
        llm_client=client,
        num_samples=SELF_CONSISTENCY_SAMPLES,
        temp_min=SELF_CONSISTENCY_TEMPERATURE_MIN,
        temp_max=SELF_CONSISTENCY_TEMPERATURE_MAX,
        confidence_threshold=CONFIDENCE_THRESHOLD
    )
    result = engine.run(msgs, parse_round2_output)
    if not result.get("success"):
        logger.error("第二轮自洽性验证全部失败")
        return {}
    return result


def _run_multi_model_round2(multi_client, round1_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
    msgs = build_round2_messages(round1_outputs)
    engine = EnsembleEngine(
        multi_model_client=multi_client,
        parser_func=parse_round2_output,
        strategy=MULTI_MODEL_STRATEGY,
        confidence_threshold=CONFIDENCE_THRESHOLD
    )
    result = engine.run(msgs)
    if not result.get("success"):
        logger.error("第二轮多模型集成都失败")
        return {}
    return result


def _run_debate_round2(client, round1_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
    msgs = build_round2_messages(round1_outputs)
    initial_resp = client.chat_completion(msgs)
    if not initial_resp:
        logger.error("第二轮初始预测失败，无法启动辩论")
        return {}
    initial_parsed = parse_round2_output(initial_resp)
    if not initial_parsed:
        logger.error("第二轮初始结果解析失败，无法启动辩论")
        return {}

    context_info = f"第一轮主题数量：{len(round1_outputs)}"
    engine = DebateEngine(
        llm_client=client,
        agents=DEBATE_AGENTS,
        num_rounds=DEBATE_ROUNDS,
        confidence_threshold=CONFIDENCE_THRESHOLD
    )
    result = engine.run(
        initial_messages=msgs,
        initial_result=initial_parsed,
        parser_func=parse_round2_output,
        context_info=context_info
    )
    if not result.get("debate_info", {}).get("success"):
        logger.error("第二轮辩论失败")
        return {}
    return result


def run_round2(round1_outputs: List[Dict[str, Any]], force_rerun: bool = False) -> Dict[str, str]:
    use_multi_model = ENABLE_MULTI_MODEL and bool(MULTI_MODEL_LIST)

    if use_multi_model:
        multi_client = MultiModelClient(
            model_configs=MULTI_MODEL_LIST,
            strategy=MULTI_MODEL_STRATEGY
        )
    else:
        client = LLMClient()

    raw_path = OUTPUTS_RAW / "round2_response.json"
    parsed_path = OUTPUTS_PARSED / "round2_paradigm.json"
    if not force_rerun and parsed_path.exists():
        logger.info("加载缓存第二轮")
        cached = read_json(parsed_path)
        if cached:
            return cached
    logger.info("开始第二轮预测")

    if use_multi_model:
        parsed = _run_multi_model_round2(multi_client, round1_outputs)
    elif ENABLE_MULTI_AGENT_DEBATE:
        parsed = _run_debate_round2(client, round1_outputs)
    elif ENABLE_SELF_CONSISTENCY:
        parsed = _run_self_consistency_round2(client, round1_outputs)
    else:
        parsed = _run_single_round2(client, round1_outputs)

    if parsed:
        write_json(parsed, parsed_path)
        return parsed
    return {}