# -*- coding:utf-8-*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock
from src.llm_orchestrator.ensemble import EnsembleEngine
from src.utils.api_client import MultiModelClient


class MockMultiModelClient:
    def __init__(self, results_by_model=None, weights=None):
        self.results_by_model = results_by_model or {}
        self.weights = weights or {}
        self.call_count = 0
        self.last_messages = None

    def chat_completion(self, messages, temperature=None, max_tokens=None):
        self.call_count += 1
        self.last_messages = messages
        results = []
        for model_name, content in self.results_by_model.items():
            if content is None:
                results.append({
                    "model_name": model_name,
                    "content": None,
                    "success": False
                })
            else:
                results.append({
                    "model_name": model_name,
                    "content": content,
                    "success": True
                })
        return {
            "results": results,
            "model_count": len(self.results_by_model)
        }

    def get_normalized_weights(self, active_models=None):
        if active_models is None:
            active_models = list(self.weights.keys())
        if not active_models:
            return {}
        total = sum(self.weights.get(name, 0.0) for name in active_models)
        if total <= 0:
            count = len(active_models)
            return {name: 1.0 / count for name in active_models}
        return {name: self.weights.get(name, 0.0) / total for name in active_models}


def mock_parser(text):
    import json
    return json.loads(text)


def test_multi_model_client_empty_config():
    with patch('src.utils.api_client.LLMClient') as mock_llm_class:
        mock_instance = MagicMock()
        mock_llm_class.return_value = mock_instance
        client = MultiModelClient(model_configs=[])
        assert client.single_model_mode is True
        assert client.single_client is not None
        assert len(client.clients) == 0


def test_multi_model_client_multiple_configs():
    with patch('src.utils.api_client.LLMClient') as mock_llm_class:
        mock_llm_class.return_value = MagicMock()
        configs = [
            {"name": "model_a", "api_key": "key_a", "base_url": "http://a.com", "model": "model-a", "weight": 0.6},
            {"name": "model_b", "api_key": "key_b", "base_url": "http://b.com", "model": "model-b", "weight": 0.4},
        ]
        client = MultiModelClient(model_configs=configs)
        assert client.single_model_mode is False
        assert len(client.clients) == 2
        assert "model_a" in client.clients
        assert "model_b" in client.clients
        assert abs(client.weights["model_a"] + client.weights["model_b"] - 1.0) < 0.001
        assert client.weights["model_a"] > client.weights["model_b"]


def test_multi_model_client_weight_normalization():
    with patch('src.utils.api_client.LLMClient') as mock_llm_class:
        mock_llm_class.return_value = MagicMock()
        configs = [
            {"name": "m1", "api_key": "k1", "weight": 2.0},
            {"name": "m2", "api_key": "k2", "weight": 3.0},
        ]
        client = MultiModelClient(model_configs=configs)
        assert abs(client.weights["m1"] - 0.4) < 0.001
        assert abs(client.weights["m2"] - 0.6) < 0.001


def test_multi_model_client_zero_weights():
    with patch('src.utils.api_client.LLMClient') as mock_llm_class:
        mock_llm_class.return_value = MagicMock()
        configs = [
            {"name": "m1", "api_key": "k1", "weight": 0.0},
            {"name": "m2", "api_key": "k2", "weight": 0.0},
        ]
        client = MultiModelClient(model_configs=configs)
        assert abs(client.weights["m1"] - 0.5) < 0.001
        assert abs(client.weights["m2"] - 0.5) < 0.001


def test_multi_model_client_chat_completion_success():
    with patch('src.utils.api_client.LLMClient') as mock_llm_class:
        mock_instances = {}

        def side_effect(api_key=None, base_url=None, model=None):
            mock = MagicMock()
            mock.chat_completion.return_value = f"response_from_{api_key}"
            mock_instances[api_key] = mock
            return mock

        mock_llm_class.side_effect = side_effect
        configs = [
            {"name": "model_a", "api_key": "key_a", "weight": 0.5},
            {"name": "model_b", "api_key": "key_b", "weight": 0.5},
        ]
        client = MultiModelClient(model_configs=configs)
        result = client.chat_completion([{"role": "user", "content": "hello"}])

        assert result["model_count"] == 2
        assert len(result["results"]) == 2
        assert all(r["success"] for r in result["results"])
        assert result["results"][0]["model_name"] in ["model_a", "model_b"]
        assert result["results"][1]["model_name"] in ["model_a", "model_b"]


