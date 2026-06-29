# -*- coding:utf-8-*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.output_parser.parse_round1 import (
    parse_round1_output,
    _extract_json,
    _fallback_parse,
    filter_unrealistic_breakthroughs,
    FORBIDDEN_WORDS,
)


def test_filter_unrealistic_breakthroughs_no_forbidden():
    items = ["正常突破A", "正常突破B", "正常突破C"]
    result = filter_unrealistic_breakthroughs(items)
    assert len(result) == 3
    assert result == items


def test_filter_unrealistic_breakthroughs_with_forbidden():
    items = [
        "正常突破A",
        "基于量子计算的突破性进展",
        "正常突破B",
        "自修复混凝土技术应用",
        "正常突破C",
    ]
    result = filter_unrealistic_breakthroughs(items)
    assert len(result) == 3
    assert "正常突破A" in result
    assert "正常突破B" in result
    assert "正常突破C" in result
    assert not any("量子计算" in r for r in result)
    assert not any("自修复混凝土" in r for r in result)


def test_filter_unrealistic_breakthroughs_empty():
    assert filter_unrealistic_breakthroughs([]) == []


def test_extract_json_pure_json():
    text = '{"topic_name": "测试主题", "bottlenecks_2030_2035": ["瓶颈1"], "breakthroughs_by_2040": ["突破1"], "deep_fusion_topics": ["A", "B"], "fusion_scenario": "场景", "typical_day_2040": "一天"}'
    result = _extract_json(text)
    assert result is not None
    assert result["topic_name"] == "测试主题"
    assert result["bottlenecks_2030_2035"] == ["瓶颈1"]


def test_extract_json_markdown_code_block():
    text = '''```json
{
  "topic_name": "测试主题",
  "bottlenecks_2030_2035": ["瓶颈1", "瓶颈2"],
  "breakthroughs_by_2040": ["突破1"],
  "deep_fusion_topics": ["A", "B"],
  "fusion_scenario": "场景描述",
  "typical_day_2040": "典型的一天"
}
```'''
    result = _extract_json(text)
    assert result is not None
    assert result["topic_name"] == "测试主题"
    assert len(result["bottlenecks_2030_2035"]) == 2


def test_extract_json_code_block_no_json_tag():
    text = '''```
{
  "topic_name": "无标签主题",
  "bottlenecks_2030_2035": ["瓶颈X"],
  "breakthroughs_by_2040": ["突破X"],
  "deep_fusion_topics": ["X", "Y"],
  "fusion_scenario": "场景X",
  "typical_day_2040": "一天X"
}
```'''
    result = _extract_json(text)
    assert result is not None
    assert result["topic_name"] == "无标签主题"


def test_extract_json_with_prefix_suffix():
    text = '''以下是分析结果：

{
  "topic_name": "前后缀主题",
  "bottlenecks_2030_2035": ["瓶颈P"],
  "breakthroughs_by_2040": ["突破P"],
  "deep_fusion_topics": ["P", "Q"],
  "fusion_scenario": "场景P",
  "typical_day_2040": "一天P"
}

希望以上内容对您有帮助。'''
    result = _extract_json(text)
    assert result is not None
    assert result["topic_name"] == "前后缀主题"


def test_extract_json_nested_structure():
    text = '''```json
{
  "topic_name": "嵌套JSON主题",
  "bottlenecks_2030_2035": ["瓶颈N"],
  "breakthroughs_by_2040": ["突破N"],
  "deep_fusion_topics": ["N", "M"],
  "fusion_scenario": "场景N",
  "typical_day_2040": "一天N",
  "extra": {
    "nested": {
      "key": "value"
    }
  }
}
```'''
    result = _extract_json(text)
    assert result is not None
    assert result["topic_name"] == "嵌套JSON主题"
    assert "extra" in result
    assert result["extra"]["nested"]["key"] == "value"


def test_extract_json_empty_input():
    assert _extract_json("") is None
    assert _extract_json("   ") is None
    assert _extract_json(None) is None


def test_extract_json_invalid_json():
    text = "这不是JSON {invalid json"
    result = _extract_json(text)
    assert result is None


def test_parse_round1_pure_json_with_forbidden_words():
    text = '''{
  "topic_name": "禁忌词测试",
  "bottlenecks_2030_2035": [
    "正常瓶颈A",
    "联邦学习技术瓶颈",
    "正常瓶颈B"
  ],
  "breakthroughs_by_2040": [
    "正常突破A",
    "量子计算驱动的革命",
    "正常突破B",
    "合成数据生成突破"
  ],
  "deep_fusion_topics": ["主题A", "主题B"],
  "fusion_scenario": "融合场景描述",
  "typical_day_2040": "典型的一天描述"
}'''
    result = parse_round1_output(text, "禁忌词测试")
    assert result is not None
    assert len(result["breakthroughs_by_2040"]) == 2
    assert "正常突破A" in result["breakthroughs_by_2040"]
    assert "正常突破B" in result["breakthroughs_by_2040"]
    assert len(result["bottlenecks_2030_2035"]) == 2
    assert "正常瓶颈A" in result["bottlenecks_2030_2035"]
    assert "正常瓶颈B" in result["bottlenecks_2030_2035"]


