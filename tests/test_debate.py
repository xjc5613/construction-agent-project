# -*- coding:utf-8 -*-
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.llm_orchestrator.debate import (
    DebateEngine,
    build_agent_review_messages,
    build_revision_messages,
    build_debate_summary_messages,
    _parse_review_text,
    AGENT_SYSTEM_PROMPTS,
    AGENT_REVIEW_QUESTIONS,
    AGENT_NAMES_CN,
)


class MockLLMClient:
    def __init__(self, responses=None):
        self.responses = responses or []
        self.call_count = 0
        self.called_messages = []

    def chat_completion(self, messages, temperature=None, max_tokens=None):
        self.called_messages.append(messages)
        idx = self.call_count
        self.call_count += 1
        if idx < len(self.responses):
            return self.responses[idx]
        return self.responses[-1] if self.responses else None


def test_agent_prompts_exist():
    expected_agents = ["tech_expert", "industry_analyst", "risk_assessor", "methodology_expert"]
    for agent in expected_agents:
        assert agent in AGENT_SYSTEM_PROMPTS, f"缺少 {agent} 的 system prompt"
        assert agent in AGENT_REVIEW_QUESTIONS, f"缺少 {agent} 的评审问题"
        assert agent in AGENT_NAMES_CN, f"缺少 {agent} 的中文名"
        assert len(AGENT_SYSTEM_PROMPTS[agent]) > 50, f"{agent} 的 system prompt 太短"
        assert len(AGENT_REVIEW_QUESTIONS[agent]) >= 3, f"{agent} 的评审问题太少"


def test_build_agent_review_messages():
    initial_result = {
        "topic_name": "建筑机器人",
        "bottlenecks_2030_2035": ["定位精度不足"],
        "breakthroughs_by_2040": ["全自动施工机器人"]
    }
    msgs = build_agent_review_messages(initial_result, "tech_expert", "测试背景")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "建筑机器人" in msgs[1]["content"]
    assert "测试背景" in msgs[1]["content"]
    assert "技术可行性" in msgs[0]["content"]


def test_build_revision_messages():
    initial_result = {"topic_name": "测试", "value": 42}
    reviews = {
        "tech_expert": "技术专家评审意见",
        "industry_analyst": "产业分析师评审意见"
    }
    msgs = build_revision_messages(initial_result, reviews)
    assert len(msgs) == 2
    assert "技术专家" in msgs[1]["content"]
    assert "产业分析师" in msgs[1]["content"]
    assert "测试" in msgs[1]["content"]


def test_build_debate_summary_messages():
    all_reviews = [
        {
            "round": 1,
            "reviews": {
                "tech_expert": "技术专家意见",
                "risk_assessor": "风险评估师意见"
            }
        }
    ]
    final_result = {"topic_name": "测试主题", "value": 100}
    msgs = build_debate_summary_messages(all_reviews, final_result)
    assert len(msgs) == 2
    assert "关键争议点" in msgs[1]["content"]
    assert "达成共识" in msgs[1]["content"]
    assert "仍存疑" in msgs[1]["content"]


def test_parse_review_text():
    review_text = """【优点】
- 预测结构清晰
- 时间节点合理

【主要问题】
- 技术路线不够详细
- 成本分析缺失

【改进建议】
- 补充技术细节
- 增加成本效益分析"""

    parsed = _parse_review_text(review_text)
    assert len(parsed["strengths"]) == 2
    assert len(parsed["issues"]) == 2
    assert len(parsed["suggestions"]) == 2
    assert "预测结构清晰" in parsed["strengths"]
    assert "技术路线不够详细" in parsed["issues"]


def test_parse_review_text_empty():
    parsed = _parse_review_text("")
    assert parsed["strengths"] == []
    assert parsed["issues"] == []
    assert parsed["suggestions"] == []


def test_parse_review_text_partial():
    review_text = """【优点】
- 只有优点"""
    parsed = _parse_review_text(review_text)
    assert len(parsed["strengths"]) == 1
    assert parsed["issues"] == []
    assert parsed["suggestions"] == []


def test_debate_engine_init_default():
    mock_client = MockLLMClient()
    engine = DebateEngine(llm_client=mock_client)
    assert engine.num_rounds == 2
    assert engine.confidence_threshold == 60.0
    assert len(engine.agents) == 4


