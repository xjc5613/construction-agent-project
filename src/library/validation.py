# -*- coding: utf-8 -*-
import re
from typing import Iterable, Mapping

from .constants import HISTORICAL_PERIODS, PUBLIC_DATASET_KINDS

DATASET_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*$")
PROJECT_LIFECYCLE_STATES = {"active", "archived"}
MATERIAL_LIFECYCLE_STATES = {"active", "inactive"}
DATASET_LIFECYCLE_STATES = {"active", "deprecated"}


def validate_dataset_version(value: str) -> str:
    value = value.strip()
    if not DATASET_VERSION_PATTERN.fullmatch(value):
        raise ValueError("版本只能包含字母、数字及分隔符 .、-、_，且不能仅为符号")
    return value


def validate_project_name(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("项目名称不能为空")
    if len(value) > 160:
        raise ValueError("项目名称不能超过160个字符")
    return value


def validate_override_reason(value: str, required: bool = False) -> str:
    value = value.strip()
    if required and not value:
        raise ValueError("证据覆盖理由不能为空")
    if len(value) > 500:
        raise ValueError("证据覆盖理由不能超过500个字符")
    return value


def validate_lifecycle(value: str, allowed: Iterable[str]) -> str:
    if value not in set(allowed):
        raise ValueError("生命周期状态无效")
    return value


def validate_classification(payload: Mapping[str, str]) -> None:
    if payload.get("period_code") not in HISTORICAL_PERIODS:
        raise ValueError("历史阶段无效")
    if payload.get("kind") not in PUBLIC_DATASET_KINDS:
        raise ValueError("数据类型必须是 IPC、论文或综合数据")


def validate_technology_associations(items: Iterable[Mapping[str, object]]) -> None:
    items = list(items)
    if not items:
        raise ValueError("主题至少需要关联一个三级技术")
    if sum(bool(item.get("is_primary")) for item in items) != 1:
        raise ValueError("主题必须且只能设置一个主技术")
