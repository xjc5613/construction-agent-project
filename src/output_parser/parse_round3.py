# -*- coding:utf-8-*-
import re
import json
from typing import List, Dict, Any, Optional, Union
from src.utils.logger import get_logger
from config.settings import ENABLE_ROADMAP_ENHANCED, ENABLE_REASONING_CHAIN
from src.output_parser.evidence_tagger import validate_reasoning_chain

logger = get_logger(__name__)

TECH_VERBS = ["研发", "开发", "研究", "突破", "验证", "测试", "攻克", "实现技术", "技术突破", "技术成熟"]
PRODUCT_VERBS = ["产品化", "商业化", "推广", "应用", "上市", "推出", "部署", "落地", "规模化", "普及"]
UNCERTAINTY_WORDS = ["不确定性", "风险", "挑战", "存疑", "尚待", "可能", "或许", "未知", "待验证", "风险因素"]
TECH_NOUNS = ["技术", "算法", "模型", "系统", "方法", "原理", "机制", "框架", "平台技术"]
PRODUCT_NOUNS = ["产品", "系统", "设备", "机器人", "软件", "平台", "工具", "解决方案"]
LOCAL_KEYWORDS = ["企业级", "企业内部", "特定场景", "局部", "单一项目", "试点"]
GLOBAL_KEYWORDS = ["全球", "世界范围", "国际", "全人类", "全球性"]


def _classify_by_features(text: str) -> str:
    tech_score = 0
    product_score = 0
    uncertainty_score = 0

    for word in UNCERTAINTY_WORDS:
        if word in text:
            uncertainty_score += 2

    for verb in TECH_VERBS:
        if verb in text:
            tech_score += 2

    for verb in PRODUCT_VERBS:
        if verb in text:
            product_score += 2

    for noun in TECH_NOUNS:
        if noun in text:
            tech_score += 1

    for noun in PRODUCT_NOUNS:
        if noun in text:
            product_score += 1

    if "技术里程碑" in text or ("技术" in text and "产品" not in text):
        tech_score += 3
    if "产品里程碑" in text or ("产品" in text and "技术" not in text):
        product_score += 3
    if "不确定性" in text:
        uncertainty_score += 5

    scores = {
        "技术里程碑": tech_score,
        "产品里程碑": product_score,
        "不确定性": uncertainty_score
    }

    max_score = max(scores.values())
    if max_score == 0:
        return "其他"
    return max(scores, key=scores.get)


def _parse_trl_level(text: str) -> Optional[int]:
    pattern = r'TRL\s*[:：]?\s*(\d)'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        try:
            level = int(match.group(1))
            if 1 <= level <= 9:
                return level
        except (ValueError, TypeError):
            pass

    level_map = {
        "基础研究": 1, "概念形成": 2, "实验验证": 3, "实验室验证": 4,
        "原型验证": 5, "示范验证": 5, "相关环境验证": 6, "系统示范": 7,
        "实际系统": 8, "成熟应用": 9, "完全成熟": 9
    }
    for key, val in level_map.items():
        if key in text:
            return val

    return None


def _parse_impact_scope(text: str) -> Optional[str]:
    for kw in GLOBAL_KEYWORDS:
        if kw in text:
            return "global"
    if "行业" in text or "产业" in text or "整个行业" in text:
        return "industry"
    for kw in LOCAL_KEYWORDS:
        if kw in text:
            return "local"
    if "局部" in text:
        return "local"
    if "全局" in text:
        return "global"
    return None


def _parse_uncertainty_level(text: str) -> Optional[str]:
    if "高不确定性" in text or "不确定性高" in text:
        return "high"
    if "中不确定性" in text or "不确定性中" in text:
        return "medium"
    if "低不确定性" in text or "不确定性低" in text:
        return "low"

    pattern = r'不确定性\s*[:：]?\s*(低|中|高)'
    match = re.search(pattern, text)
    if match:
        mapping = {"低": "low", "中": "medium", "高": "high"}
        return mapping.get(match.group(1))

    return None


def _parse_dependencies(text: str) -> Optional[List[str]]:
    pattern = r'(?:依赖|关键依赖|依赖条件|前提条件)\s*[:：]\s*(.+)'
    match = re.search(pattern, text)
    if match:
        dep_str = match.group(1).strip()
        deps = re.split(r'[、,，;；\s]+', dep_str)
        deps = [d.strip() for d in deps if d.strip()]
        if deps:
            return deps
    return None