def test_debate_engine_init_custom():
    mock_client = MockLLMClient()
    engine = DebateEngine(
        llm_client=mock_client,
        agents=["tech_expert", "risk_assessor"],
        num_rounds=3,
        confidence_threshold=70.0
    )
    assert engine.num_rounds == 3
    assert engine.confidence_threshold == 70.0
    assert len(engine.agents) == 2
    assert "tech_expert" in engine.agents
    assert "risk_assessor" in engine.agents


def test_debate_engine_init_invalid_agents():
    mock_client = MockLLMClient()
    engine = DebateEngine(
        llm_client=mock_client,
        agents=["invalid_agent", "another_bad"],
    )
    assert len(engine.agents) == 4


def test_debate_engine_init_min_rounds():
    mock_client = MockLLMClient()
    engine = DebateEngine(llm_client=mock_client, num_rounds=0)
    assert engine.num_rounds == 1


def test_debate_run_single_round():
    review_response = """【优点】
- 结构完整

【主要问题】
- 细节不足

【改进建议】
- 补充细节"""

    summary_response = "辩论摘要：技术路线存在争议，基本框架达成共识。"

    mock_client = MockLLMClient([
        review_response,
        review_response,
        review_response,
        review_response,
        summary_response,
    ])

    initial_result = {
        "topic_name": "测试主题",
        "bottlenecks_2030_2035": ["瓶颈1"],
        "breakthroughs_by_2040": ["突破1"],
    }

    def mock_parser(text):
        return json.loads(text) if text and "{" in text else None

    engine = DebateEngine(
        llm_client=mock_client,
        agents=["tech_expert", "risk_assessor"],
        num_rounds=1,
    )

    result = engine.run(
        initial_messages=[{"role": "user", "content": "test"}],
        initial_result=initial_result,
        parser_func=mock_parser,
    )

    assert "debate_info" in result
    assert result["debate_info"]["success"] is True
    assert result["debate_info"]["num_rounds"] == 1
    assert len(result["debate_info"]["agents_used"]) == 2
    assert "debate_summary" in result["debate_info"]
    assert result["topic_name"] == "测试主题"


def test_debate_run_multi_round():
    review_response = """【优点】
- 结构完整

【主要问题】
- 细节不足

【改进建议】
- 补充细节"""

    revision_response = '{"topic_name": "修正后的主题", "bottlenecks_2030_2035": ["瓶颈1", "瓶颈2"], "breakthroughs_by_2040": ["突破1"]}'
    summary_response = "多轮辩论摘要"

    mock_client = MockLLMClient([
        review_response,
        revision_response,
        review_response,
        summary_response,
    ])

    initial_result = {
        "topic_name": "初始主题",
        "bottlenecks_2030_2035": ["瓶颈1"],
        "breakthroughs_by_2040": ["突破1"],
    }

    def mock_parser(text):
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None

    engine = DebateEngine(
        llm_client=mock_client,
        agents=["tech_expert"],
        num_rounds=2,
    )

    result = engine.run(
        initial_messages=[{"role": "user", "content": "test"}],
        initial_result=initial_result,
        parser_func=mock_parser,
    )

    assert result["debate_info"]["success"] is True
    assert result["debate_info"]["num_rounds"] == 2
    assert result["debate_info"]["num_versions"] >= 2


def test_debate_run_initial_result_none():
    mock_client = MockLLMClient()
    engine = DebateEngine(llm_client=mock_client)

    result = engine.run(
        initial_messages=[],
        initial_result=None,
        parser_func=lambda x: x,
    )

    assert result["success"] is False
    assert result["final_result"] is None


def test_debate_run_all_agents_fail():
    mock_client = MockLLMClient([None, None, None, None])

    initial_result = {"topic_name": "测试", "value": 42}

    engine = DebateEngine(
        llm_client=mock_client,
        agents=["tech_expert", "risk_assessor"],
        num_rounds=2,
    )

    result = engine.run(
        initial_messages=[{"role": "user", "content": "test"}],
        initial_result=initial_result,
        parser_func=lambda x: x,
    )

    assert "debate_info" in result
    assert result["debate_info"]["num_rounds"] == 0
    assert result["topic_name"] == "测试"


