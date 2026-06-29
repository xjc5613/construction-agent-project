# -*- coding:utf-8-*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock
from src.report_generator import (
    generate_final_report,
    _get_confidence_level,
    _has_confidence_data,
    _has_evidence_data,
    _has_reasoning_chain,
    _has_roadmap_enhanced,
    _collect_low_confidence_items,
    _build_topic_section,
    _build_uncertainty_section,
    _build_methodology_section,
    _build_roadmap_section,
    _build_reasoning_chain_appendix,
)


def test_confidence_level_high():
    assert "🟢" in _get_confidence_level(90.0)
    assert "高置信" in _get_confidence_level(85.0)
    assert "🟢" in _get_confidence_level(80.0)


def test_confidence_level_medium():
    assert "🟡" in _get_confidence_level(70.0)
    assert "中置信" in _get_confidence_level(65.0)
    assert "🟡" in _get_confidence_level(60.0)


def test_confidence_level_low():
    assert "🔴" in _get_confidence_level(50.0)
    assert "低置信" in _get_confidence_level(30.0)
    assert "🔴" in _get_confidence_level(59.9)


def test_has_confidence_data_true():
    data = [
        {"topic_name": "测试", "confidence": 85.0},
        {"topic_name": "测试2"}
    ]
    assert _has_confidence_data(data) is True


def test_has_confidence_data_false():
    data = [
        {"topic_name": "测试"},
        {"topic_name": "测试2"}
    ]
    assert _has_confidence_data(data) is False


def test_has_confidence_data_empty():
    assert _has_confidence_data([]) is False


def test_has_evidence_data_true():
    data = [
        {"topic_name": "测试", "overall_evidence_score": 75.0},
    ]
    assert _has_evidence_data(data) is True


def test_has_evidence_data_false():
    data = [
        {"topic_name": "测试"},
    ]
    assert _has_evidence_data(data) is False


def test_has_reasoning_chain_round1():
    round1 = [
        {"topic_name": "测试", "reasoning_chain": [{"step": 1, "conclusion": "test"}]}
    ]
    round2 = {}
    round3 = []
    assert _has_reasoning_chain(round1, round2, round3) is True


def test_has_reasoning_chain_round2():
    round1 = []
    round2 = {"reasoning_chain": [{"step": 1, "conclusion": "test"}]}
    round3 = []
    assert _has_reasoning_chain(round1, round2, round3) is True


def test_has_reasoning_chain_round3():
    round1 = []
    round2 = {}
    round3 = {"reasoning_chain": [{"step": 1, "conclusion": "test"}]}
    assert _has_reasoning_chain(round1, round2, round3) is True


def test_has_reasoning_chain_false():
    round1 = [{"topic_name": "测试", "reasoning_chain": []}]
    round2 = {"reasoning_chain": []}
    round3 = []
    assert _has_reasoning_chain(round1, round2, round3) is False


def test_has_roadmap_enhanced_true():
    data = [
        {"year": 2030, "category": "技术里程碑", "description": "测试", "trl_level": 5}
    ]
    assert _has_roadmap_enhanced(data) is True


def test_has_roadmap_enhanced_false():
    data = [
        {"year": 2030, "category": "技术里程碑", "description": "测试"}
    ]
    assert _has_roadmap_enhanced(data) is False


def test_collect_low_confidence_items():
    round1 = [
        {
            "topic_name": "主题1",
            "confidence": 70.0,
            "low_confidence_fields": ["field1", "field2"],
            "confidence_details": {"field1": 50.0, "field2": 55.0, "field3": 70.0}
        },
        {
            "topic_name": "主题2",
            "confidence": 85.0,
            "low_confidence_fields": [],
            "confidence_details": {}
        },
        {
            "topic_name": "主题3",
            "confidence": 45.0,
            "low_confidence_fields": ["fieldA"],
            "confidence_details": {"fieldA": 40.0}
        }
    ]
    items = _collect_low_confidence_items(round1)
    assert len(items) == 3
    topics = [item["topic"] for item in items]
    assert "主题1" in topics
    assert "主题3" in topics
    fields = [item["field"] for item in items]
    assert "field1" in fields
    assert "field2" in fields
    assert "fieldA" in fields


