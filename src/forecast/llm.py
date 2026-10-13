# -*- coding: utf-8 -*-
"""Minimal JSON-structured LLM client on the OpenAI-compatible endpoint.

One clean path: messages -> model -> JSON -> Pydantic. No legacy adapters.
"""
from __future__ import annotations

import json
import re
import time
from typing import Type, TypeVar

import requests
from pydantic import BaseModel, ValidationError

from config.settings import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    MAX_RETRIES,
    MAX_TOKENS,
    REQUEST_TIMEOUT,
    TEMPERATURE,
)

T = TypeVar("T", bound=BaseModel)


class LLMJSONError(RuntimeError):
    pass


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.S)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match:
            return json.loads(match.group(0))
        raise LLMJSONError("模型返回内容不是合法 JSON")


def call_structured(
    system: str,
    user: str,
    schema: Type[T],
    *,
    temperature: float = TEMPERATURE,
    max_tokens: int = MAX_TOKENS,
    correction_attempt: int = 0,
    previous_errors: list[str] | None = None,
) -> T:
    """Call the model and validate the result against a Pydantic schema."""
    if not DEEPSEEK_API_KEY:
        raise LLMJSONError("DEEPSEEK_API_KEY 未配置，请在 .env 中填写")

    user_content = user
    if correction_attempt and previous_errors:
        user_content = (
            f"{user}\n\n[上一次输出未通过校验，请修正]\n"
            + "\n".join(f"- {e}" for e in previous_errors)
        )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                headers=headers, json=payload, timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            data = _extract_json(content)
            return schema.model_validate(data)
        except (requests.RequestException, KeyError, ValueError) as exc:
            last_error = exc
            time.sleep(min(2 ** attempt, 8))
        except ValidationError as exc:
            last_error = exc
            time.sleep(min(2 ** attempt, 8))
    raise LLMJSONError(f"结构化调用失败: {last_error}")
