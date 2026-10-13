# -*- coding: utf-8 -*-
"""Provider-neutral LangChain adapter, prompt manifests and bounded correction."""

import hashlib
import importlib.metadata
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, PrivateAttr, ValidationError

from config.settings import PROMPT_TEMPLATES_DIR
from src.utils.api_client import LLMClient
from src.library import LibraryRepository


@dataclass(frozen=True)
class JobModelConfig:
    provider: str = "openai-compatible"
    model_name: str = ""
    temperature: float = 0.1
    max_tokens: int = 4000
    native_structured_output: bool = False


def dependency_diagnostics() -> Dict[str, Any]:
    return {
        "langchain_core": importlib.metadata.version("langchain-core"),
        "langgraph": importlib.metadata.version("langgraph"),
        "python_compatible": True,
    }


class LegacyChatModelAdapter(BaseChatModel):
    config: JobModelConfig
    _client: Any = PrivateAttr()

    def __init__(self, config: JobModelConfig, client: Optional[Any] = None):
        super().__init__(config=config)
        self._client = client or LLMClient()

    @property
    def _llm_type(self) -> str:
        return "job-scoped-openai-compatible"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {"provider": self.config.provider, "model_name": self.config.model_name,
                "temperature": self.config.temperature, "max_tokens": self.config.max_tokens}

    def _generate(self, messages: List[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        payload = [{"role": "assistant" if message.type == "ai" else "user" if message.type == "human" else message.type,
                    "content": str(message.content)} for message in messages]
        content = self._client.chat_completion(
            payload, temperature=kwargs.get("temperature", self.config.temperature),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
        )
        if content is None:
            raise RuntimeError("模型提供方未返回内容")
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])


def create_chat_model(config: JobModelConfig, client: Optional[Any] = None) -> BaseChatModel:
    return LegacyChatModelAdapter(config, client)


def structured_model(model: BaseChatModel, schema: Type[BaseModel], native: bool = False):
    method = "json_schema" if native else "function_calling"
    try:
        return model.with_structured_output(schema, method=method, include_raw=True)
    except NotImplementedError:
        def fallback(value):
            response = model.invoke(value)
            content = response.content if hasattr(response, "content") else response
            if isinstance(content, str):
                content = content.strip()
                if content.startswith("```"):
                    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content)
                content = json.loads(content)
            return {"raw": response, "parsed": schema.model_validate(content), "parsing_error": None}
        return RunnableLambda(fallback)


def load_prompt_template(role: str, prompt_version: str = "v1",
                         template_dir: Path = PROMPT_TEMPLATES_DIR,
                         input_schema_version: str = "agent-input-v1",
                         output_schema_version: str = "agent-output-v1") -> Dict[str, Any]:
    system_path = template_dir / (role + "_system.txt")
    user_path = template_dir / (role + "_user.txt")
    if not system_path.is_file() or not user_path.is_file():
        raise ValueError("提示词模板不存在: %s" % role)
    system, user = system_path.read_text(encoding="utf-8"), user_path.read_text(encoding="utf-8")
    checksum = hashlib.sha256((system + "\n" + user).encode("utf-8")).hexdigest()
    def escaped(value: str) -> str:
        variables = re.findall(r"{([A-Za-z_]\w*)}", value)
        value = value.replace("{", "{{").replace("}", "}}")
        for variable in variables:
            value = value.replace("{{%s}}" % variable, "{%s}" % variable)
        return value
    return {
        "role": role, "prompt_version": prompt_version, "language": "zh-CN",
        "input_schema_version": input_schema_version,
        "output_schema_version": output_schema_version,
        "checksum": checksum, "paths": [str(system_path), str(user_path)],
        "template": ChatPromptTemplate.from_messages([("system", escaped(system)), ("human", escaped(user))]),
    }