def test_build_topic_section_with_confidence():
    topic = {
        "topic_name": "建筑机器人",
        "bottlenecks_2030_2035": ["感知精度不足", "成本过高"],
        "breakthroughs_by_2040": ["全自主施工机器人"],
        "deep_fusion_topics": ["计算机视觉", "运动控制"],
        "fusion_scenario": "机器人协同作业",
        "typical_day_2040": "机器人24小时施工",
        "confidence": 85.5,
        "low_confidence_fields": ["typical_day_2040"],
        "confidence_details": {"typical_day_2040": 50.0}
    }
    lines = _build_topic_section(topic, has_confidence=True, has_evidence=False)
    content = "".join(lines)
    assert "建筑机器人" in content
    assert "🟢" in content
    assert "高置信" in content
    assert "85.5%" in content
    assert "⚠️" in content
    assert "高不确定性项" in content
    assert "typical_day_2040" in content


def test_build_topic_section_with_evidence():
    topic = {
        "topic_name": "建筑机器人",
        "bottlenecks_2030_2035": ["感知精度不足"],
        "breakthroughs_by_2040": ["全自主施工机器人"],
        "deep_fusion_topics": [],
        "fusion_scenario": "",
        "typical_day_2040": "",
        "overall_evidence_score": 72.3
    }
    lines = _build_topic_section(topic, has_confidence=False, has_evidence=True)
    content = "".join(lines)
    assert "依据充分度" in content
    assert "72.3" in content


def test_build_topic_section_backward_compatible():
    topic = {
        "topic_name": "建筑机器人",
        "bottlenecks_2030_2035": ["感知精度不足", "成本过高"],
        "breakthroughs_by_2040": ["全自主施工机器人"],
        "deep_fusion_topics": ["计算机视觉"],
        "fusion_scenario": "机器人协同作业",
        "typical_day_2040": "机器人24小时施工"
    }
    lines = _build_topic_section(topic, has_confidence=False, has_evidence=False)
    content = "".join(lines)
    assert "建筑机器人" in content
    assert "2030-2035年瓶颈" in content
    assert "至2040年突破" in content
    assert "深度融合主题" in content
    assert "融合场景" in content
    assert "典型一天" in content
    assert "🟢" not in content
    assert "置信" not in content
    assert "依据充分度" not in content


def test_build_uncertainty_section_with_confidence():
    round1 = [
        {
            "topic_name": "主题1",
            "low_confidence_fields": ["field1"],
            "confidence_details": {"field1": 45.0}
        }
    ]
    lines = _build_uncertainty_section(round1, has_confidence=True)
    content = "".join(lines)
    assert "不确定性分析" in content
    assert "低置信度项汇总" in content
    assert "关键假设与不确定因素" in content
    assert "预测方法局限性" in content
    assert "主题1" in content
    assert "field1" in content


def test_build_uncertainty_section_without_confidence():
    round1 = [{"topic_name": "测试"}]
    lines = _build_uncertainty_section(round1, has_confidence=False)
    content = "".join(lines)
    assert "不确定性分析" in content
    assert "关键假设与不确定因素" in content
    assert "预测方法局限性" in content


def test_build_methodology_section():
    lines = _build_methodology_section()
    content = "".join(lines)
    assert "方法说明" in content
    assert "预测方法论" in content
    assert "置信度评估方式" in content
    assert "技术工具与数据来源" in content
    assert "自洽性验证" in content
    assert "多模型集成" in content
    assert "多Agent辩论" in content
    assert "高置信" in content
    assert "中置信" in content
    assert "低置信" in content


def test_build_roadmap_section_enhanced():
    round3 = [
        {
            "year": 2030,
            "category": "技术里程碑",
            "description": "技术突破",
            "trl_level": 5,
            "impact_scope": "industry",
            "uncertainty_level": "medium"
        },
        {
            "year": 2035,
            "category": "产品里程碑",
            "description": "产品落地",
            "trl_level": 7,
            "impact_scope": "global",
            "uncertainty_level": "low"
        }
    ]
    lines = _build_roadmap_section(round3, has_enhanced=True)
    content = "".join(lines)
    assert "技术路线图" in content
    assert "TRL" in content
    assert "影响范围" in content
    assert "不确定性" in content
    assert "2030" in content
    assert "2035" in content
    assert "技术里程碑" in content
    assert "产品里程碑" in content
    assert "技术突破" in content
    assert "产品落地" in content
    assert "5" in content
    assert "7" in content
    assert "行业级" in content
    assert "全局" in content
    assert "中" in content
    assert "低" in content


