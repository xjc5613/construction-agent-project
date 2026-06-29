# -*- coding:utf-8-*-
import time
import requests
from typing import Optional, Dict, List, Any
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


class MultiModelClient:
    def __init__(self, model_configs: List[Dict[str, Any]] = None, strategy: str = "weighted_vote"):
        self.strategy = strategy
        self.model_configs = model_configs or []
        self.clients: Dict[str, LLMClient] = {}
        self.weights: Dict[str, float] = {}
        self.single_model_mode = False
        self.single_client: Optional[LLMClient] = None

        if not self.model_configs:
            logger.info("多模型配置为空，回退到默认单模型模式")
            self.single_model_mode = True
            self.single_client = LLMClient()
            return

        total_weight = 0.0
        for cfg in self.model_configs:
            name = cfg.get("name")
            if not name:
                logger.warning("跳过未命名的模型配置")
                continue
            try:
                client = LLMClient(
                    api_key=cfg.get("api_key"),
                    base_url=cfg.get("base_url"),
                    model=cfg.get("model")
                )
                self.clients[name] = client
                weight = float(cfg.get("weight", 1.0))
                self.weights[name] = weight
                total_weight += weight
                logger.info(f"已加载模型: {name} (权重: {weight})")
            except Exception as e:
                logger.warning(f"模型 {name} 初始化失败: {e}，已跳过")

        if not self.clients:
            logger.warning("所有模型配置均无效，回退到默认单模型模式")
            self.single_model_mode = True
            self.single_client = LLMClient()
            return

        if total_weight <= 0:
            logger.warning("模型权重总和为0，使用等权重")
            count = len(self.clients)
            for name in self.clients:
                self.weights[name] = 1.0 / count
        else:
            for name in self.weights:
                self.weights[name] = self.weights[name] / total_weight

    def get_normalized_weights(self, active_models: List[str] = None) -> Dict[str, float]:
        if active_models is None:
            active_models = list(self.clients.keys())
        if not active_models:
            return {}

        total = sum(self.weights.get(name, 0.0) for name in active_models)
        if total <= 0:
            count = len(active_models)
            return {name: 1.0 / count for name in active_models}

        return {name: self.weights.get(name, 0.0) / total for name in active_models}

    def chat_completion(self, messages: List[Dict], temperature: float = None,
                        max_tokens: int = None) -> Dict[str, Any]:
        if self.single_model_mode:
            content = self.single_client.chat_completion(messages, temperature, max_tokens)
            return {
                "results": [{
                    "model_name": "default",
                    "content": content,
                    "success": content is not None
                }],
                "model_count": 1
            }

        results = []
        for name, client in self.clients.items():
            logger.info(f"调用模型: {name}")
            try:
                content = client.chat_completion(messages, temperature, max_tokens)
                success = content is not None
                results.append({
                    "model_name": name,
                    "content": content,
                    "success": success
                })
                if success:
                    logger.info(f"模型 {name} 调用成功")
                else:
                    logger.warning(f"模型 {name} 调用失败，返回空内容")
            except Exception as e:
                logger.error(f"模型 {name} 调用异常: {e}")
                results.append({
                    "model_name": name,
                    "content": None,
                    "success": False,
                    "error": str(e)
                })

        return {
            "results": results,
            "model_count": len(self.clients)
        }