def test_multi_model_client_chat_completion_some_fail():
    with patch('src.utils.api_client.LLMClient') as mock_llm_class:
        mock_instances = {}

        def side_effect(api_key=None, base_url=None, model=None):
            mock = MagicMock()
            if api_key == "key_a":
                mock.chat_completion.return_value = "response_a"
            else:
                mock.chat_completion.return_value = None
            mock_instances[api_key] = mock
            return mock

        mock_llm_class.side_effect = side_effect
        configs = [
            {"name": "model_a", "api_key": "key_a", "weight": 0.5},
            {"name": "model_b", "api_key": "key_b", "weight": 0.5},
        ]
        client = MultiModelClient(model_configs=configs)
        result = client.chat_completion([{"role": "user", "content": "hello"}])

        assert result["model_count"] == 2
        success_count = sum(1 for r in result["results"] if r["success"])
        fail_count = sum(1 for r in result["results"] if not r["success"])
        assert success_count == 1
        assert fail_count == 1


def test_multi_model_client_single_model_mode():
    with patch('src.utils.api_client.LLMClient') as mock_llm_class:
        mock_instance = MagicMock()
        mock_instance.chat_completion.return_value = "single_response"
        mock_llm_class.return_value = mock_instance

        client = MultiModelClient(model_configs=[])
        result = client.chat_completion([{"role": "user", "content": "hello"}])

        assert result["model_count"] == 1
        assert len(result["results"]) == 1
        assert result["results"][0]["model_name"] == "default"
        assert result["results"][0]["success"] is True
        assert result["results"][0]["content"] == "single_response"


def test_ensemble_engine_weighted_vote_identical():
    responses = {
        "model_a": '{"name": "测试主题", "value": 42}',
        "model_b": '{"name": "测试主题", "value": 42}',
        "model_c": '{"name": "测试主题", "value": 42}',
    }
    weights = {"model_a": 0.5, "model_b": 0.3, "model_c": 0.2}
    mock_client = MockMultiModelClient(responses, weights)

    engine = EnsembleEngine(
        multi_model_client=mock_client,
        parser_func=mock_parser,
        strategy="weighted_vote",
        confidence_threshold=60.0
    )

    msgs = [{"role": "user", "content": "test"}]
    result = engine.run(msgs)

    assert result["success"] is True
    assert result["num_models"] == 3
    assert result["strategy"] == "weighted_vote"
    assert result["name"] == "测试主题"
    assert result["value"] == 42
    assert result["confidence"] > 90
    assert len(result["model_consensus"]) == 3
    assert "model_a" in result["success_models"]
    assert len(result["failed_models"]) == 0


def test_ensemble_engine_weighted_vote_different():
    responses = {
        "model_a": '{"name": "方案A", "score": 90}',
        "model_b": '{"name": "方案A", "score": 85}',
        "model_c": '{"name": "方案B", "score": 70}',
    }
    weights = {"model_a": 0.5, "model_b": 0.3, "model_c": 0.2}
    mock_client = MockMultiModelClient(responses, weights)

    engine = EnsembleEngine(
        multi_model_client=mock_client,
        parser_func=mock_parser,
        strategy="weighted_vote",
        confidence_threshold=60.0
    )

    msgs = [{"role": "user", "content": "test"}]
    result = engine.run(msgs)

    assert result["success"] is True
    assert result["num_models"] == 3
    assert result["name"] == "方案A"
    assert 0 < result["confidence"] < 100


def test_ensemble_engine_majority_vote():
    responses = {
        "model_a": '{"topic": "建筑机器人", "year": 2030}',
        "model_b": '{"topic": "建筑机器人", "year": 2030}',
        "model_c": '{"topic": "数字孪生", "year": 2025}',
    }
    weights = {"model_a": 1.0, "model_b": 1.0, "model_c": 1.0}
    mock_client = MockMultiModelClient(responses, weights)

    engine = EnsembleEngine(
        multi_model_client=mock_client,
        parser_func=mock_parser,
        strategy="majority_vote",
        confidence_threshold=60.0
    )

    msgs = [{"role": "user", "content": "test"}]
    result = engine.run(msgs)

    assert result["success"] is True
    assert result["num_models"] == 3
    assert result["strategy"] == "majority_vote"
    assert result["topic"] == "建筑机器人"


