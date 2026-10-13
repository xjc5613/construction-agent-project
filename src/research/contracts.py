# -*- coding: utf-8 -*-
"""Immutable research-period contracts used by projects and frozen jobs."""

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple


LEGACY_RESEARCH_CONTRACT_VERSION = 2
CURRENT_RESEARCH_CONTRACT_VERSION = 3


@dataclass(frozen=True)
class ResearchContract:
    version: int
    name: str
    baseline_year: int
    periods: Mapping[str, Tuple[int, int]]
    period_labels: Mapping[str, str]
    target_years: Tuple[int, ...] = (2030, 2035, 2040)
    default_cutoff: str = ""
    incomplete_years: Tuple[int, ...] = ()

    def derive_forecast_nodes(self, target_year: int) -> list[int]:
        if target_year not in self.target_years:
            raise ValueError("目标年份必须是 2030、2035 或 2040")
        return [year for year in self.target_years if year <= target_year]

    def validate_baseline(self, baseline_year: int) -> None:
        if baseline_year != self.baseline_year:
            raise ValueError(
                f"研究合同 v{self.version} 的基线必须是 {self.baseline_year}"
            )

    def period_for_year(self, year: int) -> Optional[str]:
        return next(
            (
                code
                for code, (start, end) in self.periods.items()
                if start <= year <= end
            ),
            None,
        )

    def validate_period(self, period_code: str) -> None:
        if period_code not in self.periods:
            raise ValueError(
                f"历史阶段 {period_code} 不属于研究合同 v{self.version}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "name": self.name,
            "baseline_year": self.baseline_year,
            "periods": {
                code: {"start_year": bounds[0], "end_year": bounds[1],
                       "label": self.period_labels[code]}
                for code, bounds in self.periods.items()
            },
            "target_years": list(self.target_years),
            "default_cutoff": self.default_cutoff,
            "incomplete_years": list(self.incomplete_years),
        }


RESEARCH_CONTRACTS: Dict[int, ResearchContract] = {
    LEGACY_RESEARCH_CONTRACT_VERSION: ResearchContract(
        version=LEGACY_RESEARCH_CONTRACT_VERSION,
        name="legacy-stage-forecast-2026",
        baseline_year=2026,
        periods={
            "2010_2015": (2010, 2015),
            "2016_2020": (2016, 2020),
            "2021_2026": (2021, 2026),
        },
        period_labels={
            "2010_2015": "2010-2015",
            "2016_2020": "2016-2020",
            "2021_2026": "2021-2026",
        },
    ),
    CURRENT_RESEARCH_CONTRACT_VERSION: ResearchContract(
        version=CURRENT_RESEARCH_CONTRACT_VERSION,
        name="chapter-4-ipc-fusion-2025",
        baseline_year=2025,
        periods={
            "2010_2014": (2010, 2014),
            "2015_2019": (2015, 2019),
            "2020_2025": (2020, 2025),
        },
        period_labels={
            "2010_2014": "2010-2014",
            "2015_2019": "2015-2019",
            "2020_2025": "2020-2025",
        },
        default_cutoff="2025-10-01",
        incomplete_years=(2025,),
    ),
}


def get_research_contract(
    version: int = CURRENT_RESEARCH_CONTRACT_VERSION,
) -> ResearchContract:
    try:
        return RESEARCH_CONTRACTS[int(version)]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"不支持的研究合同版本：{version}") from exc


def contract_for_record(record: Mapping[str, Any]) -> ResearchContract:
    """Resolve explicit versions first and infer only for old snapshots."""
    version = record.get("research_contract_version") or record.get(
        "contract_version"
    )
    if version is not None:
        return get_research_contract(int(version))
    if int(record.get("baseline_year") or 2025) == 2026:
        return get_research_contract(LEGACY_RESEARCH_CONTRACT_VERSION)
    if record.get("legacy_mode"):
        return get_research_contract(LEGACY_RESEARCH_CONTRACT_VERSION)
    return get_research_contract(CURRENT_RESEARCH_CONTRACT_VERSION)
