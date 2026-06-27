# -*- coding:utf-8-*-
from pathlib import Path
from config.settings import DATA_RAW
from src.utils.file_io import read_text

def load_abstracts_for_topic(topic_name: str) -> str:
    safe_name = topic_name.replace(" ", "_").replace("/", "_")
    txt_path = DATA_RAW / "sample_abstracts" / f"{safe_name}.txt"
    if txt_path.exists():
        return read_text(txt_path) or ""
    return ""