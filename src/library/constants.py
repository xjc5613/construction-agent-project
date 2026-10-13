# -*- coding: utf-8 -*-
from typing import Dict, List, Tuple

from src.research.contracts import (
    CURRENT_RESEARCH_CONTRACT_VERSION,
    LEGACY_RESEARCH_CONTRACT_VERSION,
    get_research_contract,
)

TECHNOLOGY_LEVELS = {1, 2, 3}
PUBLIC_DATASET_KINDS = {"ipc", "paper", "integrated"}
COMPONENT_KINDS = {
    "ipc_metrics", "ipc_fusions", "papers", "analysis_document",
}
CURRENT_RESEARCH_CONTRACT = get_research_contract(
    CURRENT_RESEARCH_CONTRACT_VERSION
)
LEGACY_RESEARCH_CONTRACT = get_research_contract(
    LEGACY_RESEARCH_CONTRACT_VERSION
)
HISTORICAL_PERIODS: Dict[str, Tuple[int, int]] = dict(
    CURRENT_RESEARCH_CONTRACT.periods
)
PERIOD_LABELS = dict(CURRENT_RESEARCH_CONTRACT.period_labels)
LEGACY_HISTORICAL_PERIODS: Dict[str, Tuple[int, int]] = dict(
    LEGACY_RESEARCH_CONTRACT.periods
)
LEGACY_PERIOD_LABELS = dict(LEGACY_RESEARCH_CONTRACT.period_labels)
COMPATIBLE_HISTORICAL_PERIODS = {
    **LEGACY_HISTORICAL_PERIODS,
    **HISTORICAL_PERIODS,
}
COMPATIBLE_PERIOD_LABELS = {**LEGACY_PERIOD_LABELS, **PERIOD_LABELS}
BASELINE_YEAR = CURRENT_RESEARCH_CONTRACT.baseline_year
TARGET_YEARS = set(CURRENT_RESEARCH_CONTRACT.target_years)
ANALYSIS_KINDS = {
    "ipc_analysis", "paper_analysis", "integrated_analysis",
}


def derive_forecast_nodes(target_year: int) -> List[int]:
    return CURRENT_RESEARCH_CONTRACT.derive_forecast_nodes(target_year)


TECHNOLOGY_SEED = [
    ("tech_smart_construction", None, 1, "智能建造", "smart-construction", 10),
    ("tech_engineering_software", "tech_smart_construction", 2, "工程软件", "engineering-software", 10),
    ("tech_engineering_iot", "tech_smart_construction", 2, "工程物联网", "engineering-iot", 20),
    ("tech_component_production", "tech_smart_construction", 2, "构件智能生产", "component-production", 30),
    ("tech_construction_machinery", "tech_smart_construction", 2, "智能施工机械", "construction-machinery", 40),
    ("tech_data_platform", "tech_smart_construction", 2, "工程大数据与互联网平台", "data-platform", 50),
    ("tech_generative_design", "tech_engineering_software", 3, "生成式设计", "generative-design", 10),
    ("tech_engineering_analysis", "tech_engineering_software", 3, "工程分析", "engineering-analysis", 20),
    ("tech_digital_design", "tech_engineering_software", 3, "数字化设计", "digital-design", 30),
    ("tech_simulation", "tech_engineering_software", 3, "工程仿真模拟", "engineering-simulation", 40),
    ("tech_parametric_design", "tech_engineering_software", 3, "参数化设计", "parametric-design", 50),
    ("tech_large_model", "tech_engineering_software", 3, "大模型", "large-model", 60),
    ("tech_intelligent_design", "tech_engineering_software", 3, "智能设计", "intelligent-design", 70),
    ("tech_bim", "tech_engineering_software", 3, "BIM", "bim", 80),
    ("tech_smart_site", "tech_engineering_iot", 3, "智慧工地", "smart-site", 10),
    ("tech_construction_monitoring", "tech_engineering_iot", 3, "施工监测", "construction-monitoring", 20),
    ("tech_digital_twin", "tech_engineering_iot", 3, "数字孪生", "digital-twin", 30),
    ("tech_3d_printing", "tech_component_production", 3, "3D打印", "3d-printing", 10),
    ("tech_prefabricated_building", "tech_component_production", 3, "装配式建筑", "prefabricated-building", 20),
    ("tech_intelligent_construction", "tech_construction_machinery", 3, "智能施工", "intelligent-construction", 10),
    ("tech_bridge_erector", "tech_construction_machinery", 3, "架桥机", "bridge-erector", 20),
    ("tech_tower_crane", "tech_construction_machinery", 3, "塔吊", "tower-crane", 30),
    ("tech_shield_machine", "tech_construction_machinery", 3, "盾构机", "shield-machine", 40),
    ("tech_robot", "tech_construction_machinery", 3, "机器人", "robot", 50),
    ("tech_big_data", "tech_data_platform", 3, "大数据", "big-data", 10),
    ("tech_blockchain", "tech_data_platform", 3, "区块链", "blockchain", 20),
]

TECHNOLOGY_RELATION_SUGGESTIONS = [
    ("tech_digital_twin", "tech_engineering_software", "related"),
    ("tech_digital_twin", "tech_data_platform", "related"),
    ("tech_large_model", "tech_data_platform", "depends_on"),
    ("tech_smart_site", "tech_data_platform", "depends_on"),
    ("tech_bim", "tech_digital_twin", "converges_with"),
    ("tech_robot", "tech_large_model", "converges_with"),
]

LEGACY_TOPIC_MAPPINGS = {
    "参数化与生成式设计": ["tech_parametric_design", "tech_generative_design"],
    "多专业协同平台": ["tech_bim", "tech_digital_design"],
    "机器人集群协同": ["tech_robot", "tech_intelligent_construction"],
    "施工全过程数字孪生": ["tech_digital_twin", "tech_construction_monitoring"],
    "智能规范审查": ["tech_intelligent_design", "tech_engineering_analysis"],
    "建筑工程大模型技术": ["tech_large_model"],
    "装配式建筑技术": ["tech_prefabricated_building"],
    "建筑规模增材制造": ["tech_3d_printing"],
    "模块化与可重构设计": ["tech_prefabricated_building", "tech_digital_design"],
}
