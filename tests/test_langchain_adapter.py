# -*- coding: utf-8 -*-
import json

import pytest
from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from src.research.agent_schemas import EvidenceAnalysis, ThemeForecast
from src.research.langchain_adapter import (
    JobModelConfig, create_chat_model, dependency_diagnostics,
    invoke_with_bounded_correction, load_prompt_template, structured_model,
    validate_agent_output, validate_scientific_language,
)


class FakeClient:
    def __init__(self, response=None, failure=False):
        self.response, self.failure, self.calls = response, failure, []

    def chat_completion(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if self.failure:
            return None
        return self.response


def _analysis(evidence_id="evidence_1"):
    return {
        "analysis_kind": "patent",
        "claims": [{"claim": "可能形成融合", "evidence_ids": [evidence_id],
                    "confidence": "medium", "limitation": "样本限制"}],
        "conflicts": [], "limitations": ["证据仍有不确定性"],
    }


def test_dependency_prompt_and_job_scoped_model_adapter():
    diagnostics = dependency_diagnostics()
    assert diagnostics["langchain_core"] == "0.3.84"
    assert diagnostics["langgraph"] == "0.2.55"
    manifest = load_prompt_template("round1")
    assert manifest["checksum"]
    values = {name: "测试" for name in manifest["template"].input_variables}
    assert manifest["template"].invoke(values).messages
    client = FakeClient("ok")
    model = create_chat_model(JobModelConfig(model_name="test-model"), client)
    assert model.invoke([HumanMessage(content="hello")]).content == "ok"
    assert client.calls[0][1]["temperature"] == 0.1
    assert "api" not in json.dumps(model._identifying_params).lower()


def test_structured_fallback_and_provider_failure():
    client = FakeClient(json.dumps(_analysis(), ensure_ascii=False))
    model = create_chat_model(JobModelConfig(), client)
    result = structured_model(model, EvidenceAnalysis).invoke([HumanMessage(content="analyze")])
    assert isinstance(result["parsed"], EvidenceAnalysis)
    failed = create_chat_model(JobModelConfig(), FakeClient(failure=True))
    with pytest.raises(RuntimeError, match="未返回"):
        failed.invoke([HumanMessage(content="hello")])


def test_schema_and_frozen_evidence_probability_guards():
    value = EvidenceAnalysis.model_validate(_analysis())
    validate_agent_output(value, {"evidence_ids": ["evidence_1"]})
    invented = EvidenceAnalysis.model_validate(_analysis("evidence_invented"))
    with pytest.raises(ValueError, match="冻结快照之外"):
        validate_agent_output(invented, {"evidence_ids": ["evidence_1"]})
    with pytest.raises(ValidationError):
        EvidenceAnalysis.model_validate({**_analysis(), "calibrated_probability": 0.99})
    assert validate_scientific_language("该技术必然实现，成功率100%")


def test_bounded_schema_correction_success_and_exhaustion():
    responses = iter([{"bad": "shape"}, _analysis()])
    calls = []
    def invoke(payload):
        calls.append(payload)
        return next(responses)
    value = invoke_with_bounded_correction(
        invoke, {}, EvidenceAnalysis, {"evidence_ids": ["evidence_1"]}, max_retries=2
    )
    assert isinstance(value, EvidenceAnalysis)
    assert "validation_errors" in calls[1]
    with pytest.raises(ValueError, match="超过最大重试次数"):
        invoke_with_bounded_correction(
            lambda _: _analysis("evidence_fake"), {}, EvidenceAnalysis,
            {"evidence_ids": ["evidence_1"]}, max_retries=1,
        )
