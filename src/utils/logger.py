# -*- coding:utf-8-*-
import logging
import sys
from pathlib import Path
from config.settings import LOGS_DIR

def setup_logger(name="forecast", log_file="forecast.log"):
    log_path = LOGS_DIR / log_file
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

def get_logger(name=None):
    return logging.getLogger(name or "forecast")