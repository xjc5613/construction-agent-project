# -*- coding:utf-8-*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.output_parser.parse_round3 import (
    parse_round3_output,
    validate_roadmap_timeline,
    _classify_by_features,
    _parse_trl_level,
    _parse_impact_scope,
    _parse_uncertainty_level,
    _parse_dependencies,
    _parse_enhanced_format,
    _parse_legacy_format,
)


def test_parse_enhanced_format_basic():
    line = "2030 | 技术里程碑 | BIM与GIS深度融合技术 | 6 | 行业 | 低 | 三维建模算法、云计算"
    result = _parse_enhanced_format(line)
    assert result is not None
    assert result["year"] == 2030
    assert result["category"] == "技术里程碑"
    assert "BIM与GIS" in result["description"]
    assert result["trl_level"] == 6
    assert result["impact_scope"] == "industry"
    assert result["uncertainty_level"] == "low"
    assert len(result["dependencies"]) == 2
    assert "三维建模算法" in result["dependencies"]


def test_parse_enhanced_format_missing_fields():
    line = "2030 | 技术里程碑 | BIM技术"
    result = _parse_enhanced_format(line)
    assert result is None


def test_parse_enhanced_format_variations():
    line = " 2035 | 产品 | 建筑巡检机器人 | 8 | 局部 | 中 | 计算机视觉、SLAM "
    result = _parse_enhanced_format(line)
    assert result is not None
    assert result["year"] == 2035
    assert result["category"] == "产品里程碑"
    assert result["trl_level"] == 8
    assert result["impact_scope"] == "local"
    assert result["uncertainty_level"] == "medium"


def test_parse_legacy_format_basic():
    line = "2030 - 技术里程碑：BIM技术突破"
    result = _parse_legacy_format(line)
    assert result is not None
    assert result["year"] == 2030
    assert result["category"] == "技术里程碑"
    assert "BIM技术" in result["description"]


def test_parse_legacy_format_product():
    line = "2035 - 产品里程碑：建筑机器人产品化推广"
    result = _parse_legacy_format(line)
    assert result is not None
    assert result["category"] == "产品里程碑"


def test_parse_legacy_format_uncertainty():
    line = "2040 - 不确定性：通用人工智能应用风险"
    result = _parse_legacy_format(line)
    assert result is not None
    assert result["category"] == "不确定性"


def test_parse_legacy_format_no_prefix():
    line = "2030 BIM技术研发突破"
    result = _parse_legacy_format(line)
    assert result is not None
    assert result["year"] == 2030
    assert "BIM" in result["description"]


def test_parse_round3_enhanced_enabled():
    lines = [
        "2030 | 技术里程碑 | BIM技术 | 5 | 行业 | 低 | 算法",
        "2035 | 产品里程碑 | 机器人产品 | 7 | 行业 | 中 | 视觉、导航",
        "2040 | 不确定性 | AGI应用 | 4 | 全局 | 高 | 技术突破",
    ]
    items = []
    for line in lines:
        parsed = _parse_enhanced_format(line)
        assert parsed is not None
        items.append(parsed)
    assert len(items) == 3
    assert items[0]["trl_level"] == 5
    assert items[1]["impact_scope"] == "industry"
    assert items[2]["uncertainty_level"] == "high"
    assert len(items[0]["dependencies"]) == 1
    assert len(items[1]["dependencies"]) == 2


def test_parse_round3_legacy_only():
    text = """2030 - 技术里程碑：BIM技术突破
2035 - 产品里程碑：建筑机器人推广
2040 - 不确定性：政策风险因素"""
    items = parse_round3_output(text)
    assert len(items) == 3
    assert items[0]["year"] == 2030
    assert items[1]["category"] == "产品里程碑"
    assert items[2]["category"] == "不确定性"


def test_parse_round3_mixed_format():
    text = """2030 | 技术里程碑 | BIM技术 | 5 | 行业 | 低 | 算法
2035 - 产品里程碑：建筑机器人推广
2040 - 不确定性：政策风险因素"""
    items = parse_round3_output(text)
    enhanced_items = [it for it in items if '|' in str(it.get('description', ''))]
    legacy_items = [it for it in items if it.get('category') in ['产品里程碑', '不确定性']]
    assert len(items) >= 2


