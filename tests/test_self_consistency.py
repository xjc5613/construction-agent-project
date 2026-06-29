# -*- coding:utf-8-*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.llm_orchestrator.self_consistency import (
    calculate_confidence,
    aggregate_results,
    SelfConsistencyEngine,
    _text_similarity,
    _list_similarity,
    _value_similarity,
)


class MockLLMClient:
    def __init__(self, responses=None):
        self.responses = responses or []
        self.call_count = 0
        self.called_temperatures = []

    def chat_completion(self, messages, temperature=None, max_tokens=None):
        self.called_temperatures.append(temperature)
        idx = self.call_count
        self.call_count += 1
        if idx < len(self.responses):
            return self.responses[idx]
        return self.responses[-1] if self.responses else None


def test_text_similarity_identical():
    assert _text_similarity("hello world", "hello world") == 1.0


def test_text_similarity_completely_different():
    sim = _text_similarity("abcdef", "xyz")
    assert sim < 0.5


def test_text_similarity_partial():
    sim = _text_similarity("hello world", "hello python")
    assert 0.0 < sim < 1.0


def test_text_similarity_empty():
    assert _text_similarity("", "") == 1.0
    assert _text_similarity("hello", "") == 0.0
    assert _text_similarity("", "hello") == 0.0


def test_list_similarity_identical():
    a = ["a", "b", "c"]
    b = ["a", "b", "c"]
    assert _list_similarity(a, b) > 0.9


def test_list_similarity_completely_different():
    a = ["a", "b", "c"]
    b = ["x", "y", "z"]
    assert _list_similarity(a, b) < 0.3


def test_list_similarity_partial_overlap():
    a = ["a", "b", "c"]
    b = ["b", "c", "d"]
    sim = _list_similarity(a, b)
    assert 0.0 < sim < 1.0


def test_list_similarity_empty():
    assert _list_similarity([], []) == 1.0
    assert _list_similarity(["a"], []) == 0.0
    assert _list_similarity([], ["a"]) == 0.0


def test_value_similarity_strings():
    assert _value_similarity("test", "test") == 1.0
    assert 0.0 <= _value_similarity("abc", "xyz") <= 1.0


def test_value_similarity_lists():
    assert _value_similarity([1, 2], [1, 2]) > 0.9
    assert _value_similarity([], []) == 1.0


def test_value_similarity_numbers():
    assert _value_similarity(100, 100) == 1.0
    assert _value_similarity(100, 90) > 0.5


def test_value_similarity_none():
    assert _value_similarity(None, None) == 1.0
    assert _value_similarity(None, "test") == 0.0
    assert _value_similarity("test", None) == 0.0


def test_calculate_confidence_identical_results():
    items = [
        {"name": "测试主题", "count": 10, "tags": ["a", "b"]},
        {"name": "测试主题", "count": 10, "tags": ["a", "b"]},
        {"name": "测试主题", "count": 10, "tags": ["a", "b"]},
    ]
    conf = calculate_confidence(items)
    assert conf > 90


def test_calculate_confidence_different_results():
    items = [
        {"name": "主题A", "count": 10, "tags": ["a", "b"]},
        {"name": "主题B", "count": 20, "tags": ["x", "y"]},
        {"name": "主题C", "count": 30, "tags": ["m", "n"]},
    ]
    conf = calculate_confidence(items)
    assert conf < 50


def test_calculate_confidence_single_item():
    items = [{"name": "唯一", "value": 42}]
    conf = calculate_confidence(items)
    assert conf == 50.0


def test_calculate_confidence_empty():
    conf = calculate_confidence([])
    assert conf == 0.0


def test_calculate_confidence_with_weights():
    items = [
        {"name": "测试", "score": 100, "desc": "描述A"},
        {"name": "测试", "score": 95, "desc": "描述B"},
        {"name": "测试", "score": 90, "desc": "完全不同的描述内容"},
    ]
    weights = {"name": 2.0, "score": 1.0, "desc": 0.5}
    conf = calculate_confidence(items, field_weights=weights)
    assert 0.0 < conf < 100.0


