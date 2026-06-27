# -*- coding:utf-8-*-
from pathlib import Path
from config.settings import DATA_RAW
from src.utils.file_io import read_json

def load_topics() -> list:
    path = DATA_RAW / "topics.json"
    data = read_json(path)
    if data is None:
        raise FileNotFoundError(f"主题数据文件不存在: {path}")
    return data

def load_high_potential_pairs() -> list:
    path = DATA_RAW / "high_potential_pairs.json"
    data = read_json(path)
    if data is None:
        raise FileNotFoundError(f"融合对文件不存在: {path}")
    return data