def test_parse_round3_empty():
    assert parse_round3_output("") == []
    assert parse_round3_output("   ") == []
    assert parse_round3_output(None) == []


def test_parse_round3_invalid_lines():
    text = """这是一段无关文字
没有年份的行
2020 - 不在范围内的年份
abc | def | ghi"""
    items = parse_round3_output(text)
    assert len(items) == 0


def test_classify_by_features_tech():
    assert _classify_by_features("BIM技术研发突破") == "技术里程碑"
    assert _classify_by_features("算法研究与验证") == "技术里程碑"
    assert _classify_by_features("技术里程碑：新方法") == "技术里程碑"


def test_classify_by_features_product():
    assert _classify_by_features("建筑机器人产品化上市") == "产品里程碑"
    assert _classify_by_features("解决方案商业化推广") == "产品里程碑"
    assert _classify_by_features("产品里程碑：新系统") == "产品里程碑"


def test_classify_by_features_uncertainty():
    assert _classify_by_features("技术发展的不确定性因素") == "不确定性"
    assert _classify_by_features("政策风险与挑战") == "不确定性"
    assert _classify_by_features("不确定性：市场接受度") == "不确定性"


def test_parse_trl_level():
    assert _parse_trl_level("TRL: 6") == 6
    assert _parse_trl_level("TRL5级") == 5
    assert _parse_trl_level("trl 3") == 3
    assert _parse_trl_level("基础研究阶段") == 1
    assert _parse_trl_level("成熟应用") == 9
    assert _parse_trl_level("实验室验证") == 4
    assert _parse_trl_level("无相关描述") is None


def test_parse_impact_scope():
    assert _parse_impact_scope("全球范围应用") == "global"
    assert _parse_impact_scope("行业级解决方案") == "industry"
    assert _parse_impact_scope("企业级试点") == "local"
    assert _parse_impact_scope("局部场景") == "local"
    assert _parse_impact_scope("全局影响") == "global"
    assert _parse_impact_scope("普通描述") is None


def test_parse_uncertainty_level():
    assert _parse_uncertainty_level("高不确定性") == "high"
    assert _parse_uncertainty_level("不确定性中") == "medium"
    assert _parse_uncertainty_level("低不确定性风险") == "low"
    assert _parse_uncertainty_level("不确定性: 高") == "high"
    assert _parse_uncertainty_level("普通描述") is None


def test_parse_dependencies():
    result = _parse_dependencies("关键依赖：算法、算力、数据")
    assert result is not None
    assert len(result) == 3
    assert "算法" in result
    assert "算力" in result
    assert "数据" in result

    result = _parse_dependencies("依赖条件: 云计算、物联网")
    assert result is not None
    assert len(result) == 2

    assert _parse_dependencies("无依赖描述") is None


def test_validate_roadmap_timeline_pass():
    items = [
        {"year": 2030, "category": "技术里程碑", "description": "技术A", "trl_level": 4},
        {"year": 2035, "category": "技术里程碑", "description": "技术B", "trl_level": 6},
        {"year": 2040, "category": "技术里程碑", "description": "技术C", "trl_level": 8},
        {"year": 2035, "category": "产品里程碑", "description": "产品A"},
    ]
    result = validate_roadmap_timeline(items)
    assert result["passed"] is True


def test_validate_roadmap_timeline_trl_contradiction():
    items = [
        {"year": 2030, "category": "技术里程碑", "description": "技术A", "trl_level": 8},
        {"year": 2035, "category": "技术里程碑", "description": "技术B", "trl_level": 5},
    ]
    result = validate_roadmap_timeline(items)
    assert result["passed"] is False
    assert any("时间矛盾" in issue for issue in result["issues"])
    assert len(result["suggestions"]) > 0


