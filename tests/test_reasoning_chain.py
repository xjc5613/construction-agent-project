# -*- coding:utf-8-*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch
from src.output_parser.parse_round1 import parse_round1_output
from src.output_parser.parse_round2 import parse_round2_output
from src.output_parser.parse_round3 import parse_round3_output
from src.output_parser.evidence_tagger import (
    extract_ipc_codes,
    extract_fusion_pairs,
    extract_topic_mentions,
    identify_evidence_sources,
    tag_items_with_evidence,
    calculate_evidence_score,
    validate_reasoning_chain,
)


def _with_reasoning_enabled(func):
    def wrapper():
        with patch('src.output_parser.evidence_tagger.ENABLE_REASONING_CHAIN', True):
            with patch('src.output_parser.parse_round1.ENABLE_REASONING_CHAIN', True):
                with patch('src.output_parser.parse_round2.ENABLE_REASONING_CHAIN', True):
                    with patch('src.output_parser.parse_round3.ENABLE_REASONING_CHAIN', True):
                        func()
    return wrapper


def _with_reasoning_disabled(func):
    def wrapper():
        with patch('src.output_parser.evidence_tagger.ENABLE_REASONING_CHAIN', False):
            with patch('src.output_parser.parse_round1.ENABLE_REASONING_CHAIN', False):
                with patch('src.output_parser.parse_round2.ENABLE_REASONING_CHAIN', False):
                    with patch('src.output_parser.parse_round3.ENABLE_REASONING_CHAIN', False):
                        func()
    return wrapper


@_with_reasoning_enabled
def test_reasoning_chain_parse_round1_with_field():
    text = '''{
      "topic_name": "建筑机器人",
      "bottlenecks_2030_2035": ["感知精度不足（依据：B25J与E04G融合概率0.85）", "成本过高"],
      "breakthroughs_by_2040": ["全自主施工机器人", "人机协同作业"],
      "deep_fusion_topics": ["计算机视觉", "运动控制"],
      "fusion_scenario": "机器人集群协同完成复杂施工任务",
      "typical_day_2040": "工地由机器人24小时不间断施工",
      "reasoning_chain": [
        {"step": 1, "input_evidence": "B25J-011度中心度提升至0.1462", "reasoning": "度中心度增长表明技术热度高，但精度相关专利占比低", "conclusion": "感知精度不足是主要瓶颈"},
        {"step": 2, "input_evidence": "B25J与E04G融合概率0.85", "reasoning": "高融合概率表明两领域结合趋势明确", "conclusion": "机器人与施工管理深度融合是突破方向"}
      ]
    }'''
    result = parse_round1_output(text, "建筑机器人")
    assert result is not None
    assert "reasoning_chain" in result
    assert len(result["reasoning_chain"]) == 2
    assert result["reasoning_chain"][0]["step"] == 1
    assert result["reasoning_chain"][0]["conclusion"] == "感知精度不足是主要瓶颈"
    assert result["reasoning_chain"][1]["step"] == 2


@_with_reasoning_enabled
def test_reasoning_chain_parse_round1_without_field():
    text = '''{
      "topic_name": "建筑机器人",
      "bottlenecks_2030_2035": ["感知精度不足", "成本过高"],
      "breakthroughs_by_2040": ["全自主施工机器人", "人机协同作业"],
      "deep_fusion_topics": ["计算机视觉", "运动控制"],
      "fusion_scenario": "机器人集群协同完成复杂施工任务",
      "typical_day_2040": "工地由机器人24小时不间断施工"
    }'''
    result = parse_round1_output(text, "建筑机器人")
    assert result is not None
    assert "reasoning_chain" in result
    assert result["reasoning_chain"] == []


@_with_reasoning_enabled
def test_reasoning_chain_parse_round1_invalid_chain():
    text = '''{
      "topic_name": "测试主题",
      "bottlenecks_2030_2035": [],
      "breakthroughs_by_2040": [],
      "deep_fusion_topics": ["a", "b"],
      "fusion_scenario": "",
      "typical_day_2040": "",
      "reasoning_chain": "not_a_list"
    }'''
    result = parse_round1_output(text, "测试主题")
    assert result is not None
    assert result["reasoning_chain"] == []