def _parse_enhanced_format(line: str) -> Optional[Dict[str, Any]]:
    if '|' not in line:
        return None

    parts = [p.strip() for p in line.split('|')]
    if len(parts) < 7:
        return None

    year_str = parts[0].strip()
    year_match = re.search(r'(2030|2035|2040)', year_str)
    if not year_match:
        return None
    year = int(year_match.group(1))

    category_raw = parts[1].strip()
    category_map = {
        "技术里程碑": "技术里程碑",
        "产品里程碑": "产品里程碑",
        "不确定性": "不确定性",
        "技术": "技术里程碑",
        "产品": "产品里程碑",
        "风险": "不确定性"
    }
    category = category_map.get(category_raw, _classify_by_features(category_raw))

    description = parts[2].strip()

    trl_level = None
    trl_str = parts[3].strip()
    try:
        trl_match = re.search(r'\d', trl_str)
        if trl_match:
            trl_level = int(trl_match.group())
            if not (1 <= trl_level <= 9):
                trl_level = None
    except (ValueError, TypeError):
        trl_level = _parse_trl_level(trl_str)
    if trl_level is None:
        trl_level = _parse_trl_level(trl_str)

    impact_scope_raw = parts[4].strip()
    scope_map = {"局部": "local", "行业": "industry", "全局": "global"}
    impact_scope = scope_map.get(impact_scope_raw, _parse_impact_scope(impact_scope_raw))

    uncertainty_raw = parts[5].strip()
    unc_map = {"低": "low", "中": "medium", "高": "high"}
    uncertainty_level = unc_map.get(uncertainty_raw, _parse_uncertainty_level(uncertainty_raw))

    dependencies_str = parts[6].strip()
    dependencies = []
    if dependencies_str:
        deps = re.split(r'[、,，;；\s]+', dependencies_str)
        dependencies = [d.strip() for d in deps if d.strip()]

    return {
        "year": year,
        "category": category,
        "description": description,
        "trl_level": trl_level,
        "impact_scope": impact_scope,
        "uncertainty_level": uncertainty_level,
        "dependencies": dependencies
    }


def _parse_legacy_format(line: str) -> Optional[Dict[str, Any]]:
    pattern = r'(2030|2035|2040)[\s:：]*[-–—]?\s*(.+)'
    match = re.search(pattern, line)
    if not match:
        return None

    year = int(match.group(1))
    desc = match.group(2).strip()
    category = _classify_by_features(desc)
    trl_level = _parse_trl_level(desc)
    impact_scope = _parse_impact_scope(desc)
    uncertainty_level = _parse_uncertainty_level(desc)
    dependencies = _parse_dependencies(desc)

    return {
        "year": year,
        "category": category,
        "description": desc,
        "trl_level": trl_level,
        "impact_scope": impact_scope,
        "uncertainty_level": uncertainty_level,
        "dependencies": dependencies or []
    }