def test_build_roadmap_section_legacy():
    round3 = [
        {"year": 2030, "category": "技术里程碑", "description": "技术突破"},
        {"year": 2035, "category": "产品里程碑", "description": "产品落地"}
    ]
    lines = _build_roadmap_section(round3, has_enhanced=False)
    content = "".join(lines)
    assert "技术路线图" in content
    assert "2030" in content
    assert "2035" in content
    assert "TRL" not in content
    assert "影响范围" not in content


def test_build_reasoning_chain_appendix():
    round1 = [
        {
            "topic_name": "建筑机器人",
            "reasoning_chain": [
                {
                    "step": 1,
                    "input_evidence": "专利数据显示B25J增长",
                    "reasoning": "度中心度提升表明技术热度",
                    "conclusion": "机器人技术是重要方向"
                }
            ],
            "overall_evidence_score": 75.0,
            "bottlenecks_2030_2035_tagged": [
                {
                    "text": "感知精度不足",
                    "evidence_sources": [{"type": "ipc_class", "value": "B25J", "quality": "direct"}],
                    "evidence_score": 65.0
                }
            ],
            "breakthroughs_by_2040_tagged": []
        }
    ]
    round2 = {}
    round3 = []
    lines = _build_reasoning_chain_appendix(round1, round2, round3)
    content = "".join(lines)
    assert "推理链条" in content
    assert "建筑机器人" in content
    assert "步骤1" in content
    assert "输入证据" in content
    assert "推理过程" in content
    assert "结论" in content
    assert "核心依据来源" in content
    assert "整体依据充分度" in content
    assert "75.0" in content
    assert "感知精度不足" in content
    assert "ipc_class:B25J" in content


@patch('src.report_generator.write_text')
@patch('src.report_generator.OUTPUTS_REPORT')
def test_generate_final_report_with_all_features(mock_outputs, mock_write):
    mock_outputs.__truediv__.return_value = "/tmp/test_report.md"

    round1 = [
        {
            "topic_name": "建筑机器人",
            "bottlenecks_2030_2035": ["感知精度不足"],
            "breakthroughs_by_2040": ["全自主机器人"],
            "deep_fusion_topics": ["AI"],
            "fusion_scenario": "协同作业",
            "typical_day_2040": "24小时施工",
            "confidence": 85.0,
            "low_confidence_fields": ["typical_day_2040"],
            "confidence_details": {"typical_day_2040": 50.0},
            "overall_evidence_score": 70.0,
            "reasoning_chain": [{"step": 1, "conclusion": "test"}]
        }
    ]
    round2 = {
        "new_paradigm_name": "智能建造新范式",
        "new_paradigm_description": "AI驱动的全自动化建造"
    }
    round3 = [
        {
            "year": 2030,
            "category": "技术里程碑",
            "description": "技术突破",
            "trl_level": 5,
            "impact_scope": "industry",
            "uncertainty_level": "medium"
        }
    ]

    generate_final_report(round1, round2, round3)

    assert mock_write.called
    call_args = mock_write.call_args
    content = call_args[0][0]
    assert "智能建造2040技术趋势预测报告" in content
    assert "技术主题演化预测" in content
    assert "智能建造新范式" in content
    assert "技术路线图" in content
    assert "不确定性分析" in content
    assert "方法说明" in content
    assert "推理链条" in content
    assert "🟢" in content
    assert "置信度概览" in content
    assert "TRL" in content