@_with_reasoning_disabled
def test_backward_compatibility_disabled_no_field():
    text = '''{
      "topic_name": "建筑机器人",
      "bottlenecks_2030_2035": ["感知精度不足", "成本过高"],
      "breakthroughs_by_2040": ["全自主施工机器人"],
      "deep_fusion_topics": ["A", "B"],
      "fusion_scenario": "场景",
      "typical_day_2040": "一天"
    }'''
    result = parse_round1_output(text, "建筑机器人")
    assert result is not None
    assert result["topic_name"] == "建筑机器人"
    assert len(result["bottlenecks_2030_2035"]) == 2


@_with_reasoning_disabled
def test_backward_compatibility_disabled_with_field_ignored():
    text = '''{
      "topic_name": "建筑机器人",
      "bottlenecks_2030_2035": ["瓶颈1"],
      "breakthroughs_by_2040": ["突破1"],
      "deep_fusion_topics": ["A", "B"],
      "fusion_scenario": "场景",
      "typical_day_2040": "一天",
      "reasoning_chain": [{"step": 1, "conclusion": "test"}]
    }'''
    result = parse_round1_output(text, "建筑机器人")
    assert result is not None
    assert result["topic_name"] == "建筑机器人"


@_with_reasoning_enabled
def test_extract_ipc_codes_single():
    text = "G06F-030 工程设计三维数据建模"
    result = extract_ipc_codes(text)
    assert len(result) == 1
    assert result[0] == "G06F"


@_with_reasoning_enabled
def test_extract_ipc_codes_multiple():
    text = "B25J与E04G融合，G06N算法优化"
    result = extract_ipc_codes(text)
    assert len(result) == 3
    assert "B25J" in result
    assert "E04G" in result
    assert "G06N" in result


@_with_reasoning_enabled
def test_extract_ipc_codes_duplicates():
    text = "G06F 测试 G06F 重复 G06F-030"
    result = extract_ipc_codes(text)
    assert len(result) == 1
    assert result[0] == "G06F"


@_with_reasoning_enabled
def test_extract_ipc_codes_empty():
    assert extract_ipc_codes("") == []
    assert extract_ipc_codes(None) == []
    assert extract_ipc_codes("无IPC代码的文本") == []


@_with_reasoning_enabled
def test_extract_fusion_pairs_with_annotation():
    text = "机器人技术突破（依据：B25J与E04G融合概率0.85）"
    result = extract_fusion_pairs(text)
    assert len(result) == 1
    assert result[0]["ipc1"] == "B25J"
    assert result[0]["ipc2"] == "E04G"
    assert result[0]["probability"] == 0.85


@_with_reasoning_enabled
def test_extract_fusion_pairs_multiple():
    text = "多技术融合（依据：G06F与G06N融合概率0.78，B25J与G05B融合概率0.73）"
    result = extract_fusion_pairs(text)
    assert len(result) == 2


@_with_reasoning_enabled
def test_extract_fusion_pairs_empty():
    assert extract_fusion_pairs("") == []
    assert extract_fusion_pairs("无融合对的文本") == []


@_with_reasoning_enabled
def test_extract_topic_mentions():
    topics = ["多专业协同平台", "参数化与生成式设计", "机器人集群协同"]
    text = "机器人集群协同与多专业协同平台深度融合"
    result = extract_topic_mentions(text, topics)
    assert len(result) == 2
    assert "机器人集群协同" in result
    assert "多专业协同平台" in result


@_with_reasoning_enabled
def test_extract_topic_mentions_empty():
    assert extract_topic_mentions("", ["topic1"]) == []
    assert extract_topic_mentions("text", []) == []


@_with_reasoning_enabled
def test_identify_evidence_sources_ipc():
    text = "G06F-030 技术持续发展"
    result = identify_evidence_sources(text)
    assert len(result) >= 1
    types = [s["type"] for s in result]
    assert "ipc_class" in types


@_with_reasoning_enabled
def test_identify_evidence_sources_fusion():
    text = "重要突破（依据：B25J与E04G融合概率0.85）"
    result = identify_evidence_sources(text)
    assert len(result) >= 1
    types = [s["type"] for s in result]
    assert "fusion_pair" in types or "explicit_annotation" in types


@_with_reasoning_enabled
def test_identify_evidence_sources_empty():
    result = identify_evidence_sources("没有任何依据的文本")
    assert isinstance(result, list)


