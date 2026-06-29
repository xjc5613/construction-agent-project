# -*- coding:utf-8-*-
import sys
import os
import tempfile
import shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock
from pathlib import Path


def _get_mock_round1_result(topic_name, with_confidence=False, with_evidence=False, with_reasoning=False):
    result = {
        "topic_name": topic_name,
        "bottlenecks_2030_2035": ["瓶颈1", "瓶颈2"],
        "breakthroughs_by_2040": ["突破1", "突破2"],
        "deep_fusion_topics": ["融合主题1", "融合主题2"],
        "fusion_scenario": f"{topic_name}的融合场景描述",
        "typical_day_2040": f"{topic_name}的典型一天描述"
    }
    if with_confidence:
        result["confidence"] = 82.5
        result["confidence_details"] = {
            "bottlenecks_2030_2035": 85.0,
            "breakthroughs_by_2040": 80.0,
            "deep_fusion_topics": 75.0,
            "fusion_scenario": 78.0,
            "typical_day_2040": 55.0
        }
        result["low_confidence_fields"] = ["typical_day_2040"]
        result["num_samples"] = 3
    if with_evidence:
        result["overall_evidence_score"] = 72.0
        result["bottlenecks_2030_2035_tagged"] = [
            {"text": "瓶颈1", "evidence_sources": [{"type": "ipc_class", "value": "G06F", "quality": "direct"}], "evidence_score": 75.0},
            {"text": "瓶颈2", "evidence_sources": [], "evidence_score": 40.0}
        ]
        result["breakthroughs_by_2040_tagged"] = [
            {"text": "突破1", "evidence_sources": [{"type": "fusion_pair", "value": "G06F-G06N", "probability": 0.85, "quality": "direct"}], "evidence_score": 80.0},
            {"text": "突破2", "evidence_sources": [], "evidence_score": 30.0}
        ]
    if with_reasoning:
        result["reasoning_chain"] = [
            {
                "step": 1,
                "input_evidence": "专利数据显示技术热度上升",
                "reasoning": "度中心度提升表明技术重要性增加",
                "conclusion": f"{topic_name}是重要发展方向"
            },
            {
                "step": 2,
                "input_evidence": "跨领域融合趋势明显",
                "reasoning": "多技术交叉融合催生创新",
                "conclusion": f"{topic_name}将与其他技术深度融合"
            }
        ]
    return result


def _get_mock_round2_result(with_confidence=False, with_reasoning=False):
    result = {
        "new_paradigm_name": "AI驱动的全生命周期智能建造新范式",
        "new_paradigm_description": "基于大模型、数字孪生、机器人集群等技术，实现从设计、施工到运维的全流程智能化、自动化建造，大幅提升效率、降低成本、保障安全。"
    }
    if with_confidence:
        result["confidence"] = 78.0
        result["confidence_details"] = {"new_paradigm_name": 80.0, "new_paradigm_description": 75.0}
        result["low_confidence_fields"] = []
    if with_reasoning:
        result["reasoning_chain"] = [
            {
                "step": 1,
                "input_evidence": "多技术融合趋势",
                "reasoning": "AI、机器人、数字孪生等技术汇聚",
                "conclusion": "将催生新的建造范式"
            }
        ]
    return result


