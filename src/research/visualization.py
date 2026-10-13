# -*- coding: utf-8 -*-
"""Versioned, renderer-neutral scientific chart data and publication figures."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Literal

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from pydantic import BaseModel, Field, model_validator

from src.research.repository import canonical_checksum

CHART_SCHEMA_VERSION = "scientific-chart-v1"
PALETTE = ("#216869", "#4D6CFA", "#B7673C", "#7251A3", "#008A8C", "#9A6A00")
STATUS_STYLE = {
    "observed": {"line": "-", "marker": "o"}, "derived": {"line": "-", "marker": "D"},
    "predicted": {"line": "--", "marker": "^"}, "agent_generated": {"line": ":", "marker": "*"},
    "human_reviewed": {"line": "-.", "marker": "s"},
}


def _configure_fonts() -> None:
    candidates = [
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    names = []
    for value in candidates:
        if os.path.exists(value):
            try:
                font_manager.fontManager.addfont(value)
                names.append(font_manager.FontProperties(fname=value).get_name())
            except (OSError, RuntimeError):
                pass
    plt.rcParams.update({
        "font.family": [*(names[:1] or []), "DejaVu Sans"],
        "font.sans-serif": [*names, "DejaVu Sans"], "axes.unicode_minus": False,
        "svg.fonttype": "path", "svg.hashsalt": "scientific-chart-v1", "pdf.fonttype": 42,
    })


_configure_fonts()


class ChartSeries(BaseModel):
    series_id: str
    label: str
    evidence_status: Literal["observed", "derived", "predicted", "agent_generated", "human_reviewed"]
    values: List[Dict[str, Any]]
    color: str = ""
    accessibility_label: str = ""


class ScientificChartData(BaseModel):
    schema_version: str = CHART_SCHEMA_VERSION
    figure_number: str
    chart_kind: Literal["network_small_multiples", "centrality_trajectory", "fusion_ranking",
                        "fusion_matrix", "community_evolution", "convergence_matrix", "validation_panel", "roadmap_swimlane"]
    title: str
    caption: str
    source_note: str
    sample_size: int = Field(ge=0)
    cutoff: str
    series: List[ChartSeries]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    checksum: str = ""

    @model_validator(mode="after")
    def seal(self):
        if not self.caption or not self.source_note or not self.cutoff:
            raise ValueError("科研图件必须包含图注、来源说明与数据截止")
        if not self.checksum:
            self.checksum = canonical_checksum(self.model_dump(exclude={"checksum"}))
        return self


class ScientificFigureRenderer:
    """Render the same chart contract to vector SVG and 600-DPI PNG."""

    def render(self, chart: ScientificChartData, output_dir: Path) -> Dict[str, Any]:
        output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
        stem = "%s-%s" % (chart.figure_number.replace(".", "-"), chart.chart_kind)
        fig, ax = plt.subplots(figsize=(10.5, 6.2), constrained_layout=True)
        self._draw(ax, chart)
        fig.suptitle("%s  %s" % (chart.figure_number, chart.title), fontsize=14, fontweight="bold")
        fig.text(.01, .005, "%s｜n=%d｜截止=%s｜校验=%s" % (
            chart.source_note, chart.sample_size, chart.cutoff, chart.checksum[:12]
        ), fontsize=7, color="#45545A")
        png, svg = output_dir / (stem + ".png"), output_dir / (stem + ".svg")
        metadata = {"Creator": "TechForecast scientific-chart-v1", "Date": "2025-10-01"}
        fig.savefig(png, dpi=600, facecolor="white", metadata=metadata)
        fig.savefig(svg, format="svg", facecolor="white", metadata=metadata)
        plt.close(fig)
        sidecar = output_dir / (stem + ".json")
        sidecar.write_text(json.dumps(chart.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
        return {"png": str(png), "svg": str(svg), "chart_data": str(sidecar),
                "checksum": chart.checksum, "accessibility_description": chart.caption}

    def _draw(self, ax, chart):
        if chart.chart_kind in {"convergence_matrix", "fusion_matrix"}: self._matrix(ax, chart)
        elif chart.chart_kind == "roadmap_swimlane": self._roadmap(ax, chart)
        elif chart.chart_kind == "network_small_multiples": self._network(ax, chart)
        else: self._series(ax, chart)
        ax.set_title(chart.caption, fontsize=9, loc="left", color="#45545A", pad=10)

    @staticmethod
    def _series(ax, chart):
        for index, series in enumerate(chart.series):
            points = series.values
            x = [item.get("x", item.get("year", item.get("rank", i + 1))) for i, item in enumerate(points)]
            y = [item.get("y", item.get("value", item.get("score", 0))) for item in points]
            style, color = STATUS_STYLE[series.evidence_status], series.color or PALETTE[index % len(PALETTE)]
            ax.plot(x, y, style["line"], marker=style["marker"], linewidth=1.7,
                    markersize=4.5, color=color, label=series.label)
            lows, highs = [item.get("low") for item in points], [item.get("high") for item in points]
            if points and all(value is not None for value in lows + highs): ax.fill_between(x, lows, highs, alpha=.14, color=color)
        ax.grid(axis="y", color="#DDE4E3", linewidth=.7); ax.legend(frameon=False, fontsize=8)

    @staticmethod
    def _network(ax, chart):
        for index, series in enumerate(chart.series):
            color, style = series.color or PALETTE[index % len(PALETTE)], STATUS_STYLE[series.evidence_status]
            offset = index * 3.0
            nodes = {}
            for edge in series.values:
                ax.plot([edge["x1"] + offset, edge["x2"] + offset], [edge["y1"], edge["y2"]], linestyle=style["line"],
                        color=color, alpha=.55, linewidth=max(.5, edge.get("weight", 1)))
                nodes[edge.get("ipc1", "")] = (edge["x1"] + offset, edge["y1"], edge.get("community1", ""))
                nodes[edge.get("ipc2", "")] = (edge["x2"] + offset, edge["y2"], edge.get("community2", ""))
            for code, (x, y, community) in nodes.items():
                node_color = PALETTE[int(canonical_checksum(community)[:8], 16) % len(PALETTE)] if community else color
                ax.scatter([x], [y], s=18, color=node_color, edgecolor="white", linewidth=.35, zorder=3)
                if len(nodes) <= 20: ax.text(x, y + .05, code, fontsize=5.5, ha="center")
            ax.text(offset, 1.25, series.label, ha="center", fontsize=9, fontweight="bold")
            if index < len(chart.series) - 1: ax.axvline(offset + 1.5, color="#DDE4E3", linewidth=.7)
        ax.set_aspect("equal"); ax.set_xlim(-1.5, max(1.5, (len(chart.series) - 1) * 3 + 1.5)); ax.set_ylim(-1.35, 1.4); ax.axis("off")

    @staticmethod
    def _matrix(ax, chart):
        rows = chart.series[0].values if chart.series else []
        matrix = [item.get("values", []) for item in rows]
        image = ax.imshow(matrix or [[0]], cmap="BrBG", vmin=-1, vmax=1, aspect="auto")
        ax.set_yticks(range(len(rows)), [item.get("label", "") for item in rows])
        if rows: ax.set_xticks(range(len(rows[0].get("values", []))), chart.metadata.get("columns", []))
        plt.colorbar(image, ax=ax, label="方向一致性（-1 冲突，+1 收敛）")

    @staticmethod
    def _roadmap(ax, chart):
        for lane, series in enumerate(chart.series):
            color = series.color or PALETTE[lane % len(PALETTE)]
            for item in series.values:
                start, end = int(item["start"]), int(item["end"])
                uncertainty = item.get("uncertainty", "medium")
                alpha = {"low": .85, "medium": .62, "high": .38}.get(uncertainty, .48)
                hatch = "///" if uncertainty == "high" else "" 
                ax.barh(lane, end - start, left=start, height=.42, color=color, alpha=alpha, hatch=hatch)
                ax.text(start + .15, lane, "%s · TRL%s · U:%s" % (item["label"], item.get("trl", "?"), uncertainty), va="center", fontsize=7)
        ax.set_yticks(range(len(chart.series)), [item.label for item in chart.series])
        ax.set_xticks([2025, 2030, 2035, 2040]); ax.set_xlim(2025, 2041); ax.grid(axis="x", color="#DDE4E3", linewidth=.7)


def visual_accessibility_audit(chart: ScientificChartData) -> Dict[str, Any]:
    statuses = {series.evidence_status for series in chart.series}
    encodings = {(STATUS_STYLE[state]["line"], STATUS_STYLE[state]["marker"]) for state in statuses}
    warnings = []
    if len(encodings) != len(statuses): warnings.append("证据状态的非颜色编码发生冲突")
    if not all(series.label and (series.accessibility_label or chart.caption) for series in chart.series):
        warnings.append("序列缺少可访问文本")
    labels = [series.label for series in chart.series]
    if len(labels) != len(set(labels)): warnings.append("图例标签重叠")
    return {"passed": not warnings, "warnings": warnings, "status_not_color_only": len(encodings) == len(statuses),
            "grayscale_compatible": len(encodings) == len(statuses)}
