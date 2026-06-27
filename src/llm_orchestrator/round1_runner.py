# -*- coding:utf-8-*-
from typing import List, Dict, Any
from config.settings import OUTPUTS_RAW, OUTPUTS_PARSED
from src.utils.api_client import LLMClient
from src.utils.logger import get_logger
from src.utils.file_io import write_json, read_json
from src.prompt_builder import build_round1_messages
from src.output_parser import parse_round1_output

logger = get_logger(__name__)

def run_round1(topic_inputs: List[Dict[str, Any]], force_rerun: bool = False) -> List[Dict[str, Any]]:
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
        msgs = build_round1_messages(inp)
        resp = client.chat_completion(msgs)
        if not resp:
            logger.error(f"主题 {name} API 失败")
            continue
        write_json({"topic": name, "response": resp}, raw_path)
        parsed = parse_round1_output(resp, name)
        if parsed:
            write_json(parsed, parsed_path)
            results.append(parsed)
            logger.info(f"完成: {name}")
        else:
            logger.error(f"解析失败: {name}")
    logger.info(f"第一轮完成: {len(results)}/{len(topic_inputs)}")
    return results