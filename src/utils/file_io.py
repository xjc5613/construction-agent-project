# -*- coding:utf-8-*-
import json
from pathlib import Path
from typing import Any, Optional
from .logger import get_logger

logger = get_logger(__name__)

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def read_json(file_path: Path, encoding="utf-8") -> Optional[Any]:
    try:
        with open(file_path, "r", encoding=encoding) as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"读取 JSON 失败: {file_path}, 错误: {e}")
        return None

def write_json(data: Any, file_path: Path, encoding="utf-8", indent=2) -> bool:
    try:
        ensure_dir(file_path.parent)
        with open(file_path, "w", encoding=encoding) as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        return True
    except Exception as e:
        logger.error(f"写入 JSON 失败: {file_path}, 错误: {e}")
        return False

def read_text(file_path: Path, encoding="utf-8") -> Optional[str]:
    try:
        with open(file_path, "r", encoding=encoding) as f:
            return f.read()
    except Exception as e:
        logger.error(f"读取文本失败: {file_path}, 错误: {e}")
        return None

def write_text(content: str, file_path: Path, encoding="utf-8") -> bool:
    try:
        ensure_dir(file_path.parent)
        with open(file_path, "w", encoding=encoding) as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error(f"写入文本失败: {file_path}, 错误: {e}")
        return False