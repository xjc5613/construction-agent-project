# -*- coding: utf-8 -*-
"""Deterministic, framework-independent temporal IPC network reconstruction."""

import itertools
import json
import math
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from uuid import uuid4

from src.library import LibraryRepository
from src.research.contracts import get_research_contract
from src.research.repository import ResearchRepository, canonical_checksum


ALGORITHM_VERSION = "ipc-dynamic-network-v1"


def _id(prefix: str) -> str:
    return "%s_%s" % (prefix, uuid4().hex[:16])


@dataclass(frozen=True)
class NetworkParameters:
    research_contract_version: int = 3
    minimum_support: int = 1
    completeness_policy: str = "include_partial_with_sensitivity"
    community_algorithm: str = "deterministic-components-v1"
    layout_algorithm: str = "shared-circle-v1"
    random_seed: int = 0


def _pair(left: str, right: str) -> Tuple[str, str]:
    return tuple(sorted((left, right)))


def _distances(adjacency: Dict[str, Dict[str, float]], source: str) -> Dict[str, int]:
    distance, queue = {source: 0}, deque([source])
    while queue:
        node = queue.popleft()
        for neighbor in sorted(adjacency[node]):
            if neighbor not in distance:
                distance[neighbor] = distance[node] + 1
                queue.append(neighbor)
    return distance