def test_debate_run_some_agents_fail():
    review_response = """【优点】
- 测试优点

【主要问题】
- 测试问题

【改进建议】
- 测试建议"""

    summary_response = "摘要"

    mock_client = MockLLMClient([
        review_response,
        None,
        summary_response,
    ])

    initial_result = {"topic_name": "测试", "value": 42}

    engine = DebateEngine(
        llm_client=mock_client,
        agents=["tech_expert", "industry_analyst"],
        num_rounds=1,
    )

    result = engine.run(
        initial_messages=[{"role": "user", "content": "test"}],
        initial_result=initial_result,
        parser_func=lambda x: x if isinstance(x, dict) else None,
    )

    assert result["debate_info"]["success"] is True
    assert len(result["debate_info"]["agents_used"]) == 1
    assert "tech_expert" in result["debate_info"]["agents_used"]


def test_debate_run_with_parser_args():
    review_response = """【优点】
- 好

【主要问题】
- 差

【改进建议】
- 改进"""

    summary_response = "摘要"

    mock_client = MockLLMClient([
        review_response,
        summary_response,
    ])

    initial_result = {"topic_name": "测试", "value": 42}
    extra_arg = "额外参数"

    def mock_parser(text, arg1):
        assert arg1 == extra_arg
        return {"topic_name": "测试", "value": 42, "arg": arg1}

    engine = DebateEngine(
        llm_client=mock_client,
        agents=["tech_expert"],
        num_rounds=1,
    )

    result = engine.run(
        initial_messages=[{"role": "user", "content": "test"}],
        initial_result=initial_result,
        parser_func=mock_parser,
        parser_args=(extra_arg,),
    )

    assert result["debate_info"]["success"] is True


def test_debate_run_with_context_info():
    review_response = """【优点】
- 有背景信息

【主要问题】
- 暂无

【改进建议】
- 暂无"""

    summary_response = "带背景的摘要"

    mock_client = MockLLMClient([
        review_response,
        summary_response,
    ])

    initial_result = {"topic_name": "测试主题"}
    context = "智能建造领域，建筑机器人方向"

    engine = DebateEngine(
        llm_client=mock_client,
        agents=["tech_expert"],
        num_rounds=1,
    )

    result = engine.run(
        initial_messages=[{"role": "user", "content": "test"}],
        initial_result=initial_result,
        parser_func=lambda x: x if isinstance(x, dict) else None,
        context_info=context,
    )

    assert result["debate_info"]["success"] is True
    assert mock_client.call_count >= 1


def test_debate_confidence_calculation():
    review_resp = """【优点】
- 不错

【主要问题】
- 可以改进

【改进建议】
- 优化"""

    revision1 = '{"topic_name": "主题A", "score": 90, "items": ["a", "b"]}'
    revision2 = '{"topic_name": "主题A", "score": 85, "items": ["a", "c"]}'
    summary = "摘要"

    mock_client = MockLLMClient([
        review_resp,
        review_resp,
        revision1,
        review_resp,
        review_resp,
        summary,
    ])

    initial = {"topic_name": "主题A", "score": 80, "items": ["a"]}

    def parser(text):
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None

    engine = DebateEngine(
        llm_client=mock_client,
        agents=["tech_expert"],
        num_rounds=3,
    )

    result = engine.run(
        initial_messages=[{"role": "user", "content": "test"}],
        initial_result=initial,
        parser_func=parser,
    )

    assert "debate_info" in result
    assert 0.0 <= result["debate_info"]["confidence"] <= 100.0


def run_all_tests():
    test_funcs = [
        test_agent_prompts_exist,
        test_build_agent_review_messages,
        test_build_revision_messages,
        test_build_debate_summary_messages,
        test_parse_review_text,
        test_parse_review_text_empty,
        test_parse_review_text_partial,
        test_debate_engine_init_default,
        test_debate_engine_init_custom,
        test_debate_engine_init_invalid_agents,
        test_debate_engine_init_min_rounds,
        test_debate_run_single_round,
        test_debate_run_multi_round,
        test_debate_run_initial_result_none,
        test_debate_run_all_agents_fail,
        test_debate_run_some_agents_fail,
        test_debate_run_with_parser_args,
        test_debate_run_with_context_info,
        test_debate_confidence_calculation,
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