def _get_mock_round3_result(with_enhanced=False, with_reasoning=False):
    if with_enhanced:
        items = [
            {
                "year": 2030,
                "category": "技术里程碑",
                "description": "基础算法与关键技术突破",
                "trl_level": 4,
                "impact_scope": "industry",
                "uncertainty_level": "low",
                "dependencies": ["AI算法", "传感器技术"]
            },
            {
                "year": 2035,
                "category": "产品里程碑",
                "description": "商业化产品规模化应用",
                "trl_level": 7,
                "impact_scope": "global",
                "uncertainty_level": "medium",
                "dependencies": ["成本下降", "标准制定"]
            },
            {
                "year": 2040,
                "category": "技术里程碑",
                "description": "全自主智能建造系统成熟",
                "trl_level": 9,
                "impact_scope": "global",
                "uncertainty_level": "high",
                "dependencies": ["通用AI", "机器人技术"]
            }
        ]
    else:
        items = [
            {"year": 2030, "category": "技术里程碑", "description": "基础算法与关键技术突破"},
            {"year": 2035, "category": "产品里程碑", "description": "商业化产品规模化应用"},
            {"year": 2040, "category": "技术里程碑", "description": "全自主智能建造系统成熟"}
        ]

    if with_reasoning:
        return {
            "roadmap_items": items,
            "reasoning_chain": [
                {
                    "step": 1,
                    "input_evidence": "技术发展S曲线",
                    "reasoning": "从研发到应用需经历技术验证、产品化、规模化阶段",
                    "conclusion": "2030年技术突破，2035年产品化，2040年成熟"
                }
            ]
        }
    return items


def test_default_config_end_to_end():
    """测试默认配置下完整流程（mock掉真实API调用）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        mock_outputs_parsed = tmp_path / "outputs" / "parsed"
        mock_outputs_report = tmp_path / "outputs" / "final_report"

        topic_inputs = [
            {"topic_name": "建筑机器人", "keywords": ["机器人"], "example": "test", "ipc_trend": "test", "fusion_pairs": []},
            {"topic_name": "数字孪生", "keywords": ["数字孪生"], "example": "test", "ipc_trend": "test", "fusion_pairs": []}
        ]

        mock_round1_results = [
            _get_mock_round1_result("建筑机器人"),
            _get_mock_round1_result("数字孪生")
        ]
        mock_round2_result = _get_mock_round2_result()
        mock_round3_result = _get_mock_round3_result()

        with patch('src.main.build_round1_inputs', return_value=topic_inputs):
            with patch('src.main.run_round1', return_value=mock_round1_results):
                with patch('src.main.run_round2', return_value=mock_round2_result):
                    with patch('src.main.run_round3', return_value=mock_round3_result):
                        with patch('src.report_generator.OUTPUTS_REPORT', mock_outputs_report):
                            from src.main import main
                            main()

        report_path = mock_outputs_report / "forecast_report.md"
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "智能建造2040技术趋势预测报告" in content
        assert "技术主题演化预测" in content
        assert "智能建造新范式" in content
        assert "技术路线图" in content
        assert "不确定性分析" in content
        assert "方法说明" in content
        assert "建筑机器人" in content
        assert "数字孪生" in content


def test_self_consistency_enabled():
    """测试自洽性验证功能开启"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        mock_outputs_report = tmp_path / "outputs" / "final_report"

        round1 = [
            _get_mock_round1_result("建筑机器人", with_confidence=True),
            _get_mock_round1_result("数字孪生", with_confidence=True)
        ]
        round2 = _get_mock_round2_result(with_confidence=True)
        round3 = _get_mock_round3_result()

        from src.report_generator import generate_final_report
        with patch('src.report_generator.OUTPUTS_REPORT', mock_outputs_report):
            generate_final_report(round1, round2, round3)

        report_path = mock_outputs_report / "forecast_report.md"
        content = report_path.read_text(encoding="utf-8")
        assert "置信度概览" in content
        assert "🟢" in content
        assert "高置信" in content
        assert "低置信度项汇总" in content
        assert "高不确定性项" in content