def test_calculate_confidence_list_fields():
    items = [
        {"items": ["a", "b", "c"]},
        {"items": ["a", "b", "c"]},
        {"items": ["a", "b", "d"]},
    ]
    conf = calculate_confidence(items)
    assert 0.0 < conf < 100.0


def test_aggregate_results_basic():
    items = [
        {"name": "主题A", "value": 10},
        {"name": "主题A", "value": 10},
        {"name": "主题B", "value": 20},
    ]
    result = aggregate_results(items, confidence=75.0, confidence_threshold=60.0)
    assert "name" in result
    assert result["confidence"] == 75.0
    assert "confidence_details" in result
    assert "low_confidence_fields" in result
    assert result["num_samples"] == 3


def test_aggregate_results_majority_selection():
    items = [
        {"topic": "建筑机器人", "bottlenecks": ["a", "b"]},
        {"topic": "建筑机器人", "bottlenecks": ["a", "b"]},
        {"topic": "数字孪生", "bottlenecks": ["x", "y"]},
    ]
    result = aggregate_results(items, confidence=65.0)
    assert result["topic"] == "建筑机器人"


def test_aggregate_results_low_confidence_fields():
    items = [
        {"stable": "相同值", "unstable": "版本A"},
        {"stable": "相同值", "unstable": "版本B"},
        {"stable": "相同值", "unstable": "版本C"},
    ]
    result = aggregate_results(items, confidence=50.0, confidence_threshold=80.0)
    assert "unstable" in result["low_confidence_fields"]
    assert "stable" not in result["low_confidence_fields"]


def test_aggregate_results_empty():
    result = aggregate_results([], confidence=0.0)
    assert result["confidence"] == 0.0
    assert result["num_samples"] == 0


def test_aggregate_results_single_item():
    items = [{"name": "唯一结果", "value": 42}]
    result = aggregate_results(items, confidence=50.0)
    assert result["name"] == "唯一结果"
    assert result["num_samples"] == 1


def test_self_consistency_engine_init():
    mock_client = MockLLMClient()
    engine = SelfConsistencyEngine(
        llm_client=mock_client,
        num_samples=5,
        temp_min=0.2,
        temp_max=0.8,
        confidence_threshold=70.0
    )
    assert engine.num_samples == 5
    assert engine.temp_min == 0.2
    assert engine.temp_max == 0.8
    assert engine.confidence_threshold == 70.0


def test_self_consistency_engine_temperatures_linear():
    mock_client = MockLLMClient()
    engine = SelfConsistencyEngine(mock_client, num_samples=3, temp_min=0.1, temp_max=0.5)
    temps = engine._generate_temperatures()
    assert len(temps) == 3
    assert temps[0] == 0.1
    assert temps[2] == 0.5
    assert temps[0] < temps[1] < temps[2]


def test_self_consistency_engine_single_sample():
    mock_client = MockLLMClient()
    engine = SelfConsistencyEngine(mock_client, num_samples=1, temp_min=0.3, temp_max=0.7)
    temps = engine._generate_temperatures()
    assert len(temps) == 1
    assert temps[0] == 0.3


def test_self_consistency_engine_run_success():
    response = '{"name": "测试", "value": 42}'
    mock_client = MockLLMClient([response, response, response])

    def mock_parser(text):
        import json
        return json.loads(text)

    engine = SelfConsistencyEngine(mock_client, num_samples=3)
    msgs = [{"role": "user", "content": "test"}]
    result = engine.run(msgs, mock_parser)

    assert result["success"] is True
    assert result["num_samples"] == 3
    assert result["confidence"] > 90
    assert "name" in result
    assert result["name"] == "测试"
    assert mock_client.call_count == 3
    assert len(mock_client.called_temperatures) == 3


def test_self_consistency_engine_run_with_parser_args():
    response = '{"value": 42}'
    mock_client = MockLLMClient([response, response])

    def mock_parser(text, topic):
        import json
        data = json.loads(text)
        data["topic"] = topic
        return data

    engine = SelfConsistencyEngine(mock_client, num_samples=2)
    msgs = [{"role": "user", "content": "test"}]
    result = engine.run(msgs, mock_parser, parser_args=("测试主题",))

    assert result["success"] is True
    assert result["topic"] == "测试主题"