def persist_prompt_manifest(repository: LibraryRepository, manifest: Dict[str, Any]) -> str:
    identifier = "prompt_" + manifest["checksum"][:16]
    with repository.db.transaction() as connection:
        connection.execute(
            """INSERT OR IGNORE INTO prompt_manifests(prompt_manifest_id,role,prompt_version,
               language,input_schema_version,output_schema_version,template_checksum,template_path)
               VALUES (?,?,?,?,?,?,?,?)""",
            (identifier, manifest["role"], manifest["prompt_version"], manifest["language"],
             manifest["input_schema_version"], manifest["output_schema_version"],
             manifest["checksum"], json.dumps(manifest["paths"], ensure_ascii=False)),
        )
    return identifier


def persist_model_manifest(repository: LibraryRepository, config: JobModelConfig,
                           dependencies: Optional[Dict[str, Any]] = None) -> str:
    payload = {"provider": config.provider, "model_name": config.model_name,
               "temperature": config.temperature, "max_tokens": config.max_tokens,
               "dependencies": dependencies or dependency_diagnostics()}
    checksum = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    identifier = "model_manifest_" + checksum[:16]
    with repository.db.transaction() as connection:
        connection.execute(
            """INSERT OR IGNORE INTO model_manifests(model_manifest_id,provider,model_name,
               model_profile_json,parameters_json,dependency_versions_json,checksum)
               VALUES (?,?,?,?,?,?,?)""",
            (identifier, config.provider, config.model_name, "{}",
             json.dumps({"temperature": config.temperature, "max_tokens": config.max_tokens}),
             json.dumps(payload["dependencies"], sort_keys=True), checksum),
        )
    return identifier


def validate_agent_output(value: BaseModel, frozen: Dict[str, Any]) -> None:
    payload = value.model_dump()
    rendered = json.dumps(payload, ensure_ascii=False)
    allowed_evidence = set(frozen.get("evidence_ids", []))
    cited = set()
    def collect(item):
        if isinstance(item, dict):
            for key, child in item.items():
                if key == "evidence_ids" and isinstance(child, list):
                    cited.update(str(value) for value in child)
                else:
                    collect(child)
        elif isinstance(item, list):
            for child in item:
                collect(child)
    collect(payload)
    unknown = cited - allowed_evidence
    if unknown:
        raise ValueError("输出引用了冻结快照之外的证据 ID: " + ", ".join(sorted(unknown)))
    allowed_ipcs = set(frozen.get("ipc_codes", []))
    mentioned_ipcs = set(re.findall(r"\b[A-H]\d{2}[A-Z]\d+/\d+\b", rendered))
    if allowed_ipcs and not mentioned_ipcs <= allowed_ipcs:
        raise ValueError("输出包含冻结范围外 IPC")
    allowed_years = {int(year) for year in frozen.get("forecast_nodes", [2030, 2035, 2040])}
    mentioned_years = {int(year) for year in re.findall(r"\b20(?:30|35|40)\b", rendered)}
    if not mentioned_years <= allowed_years:
        raise ValueError("输出包含目标范围外预测年份")


def validate_scientific_language(text: str) -> List[str]:
    findings = []
    if re.search(r"(必然|一定会|毫无疑问|完全证明|因而导致)", text):
        findings.append("存在因果或确定性过度陈述")
    if re.search(r"\b100%\b|百分之百", text):
        findings.append("存在不受支持的绝对置信表述")
    if not re.search(r"(限制|不确定|可能|情景|证据)", text):
        findings.append("缺少限制或不确定性说明")
    return findings


def invoke_with_bounded_correction(
    invoke, payload: Dict[str, Any], schema: Type[BaseModel], frozen: Dict[str, Any],
    max_retries: int = 2,
) -> BaseModel:
    errors = []
    for attempt in range(max_retries + 1):
        request = payload if not errors else {**payload, "validation_errors": errors,
                                               "correction_attempt": attempt}
        try:
            raw = invoke(request)
            value = raw if isinstance(raw, schema) else schema.model_validate(raw)
            validate_agent_output(value, frozen)
            language_findings = validate_scientific_language(json.dumps(value.model_dump(), ensure_ascii=False))
            if language_findings:
                raise ValueError("；".join(language_findings))
            return value
        except (ValidationError, ValueError) as exc:
            errors = [str(exc)]
    raise ValueError("结构化输出校正超过最大重试次数: " + "；".join(errors))
