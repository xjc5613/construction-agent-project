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
from src.prompt_builder import build_round3_messages
from src.output_parser import parse_round3_output
from .self_consistency import SelfConsistencyEngine
from .ensemble import EnsembleEngine
from .debate import DebateEngine

logger = get_logger(__name__)


def _run_single_round3(client, round1_outputs: List[Dict[str, Any]], round2_output: Dict[str, str]) -> List[Dict[str, Any]]:
    msgs = build_round3_messages(round1_outputs, round2_output)
    resp = client.chat_completion(msgs)
    if not resp:
        logger.error("第三轮 API 失败")
        return []
    parsed = parse_round3_output(resp)
    if parsed:
        return parsed
    return []


def _run_self_consistency_round3(client, round1_outputs: List[Dict[str, Any]], round2_output: Dict[str, str]) -> Dict[str, Any]:
    msgs = build_round3_messages(round1_outputs, round2_output)
    engine = SelfConsistencyEngine(
        llm_client=client,
        num_samples=SELF_CONSISTENCY_SAMPLES,
        temp_min=SELF_CONSISTENCY_TEMPERATURE_MIN,
        temp_max=SELF_CONSISTENCY_TEMPERATURE_MAX,
        confidence_threshold=CONFIDENCE_THRESHOLD
    )
    result = engine.run(msgs, parse_round3_output)
    if not result.get("success"):
        logger.error("第三轮自洽性验证全部失败")
        return []
    return result


def _run_multi_model_round3(multi_client, round1_outputs: List[Dict[str, Any]], round2_output: Dict[str, str]) -> Dict[str, Any]:
    msgs = build_round3_messages(round1_outputs, round2_output)
    engine = EnsembleEngine(
        multi_model_client=multi_client,
        parser_func=parse_round3_output,
        strategy=MULTI_MODEL_STRATEGY,
        confidence_threshold=CONFIDENCE_THRESHOLD
    )
    result = engine.run(msgs)
    if not result.get("success"):
        logger.error("第三轮多模型集成都失败")
        return []
    return result


def _run_debate_round3(client, round1_outputs: List[Dict[str, Any]], round2_output: Dict[str, str]) -> Dict[str, Any]:
    msgs = build_round3_messages(round1_outputs, round2_output)
    initial_resp = client.chat_completion(msgs)
    if not initial_resp:
        logger.error("第三轮初始预测失败，无法启动辩论")
        return []
    initial_parsed = parse_round3_output(initial_resp)
    if not initial_parsed:
        logger.error("第三轮初始结果解析失败，无法启动辩论")
        return []

    context_info = f"第一轮主题数量：{len(round1_outputs)}\n第二轮范式：{round2_output.get('paradigm', '') if isinstance(round2_output, dict) else ''}"
    engine = DebateEngine(
        llm_client=client,
        agents=DEBATE_AGENTS,
        num_rounds=DEBATE_ROUNDS,
        confidence_threshold=CONFIDENCE_THRESHOLD
    )
    result = engine.run(
        initial_messages=msgs,
        initial_result={"roadmap": initial_parsed},
        parser_func=parse_round3_output,
        context_info=context_info
    )
    if not result.get("debate_info", {}).get("success"):
        logger.error("第三轮辩论失败")
        return []
    return result


def run_round3(round1_outputs: List[Dict[str, Any]], round2_output: Dict[str, str], force_rerun: bool = False) -> List[Dict[str, Any]]:
    use_multi_model = ENABLE_MULTI_MODEL and bool(MULTI_MODEL_LIST)

    if use_multi_model:
        multi_client = MultiModelClient(
            model_configs=MULTI_MODEL_LIST,
            strategy=MULTI_MODEL_STRATEGY
        )
    else:
        client = LLMClient()

    raw_path = OUTPUTS_RAW / "round3_response.json"
    parsed_path = OUTPUTS_PARSED / "round3_roadmap.json"
    if not force_rerun and parsed_path.exists():
        logger.info("加载缓存第三轮")
        cached = read_json(parsed_path)
        if cached:
            return cached
    logger.info("开始第三轮预测")

    if use_multi_model:
        parsed = _run_multi_model_round3(multi_client, round1_outputs, round2_output)
    elif ENABLE_MULTI_AGENT_DEBATE:
        parsed = _run_debate_round3(client, round1_outputs, round2_output)
    elif ENABLE_SELF_CONSISTENCY:
        parsed = _run_self_consistency_round3(client, round1_outputs, round2_output)
    else:
        parsed = _run_single_round3(client, round1_outputs, round2_output)

    if parsed:
        write_json(parsed, parsed_path)
        return parsed
    return []