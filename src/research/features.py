# -*- coding: utf-8 -*-
"""Leakage-safe fusion candidate and temporal feature pipeline."""

import itertools
import json
import math
from dataclasses import asdict, dataclass
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4

from src.library import LibraryRepository
from src.research.repository import canonical_checksum


FEATURE_SCHEMA_VERSION = "fusion-features-v1"


def _id(prefix: str) -> str:
    return "%s_%s" % (prefix, uuid4().hex[:16])


def _pair(left: str, right: str) -> Tuple[str, str]:
    return tuple(sorted((left, right)))


@dataclass(frozen=True)
class CandidatePolicy:
    target_type: str = "emergence"
    minimum_support: int = 1
    edge_threshold: float = 0.0
    forecast_horizon: int = 5
    cross_domain_only: bool = False
    negative_sampling: str = "all_eligible"
    max_candidates: int = 10000


class FusionFeaturePipeline:
    def __init__(self, repository: Optional[LibraryRepository] = None):
        self.repository = repository or LibraryRepository()

    def build(
        self, network_result: Dict[str, Any], *, cutoff_year: int,
        policy: Optional[CandidatePolicy] = None,
        patent_text_signals: Iterable[Dict[str, Any]] = (),
        paper_signals: Iterable[Dict[str, Any]] = (),
        taxonomy: Optional[Dict[str, str]] = None,
        mappings: Iterable[Dict[str, Any]] = (),
    ) -> Dict[str, Any]:
        policy = policy or CandidatePolicy()
        if policy.target_type not in {"emergence", "strengthening"}:
            raise ValueError("预测目标必须是 emergence 或 strengthening")
        annual = {int(year): value for year, value in network_result["annual"].items()
                  if int(year) <= cutoff_year}
        nodes = sorted(network_result.get("layout", {}))
        latest_edges = self._edges_at_or_before(annual, cutoff_year)
        candidates = []
        for left, right in itertools.combinations(nodes, 2):
            pair = (left, right)
            observed = pair in latest_edges
            if policy.target_type == "emergence" and observed:
                continue
            if policy.target_type == "strengthening" and not observed:
                continue
            if policy.cross_domain_only and taxonomy and taxonomy.get(left) == taxonomy.get(right):
                continue
            features, lineage = self._features(
                pair, annual, cutoff_year, patent_text_signals, paper_signals,
                taxonomy or {}, mappings,
            )
            candidates.append({
                "ipc1": left, "ipc2": right, "target_type": policy.target_type,
                "eligible": True, "exclusion_reason": "", "features": features,
                "lineage": lineage,
            })
        candidates.sort(key=lambda item: (item["ipc1"], item["ipc2"]))
        candidates = candidates[:policy.max_candidates]
        result = {
            "schema_version": FEATURE_SCHEMA_VERSION, "cutoff_year": cutoff_year,
            "policy": asdict(policy), "candidates": candidates,
            "feature_definitions": self.feature_definitions(),
        }
        result["checksum"] = canonical_checksum(result)
        return result

    @staticmethod
    def _edges_at_or_before(annual, cutoff):
        result = {}
        for year in sorted(year for year in annual if year <= cutoff):
            for edge in annual[year]["edges"]:
                result[_pair(edge["ipc1"], edge["ipc2"])] = edge
        return result

    def _features(self, pair, annual, cutoff, patent_signals, paper_signals,
                  taxonomy, mappings):
        left, right = pair
        adjacency = {node: set() for node in {left, right}}
        edge_history, left_degree, right_degree = [], [], []
        for year in sorted(annual):
            year_adj = {}
            for edge in annual[year]["edges"]:
                a, b = edge["ipc1"], edge["ipc2"]
                year_adj.setdefault(a, set()).add(b)
                year_adj.setdefault(b, set()).add(a)
                if _pair(a, b) == pair:
                    edge_history.append((year, float(edge.get("association_strength") or 0)))
            adjacency = year_adj
            left_degree.append((year, len(year_adj.get(left, set()))))
            right_degree.append((year, len(year_adj.get(right, set()))))
        left_neighbors, right_neighbors = adjacency.get(left, set()), adjacency.get(right, set())
        common = left_neighbors & right_neighbors
        adamic = sum(1 / math.log(len(adjacency.get(node, set())))
                     for node in common if len(adjacency.get(node, set())) > 1)
        resource = sum(1 / len(adjacency.get(node, set()))
                       for node in common if adjacency.get(node, set()))
        mapping_rows = [row for row in mappings if int(row.get("observed_year", cutoff)) <= cutoff]
        mapped = {row.get("ipc_code_raw"): row.get("ipc_code_normalized") for row in mapping_rows}
        text = self._signal_score(pair, patent_signals, cutoff)
        papers = self._signal_score(pair, paper_signals, cutoff)
        features = {
            "common_neighbors": float(len(common)), "adamic_adar": adamic,
            "resource_allocation": resource,
            "preferential_attachment": float(len(left_neighbors) * len(right_neighbors)),
            "community_distance": 0.0 if common else 1.0,
            "left_degree_slope": self._slope(left_degree),
            "right_degree_slope": self._slope(right_degree),
            "edge_strength_slope": self._slope(edge_history),
            "patent_text_convergence": text,
            "paper_signal_convergence": papers,
            "taxonomy_distance": 0.0 if taxonomy.get(left) and taxonomy.get(left) == taxonomy.get(right) else 1.0,
            "mapping_available": float(left in mapped or right in mapped),
        }
        lineage = {
            name: {"cutoff_year": cutoff, "source_years": sorted(annual),
                   "source_kind": "network"}
            for name in features
        }
        lineage["patent_text_convergence"]["source_kind"] = "patent_text"
        lineage["paper_signal_convergence"]["source_kind"] = "paper"
        lineage["mapping_available"]["source_kind"] = "ipc_mapping"
        return features, lineage

    @staticmethod
    def _signal_score(pair, signals, cutoff):
        values = [float(item.get("score", 0)) for item in signals
                  if int(item.get("observed_year", item.get("year", 0))) <= cutoff
                  and _pair(item.get("ipc1", ""), item.get("ipc2", "")) == pair]
        return mean(values) if values else 0.0

    @staticmethod
    def _slope(points):
        if len(points) < 2:
            return 0.0
        x_bar, y_bar = mean(x for x, _ in points), mean(y for _, y in points)
        denominator = sum((x - x_bar) ** 2 for x, _ in points)
        return sum((x - x_bar) * (y - y_bar) for x, y in points) / denominator if denominator else 0.0

    @staticmethod
    def feature_definitions():
        return {
            "common_neighbors": "截断时点共同邻居数",
            "adamic_adar": "共同邻居按对数度数衰减",
            "resource_allocation": "共同邻居资源分配指数",
            "preferential_attachment": "两节点度数乘积",
            "community_distance": "截断网络的社群邻近代理",
            "left_degree_slope": "左节点截断前度数趋势",
            "right_degree_slope": "右节点截断前度数趋势",
            "edge_strength_slope": "已有边截断前强度趋势",
            "patent_text_convergence": "带时间戳专利文本融合信号",
            "paper_signal_convergence": "带时间戳论文融合信号",
            "taxonomy_distance": "冻结分类域距离代理",
            "mapping_available": "截断前 IPC 映射可用性",
        }

    def persist(self, network_run_id: str, result: Dict[str, Any]) -> str:
        with self.repository.db.transaction() as connection:
            existing = connection.execute(
                "SELECT feature_run_id FROM feature_runs WHERE input_checksum=? AND schema_version=?",
                (result["checksum"], result["schema_version"]),
            ).fetchone()
            if existing:
                return existing[0]
            run_id = _id("features")
            connection.execute(
                """INSERT INTO feature_runs(feature_run_id,network_run_id,cutoff_year,target_type,
                   schema_version,candidate_policy_json,feature_definitions_json,input_checksum,
                   result_checksum,status) VALUES (?,?,?,?,?,?,?,?,?,'completed')""",
                (run_id, network_run_id, result["cutoff_year"], result["policy"]["target_type"],
                 result["schema_version"], json.dumps(result["policy"], sort_keys=True),
                 json.dumps(result["feature_definitions"], ensure_ascii=False, sort_keys=True),
                 result["checksum"], result["checksum"]),
            )
            for item in result["candidates"]:
                candidate_id = _id("candidate")
                connection.execute(
                    """INSERT INTO fusion_candidates(candidate_id,feature_run_id,ipc1,ipc2,
                       target_type,eligible,exclusion_reason,label,label_window)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (candidate_id, run_id, item["ipc1"], item["ipc2"], item["target_type"],
                     int(item["eligible"]), item["exclusion_reason"], item.get("label"),
                     item.get("label_window", "")),
                )
                for name, value in item["features"].items():
                    connection.execute(
                        """INSERT INTO fusion_features(feature_value_id,candidate_id,feature_name,
                           feature_value,feature_status,lineage_json) VALUES (?,?,?,?,?,?)""",
                        (_id("feature"), candidate_id, name, value,
                         "observed" if value is not None else "missing",
                         json.dumps(item["lineage"][name], sort_keys=True)),
                    )
        return run_id