def test_ensemble_engine_consensus_all_agree():
    responses = {
        "model_a": '{"result": "同意", "level": "high"}',
        "model_b": '{"result": "同意", "level": "high"}',
        "model_c": '{"result": "同意", "level": "high"}',
    }
    weights = {"model_a": 1.0, "model_b": 1.0, "model_c": 1.0}
    mock_client = MockMultiModelClient(responses, weights)

    engine = EnsembleEngine(
        multi_model_client=mock_client,
        parser_func=mock_parser,
        strategy="consensus",
        confidence_threshold=60.0
    )

    msgs = [{"role": "user", "content": "test"}]
    result = engine.run(msgs)

    assert result["success"] is True
    assert result["num_models"] == 3
    assert result["strategy"] == "consensus"
    assert result["result"] == "同意"
    assert result["level"] == "high"
    assert result["confidence"] > 90


def test_ensemble_engine_consensus_disagree():
    responses = {
        "model_a": '{"result": "方案A"}',
        "model_b": '{"result": "方案B"}',
        "model_c": '{"result": "方案C"}',
    }
    weights = {"model_a": 1.0, "model_b": 1.0, "model_c": 1.0}
    mock_client = MockMultiModelClient(responses, weights)

    engine = EnsembleEngine(
        multi_model_client=mock_client,
        parser_func=mock_parser,
        strategy="consensus",
        confidence_threshold=60.0
    )

    msgs = [{"role": "user", "content": "test"}]
    result = engine.run(msgs)

    assert result["success"] is True
    assert result["num_models"] == 3
    assert result["confidence"] <= 30.0


def test_ensemble_engine_some_models_fail():
    responses = {
        "model_a": '{"name": "测试", "value": 100}',
        "model_b": None,
        "model_c": '{"name": "测试", "value": 100}',
    }
    weights = {"model_a": 0.4, "model_b": 0.3, "model_c": 0.3}
    mock_client = MockMultiModelClient(responses, weights)

    engine = EnsembleEngine(
        multi_model_client=mock_client,
        parser_func=mock_parser,
        strategy="weighted_vote",
        confidence_threshold=60.0
    )

    msgs = [{"role": "user", "content": "test"}]
    result = engine.run(msgs)

    assert result["success"] is True
    assert result["num_models"] == 2
    assert len(result["failed_models"]) == 1
    assert "model_b" in result["failed_models"]
    assert len(result["success_models"]) == 2
    assert result["name"] == "测试"
    assert result["value"] == 100


def test_ensemble_engine_all_models_fail():
    responses = {
        "model_a": None,
        "model_b": None,
    }
    weights = {"model_a": 0.5, "model_b": 0.5}
    mock_client = MockMultiModelClient(responses, weights)

    engine = EnsembleEngine(
        multi_model_client=mock_client,
        parser_func=mock_parser,
        strategy="weighted_vote",
        confidence_threshold=60.0
    )

    msgs = [{"role": "user", "content": "test"}]
    result = engine.run(msgs)

    assert result["success"] is False
    assert result["num_models"] == 0
    assert result["confidence"] == 0.0
    assert len(result["failed_models"]) == 2


def test_ensemble_engine_with_parser_args():
    responses = {
        "model_a": '{"value": 42}',
        "model_b": '{"value": 42}',
    }
    weights = {"model_a": 0.5, "model_b": 0.5}
    mock_client = MockMultiModelClient(responses, weights)

    def parser_with_args(text, topic):
        import json
        data = json.loads(text)
        data["topic"] = topic
        return data

    engine = EnsembleEngine(
        multi_model_client=mock_client,
        parser_func=parser_with_args,
        strategy="weighted_vote",
        confidence_threshold=60.0
    )

    msgs = [{"role": "user", "content": "test"}]
    result = engine.run(msgs, parser_args=("测试主题",))

    assert result["success"] is True
    assert result["topic"] == "测试主题"
    assert result["value"] == 42


def test_ensemble_engine_parser_exception():
    responses = {
        "model_a": 'invalid json',
        "model_b": '{"value": 42}',
    }
    weights = {"model_a": 0.5, "model_b": 0.5}
    mock_client = MockMultiModelClient(responses, weights)

    engine = EnsembleEngine(
        multi_model_client=mock_client,
        parser_func=mock_parser,
        strategy="weighted_vote",
        confidence_threshold=60.0
    )

    msgs = [{"role": "user", "content": "test"}]
    result = engine.run(msgs)

    assert result["success"] is True
    assert result["num_models"] == 1
    assert result["value"] == 42