def _extract_json_roadmap_and_reasoning(text: str) -> tuple:
    reasoning_chain = []
    roadmap_items = []
    
    if not text or not text.strip():
        return roadmap_items, reasoning_chain
    
    data = None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    
    if data is None:
        code_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(code_pattern, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            try:
                data = json.loads(candidate)
            except (json.JSONDecodeError, ValueError):
                pass
    
    if data and isinstance(data, dict):
        if ENABLE_REASONING_CHAIN and "reasoning_chain" in data:
            reasoning_chain = validate_reasoning_chain(data["reasoning_chain"])
        
        roadmap_key = None
        for key in ["roadmap", "milestones", "timeline", "路线图", "里程碑", "roadmap_items"]:
            if key in data and isinstance(data[key], list):
                roadmap_key = key
                break
        
        if roadmap_key:
            for item in data[roadmap_key]:
                if isinstance(item, dict):
                    year = item.get("year") or item.get("年份")
                    desc = item.get("description") or item.get("描述") or item.get("内容", "")
                    cat = item.get("category") or item.get("分类", "其他")
                    if year and desc:
                        try:
                            year = int(year)
                            parsed_item = {
                                "year": year,
                                "category": cat,
                                "description": str(desc)
                            }
                            if "trl_level" in item:
                                parsed_item["trl_level"] = item["trl_level"]
                            if "impact_scope" in item:
                                parsed_item["impact_scope"] = item["impact_scope"]
                            if "uncertainty_level" in item:
                                parsed_item["uncertainty_level"] = item["uncertainty_level"]
                            if "dependencies" in item:
                                parsed_item["dependencies"] = item["dependencies"]
                            roadmap_items.append(parsed_item)
                        except (ValueError, TypeError):
                            pass
    
    return roadmap_items, reasoning_chain


def parse_round3_output(raw_response: str) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    json_roadmap_items, reasoning_chain = _extract_json_roadmap_and_reasoning(raw_response)
    
    if json_roadmap_items:
        items = json_roadmap_items
    else:
        items = []
        if not raw_response or not raw_response.strip():
            logger.warning("输入为空，未提取到路线图条目")
            if ENABLE_REASONING_CHAIN:
                return {"roadmap_items": items, "reasoning_chain": reasoning_chain}
            return items

        lines = raw_response.split('\n')
        enhanced_count = 0
        legacy_count = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if ENABLE_ROADMAP_ENHANCED and '|' in line:
                parsed = _parse_enhanced_format(line)
                if parsed:
                    items.append(parsed)
                    enhanced_count += 1
                    continue

            parsed = _parse_legacy_format(line)
            if parsed:
                items.append(parsed)
                legacy_count += 1

        if not items:
            logger.warning("未提取到路线图条目")
        else:
            logger.info(f"提取到 {len(items)} 条路线图条目 (增强格式: {enhanced_count}, 传统格式: {legacy_count})")

    if ENABLE_REASONING_CHAIN:
        return {"roadmap_items": items, "reasoning_chain": reasoning_chain}
    return items


def validate_roadmap_timeline(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    result = {
        "passed": True,
        "issues": [],
        "suggestions": []
    }

    if not items:
        result["passed"] = False
        result["issues"].append("路线图条目为空，无法进行时间序列校验")
        return result

    year_groups = {}
    for item in items:
        year = item.get("year")
        if year not in year_groups:
            year_groups[year] = []
        year_groups[year].append(item)

    years_sorted = sorted(year_groups.keys())

    for i in range(len(years_sorted) - 1):
        earlier_year = years_sorted[i]
        later_year = years_sorted[i + 1]

        earlier_techs = [it for it in year_groups[earlier_year]
                          if it.get("category") == "技术里程碑" and it.get("trl_level") is not None]
        later_techs = [it for it in year_groups[later_year]
                       if it.get("category") == "技术里程碑" and it.get("trl_level") is not None]

        if earlier_techs and later_techs:
            earlier_max_trl = max(it["trl_level"] for it in earlier_techs)
            later_min_trl = min(it["trl_level"] for it in later_techs)
            if earlier_max_trl > later_min_trl:
                result["passed"] = False
                issue = (f"时间矛盾：{earlier_year}年技术里程碑最高TRL({earlier_max_trl}) "
                       f"高于 {later_year}年最低TRL({later_min_trl})")
                result["issues"].append(issue)
                result["suggestions"].append(
                    f"建议调整 {later_year}年的技术TRL等级，使其不低于{earlier_max_trl}")

    tech_milestones = sorted(
        [(it.get("year"), it.get("description", "")) for it in items if it.get("category") == "技术里程碑"],
        key=lambda x: x[0]
    )
    product_milestones = sorted(
        [(it.get("year"), it.get("description", "")) for it in items if it.get("category") == "产品里程碑"],
        key=lambda x: x[0]
    )

    if tech_milestones and product_milestones:
        first_product_year = product_milestones[0][0]
        last_tech_before_product = max(
            [t[0] for t in tech_milestones if t[0] <= first_product_year],
            default=None
        )
        if last_tech_before_product is None and tech_milestones[0][0] > first_product_year:
            result["passed"] = False
            issue = (f"逻辑矛盾：首个产品里程碑({first_product_year}年) "
                    f"早于首个技术里程碑({tech_milestones[0][0]}年)")
            result["issues"].append(issue)
            result["suggestions"].append(
                "建议调整技术里程碑早于对应的产品里程碑")

    for year in years_sorted:
        year_items = year_groups[year]
        tech_count = sum(1 for it in year_items if it.get("category") == "技术里程碑")
        product_count = sum(1 for it in year_items if it.get("category") == "产品里程碑")
        if tech_count == 0 and product_count > 0 and year < 2040:
            result["issues"].append(
                f"{year}年有 {product_count} 个产品里程碑，但无技术里程碑")
            result["suggestions"].append(
                f"建议在 {year} 年前补充相应的技术里程碑作为支撑")

    for item in items:
        trl = item.get("trl_level")
        year = item.get("year")
        cat = item.get("category")
        if trl is not None and year in years_sorted:
            year_idx = years_sorted.index(year)
            expected_min_trl = max(1, year_idx * 2 + 2)
            expected_max_trl = min(9, year_idx * 2 + 5)
            if trl < expected_min_trl and cat == "技术里程碑":
                result["issues"].append(
                    f"{year}年 '{item.get('description', '')}' 的TRL({trl})可能偏低")
                result["suggestions"].append(
                    f"建议调整TRL到 {expected_min_trl}-{expected_max_trl} 区间")
            elif trl > expected_max_trl and cat == "技术里程碑" and year < 2040:
                result["issues"].append(
                    f"{year}年 '{item.get('description', '')}' 的TRL({trl})可能偏高")
                result["suggestions"].append(
                    f"建议调整TRL到 {expected_min_trl}-{expected_max_trl} 区间")

    return result
