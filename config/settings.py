# -*- coding:utf-8-*-
import os
import json
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

ROOT_DIR = Path(__file__).parent.parent


def _str_to_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return value.strip().lower() in ("true", "1", "yes", "on")


def _parse_json_env(value, default):
    if value is None or value.strip() == "":
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return default


# API 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 模型超参数
TEMPERATURE = float(os.getenv("TEMPERATURE", 0.15))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", 2048))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 60))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))

# 路径
DATA_RAW = ROOT_DIR / "data" / "raw"
DATA_PROCESSED = ROOT_DIR / "data" / "processed"
OUTPUTS_RAW = ROOT_DIR / "outputs" / "raw"
OUTPUTS_PARSED = ROOT_DIR / "outputs" / "parsed"
OUTPUTS_REPORT = ROOT_DIR / "outputs" / "final_report"
LOGS_DIR = ROOT_DIR / "logs"
PROMPT_TEMPLATES_DIR = ROOT_DIR / "config" / "prompt_templates"

# 创建目录
for dir_path in [DATA_PROCESSED, OUTPUTS_RAW, OUTPUTS_PARSED, OUTPUTS_REPORT, LOGS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ===== 功能开关 =====
ENABLE_SELF_CONSISTENCY = _str_to_bool(os.getenv("ENABLE_SELF_CONSISTENCY"), False)
ENABLE_MULTI_MODEL = _str_to_bool(os.getenv("ENABLE_MULTI_MODEL"), False)
ENABLE_MULTI_AGENT_DEBATE = _str_to_bool(os.getenv("ENABLE_MULTI_AGENT_DEBATE"), False)
ENABLE_REASONING_CHAIN = _str_to_bool(os.getenv("ENABLE_REASONING_CHAIN"), False)

# ===== 自洽性验证配置 =====
SELF_CONSISTENCY_SAMPLES = int(os.getenv("SELF_CONSISTENCY_SAMPLES", 3))
SELF_CONSISTENCY_TEMPERATURE_MIN = float(os.getenv("SELF_CONSISTENCY_TEMPERATURE_MIN", 0.1))
SELF_CONSISTENCY_TEMPERATURE_MAX = float(os.getenv("SELF_CONSISTENCY_TEMPERATURE_MAX", 0.5))
CONFIDENCE_THRESHOLD = int(os.getenv("CONFIDENCE_THRESHOLD", 60))

# ===== 多模型集成配置 =====
MULTI_MODEL_LIST = _parse_json_env(os.getenv("MULTI_MODEL_LIST"), [])
MULTI_MODEL_STRATEGY = os.getenv("MULTI_MODEL_STRATEGY", "weighted_vote")

# ===== 多Agent辩论配置 =====
DEBATE_ROUNDS = int(os.getenv("DEBATE_ROUNDS", 2))
DEBATE_AGENTS = _parse_json_env(os.getenv("DEBATE_AGENTS"), ["tech_expert", "industry_analyst", "risk_assessor"])

# ===== 路线图增强配置 =====
ENABLE_ROADMAP_ENHANCED = _str_to_bool(os.getenv("ENABLE_ROADMAP_ENHANCED"), False)

# ===== 回溯验证配置 =====
BACKTEST_HISTORICAL_YEAR = int(os.getenv("BACKTEST_HISTORICAL_YEAR", 2020))

# ===== 单主题路线图配置 =====
ENABLE_PER_TOPIC_ROADMAP = _str_to_bool(os.getenv("ENABLE_PER_TOPIC_ROADMAP"), False)
PER_TOPIC_ROADMAP_STAGES = ["2025", "2030", "2035", "2040"]