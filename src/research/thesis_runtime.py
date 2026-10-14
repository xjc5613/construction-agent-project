# -*- coding: utf-8 -*-
"""Job-scoped model and graph factory for thesis evolution forecasting."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from src.library import LibraryRepository
from src.research.langchain_adapter import (
    JobModelConfig, create_chat_model, load_prompt_template, persist_model_manifest,
    persist_prompt_manifest, structured_model,
)
from src.research.thesis_graph import ThesisAgentRoles, ThesisDeliberationGraph, ThesisGraphContext
from src.research.thesis_repository import ThesisRepository


def build_thesis_graph(repository: LibraryRepository, job_id: str,
                       override_options: Optional[Dict[str, Any]] = None) -> ThesisDeliberationGraph:
    job = repository.get_forecast_job(job_id)
    if not job:
        raise ValueError("预测任务不存在")
    options = {**job.get("options", {}), **(override_options or {})}
    config = JobModelConfig(**{key: options[key] for key in (
        "provider", "model_name", "temperature", "max_tokens", "native_structured_output"
    ) if key in options})
    model = None
    call_count = 0
    thesis_repository = ThesisRepository(repository.db)

    def invoke_role(role: str, payload: Dict[str, Any], schema):
        nonlocal model, call_count
        max_calls = int(options.get("run_budget", {}).get("max_model_calls", 0) or 0)
        if max_calls and call_count >= max_calls:
            raise RuntimeError("论文研判模型调用预算已耗尽")
        call_count += 1
        if model is None:
            model = create_chat_model(config)
        prompt = load_prompt_template(
            role, prompt_version="thesis-v1",
            input_schema_version="thesis-role-input-v1",
            output_schema_version=getattr(schema, "__name__", "thesis-output-v1"),
        )
        prompt_id = persist_prompt_manifest(repository, prompt)
        model_id = persist_model_manifest(repository, config)
        request = {"payload": json.dumps(payload, ensure_ascii=False, sort_keys=True)}
        try:
            messages = prompt["template"].invoke(request)
            result = structured_model(model, schema, config.native_structured_output).invoke(messages)
            if isinstance(result, dict) and result.get("parsing_error"):
                raise ValueError("结构化模型输出解析失败: %s" % result["parsing_error"])
            parsed = result.get("parsed") if isinstance(result, dict) else result
            value = parsed.model_dump() if hasattr(parsed, "model_dump") else parsed
            claim = payload.get("claim", {})
            claim_version_id = ""
            if claim.get("claim_id") and claim.get("version"):
                claim_version_id = thesis_repository.claim_version_id(
                    job_id, claim["claim_id"], int(claim["version"]))
            thesis_repository.record_agent_call(
                job_id, role, payload, value, "completed",
                prompt_manifest_id=prompt_id, model_manifest_id=model_id,
                claim_version_id=claim_version_id,
            )
            return value
        except Exception as exc:
            thesis_repository.record_agent_call(
                job_id, role, payload, None, "failed",
                prompt_manifest_id=prompt_id, model_manifest_id=model_id,
                error={"message": str(exc)},
            )
            raise

    context = ThesisGraphContext(
        repository=repository, thesis_repository=thesis_repository,
        job_id=job_id, project_id=job["project_id"],
        revision_limit=int(options.get("revision_limit", 2)),
        compute_concurrency=int(options.get("compute_concurrency", 4)),
        run_budget=options.get("run_budget", {}),
    )
    graph = ThesisDeliberationGraph(context, ThesisAgentRoles(invoke_role))
    graph.thread_id = job.get("graph_thread_id", "")
    return graph