def test_self_consistency_engine_all_fail():
    mock_client = MockLLMClient([None, None, None])

    def mock_parser(text):
        return {"content": text}

    engine = SelfConsistencyEngine(mock_client, num_samples=3)
    msgs = [{"role": "user", "content": "test"}]
    result = engine.run(msgs, mock_parser)

    assert result["success"] is False
    assert result["num_samples"] == 0
    assert result["confidence"] == 0.0


def test_self_consistency_engine_some_fail():
    responses = ['{"val": 1}', None, '{"val": 1}']
    mock_client = MockLLMClient(responses)

    def mock_parser(text):
        import json
        return json.loads(text)

    engine = SelfConsistencyEngine(mock_client, num_samples=3)
    msgs = [{"role": "user", "content": "test"}]
    result = engine.run(msgs, mock_parser)

    assert result["success"] is True
    assert result["num_samples"] == 2
    assert mock_client.call_count == 3


def test_self_consistency_engine_parser_exception():
    response = 'invalid json'
    mock_client = MockLLMClient([response, response])

    def mock_parser(text):
        import json
        return json.loads(text)

    engine = SelfConsistencyEngine(mock_client, num_samples=2)
    msgs = [{"role": "user", "content": "test"}]
    result = engine.run(msgs, mock_parser)

    assert result["success"] is False
    assert result["num_samples"] == 0


def test_self_consistency_engine_different_results():
    responses = [
        '{"name": "方案A", "score": 90}',
        '{"name": "方案B", "score": 80}',
        '{"name": "方案A", "score": 85}',
    ]
    mock_client = MockLLMClient(responses)

    def mock_parser(text):
        import json
        return json.loads(text)

    engine = SelfConsistencyEngine(mock_client, num_samples=3, confidence_threshold=70.0)
    msgs = [{"role": "user", "content": "test"}]
    result = engine.run(msgs, mock_parser)

    assert result["success"] is True
    assert result["num_samples"] == 3
    assert 0.0 < result["confidence"] < 100.0
    assert result["name"] == "方案A"


def test_num_samples_minimum_one():
    mock_client = MockLLMClient(["test"])
    engine = SelfConsistencyEngine(mock_client, num_samples=0)
    assert engine.num_samples == 1


def test_confidence_details_in_result():
    items = [
        {"field_a": "相同", "field_b": "值1"},
        {"field_a": "相同", "field_b": "值2"},
        {"field_a": "相同", "field_b": "值3"},
    ]
    result = aggregate_results(items, confidence=60.0)
    assert "confidence_details" in result
    assert "field_a" in result["confidence_details"]
    assert "field_b" in result["confidence_details"]
    assert result["confidence_details"]["field_a"] > result["confidence_details"]["field_b"]


def run_all_tests():
    test_funcs = [
        test_text_similarity_identical,
        test_text_similarity_completely_different,
        test_text_similarity_partial,
        test_text_similarity_empty,
        test_list_similarity_identical,
        test_list_similarity_completely_different,
        test_list_similarity_partial_overlap,
        test_list_similarity_empty,
        test_value_similarity_strings,
        test_value_similarity_lists,
        test_value_similarity_numbers,
        test_value_similarity_none,
        test_calculate_confidence_identical_results,
        test_calculate_confidence_different_results,
        test_calculate_confidence_single_item,
        test_calculate_confidence_empty,
        test_calculate_confidence_with_weights,
        test_calculate_confidence_list_fields,
        test_aggregate_results_basic,
        test_aggregate_results_majority_selection,
        test_aggregate_results_low_confidence_fields,
        test_aggregate_results_empty,
        test_aggregate_results_single_item,
        test_self_consistency_engine_init,
        test_self_consistency_engine_temperatures_linear,
        test_self_consistency_engine_single_sample,
        test_self_consistency_engine_run_success,
        test_self_consistency_engine_run_with_parser_args,
        test_self_consistency_engine_all_fail,
        test_self_consistency_engine_some_fail,
        test_self_consistency_engine_parser_exception,
        test_self_consistency_engine_different_results,
        test_num_samples_minimum_one,
        test_confidence_details_in_result,
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
