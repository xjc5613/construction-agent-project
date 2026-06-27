# -*- coding:utf-8-*-
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

ROOT_DIR = Path(__file__).parent.parent

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