def _betweenness(adjacency: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    nodes = sorted(adjacency)
    scores = dict.fromkeys(nodes, 0.0)
    for source in nodes:
        stack, predecessors = [], {node: [] for node in nodes}
        sigma, distance = dict.fromkeys(nodes, 0.0), dict.fromkeys(nodes, -1)
        sigma[source], distance[source] = 1.0, 0
        queue = deque([source])
        while queue:
            vertex = queue.popleft()
            stack.append(vertex)
            for neighbor in sorted(adjacency[vertex]):
                if distance[neighbor] < 0:
                    queue.append(neighbor)
                    distance[neighbor] = distance[vertex] + 1
                if distance[neighbor] == distance[vertex] + 1:
                    sigma[neighbor] += sigma[vertex]
                    predecessors[neighbor].append(vertex)
        dependency = dict.fromkeys(nodes, 0.0)
        while stack:
            vertex = stack.pop()
            for predecessor in predecessors[vertex]:
                dependency[predecessor] += (
                    sigma[predecessor] / sigma[vertex]
                ) * (1 + dependency[vertex])
            if vertex != source:
                scores[vertex] += dependency[vertex]
    scale = 1 / ((len(nodes) - 1) * (len(nodes) - 2)) if len(nodes) > 2 else 0
    return {node: value * scale for node, value in scores.items()}


def _eigenvector(adjacency: Dict[str, Dict[str, float]]) -> Dict[str, Optional[float]]:
    nodes = sorted(adjacency)
    if not nodes:
        return {}
    values = {node: 1 / math.sqrt(len(nodes)) for node in nodes}
    for _ in range(200):
        updated = {
            node: sum(weight * values[neighbor] for neighbor, weight in adjacency[node].items())
            for node in nodes
        }
        norm = math.sqrt(sum(value * value for value in updated.values()))
        if not norm:
            return {node: None for node in nodes}
        updated = {node: value / norm for node, value in updated.items()}
        if max(abs(updated[node] - values[node]) for node in nodes) < 1e-12:
            values = updated
            break
        values = updated
    return values


def _components(adjacency: Dict[str, Dict[str, float]]) -> List[List[str]]:
    remaining, result = set(adjacency), []
    while remaining:
        start = min(remaining)
        component, queue = set(), [start]
        while queue:
            node = queue.pop()
            if node in component:
                continue
            component.add(node)
            queue.extend(sorted(adjacency[node], reverse=True))
        remaining -= component
        result.append(sorted(component))
    return sorted(result, key=lambda values: (-len(values), values))


def calculate_node_measures(
    nodes: Iterable[str], edges: Dict[Tuple[str, str], Dict[str, Any]]
) -> List[Dict[str, Any]]:
    ordered = sorted(set(nodes))
    adjacency = {node: {} for node in ordered}
    for (left, right), edge in edges.items():
        weight = float(edge.get("cooccurrence_count") or 1)
        adjacency[left][right] = weight
        adjacency[right][left] = weight
    betweenness, eigenvector = _betweenness(adjacency), _eigenvector(adjacency)
    component_by_node = {}
    for component in _components(adjacency):
        stable = "community-" + canonical_checksum(component)[:10]
        for node in component:
            component_by_node[node] = stable
    result = []
    for node in ordered:
        distances = _distances(adjacency, node)
        connected_to_all = len(distances) == len(ordered)
        degree = len(adjacency[node]) / (len(ordered) - 1) if len(ordered) > 1 else 0.0
        closeness = ((len(distances) - 1) / sum(distances.values())) if len(distances) > 1 else None
        result.append({
            "ipc_code": node, "degree_centrality": degree,
            "betweenness_centrality": betweenness[node], "closeness_centrality": closeness,
            "eccentricity": max(distances.values()) if connected_to_all and distances else None,
            "eigenvector_centrality": eigenvector[node], "community_id": component_by_node[node],
            "undefined": [name for name, value in (("closeness", closeness),
                          ("eccentricity", max(distances.values()) if connected_to_all and distances else None),
                          ("eigenvector", eigenvector[node])) if value is None],
        })
    return result


class DynamicIPCNetworkService:
    def __init__(self, repository: Optional[LibraryRepository] = None):
        self.repository = repository or LibraryRepository()
        self.research = ResearchRepository(self.repository.db)

    def records_from_database(self, dataset_ids: List[str]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        if not dataset_ids:
            return [], []
        placeholders = ",".join("?" for _ in dataset_ids)
        with self.repository.db.connect() as connection:
            rows = connection.execute(
                """SELECT p.patent_id,p.application_year,pi.ipc_code_normalized
                   FROM patents p JOIN patent_ipcs pi ON pi.patent_id=p.patent_id
                   WHERE p.dataset_id IN (%s) AND pi.mapping_status='mapped'
                   ORDER BY p.application_year,p.patent_id,pi.ipc_code_normalized""" % placeholders,
                dataset_ids,
            ).fetchall()
            reduced = [dict(row) for row in connection.execute(
                """SELECT * FROM reduced_ipc_edges WHERE dataset_id IN (%s)
                   AND review_status='approved' ORDER BY year,ipc1,ipc2""" % placeholders,
                dataset_ids,
            ).fetchall()]
        patents = {}
        for row in rows:
            item = patents.setdefault(row["patent_id"], {
                "patent_id": row["patent_id"], "year": int(row["application_year"]), "ipc_codes": []
            })
            item["ipc_codes"].append(row["ipc_code_normalized"])
        return list(patents.values()), reduced

    def build(
        self, patents: Iterable[Dict[str, Any]], *,
        reduced_edges: Iterable[Dict[str, Any]] = (),
        parameters: Optional[NetworkParameters] = None,
    ) -> Dict[str, Any]:
        parameters = parameters or NetworkParameters()
        contract = get_research_contract(parameters.research_contract_version)
        annual_patents, all_nodes = defaultdict(list), set()
        for patent in patents:
            codes = sorted(set(patent.get("ipc_codes") or []))
            all_nodes.update(codes)
            annual_patents[int(patent["year"])].append({**patent, "ipc_codes": codes})
        reduced_by_year = defaultdict(list)
        for edge in reduced_edges:
            reduced_by_year[int(edge["year"])].append(edge)
            all_nodes.update((edge["ipc1"], edge["ipc2"]))
        layout = self._shared_layout(all_nodes)
        annual = {}
        for year in sorted(set(annual_patents) | set(reduced_by_year)):
            annual[str(year)] = self._observation(
                annual_patents[year], reduced_by_year[year], all_nodes,
                parameters.minimum_support, layout,
            )
        periods = {}
        for code, (start, end) in contract.periods.items():
            period_patents = [patent for year, values in annual_patents.items()
                              if start <= year <= end for patent in values]
            period_reduced = [edge for year, values in reduced_by_year.items()
                              if start <= year <= end for edge in values]
            periods[code] = self._observation(
                period_patents, period_reduced, all_nodes,
                parameters.minimum_support, layout,
            )
        transitions = self._transitions(periods, list(contract.periods))
        result = {
            "schema_version": "network-result-v1", "algorithm_version": ALGORITHM_VERSION,
            "parameters": asdict(parameters), "annual": annual, "periods": periods,
            "transitions": transitions, "layout": layout,
            "evidence_grade": "canonical" if annual_patents else "reduced_edge",
        }
        result["result_checksum"] = canonical_checksum(result)
        return result

    @staticmethod
    def _shared_layout(nodes: Set[str]) -> Dict[str, Dict[str, float]]:
        ordered = sorted(nodes)
        count = max(1, len(ordered))
        return {node: {"x": round(math.cos(2 * math.pi * i / count), 8),
                       "y": round(math.sin(2 * math.pi * i / count), 8)}
                for i, node in enumerate(ordered)}

    @staticmethod
    def _observation(patents, reduced_edges, all_nodes, minimum_support, layout):
        node_counts, edge_patents = Counter(), defaultdict(set)
        for patent in patents:
            codes = sorted(set(patent["ipc_codes"]))
            for code in codes:
                node_counts[code] += 1
            for left, right in itertools.combinations(codes, 2):
                edge_patents[_pair(left, right)].add(str(patent["patent_id"]))
        edges = {}
        total = len({str(patent["patent_id"]) for patent in patents})
        for pair, patent_ids in edge_patents.items():
            support = len(patent_ids)
            if support < minimum_support:
                continue
            left, right = pair
            denominator = math.sqrt(node_counts[left] * node_counts[right])
            union = node_counts[left] + node_counts[right] - support
            edges[pair] = {
                "ipc1": left, "ipc2": right, "cooccurrence_count": support,
                "supporting_patent_count": support, "supporting_patent_ids": sorted(patent_ids),
                "association_strength": support / denominator if denominator else None,
                "jaccard": support / union if union else None,
                "pmi": math.log((support * total) / (node_counts[left] * node_counts[right]))
                if total and node_counts[left] and node_counts[right] else None,
                "denominators": {"total_patents": total, "ipc1_count": node_counts[left],
                                 "ipc2_count": node_counts[right]},
                "evidence_grade": "canonical",
            }
        for edge in reduced_edges:
            pair = _pair(edge["ipc1"], edge["ipc2"])
            support = int(edge["cooccurrence_count"])
            if support < minimum_support or pair in edges:
                continue
            left_count, right_count = edge.get("ipc1_count"), edge.get("ipc2_count")
            total_count = edge.get("total_patent_count")
            denominator = math.sqrt(left_count * right_count) if left_count and right_count else None
            union = left_count + right_count - support if left_count and right_count else None
            edges[pair] = {
                "ipc1": pair[0], "ipc2": pair[1], "cooccurrence_count": support,
                "supporting_patent_count": int(edge.get("source_patent_count") or support),
                "supporting_patent_ids": [],
                "association_strength": support / denominator if denominator else None,
                "jaccard": support / union if union else None,
                "pmi": math.log((support * total_count) / (left_count * right_count))
                if total_count and left_count and right_count else None,
                "denominators": {"total_patents": total_count, "ipc1_count": left_count,
                                 "ipc2_count": right_count},
                "evidence_grade": "reduced_edge",
            }
        measures = calculate_node_measures(all_nodes, edges)
        for item in measures:
            item.update(layout[item["ipc_code"]])
            item["patent_count"] = node_counts[item["ipc_code"]]
        return {"nodes": measures, "edges": [edges[key] for key in sorted(edges)],
                "patent_count": total}

    @staticmethod
    def _transitions(periods, period_order):
        result = []
        first_appearance = {}
        for period in period_order:
            for node in periods[period]["nodes"]:
                if node["patent_count"] or node["degree_centrality"]:
                    first_appearance.setdefault(node["ipc_code"], period)
        for code, period in sorted(first_appearance.items()):
            trajectory = []
            for observation in period_order:
                node = next(item for item in periods[observation]["nodes"] if item["ipc_code"] == code)
                trajectory.append({"period": observation, "degree": node["degree_centrality"],
                                   "community_id": node["community_id"]})
            transition_type = "peripheral_to_core" if trajectory[-1]["degree"] > trajectory[0]["degree"] else "persistent"
            result.append({"ipc_code": code, "first_appearance": period, "trajectory": trajectory,
                           "transition_type": transition_type,
                           "community_movement": len({item["community_id"] for item in trajectory}) > 1})
        return result

    def build_and_persist(self, project_id: str, snapshot: Dict[str, Any],
                          parameters: Optional[NetworkParameters] = None) -> Dict[str, Any]:
        parameters = parameters or NetworkParameters()
        patents, reduced = self.records_from_database(snapshot["dataset_ids"])
        input_payload = {"snapshot_checksum": snapshot["checksum"], "patents": patents,
                         "reduced_edges": reduced, "parameters": asdict(parameters)}
        input_checksum = canonical_checksum(input_payload)
        run = self.research.create_network_run({
            "project_id": project_id, "snapshot_checksum": snapshot["checksum"],
            "research_contract_version": parameters.research_contract_version,
            "algorithm_version": ALGORITHM_VERSION, "parameters": asdict(parameters),
            "input_checksum": input_checksum, "random_seed": parameters.random_seed,
            "evidence_grade": "canonical" if patents else "reduced_edge",
        })
        result = self.build(patents, reduced_edges=reduced, parameters=parameters)
        if run["status"] != "completed":
            self._persist_result(run["network_run_id"], result)
            self.research.complete_network_run(run["network_run_id"], result["result_checksum"])
        return {"run": self.research.create_network_run({
                    "project_id": project_id, "snapshot_checksum": snapshot["checksum"],
                    "algorithm_version": ALGORITHM_VERSION, "input_checksum": input_checksum}),
                "result": result}

    def _persist_result(self, run_id: str, result: Dict[str, Any]) -> None:
        with self.repository.db.transaction() as connection:
            for kind, observations in (("annual", result["annual"]), ("period", result["periods"])):
                for key, observation in observations.items():
                    for node in observation["nodes"]:
                        connection.execute(
                            """INSERT INTO network_nodes(node_measure_id,network_run_id,observation_kind,
                               observation_key,ipc_code,patent_count,degree_centrality,betweenness_centrality,
                               closeness_centrality,eccentricity,eigenvector_centrality,community_id,
                               layout_x,layout_y,metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (_id("node"), run_id, kind, key, node["ipc_code"], node["patent_count"],
                             node["degree_centrality"], node["betweenness_centrality"],
                             node["closeness_centrality"], node["eccentricity"],
                             node["eigenvector_centrality"], node["community_id"], node["x"], node["y"],
                             json.dumps({"undefined": node["undefined"]})),
                        )
                        connection.execute(
                            """INSERT INTO community_memberships(membership_id,network_run_id,
                               observation_kind,observation_key,ipc_code,community_id,stable_community_id,
                               algorithm_version) VALUES (?,?,?,?,?,?,?,?)""",
                            (_id("membership"), run_id, kind, key, node["ipc_code"], node["community_id"],
                             node["community_id"], "deterministic-components-v1"),
                        )
                    table = "ipc_edges_yearly" if kind == "annual" else "ipc_edges_period"
                    observation_column = "year" if kind == "annual" else "period_code"
                    for edge in observation["edges"]:
                        connection.execute(
                            """INSERT INTO %s(edge_id,network_run_id,%s,ipc1,ipc2,cooccurrence_count,
                               supporting_patent_count,association_strength,jaccard,pmi,denominators_json,
                               supporting_patent_ids_json,evidence_grade) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"""
                            % (table, observation_column),
                            (_id("edge"), run_id, int(key) if kind == "annual" else key,
                             edge["ipc1"], edge["ipc2"], edge["cooccurrence_count"],
                             edge["supporting_patent_count"], edge["association_strength"], edge["jaccard"],
                             edge["pmi"], json.dumps(edge["denominators"]),
                             json.dumps(edge["supporting_patent_ids"]), edge["evidence_grade"]),
                        )
            for transition in result["transitions"]:
                trajectory = transition["trajectory"]
                for before, after in zip(trajectory, trajectory[1:]):
                    connection.execute(
                        """INSERT INTO node_transitions(transition_id,network_run_id,ipc_code,
                           from_observation,to_observation,transition_type,before_json,after_json,
                           threshold_json,sensitivity_status) VALUES (?,?,?,?,?,?,?,?,?,'not_evaluated')""",
                        (_id("transition"), run_id, transition["ipc_code"], before["period"],
                         after["period"], transition["transition_type"],
                         json.dumps(before, sort_keys=True), json.dumps(after, sort_keys=True),
                         json.dumps({"degree_change_threshold": 0}, sort_keys=True)),
                    )

    def edge_evidence(self, run_id: str, ipc1: str, ipc2: str, *,
                      page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        left, right = _pair(ipc1, ipc2)
        with self.repository.db.connect() as connection:
            rows = connection.execute(
                """SELECT year,supporting_patent_ids_json,evidence_grade,cooccurrence_count
                   FROM ipc_edges_yearly WHERE network_run_id=? AND ipc1=? AND ipc2=?
                   ORDER BY year LIMIT ? OFFSET ?""",
                (run_id, left, right, page_size, (page - 1) * page_size),
            ).fetchall()
        items = [{**dict(row), "supporting_patent_ids": json.loads(row["supporting_patent_ids_json"])}
                 for row in rows]
        for item in items:
            item.pop("supporting_patent_ids_json", None)
        return {"items": items, "page": page, "page_size": page_size}