def test_multi_model_enabled():
    """测试多模型集成功能开启"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        mock_outputs_report = tmp_path / "outputs" / "final_report"

        round1 = [
            _get_mock_round1_result("建筑机器人", with_confidence=True),
        ]
        round1[0]["num_models"] = 3
        round1[0]["success_models"] = ["model1", "model2", "model3"]
        round1[0]["strategy"] = "weighted_vote"

        round2 = _get_mock_round2_result(with_confidence=True)
        round3 = _get_mock_round3_result()

        from src.report_generator import generate_final_report
        with patch('src.report_generator.OUTPUTS_REPORT', mock_outputs_report):
            generate_final_report(round1, round2, round3)

        report_path = mock_outputs_report / "forecast_report.md"
        content = report_path.read_text(encoding="utf-8")
        assert "置信度概览" in content


def test_multi_agent_debate_enabled():
    """测试多Agent辩论功能开启"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        mock_outputs_report = tmp_path / "outputs" / "final_report"

        round1 = [
            _get_mock_round1_result("建筑机器人"),
        ]
        round1[0]["debate_info"] = {
            "success": True,
            "num_rounds": 2,
            "agents_used": ["tech_expert", "industry_analyst", "risk_assessor"],
            "confidence": 80.0,
            "debate_summary": "经过多轮辩论，专家们达成了基本共识..."
        }

        round2 = _get_mock_round2_result()
        round3 = _get_mock_round3_result()

        from src.report_generator import generate_final_report
        with patch('src.report_generator.OUTPUTS_REPORT', mock_outputs_report):
            generate_final_report(round1, round2, round3)

        report_path = mock_outputs_report / "forecast_report.md"
        assert report_path.exists()


def test_reasoning_chain_enabled():
    """测试推理链条功能开启"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        mock_outputs_report = tmp_path / "outputs" / "final_report"

        round1 = [
            _get_mock_round1_result("建筑机器人", with_evidence=True, with_reasoning=True),
        ]
        round2 = _get_mock_round2_result(with_reasoning=True)
        round3 = _get_mock_round3_result(with_reasoning=True)

        from src.report_generator import generate_final_report
        with patch('src.report_generator.OUTPUTS_REPORT', mock_outputs_report):
            generate_final_report(round1, round2, round3)

        report_path = mock_outputs_report / "forecast_report.md"
        content = report_path.read_text(encoding="utf-8")
        assert "推理链条" in content
        assert "核心依据来源" in content
        assert "步骤1" in content
        assert "依据充分度" in content


def test_roadmap_enhanced_enabled():
    """测试路线图增强功能开启"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        mock_outputs_report = tmp_path / "outputs" / "final_report"

        round1 = [_get_mock_round1_result("建筑机器人")]
        round2 = _get_mock_round2_result()
        round3 = _get_mock_round3_result(with_enhanced=True)

        from src.report_generator import generate_final_report
        with patch('src.report_generator.OUTPUTS_REPORT', mock_outputs_report):
            generate_final_report(round1, round2, round3)

        report_path = mock_outputs_report / "forecast_report.md"
        content = report_path.read_text(encoding="utf-8")
        assert "TRL" in content
        assert "影响范围" in content
        assert "不确定性" in content
        assert "行业级" in content
        assert "全局" in content