def test_ensemble_engine_model_consensus_field():
    responses = {
        "model_a": '{"name": "主题A", "score": 90}',
        "model_b": '{"name": "主题A", "score": 80}',
    }
    weights = {"model_a": 0.5, "model_b": 0.5}
    mock_client = MockMultiModelClient(responses, weights)

    engine = EnsembleEngine(
        multi_model_client=mock_client,
        parser_func=mock_parser,
        strategy="weighted_vote",
        confidence_threshold=60.0
    )

    msgs = [{"role": "user", "content": "test"}]
    result = engine.run(msgs)

    assert "model_consensus" in result
    assert len(result["model_consensus"]) == 2
    for mc in result["model_consensus"]:
        assert "model_name" in mc
        assert "field_similarities" in mc
        assert "name" in mc["field_similarities"]
        assert "score" in mc["field_similarities"]


def test_ensemble_engine_low_confidence_fields():
    responses = {
        "model_a": '{"stable": "相同值", "unstable": "版本A"}',
        "model_b": '{"stable": "相同值", "unstable": "版本B"}',
        "model_c": '{"stable": "相同值", "unstable": "版本C"}',
    }
    weights = {"model_a": 1.0, "model_b": 1.0, "model_c": 1.0}
    mock_client = MockMultiModelClient(responses, weights)

    engine = EnsembleEngine(
        multi_model_client=mock_client,
        parser_func=mock_parser,
        strategy="weighted_vote",
        confidence_threshold=80.0
    )

    msgs = [{"role": "user", "content": "test"}]
    result = engine.run(msgs)

    assert "low_confidence_fields" in result
    assert "unstable" in result["low_confidence_fields"]
    assert "stable" not in result["low_confidence_fields"]


def test_ensemble_engine_single_model():
    responses = {
        "only_model": '{"name": "唯一模型", "value": 999}',
    }
    weights = {"only_model": 1.0}
    mock_client = MockMultiModelClient(responses, weights)

    engine = EnsembleEngine(
        multi_model_client=mock_client,
        parser_func=mock_parser,
        strategy="weighted_vote",
        confidence_threshold=60.0
    )

    msgs = [{"role": "user", "content": "test"}]
    result = engine.run(msgs)

    assert result["success"] is True
    assert result["num_models"] == 1
    assert result["name"] == "唯一模型"
    assert result["value"] == 999
    assert result["confidence"] == 50.0


def test_get_normalized_weights_with_active_models():
    with patch('src.utils.api_client.LLMClient') as mock_llm_class:
        mock_llm_class.return_value = MagicMock()
        configs = [
            {"name": "m1", "api_key": "k1", "weight": 2.0},
            {"name": "m2", "api_key": "k2", "weight": 3.0},
            {"name": "m3", "api_key": "k3", "weight": 5.0},
        ]
        client = MultiModelClient(model_configs=configs)
        active = ["m1", "m2"]
        norm = client.get_normalized_weights(active)
        assert abs(norm["m1"] + norm["m2"] - 1.0) < 0.001
        assert norm["m1"] == 0.4
        assert norm["m2"] == 0.6
        assert "m3" not in norm


def run_all_tests():
    test_funcs = [
        test_multi_model_client_empty_config,
        test_multi_model_client_multiple_configs,
        test_multi_model_client_weight_normalization,
        test_multi_model_client_zero_weights,
        test_multi_model_client_chat_completion_success,
        test_multi_model_client_chat_completion_some_fail,
        test_multi_model_client_single_model_mode,
        test_ensemble_engine_weighted_vote_identical,
        test_ensemble_engine_weighted_vote_different,
        test_ensemble_engine_majority_vote,
        test_ensemble_engine_consensus_all_agree,
        test_ensemble_engine_consensus_disagree,
        test_ensemble_engine_some_models_fail,
        test_ensemble_engine_all_models_fail,
        test_ensemble_engine_with_parser_args,
        test_ensemble_engine_parser_exception,
        test_ensemble_engine_model_consensus_field,
        test_ensemble_engine_low_confidence_fields,
        test_ensemble_engine_single_model,
        test_get_normalized_weights_with_active_models,
    ]

    passed = 0
    failed = 0
    for func in test_funcs:
        try:
            func()
            print(f"✓ {func.__name__}")
            passed += 1
        except Exception as e:
            print(f"✗ {func.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n总计: {passed} 通过, {failed} 失败")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