@_with_reasoning_enabled
def test_tag_items_with_evidence():
    items = [
        "感知精度不足（依据：B25J与E04G融合概率0.85）",
        "成本过高",
        "G06F算法优化带来的突破"
    ]
    result = tag_items_with_evidence(items)
    assert len(result) == 3
    for item in result:
        assert "text" in item
        assert "evidence_sources" in item
        assert "evidence_score" in item
        assert isinstance(item["evidence_score"], float)
        assert 0.0 <= item["evidence_score"] <= 100.0


@_with_reasoning_enabled
def test_calculate_evidence_score_no_evidence():
    score = calculate_evidence_score("无依据文本", [])
    assert score == 0.0


@_with_reasoning_enabled
def test_calculate_evidence_score_with_ipc():
    evidence = [{"type": "ipc_class", "value": "G06F", "quality": "direct"}]
    score = calculate_evidence_score("测试", evidence)
    assert score > 0.0
    assert score <= 100.0


@_with_reasoning_enabled
def test_calculate_evidence_score_with_fusion():
    evidence = [
        {"type": "fusion_pair", "value": "B25J-E04G", "probability": 0.85, "quality": "direct"}
    ]
    score = calculate_evidence_score("测试", evidence)
    assert score > 0.0


@_with_reasoning_enabled
def test_calculate_evidence_score_multiple_sources():
    evidence = [
        {"type": "ipc_class", "value": "G06F", "quality": "direct"},
        {"type": "fusion_pair", "value": "G06F-G06N", "probability": 0.78, "quality": "direct"},
        {"type": "explicit_annotation", "value": "度中心度增长", "quality": "direct"}
    ]
    score = calculate_evidence_score("测试", evidence)
    assert score > 30.0
    assert score <= 100.0


@_with_reasoning_enabled
def test_calculate_evidence_score_cap_100():
    evidence = [
        {"type": "ipc_class", "value": "G06F", "quality": "direct"},
        {"type": "ipc_class", "value": "G06N", "quality": "direct"},
        {"type": "ipc_class", "value": "B25J", "quality": "direct"},
        {"type": "fusion_pair", "value": "A-B", "probability": 0.99, "quality": "direct"},
        {"type": "explicit_annotation", "value": "test", "quality": "direct"},
        {"type": "topic_name", "value": "test", "quality": "direct"},
    ]
    score = calculate_evidence_score("测试", evidence)
    assert score <= 100.0


@_with_reasoning_enabled
def test_validate_reasoning_chain_valid():
    chain = [
        {"step": 1, "input_evidence": "evidence1", "reasoning": "reasoning1", "conclusion": "conclusion1"},
        {"step": 2, "input_evidence": "evidence2", "reasoning": "reasoning2", "conclusion": "conclusion2"}
    ]
    result = validate_reasoning_chain(chain)
    assert len(result) == 2
    assert result[0]["step"] == 1


@_with_reasoning_enabled
def test_validate_reasoning_chain_invalid_not_list():
    assert validate_reasoning_chain("not_a_list") == []
    assert validate_reasoning_chain(None) == []
    assert validate_reasoning_chain(123) == []


@_with_reasoning_enabled
def test_validate_reasoning_chain_missing_fields():
    chain = [
        {"step": 1},
        {"conclusion": "no step"},
        {"step": 2, "conclusion": "valid"}
    ]
    result = validate_reasoning_chain(chain)
    assert len(result) == 1
    assert result[0]["step"] == 2


@_with_reasoning_enabled
def test_validate_reasoning_chain_empty():
    assert validate_reasoning_chain([]) == []


@_with_reasoning_enabled
def test_parse_round2_with_reasoning_chain():
    text = '''```json
    {
      "new_paradigm_name": "智能建造新范式",
      "new_paradigm_description": "AI驱动的全自动化建造",
      "reasoning_chain": [
        {"step": 1, "input_evidence": "多技术融合趋势", "reasoning": "技术融合催生新范式", "conclusion": "智能建造新范式将出现"}
      ]
    }
    ```'''
    result = parse_round2_output(text)
    assert result is not None
    assert result["new_paradigm_name"] == "智能建造新范式"
    assert "reasoning_chain" in result
    assert len(result["reasoning_chain"]) == 1


@_with_reasoning_enabled
def test_parse_round2_without_reasoning_chain():
    text = "新范式名称：测试范式\n范式描述：这是一个测试"
    result = parse_round2_output(text)
    assert result is not None
    assert result["new_paradigm_name"] == "测试范式"
    assert "reasoning_chain" in result
    assert result["reasoning_chain"] == []