def test_all_features_enabled():
    """测试全功能开启配置"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        mock_outputs_report = tmp_path / "outputs" / "final_report"

        round1 = [
            _get_mock_round1_result("建筑机器人", with_confidence=True, with_evidence=True, with_reasoning=True),
            _get_mock_round1_result("数字孪生", with_confidence=True, with_evidence=True, with_reasoning=True),
        ]
        round1[0]["debate_info"] = {
            "success": True,
            "num_rounds": 2,
            "agents_used": ["tech_expert", "industry_analyst"],
            "confidence": 85.0
        }
        round1[0]["num_models"] = 3

        round2 = _get_mock_round2_result(with_confidence=True, with_reasoning=True)
        round3 = _get_mock_round3_result(with_enhanced=True, with_reasoning=True)

        from src.report_generator import generate_final_report
        with patch('src.report_generator.OUTPUTS_REPORT', mock_outputs_report):
            generate_final_report(round1, round2, round3)

        report_path = mock_outputs_report / "forecast_report.md"
        content = report_path.read_text(encoding="utf-8")
        assert "置信度概览" in content
        assert "🟢" in content
        assert "低置信度项汇总" in content
        assert "依据充分度" in content
        assert "TRL" in content
        assert "影响范围" in content
        assert "推理链条" in content
        assert "核心依据来源" in content
        assert "方法说明" in content
        assert "不确定性分析" in content


def test_cache_mechanism_force_rerun():
    """测试缓存机制（force_rerun参数）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        mock_outputs_parsed = tmp_path / "outputs" / "parsed"
        mock_outputs_parsed.mkdir(parents=True, exist_ok=True)

        cached_data = {"topic_name": "cached_topic", "confidence": 99.9}
        import json
        cache_file = mock_outputs_parsed / "round1_测试主题.json"
        cache_file.write_text(json.dumps(cached_data, ensure_ascii=False), encoding="utf-8")

        with patch('src.llm_orchestrator.round1_runner.OUTPUTS_PARSED', mock_outputs_parsed):
            with patch('src.llm_orchestrator.round1_runner.OUTPUTS_RAW', mock_outputs_parsed):
                with patch('src.llm_orchestrator.round1_runner.LLMClient') as mock_client_cls:
                    mock_client = MagicMock()
                    mock_client.chat_completion.return_value = None
                    mock_client_cls.return_value = mock_client

                    from src.llm_orchestrator.round1_runner import run_round1

                    topic_inputs = [{"topic_name": "测试主题", "keywords": [], "example": "", "ipc_trend": "", "fusion_pairs": []}]

                    results = run_round1(topic_inputs, force_rerun=False)
                    assert len(results) == 1
                    assert results[0]["topic_name"] == "cached_topic"
                    assert results[0]["confidence"] == 99.9

                    results_forced = run_round1(topic_inputs, force_rerun=True)
                    assert len(results_forced) == 0


def test_main_function_module_import():
    """测试主模块可以正确导入"""
    from src.main import main
    assert callable(main)


def test_report_generator_module_import():
    """测试报告生成器模块可以正确导入"""
    from src.report_generator import generate_final_report
    assert callable(generate_final_report)


def test_round1_runner_module_import():
    """测试Round1运行器模块可以正确导入"""
    from src.llm_orchestrator.round1_runner import run_round1
    assert callable(run_round1)


def test_round2_runner_module_import():
    """测试Round2运行器模块可以正确导入"""
    from src.llm_orchestrator.round2_runner import run_round2
    assert callable(run_round2)


def test_round3_runner_module_import():
    """测试Round3运行器模块可以正确导入"""
    from src.llm_orchestrator.round3_runner import run_round3
    assert callable(run_round3)


def test_settings_consistency():
    """测试配置设置的一致性"""
    from config import settings
    assert hasattr(settings, 'ENABLE_SELF_CONSISTENCY')
    assert hasattr(settings, 'ENABLE_MULTI_MODEL')
    assert hasattr(settings, 'ENABLE_MULTI_AGENT_DEBATE')
    assert hasattr(settings, 'ENABLE_REASONING_CHAIN')
    assert hasattr(settings, 'ENABLE_ROADMAP_ENHANCED')
    assert hasattr(settings, 'CONFIDENCE_THRESHOLD')
    assert isinstance(settings.ENABLE_SELF_CONSISTENCY, bool)
    assert isinstance(settings.ENABLE_MULTI_MODEL, bool)
    assert isinstance(settings.ENABLE_MULTI_AGENT_DEBATE, bool)
    assert isinstance(settings.ENABLE_REASONING_CHAIN, bool)
    assert isinstance(settings.ENABLE_ROADMAP_ENHANCED, bool)


def run_all_tests():
    test_funcs = [
        test_default_config_end_to_end,
        test_self_consistency_enabled,
        test_multi_model_enabled,
        test_multi_agent_debate_enabled,
        test_reasoning_chain_enabled,
        test_roadmap_enhanced_enabled,
        test_all_features_enabled,
        test_cache_mechanism_force_rerun,
        test_main_function_module_import,
        test_report_generator_module_import,
        test_round1_runner_module_import,
        test_round2_runner_module_import,
        test_round3_runner_module_import,
        test_settings_consistency,
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
