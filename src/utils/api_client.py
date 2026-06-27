# -*- coding:utf-8-*-
import time
import requests
from typing import Optional, Dict, List
from config.settings import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    TEMPERATURE, MAX_TOKENS, REQUEST_TIMEOUT, MAX_RETRIES
)
from .logger import get_logger

logger = get_logger(__name__)

class LLMClient:
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or DEEPSEEK_API_KEY
        self.base_url = base_url or DEEPSEEK_BASE_URL
        self.model = model or DEEPSEEK_MODEL
        self.timeout = REQUEST_TIMEOUT
        self.max_retries = MAX_RETRIES
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY 未设置")

    def _get_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def chat_completion(self, messages: List[Dict], temperature: float = None, max_tokens: int = None) -> Optional[str]:
        temperature = temperature or TEMPERATURE
        max_tokens = max_tokens or MAX_TOKENS
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"调用 LLM API (尝试 {attempt}/{self.max_retries})")
                start = time.time()
                resp = requests.post(f"{self.base_url}/chat/completions", headers=self._get_headers(),
                                     json=payload, timeout=self.timeout)
                elapsed = time.time() - start
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                logger.info(f"成功，耗时 {elapsed:.2f}s，token: {usage}")
                return content
            except Exception as e:
                logger.warning(f"失败 (尝试 {attempt}): {e}")
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
        logger.error("API 调用失败，已达最大重试次数")
        return None