@_with_reasoning_enabled
def test_parse_round3_with_reasoning_chain():
    text = '''```json
    {
      "roadmap": [
        {"year": 2030, "category": "技术里程碑", "description": "技术突破"},
        {"year": 2035, "category": "产品里程碑", "description": "产品落地"}
      ],
      "reasoning_chain": [
        {"step": 1, "input_evidence": "趋势数据", "reasoning": "分析推导", "conclusion": "2030年技术突破"}
      ]
    }
    ```'''
    result = parse_round3_output(text)
    assert isinstance(result, dict)
    assert "roadmap_items" in result
    assert "reasoning_chain" in result
    assert len(result["roadmap_items"]) == 2
    assert len(result["reasoning_chain"]) == 1


@_with_reasoning_disabled
def test_parse_round3_backward_compatible():
    text = "2030 - 技术研发突破\n2035 - 产品商业化应用"
    result = parse_round3_output(text)
    assert isinstance(result, list)
    assert len(result) == 2


@_with_reasoning_enabled
def test_round1_evidence_tagged_fields():
    text = '''{
      "topic_name": "机器人集群协同",
      "bottlenecks_2030_2035": ["感知精度不足（依据：B25J与E04G融合概率0.85）", "成本过高"],
      "breakthroughs_by_2040": ["G06N智能算法提升自主决策能力"],
      "deep_fusion_topics": ["建筑工程大模型技术", "施工全过程数字孪生"],
      "fusion_scenario": "融合场景",
      "typical_day_2040": "典型一天",
      "reasoning_chain": []
    }'''
    result = parse_round1_output(text, "机器人集群协同")
    assert result is not None
    assert "bottlenecks_2030_2035_tagged" in result
    assert "breakthroughs_by_2040_tagged" in result
    assert "overall_evidence_score" in result
    assert isinstance(result["overall_evidence_score"], float)
    assert 0.0 <= result["overall_evidence_score"] <= 100.0


@_with_reasoning_disabled
def test_disabled_no_tagged_fields():
    text = '''{
      "topic_name": "测试",
      "bottlenecks_2030_2035": ["瓶颈1"],
      "breakthroughs_by_2040": ["突破1"],
      "deep_fusion_topics": ["A", "B"],
      "fusion_scenario": "",
      "typical_day_2040": ""
    }'''
    result = parse_round1_output(text, "测试")
    assert result is not None
    assert "bottlenecks_2030_2035_tagged" not in result
    assert "breakthroughs_by_2040_tagged" not in result
    assert "overall_evidence_score" not in result


def run_all_tests():
    test_funcs = [
        test_reasoning_chain_parse_round1_with_field,
        test_reasoning_chain_parse_round1_without_field,
        test_reasoning_chain_parse_round1_invalid_chain,
        test_backward_compatibility_disabled_no_field,
        test_backward_compatibility_disabled_with_field_ignored,
        test_extract_ipc_codes_single,
        test_extract_ipc_codes_multiple,
        test_extract_ipc_codes_duplicates,
        test_extract_ipc_codes_empty,
        test_extract_fusion_pairs_with_annotation,
        test_extract_fusion_pairs_multiple,
        test_extract_fusion_pairs_empty,
        test_extract_topic_mentions,
        test_extract_topic_mentions_empty,
        test_identify_evidence_sources_ipc,
        test_identify_evidence_sources_fusion,
        test_identify_evidence_sources_empty,
        test_tag_items_with_evidence,
        test_calculate_evidence_score_no_evidence,
        test_calculate_evidence_score_with_ipc,
        test_calculate_evidence_score_with_fusion,
        test_calculate_evidence_score_multiple_sources,
        test_calculate_evidence_score_cap_100,
        test_validate_reasoning_chain_valid,
        test_validate_reasoning_chain_invalid_not_list,
        test_validate_reasoning_chain_missing_fields,
        test_validate_reasoning_chain_empty,
        test_parse_round2_with_reasoning_chain,
        test_parse_round2_without_reasoning_chain,
        test_parse_round3_with_reasoning_chain,
        test_parse_round3_backward_compatible,
        test_round1_evidence_tagged_fields,
        test_disabled_no_tagged_fields,
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