@patch('src.report_generator.write_text')
@patch('src.report_generator.OUTPUTS_REPORT')
def test_generate_final_report_backward_compatible(mock_outputs, mock_write):
    mock_outputs.__truediv__.return_value = "/tmp/test_report.md"

    round1 = [
        {
            "topic_name": "建筑机器人",
            "bottlenecks_2030_2035": ["感知精度不足", "成本过高"],
            "breakthroughs_by_2040": ["全自主施工机器人"],
            "deep_fusion_topics": ["计算机视觉", "运动控制"],
            "fusion_scenario": "机器人集群协同完成复杂施工任务",
            "typical_day_2040": "工地由机器人24小时不间断施工"
        }
    ]
    round2 = {
        "new_paradigm_name": "智能建造新范式",
        "new_paradigm_description": "AI驱动的全自动化建造"
    }
    round3 = [
        {"year": 2030, "category": "技术里程碑", "description": "技术研发突破"},
        {"year": 2035, "category": "产品里程碑", "description": "产品商业化应用"}
    ]

    generate_final_report(round1, round2, round3)

    assert mock_write.called
    call_args = mock_write.call_args
    content = call_args[0][0]
    assert "智能建造2040技术趋势预测报告" in content
    assert "技术主题演化预测" in content
    assert "智能建造新范式" in content
    assert "技术路线图" in content
    assert "不确定性分析" in content
    assert "方法说明" in content
    assert "置信度概览" not in content
    assert "TRL" not in content
    assert "建筑机器人  🟢" not in content
    assert "建筑机器人  🟡" not in content
    assert "建筑机器人  🔴" not in content
    assert "高置信度项" not in content
    assert "低置信度项汇总" not in content


@patch('src.report_generator.write_text')
@patch('src.report_generator.OUTPUTS_REPORT')
def test_generate_final_report_empty_inputs(mock_outputs, mock_write):
    mock_outputs.__truediv__.return_value = "/tmp/test_report.md"

    generate_final_report([], {}, [])

    assert mock_write.called
    call_args = mock_write.call_args
    content = call_args[0][0]
    assert "智能建造2040技术趋势预测报告" in content


def test_tagged_items_display():
    topic = {
        "topic_name": "测试主题",
        "bottlenecks_2030_2035": ["瓶颈1", "瓶颈2"],
        "bottlenecks_2030_2035_tagged": [
            {"text": "瓶颈1（带依据）", "evidence_sources": [], "evidence_score": 60.0},
            {"text": "瓶颈2", "evidence_sources": [], "evidence_score": 40.0}
        ],
        "breakthroughs_by_2040": ["突破1"],
        "breakthroughs_by_2040_tagged": [
            {"text": "突破1（带依据）", "evidence_sources": [], "evidence_score": 70.0}
        ],
        "deep_fusion_topics": [],
        "fusion_scenario": "",
        "typical_day_2040": "",
        "confidence": 75.0,
        "low_confidence_fields": ["bottlenecks_2030_2035"],
        "confidence_details": {"bottlenecks_2030_2035": 50.0}
    }
    lines = _build_topic_section(topic, has_confidence=True, has_evidence=True)
    content = "".join(lines)
    assert "瓶颈1（带依据）" in content
    assert "瓶颈2" in content
    assert "突破1（带依据）" in content
    assert "⚠️" in content


def run_all_tests():
    test_funcs = [
        test_confidence_level_high,
        test_confidence_level_medium,
        test_confidence_level_low,
        test_has_confidence_data_true,
        test_has_confidence_data_false,
        test_has_confidence_data_empty,
        test_has_evidence_data_true,
        test_has_evidence_data_false,
        test_has_reasoning_chain_round1,
        test_has_reasoning_chain_round2,
        test_has_reasoning_chain_round3,
        test_has_reasoning_chain_false,
        test_has_roadmap_enhanced_true,
        test_has_roadmap_enhanced_false,
        test_collect_low_confidence_items,
        test_build_topic_section_with_confidence,
        test_build_topic_section_with_evidence,
        test_build_topic_section_backward_compatible,
        test_build_uncertainty_section_with_confidence,
        test_build_uncertainty_section_without_confidence,
        test_build_methodology_section,
        test_build_roadmap_section_enhanced,
        test_build_roadmap_section_legacy,
        test_build_reasoning_chain_appendix,
        test_generate_final_report_with_all_features,
        test_generate_final_report_backward_compatible,
        test_generate_final_report_empty_inputs,
        test_tagged_items_display,
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
