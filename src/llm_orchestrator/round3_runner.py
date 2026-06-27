# -*- coding:utf-8-*-
from typing import List, Dict, Any
from config.settings import OUTPUTS_RAW, OUTPUTS_PARSED
from src.utils.api_client import LLMClient
from src.utils.logger import get_logger
from src.utils.file_io import write_json, read_json
from src.prompt_builder import build_round3_messages
from src.output_parser import parse_round3_output

logger = get_logger(__name__)

def run_round3(round1_outputs: List[Dict[str, Any]], round2_output: Dict[str, str], force_rerun: bool = False) -> List[Dict[str, Any]]:
    client = LLMClient()
    raw_path = OUTPUTS_RAW / "round3_response.json"
    parsed_path = OUTPUTS_PARSED / "round3_roadmap.json"
    if not force_rerun and parsed_path.exists():
        logger.info("加载缓存第三轮")
        cached = read_json(parsed_path)
        if cached:
            return cached
    logger.info("开始第三轮预测")
    msgs = build_round3_messages(round1_outputs, round2_output)
    resp = client.chat_completion(msgs)
    if not resp:
        logger.error("第三轮 API 失败")
        return []
    write_json({"response": resp}, raw_path)
    parsed = parse_round3_output(resp)
    if parsed:
        write_json(parsed, parsed_path)
        return parsed
    return []