def test_validate_roadmap_timeline_product_before_tech():
    items = [
        {"year": 2035, "category": "产品里程碑", "description": "产品A"},
        {"year": 2040, "category": "技术里程碑", "description": "技术A", "trl_level": 5},
    ]
    result = validate_roadmap_timeline(items)
    assert result["passed"] is False
    assert any("逻辑矛盾" in issue for issue in result["issues"])


def test_validate_roadmap_timeline_no_tech_with_product():
    items = [
        {"year": 2030, "category": "产品里程碑", "description": "产品A"},
        {"year": 2035, "category": "技术里程碑", "description": "技术A", "trl_level": 6},
    ]
    result = validate_roadmap_timeline(items)
    assert any("但无技术里程碑" in issue for issue in result["issues"])


def test_validate_roadmap_timeline_empty():
    result = validate_roadmap_timeline([])
    assert result["passed"] is False
    assert len(result["issues"]) > 0


def test_validate_roadmap_timeline_no_trl():
    items = [
        {"year": 2030, "category": "技术里程碑", "description": "技术A"},
        {"year": 2035, "category": "产品里程碑", "description": "产品A"},
    ]
    result = validate_roadmap_timeline(items)
    assert result["passed"] is True


def test_validate_roadmap_timeline_trl_skew_low():
    items = [
        {"year": 2040, "category": "技术里程碑", "description": "不成熟的技术", "trl_level": 1},
    ]
    result = validate_roadmap_timeline(items)
    assert any("TRL" in issue and "偏低" in issue for issue in result["issues"])


def test_validate_roadmap_timeline_trl_skew_high():
    items = [
        {"year": 2030, "category": "技术里程碑", "description": "过早成熟技术", "trl_level": 9},
    ]
    result = validate_roadmap_timeline(items)
    assert any("TRL" in issue and "偏高" in issue for issue in result["issues"])


def test_legacy_format_backward_compatibility():
    old_style_texts = [
        "2030 - 技术里程碑：xxx",
        "2035 - 产品里程碑：yyy",
        "2040 - 不确定性：zzz",
        "2030 技术研发突破",
        "2035: 产品应用推广",
    ]
    for text in old_style_texts:
        items = parse_round3_output(text)
        assert len(items) == 1, f"旧格式解析失败: {text}"
        assert "year" in items[0]
        assert "category" in items[0]
        assert "description" in items[0]
        assert "trl_level" in items[0]
        assert "impact_scope" in items[0]
        assert "uncertainty_level" in items[0]
        assert "dependencies" in items[0]


def test_enhanced_fields_default_values():
    line = "2030 - 普通描述无额外字段"
    items = parse_round3_output(line)
    assert len(items) == 1
    item = items[0]
    assert item["year"] == 2030
    assert "description" in item
    assert item["dependencies"] == []


def run_all_tests():
    test_funcs = [
        test_parse_enhanced_format_basic,
        test_parse_enhanced_format_missing_fields,
        test_parse_enhanced_format_variations,
        test_parse_legacy_format_basic,
        test_parse_legacy_format_product,
        test_parse_legacy_format_uncertainty,
        test_parse_legacy_format_no_prefix,
        test_parse_round3_enhanced_enabled,
        test_parse_round3_legacy_only,
        test_parse_round3_mixed_format,
        test_parse_round3_empty,
        test_parse_round3_invalid_lines,
        test_classify_by_features_tech,
        test_classify_by_features_product,
        test_classify_by_features_uncertainty,
        test_parse_trl_level,
        test_parse_impact_scope,
        test_parse_uncertainty_level,
        test_parse_dependencies,
        test_validate_roadmap_timeline_pass,
        test_validate_roadmap_timeline_trl_contradiction,
        test_validate_roadmap_timeline_product_before_tech,
        test_validate_roadmap_timeline_no_tech_with_product,
        test_validate_roadmap_timeline_empty,
        test_validate_roadmap_timeline_no_trl,
        test_validate_roadmap_timeline_trl_skew_low,
        test_validate_roadmap_timeline_trl_skew_high,
        test_legacy_format_backward_compatibility,
        test_enhanced_fields_default_values,
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