def test_parse_round1_markdown_code_block():
    text = '''以下是智能建造技术预测分析：

```json
{
  "topic_name": "建筑机器人",
  "bottlenecks_2030_2035": ["感知精度不足", "成本过高"],
  "breakthroughs_by_2040": ["全自主施工机器人", "人机协同作业"],
  "deep_fusion_topics": ["计算机视觉", "运动控制"],
  "fusion_scenario": "机器人集群协同完成复杂施工任务",
  "typical_day_2040": "工地由机器人24小时不间断施工"
}
```

以上内容仅供参考。'''
    result = parse_round1_output(text, "建筑机器人")
    assert result is not None
    assert result["topic_name"] == "建筑机器人"
    assert len(result["bottlenecks_2030_2035"]) == 2
    assert len(result["breakthroughs_by_2040"]) == 2
    assert len(result["deep_fusion_topics"]) == 2


def test_parse_round1_fallback_bullet_list():
    text = '''主题：模块化建筑

技术瓶颈：
- 标准化程度不足
- 连接方式可靠性待提升
- 运输成本过高

关键突破：
- 通用模块化接口标准
- 快速连接技术
- 智能吊装系统

深度融合主题：
- 智能制造
- BIM技术

融合场景：模块化建筑与智能制造深度融合，实现按需定制。

典型一天：工厂预制构件，现场快速组装。'''
    result = parse_round1_output(text, "模块化建筑")
    assert result is not None
    assert result["topic_name"] == "模块化建筑"
    assert len(result["bottlenecks_2030_2035"]) >= 2
    assert len(result["breakthroughs_by_2040"]) >= 2
    assert len(result["deep_fusion_topics"]) == 2
    assert result["fusion_scenario"] != ""
    assert result["typical_day_2040"] != ""


def test_parse_round1_fallback_numbered_list():
    text = '''主题：数字孪生

瓶颈：
1. 数据采集精度不足
2. 实时渲染性能瓶颈
3. 多源数据融合困难

突破：
1. 全生命周期数字孪生
2. 实时仿真优化
3. 虚实融合交互

深度融合：
- 物联网
- 大数据

融合场景：数字孪生贯穿建筑全生命周期。

典型一天：通过数字孪生监控建筑运行状态。'''
    result = parse_round1_output(text, "数字孪生")
    assert result is not None
    assert result["topic_name"] == "数字孪生"
    assert len(result["bottlenecks_2030_2035"]) >= 2
    assert len(result["breakthroughs_by_2040"]) >= 2


def test_parse_round1_empty_input():
    result = parse_round1_output("", "空输入测试")
    assert result is not None
    assert result["topic_name"] == "空输入测试"
    assert isinstance(result["bottlenecks_2030_2035"], list)
    assert isinstance(result["breakthroughs_by_2040"], list)
    assert isinstance(result["deep_fusion_topics"], list)


def test_parse_round1_missing_fields():
    text = '{"topic_name": "缺字段主题"}'
    result = parse_round1_output(text, "缺字段主题")
    assert result is not None
    assert result["topic_name"] == "缺字段主题"
    assert result["bottlenecks_2030_2035"] == []
    assert result["breakthroughs_by_2040"] == []
    assert result["deep_fusion_topics"] == []
    assert result["fusion_scenario"] == ""
    assert result["typical_day_2040"] == ""


def test_parse_round1_topic_name_filled():
    text = '{"bottlenecks_2030_2035": [], "breakthroughs_by_2040": [], "deep_fusion_topics": ["a","b"], "fusion_scenario": "", "typical_day_2040": ""}'
    result = parse_round1_output(text, "补全主题")
    assert result["topic_name"] == "补全主题"


def test_forbidden_words_all_covered():
    assert len(FORBIDDEN_WORDS) > 0
    for word in FORBIDDEN_WORDS:
        items = [f"包含{word}的条目"]
        result = filter_unrealistic_breakthroughs(items)
        assert len(result) == 0, f"禁忌词 {word} 未被正确过滤"


def run_all_tests():
    test_funcs = [
        test_filter_unrealistic_breakthroughs_no_forbidden,
        test_filter_unrealistic_breakthroughs_with_forbidden,
        test_filter_unrealistic_breakthroughs_empty,
        test_extract_json_pure_json,
        test_extract_json_markdown_code_block,
        test_extract_json_code_block_no_json_tag,
        test_extract_json_with_prefix_suffix,
        test_extract_json_nested_structure,
        test_extract_json_empty_input,
        test_extract_json_invalid_json,
        test_parse_round1_pure_json_with_forbidden_words,
        test_parse_round1_markdown_code_block,
        test_parse_round1_fallback_bullet_list,
        test_parse_round1_fallback_numbered_list,
        test_parse_round1_empty_input,
        test_parse_round1_missing_fields,
        test_parse_round1_topic_name_filled,
        test_forbidden_words_all_covered,
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
            failed += 1

    print(f"\n总计: {passed} 通过, {failed} 失败")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
