# -*- coding: utf-8 -*-
"""Build publication chart contracts directly from persisted scientific artifacts."""

import json
from typing import Any, Dict, List

from src.library import LibraryRepository
from src.research.visualization import ChartSeries, ScientificChartData


class ScientificChartFactory:
    def __init__(self, repository: LibraryRepository):
        self.repository = repository

    def for_project(self, project_id: str, cutoff: str = "2025-10-01") -> List[ScientificChartData]:
        with self.repository.db.connect() as connection:
            run = connection.execute(
                "SELECT * FROM network_runs WHERE project_id=? AND status='completed' ORDER BY created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        if not run:
            return []
        run_id = run["network_run_id"]
        charts = [self._network(run_id, cutoff), self._centrality(run_id, cutoff),
                  self._communities(run_id, cutoff)]
        fusion = self._fusion(run_id, cutoff)
        charts.extend(fusion)
        convergence = self._convergence(run_id, cutoff)
        if convergence: charts.append(convergence)
        charts.extend(self._validation(run_id, cutoff))
        return charts

    def _network(self, run_id, cutoff):
        series = []
        with self.repository.db.connect() as connection:
            for period in ("2010_2014", "2015_2019", "2020_2025"):
                coords = {row["ipc_code"]: (row["layout_x"], row["layout_y"])
                          for row in connection.execute(
                    """SELECT ipc_code,layout_x,layout_y FROM network_nodes WHERE network_run_id=?
                       AND observation_kind='period' AND observation_key=?""", (run_id, period)
                ).fetchall()}
                communities = {row["ipc_code"]: row["stable_community_id"] for row in connection.execute(
                    """SELECT ipc_code,stable_community_id FROM community_memberships WHERE network_run_id=?
                       AND observation_kind='period' AND observation_key=?""", (run_id, period)
                ).fetchall()}
                values = []
                for edge in connection.execute(
                    "SELECT ipc1,ipc2,association_strength FROM ipc_edges_period WHERE network_run_id=? AND period_code=?",
                    (run_id, period),
                ).fetchall():
                    if edge["ipc1"] in coords and edge["ipc2"] in coords:
                        left, right = coords[edge["ipc1"]], coords[edge["ipc2"]]
                        values.append({"x1": left[0], "y1": left[1], "x2": right[0], "y2": right[1],
                                       "ipc1": edge["ipc1"], "ipc2": edge["ipc2"],
                                       "community1": communities.get(edge["ipc1"]), "community2": communities.get(edge["ipc2"]),
                                       "weight": min(3, .5 + float(edge["association_strength"] or 0))})
                series.append(ChartSeries(series_id=period, label=period.replace("_", "—"),
                                          evidence_status="observed", values=values))
        return ScientificChartData(figure_number="图4-1", chart_kind="network_small_multiples",
            title="IPC 共现网络阶段比较", caption="固定布局用于跨期结构比较；实线表示观测共现边。",
            source_note="规范化专利—IPC 归属与冻结网络运行", sample_size=sum(len(s.values) for s in series),
            cutoff=cutoff, series=series, metadata={"network_run_id": run_id})

    def _centrality(self, run_id, cutoff):
        with self.repository.db.connect() as connection:
            top = [row[0] for row in connection.execute(
                """SELECT ipc_code FROM network_nodes WHERE network_run_id=? AND observation_kind='period'
                   GROUP BY ipc_code ORDER BY MAX(degree_centrality) DESC LIMIT 8""", (run_id,)
            ).fetchall()]
            series = []
            for code in top:
                values = [{"x": index + 1, "value": row["degree_centrality"] or 0, "period": row["observation_key"]}
                          for index, row in enumerate(connection.execute(
                    """SELECT observation_key,degree_centrality FROM network_nodes WHERE network_run_id=?
                       AND observation_kind='period' AND ipc_code=? ORDER BY observation_key""", (run_id, code)
                ).fetchall())]
                series.append(ChartSeries(series_id=code, label=code, evidence_status="derived", values=values))
            transitions = connection.execute(
                """SELECT to_observation,COUNT(*) count FROM node_transitions WHERE network_run_id=?
                   AND transition_type='peripheral_to_core' GROUP BY to_observation ORDER BY to_observation""", (run_id,)
            ).fetchall()
            if transitions:
                series.append(ChartSeries(series_id="peripheral_to_core", label="边缘→核心节点数",
                    evidence_status="derived", values=[{"x": i + 1, "value": row["count"], "period": row["to_observation"]}
                                                       for i, row in enumerate(transitions)]))
        return ScientificChartData(figure_number="图4-2", chart_kind="centrality_trajectory", title="IPC 中心性迁移",
            caption="度中心性由观测网络推导；跨期上升仅表示结构位置变化。", source_note="确定性网络中心性",
            sample_size=len(top), cutoff=cutoff, series=series, metadata={"x_labels": ["2010—2014", "2015—2019", "2020—2025"]})

    def _communities(self, run_id, cutoff):
        with self.repository.db.connect() as connection:
            rows = connection.execute(
                """SELECT stable_community_id,observation_key,COUNT(*) count FROM community_memberships
                   WHERE network_run_id=? AND observation_kind='period'
                   GROUP BY stable_community_id,observation_key ORDER BY stable_community_id,observation_key""", (run_id,)
            ).fetchall()
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows: grouped.setdefault(row["stable_community_id"], []).append({"x": len(grouped.get(row["stable_community_id"], [])) + 1, "value": row["count"]})
        series = [ChartSeries(series_id=key, label=key, evidence_status="derived", values=value)
                  for key, value in sorted(grouped.items())]
        return ScientificChartData(figure_number="图4-3", chart_kind="community_evolution", title="IPC 社群规模演化",
            caption="连线表示稳定社群标识的成员数变化，不代表专利、知识或因果流量。", source_note="冻结种子社群检测",
            sample_size=sum(len(v) for v in grouped.values()), cutoff=cutoff, series=series)

    def _fusion(self, run_id, cutoff):
        with self.repository.db.connect() as connection:
            rows = connection.execute(
                """SELECT p.rank,p.raw_score,p.interval_low,p.interval_high,p.probability_status,p.stability_status,
                          c.candidate_id,c.ipc1,c.ipc2,c.target_type FROM fusion_predictions p
                   JOIN fusion_candidates c ON c.candidate_id=p.candidate_id JOIN feature_runs f
                   ON f.feature_run_id=c.feature_run_id WHERE f.network_run_id=? ORDER BY c.target_type,p.rank LIMIT 60""",
                (run_id,),
            ).fetchall()
        if not rows: return []
        series = []
        for target in ("emergence", "strengthening"):
            values = [{"rank": row["rank"], "score": row["raw_score"], "low": row["interval_low"],
                       "high": row["interval_high"], "label": "%s × %s" % (row["ipc1"], row["ipc2"]),
                       "stability": row["stability_status"], "probability_status": row["probability_status"]}
                      for row in rows if row["target_type"] == target]
            if values: series.append(ChartSeries(series_id=target, label=target, evidence_status="predicted", values=values))
        ranking = ScientificChartData(figure_number="图4-4", chart_kind="fusion_ranking", title="IPC 融合候选排序",
            caption="虚线与三角表示模型预测；区间缺失时不得解读为概率置信区间。", source_note="历史验证后的确定性模型",
            sample_size=len(rows), cutoff=cutoff, series=series)
        codes = sorted({row["ipc1"] for row in rows} | {row["ipc2"] for row in rows})[:20]
        lookup = {tuple(sorted((row["ipc1"], row["ipc2"]))): float(row["raw_score"]) for row in rows}
        matrix_rows = [{"label": left, "values": [lookup.get(tuple(sorted((left, right))), 0) if left != right else 0 for right in codes]} for left in codes]
        matrix = ScientificChartData(figure_number="图4-5", chart_kind="fusion_matrix", title="IPC 融合评分矩阵",
            caption="矩阵为模型分数而非人工概率；对角线不参与候选定义。", source_note="确定性融合模型",
            sample_size=len(rows), cutoff=cutoff, series=[ChartSeries(series_id="fusion", label="模型分数",
                evidence_status="predicted", values=matrix_rows)], metadata={"columns": codes})
        return [ranking, matrix]

    def _convergence(self, run_id, cutoff):
        with self.repository.db.connect() as connection:
            rows = connection.execute(
                """SELECT c.ipc1,c.ipc2,
                      MAX(CASE WHEN x.feature_name='patent_text_convergence' THEN x.feature_value END) patent_signal,
                      MAX(CASE WHEN x.feature_name='paper_signal_convergence' THEN x.feature_value END) paper_signal
                   FROM fusion_candidates c JOIN feature_runs f ON f.feature_run_id=c.feature_run_id
                   JOIN fusion_features x ON x.candidate_id=c.candidate_id WHERE f.network_run_id=?
                   GROUP BY c.candidate_id ORDER BY c.ipc1,c.ipc2 LIMIT 30""", (run_id,)
            ).fetchall()
        if not rows: return None
        values = [{"label": "%s×%s" % (row["ipc1"], row["ipc2"]),
                   "values": [row["patent_signal"] or 0, row["paper_signal"] or 0,
                              (row["patent_signal"] or 0) - (row["paper_signal"] or 0)]} for row in rows]
        return ScientificChartData(figure_number="图4-6", chart_kind="convergence_matrix", title="专利—论文信号收敛与冲突",
            caption="前两列为带时间戳的来源信号，差值方向仅表示来源冲突，不表示因果。", source_note="冻结专利文本与论文类型信号",
            sample_size=len(rows), cutoff=cutoff, series=[ChartSeries(series_id="convergence", label="来源信号",
                evidence_status="derived", values=values)], metadata={"columns": ["专利信号", "论文信号", "方向差"]})

    def _validation(self, run_id, cutoff):
        with self.repository.db.connect() as connection:
            rows = connection.execute(
                """SELECT m.model_run_id,v.metric_name,v.metric_value,v.interval_low,v.interval_high
                   FROM validation_metrics v JOIN model_runs m ON m.model_run_id=v.model_run_id
                   JOIN feature_runs f ON f.feature_run_id=m.feature_run_id WHERE f.network_run_id=?
                   AND v.status='estimated' ORDER BY m.model_run_id,v.metric_name""", (run_id,)
            ).fetchall()
            calibration_rows = connection.execute(
                """SELECT p.calibrated_probability,c.label FROM fusion_predictions p JOIN fusion_candidates c
                   ON c.candidate_id=p.candidate_id JOIN model_runs m ON m.model_run_id=p.model_run_id
                   JOIN feature_runs f ON f.feature_run_id=m.feature_run_id WHERE f.network_run_id=?
                   AND p.calibrated_probability IS NOT NULL AND c.label IS NOT NULL""", (run_id,)
            ).fetchall()
            ablations = connection.execute(
                """SELECT a.omitted_feature_family,a.metrics_json FROM ablation_runs a JOIN model_runs m
                   ON m.model_run_id=a.model_run_id JOIN feature_runs f ON f.feature_run_id=m.feature_run_id
                   WHERE f.network_run_id=? ORDER BY a.omitted_feature_family""", (run_id,)
            ).fetchall()
            sensitivities = connection.execute(
                """SELECT s.sensitivity_kind,s.candidate_changes_json FROM sensitivity_runs s JOIN model_runs m
                   ON m.model_run_id=s.model_run_id JOIN feature_runs f ON f.feature_run_id=m.feature_run_id
                   WHERE f.network_run_id=? ORDER BY s.sensitivity_kind""", (run_id,)
            ).fetchall()
        charts = []
        if rows:
            grouped: Dict[str, List[Dict[str, Any]]] = {}
            for row in rows: grouped.setdefault(row["model_run_id"], []).append({"x": len(grouped.get(row["model_run_id"], [])) + 1,
                "value": row["metric_value"], "low": row["interval_low"], "high": row["interval_high"], "metric": row["metric_name"]})
            series = [ChartSeries(series_id=key, label=key, evidence_status="derived", values=value) for key, value in grouped.items()]
            charts.append(ScientificChartData(figure_number="图4-7", chart_kind="validation_panel", title="历史验证与基线比较",
                caption="时间顺序折上的排序、基线和校准指标；不可估计值不绘制。", source_note="滚动起点历史验证",
                sample_size=len(rows), cutoff=cutoff, series=series))
        if calibration_rows:
            bins = []
            for index in range(10):
                members = [row for row in calibration_rows if index / 10 <= row["calibrated_probability"] < (index + 1) / 10
                           or (index == 9 and row["calibrated_probability"] == 1)]
                if members: bins.append({"x": sum(row["calibrated_probability"] for row in members) / len(members),
                    "value": sum(row["label"] for row in members) / len(members), "count": len(members)})
            charts.append(ScientificChartData(figure_number="图4-8", chart_kind="validation_panel", title="概率可靠性",
                caption="横轴为预测概率，纵轴为历史观测频率；仅绘制有样本的分箱。", source_note="保留集概率校准",
                sample_size=len(calibration_rows), cutoff=cutoff, series=[ChartSeries(series_id="reliability", label="可靠性",
                    evidence_status="derived", values=bins), ChartSeries(series_id="ideal", label="理想校准", evidence_status="observed",
                    values=[{"x": 0, "value": 0}, {"x": 1, "value": 1}])]))
        if ablations:
            values = [{"x": i + 1, "value": self._first_number(json.loads(row["metrics_json"])), "family": row["omitted_feature_family"]}
                      for i, row in enumerate(ablations)]
            charts.append(ScientificChartData(figure_number="图4-9", chart_kind="validation_panel", title="特征族消融",
                caption="移除各特征族后的首要注册指标；应结合完整指标表解释。", source_note="预注册特征族消融",
                sample_size=len(values), cutoff=cutoff, series=[ChartSeries(series_id="ablation", label="消融指标",
                    evidence_status="derived", values=values)]))
        if sensitivities:
            values = []
            for i, row in enumerate(sensitivities):
                changes = json.loads(row["candidate_changes_json"])
                unstable = sum(bool(item.get("unstable") or item.get("selection_changed")) for item in changes)
                values.append({"x": i + 1, "value": unstable / max(1, len(changes)), "kind": row["sensitivity_kind"]})
            charts.append(ScientificChartData(figure_number="图4-10", chart_kind="validation_panel", title="敏感性稳定度",
                caption="纵轴为各设定下不稳定或选择改变的候选比例。", source_note="候选定义与数据边界敏感性分析",
                sample_size=len(values), cutoff=cutoff, series=[ChartSeries(series_id="sensitivity", label="不稳定比例",
                    evidence_status="derived", values=values)]))
        return charts

    @staticmethod
    def _first_number(value):
        if isinstance(value, (int, float)): return float(value)
        if isinstance(value, dict):
            for child in value.values():
                found = ScientificChartFactory._first_number(child)
                if found is not None: return found
        if isinstance(value, list):
            for child in value:
                found = ScientificChartFactory._first_number(child)
                if found is not None: return found
        return 0.0
