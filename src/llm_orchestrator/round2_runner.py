# -*- coding:utf-8-*-
from typing import List, Dict, Any
from config.settings import OUTPUTS_RAW, OUTPUTS_PARSED
from src.utils.api_client import LLMClient
from src.utils.logger import get_logger
from src.utils.file_io import write_json, read_json
from src.prompt_builder import build_round2_messages
from src.output_parser import parse_round2_output

logger = get_logger(__name__)

def run_round2(round1_outputs: List[Dict[str, Any]], force_rerun: bool = False) -> Dict[str, str]:
    client = LLMClient()
    raw_path = OUTPUTS_RAW / "round2_response.json"
    parsed_path = OUTPUTS_PARSED / "round2_paradigm.json"
    if not force_rerun and parsed_path.exists():
        logger.info("加载缓存第二轮")
        cached = read_json(parsed_path)
        if cached:
            return cached
    logger.info("开始第二轮预测")
    msgs = build_round2_messages(round1_outputs)
    resp = client.chat_completion(msgs)
    if not resp:
        logger.error("第二轮 API 失败")
        return {}
    write_json({"response": resp}, raw_path)
    parsed = parse_round2_output(resp)
    if parsed:
        write_json(parsed, parsed_path)
        return parsed
    return {}