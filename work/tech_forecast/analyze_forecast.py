from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import numpy as np
from openpyxl import load_workbook
from PIL import Image


ROOT = Path(__file__).resolve().parent
INPUTS = ROOT / "inputs"
EXTRACTED = ROOT / "extracted"
FIGURES = ROOT / "figures"
OUTPUT = ROOT / "output"
FIGURES.mkdir(parents=True, exist_ok=True)
OUTPUT.mkdir(parents=True, exist_ok=True)

FONT_PATH = "/System/Library/Fonts/Hiragino Sans GB.ttc"
ZH_FONT = FontProperties(fname=FONT_PATH)
ZH_BOLD = FontProperties(fname=FONT_PATH, weight="bold")

TOPICS = {
    "T1": "多专业协同平台",
    "T2": "参数化与生成式设计",
    "T3": "机器人集群协同",
    "T4": "施工全过程数字孪生",
    "T5": "智能规范审查",
    "T6": "建筑工程大模型",
    "T7": "装配式建筑",
    "T8": "建筑规模增材制造",
    "T9": "模块化与可重构设计",
}

LABEL_MAP = {
    "T1": {"BIM", "大数据", "工程软件", "区块链", "智慧工地"},
    "T2": {"参数化设计", "生成式设计", "数字化设计", "智能设计"},
    "T3": {"机器人", "架桥机", "塔吊", "智能施工"},
    "T4": {"盾构机", "工程仿真模拟", "施工监测", "数字孪生"},
    "T6": {"大模型", "自然语言处理"},
    "T7": {"装配式建筑"},
    "T8": {"3D打印"},
}

REGEX_MAP = {
    "T5": re.compile(r"规范.{0,8}(审查|审核|校核)|审图|合规.{0,6}(审查|校核)|施工图.{0,8}(审查|审核)|自动审查|智能审查"),
    "T9": re.compile(r"模块化|可重构|重构设计|模块组合|模块拼装|模块拆装|可拆卸.{0,8}(建筑|构件|结构)"),
}

IPC_MAP = {
    "T1": ["G06F30", "G06Q50", "G16Y10", "H04W4", "H04L29"],
    "T2": ["G06F30", "G06N3"],
    "T3": ["B25J11", "B66C23", "G05D1", "B62D57"],
    "T4": ["G06F30", "G06N3", "G01B11", "G01S17", "E02D33", "G08B21"],
    "T5": ["G06F30", "G06N3", "G06Q50"],
    "T6": ["G06N3", "G06F30"],
    "T7": ["E04B1", "E04B2", "E04C3"],
    "T8": ["B33Y70", "B28B1", "C04B28", "B28C7"],
    "T9": ["E04B1", "E04B2", "E04C3", "G06F30"],
}

CONVERGENCE = {
    "T1": 0.62,
    "T2": 0.88,
    "T3": 0.91,
    "T4": 0.93,
    "T5": 0.86,
    "T6": 0.90,
    "T7": 0.78,
    "T8": 0.56,
    "T9": 0.82,
}

COVERAGE = {
    "T1": "高",
    "T2": "高",
    "T3": "高",
    "T4": "高",
    "T5": "中（基于审查/规范词项代理）",
    "T6": "中（大模型样本起步较晚）",
    "T7": "高",
    "T8": "高",
    "T9": "低（基于模块化/可重构词项代理）",
}


def parse_year(value) -> int | None:
    if isinstance(value, datetime):
        return value.year
    if value is None:
        return None
    match = re.match(r"(\d{4})", str(value))
    return int(match.group(1)) if match else None


def load_patents() -> list[dict]:
    wb = load_workbook(INPUTS / "topic_times.xlsx", read_only=True, data_only=True)
    ws = wb["Sheet1"]
    records = []
    current_label = None
    current_stage = None
    for row_no, row in enumerate(ws.iter_rows(min_row=2, max_col=6, values_only=True), start=2):
        serial, title, abstract, applied, ipc, label = row
        if row_no == 126:
            current_stage = 2
            current_label = None
        elif row_no == 1711:
            current_stage = 3
            current_label = None
        if label:
            current_label = str(label).strip()
        if current_stage not in (2, 3):
            continue
        year = parse_year(applied)
        if not title or not year or not current_label:
            continue
        records.append(
            {
                "row": row_no,
                "stage": current_stage,
                "serial": serial,
                "title": str(title).strip(),
                "abstract": str(abstract or "").strip(),
                "year": year,
                "ipc": str(ipc or "").strip(),
                "label": current_label,
            }
        )
    return records


def patent_key(record: dict) -> tuple:
    return (record["title"], record["year"])


def build_topic_counts(records: list[dict]) -> tuple[dict, dict]:
    topic_records: dict[str, dict[tuple, dict]] = {t: {} for t in TOPICS}
    for record in records:
        key = patent_key(record)
        text = record["title"] + " " + record["abstract"]
        for topic, labels in LABEL_MAP.items():
            if record["label"] in labels:
                topic_records[topic][key] = record
        for topic, pattern in REGEX_MAP.items():
            if pattern.search(text):
                topic_records[topic][key] = record

    counts = {t: {y: 0 for y in range(2015, 2026)} for t in TOPICS}
    for topic, keyed in topic_records.items():
        for record in keyed.values():
            if record["year"] in counts[topic]:
                counts[topic][record["year"]] += 1
    return counts, topic_records


def parse_ipc_metrics() -> dict[int, dict[str, dict[str, float]]]:
    data = json.loads((EXTRACTED / "ipc_network.json").read_text(encoding="utf-8"))
    stages: dict[int, dict[str, dict[str, float]]] = {1: {}, 2: {}, 3: {}}
    stage = None
    for p in data["paragraphs"]:
        text = p["text"].strip()
        if "阶段1IPC" in text:
            stage = 1
            continue
        if "阶段2IPC" in text:
            stage = 2
            continue
        if "阶段3IPC" in text:
            stage = 3
            continue
        if stage is None or text.startswith("Degree"):
            continue
        parts = [x.strip() for x in text.split(",")]
        if len(parts) != 6 or not re.fullmatch(r"[A-Z]\d{2}[A-Z]?\d+", parts[0]):
            continue
        try:
            stages[stage][parts[0]] = {
                "degree": float(parts[1]),
                "betweenness": float(parts[2]),
                "closeness": float(parts[3]),
                "eigenvector": float(parts[4]),
                "eccentricity": float(parts[5]),
            }
        except ValueError:
            continue
    return stages


def percentile(values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(values.items(), key=lambda x: x[1])
    n = len(ordered)
    if n <= 1:
        return {k: 0.5 for k in values}
    return {k: i / (n - 1) for i, (k, _) in enumerate(ordered)}


def network_node_scores(stages: dict) -> dict[str, dict]:
    s2, s3 = stages[2], stages[3]
    deg_pct = percentile({k: v["degree"] for k, v in s3.items()})
    bet_pct = percentile({k: v["betweenness"] for k, v in s3.items()})
    clo_pct = percentile({k: v["closeness"] for k, v in s3.items()})
    common = set(s2) & set(s3)
    delta = {
        k: (s3[k]["degree"] - s2[k]["degree"]) + 0.7 * (s3[k]["betweenness"] - s2[k]["betweenness"])
        for k in common
    }
    delta_pct = percentile(delta)
    out = {}
    for k, v in s3.items():
        structural = 0.40 * deg_pct[k] + 0.35 * bet_pct[k] + 0.25 * clo_pct[k]
        transition = delta_pct.get(k, 0.55)
        out[k] = {
            **v,
            "stage2_degree": s2.get(k, {}).get("degree"),
            "stage2_betweenness": s2.get(k, {}).get("betweenness"),
            "structural": structural,
            "transition": transition,
            "network_score": 0.60 * structural + 0.40 * transition,
        }
    return out


def weighted_log_slope(counts: dict[int, int], start=2018, end=2024) -> tuple[float, float, float]:
    years = np.arange(start, end + 1, dtype=float)
    vals = np.array([counts.get(int(y), 0) for y in years], dtype=float)
    x = years - years.mean()
    y = np.log1p(vals)
    weights = np.array([0.72 ** (end - int(year)) for year in years], dtype=float)
    X = np.column_stack([np.ones_like(x), x])
    beta = np.linalg.solve(X.T @ (weights[:, None] * X), X.T @ (weights * y))
    fitted = X @ beta
    resid = y - fitted
    slope = float(np.clip(beta[1], -0.15, 0.25))
    rmse = float(np.sqrt(np.average(resid**2, weights=weights)))
    return slope, float(beta[0]), rmse


def project_counts(counts: dict[int, int], slope: float, rmse: float) -> dict[int, dict[str, int]]:
    base = max(counts.get(2024, 0), 1)
    out = {}
    for year in (2025, 2026, 2027, 2030, 2035, 2040):
        horizon = year - 2024
        # Damp extrapolation: each additional year contributes 88% of the previous year's log-growth.
        effective_horizon = sum(0.88**i for i in range(horizon))
        median = base * math.exp(slope * effective_horizon)
        spread = 1.282 * max(rmse, 0.20) * math.sqrt(1 + horizon / 4)
        out[year] = {
            "median": int(round(median)),
            "low80": max(0, int(round(median * math.exp(-spread)))),
            "high80": int(round(median * math.exp(spread))),
        }
    return out


def minmax(values: dict[str, float]) -> dict[str, float]:
    lo, hi = min(values.values()), max(values.values())
    if math.isclose(lo, hi):
        return {k: 0.5 for k in values}
    return {k: (v - lo) / (hi - lo) for k, v in values.items()}


def score_topics(counts: dict, node_scores: dict) -> dict[str, dict]:
    slopes, volumes, networks = {}, {}, {}
    aux = {}
    for topic in TOPICS:
        slope, intercept, rmse = weighted_log_slope(counts[topic])
        slopes[topic] = slope
        volumes[topic] = math.log1p(sum(counts[topic][y] for y in range(2021, 2025)))
        candidate_scores = [node_scores[c]["network_score"] for c in IPC_MAP[topic] if c in node_scores]
        networks[topic] = float(np.mean(sorted(candidate_scores, reverse=True)[:3])) if candidate_scores else 0.35
        aux[topic] = {"slope": slope, "intercept": intercept, "rmse": rmse}
    momentum_n = minmax(slopes)
    intensity_n = minmax(volumes)
    network_n = minmax(networks)
    result = {}
    for topic in TOPICS:
        balanced = (
            0.30 * momentum_n[topic]
            + 0.20 * intensity_n[topic]
            + 0.35 * network_n[topic]
            + 0.15 * CONVERGENCE[topic]
        )
        market = 0.38 * momentum_n[topic] + 0.34 * intensity_n[topic] + 0.18 * network_n[topic] + 0.10 * CONVERGENCE[topic]
        structural = 0.18 * momentum_n[topic] + 0.14 * intensity_n[topic] + 0.48 * network_n[topic] + 0.20 * CONVERGENCE[topic]
        result[topic] = {
            "topic_name": TOPICS[topic],
            "recent_count_2021_2024": sum(counts[topic][y] for y in range(2021, 2025)),
            "log_growth_slope": slopes[topic],
            "annualized_signal_growth": math.exp(slopes[topic]) - 1,
            "momentum_norm": momentum_n[topic],
            "intensity_norm": intensity_n[topic],
            "network_raw": networks[topic],
            "network_norm": network_n[topic],
            "convergence": CONVERGENCE[topic],
            "balanced_score": 100 * balanced,
            "market_score": 100 * market,
            "structural_score": 100 * structural,
            "scenario_rank_range": None,
            "coverage_confidence": COVERAGE[topic],
            "projection": project_counts(counts[topic], slopes[topic], aux[topic]["rmse"]),
        }
    for scenario in ("balanced_score", "market_score", "structural_score"):
        order = sorted(result, key=lambda t: result[t][scenario], reverse=True)
        for rank, topic in enumerate(order, start=1):
            result[topic].setdefault("scenario_ranks", {})[scenario] = rank
    for topic in result:
        ranks = list(result[topic]["scenario_ranks"].values())
        result[topic]["scenario_rank_range"] = [min(ranks), max(ranks)]
        result[topic]["activity_2021_2026"] = (
            result[topic]["recent_count_2021_2024"]
            + result[topic]["projection"][2025]["median"]
            + result[topic]["projection"][2026]["median"]
        )
    return result


def write_tables(records, counts, stages, node_scores, scores) -> None:
    unique_records = {patent_key(r) for r in records}
    audit = {
        "xlsx_rows_excluding_header": 5913,
        "manuscript_reported_patents": 5926,
        "difference": 13,
        "analyzed_labeled_records_2015_2025": len(records),
        "unique_patents_in_labeled_records": len(unique_records),
        "latest_year_partial": 2025,
        "latest_data_cutoff_from_manuscript": "2025-10-01",
        "trend_fit_years": "2018-2024",
        "evidence_horizon": "2026 (2025 full-year and 2026 are model estimates, not observations)",
        "notes": [
            "2025 is treated as right-censored and excluded from trend fitting.",
            "The 2025 full-year nowcast and 2026 forecast are model-derived evidence extensions with 80% exploratory intervals.",
            "Topic 5 and Topic 9 use transparent keyword proxies because the workbook has no dedicated labels for these BERTopic topics.",
            "Counts are patent activity signals, not de-duplicated global patent-family counts.",
        ],
    }
    (OUTPUT / "data_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    with (OUTPUT / "theme_annual_counts.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["topic_id", "topic_name"] + list(range(2015, 2026)))
        for topic in TOPICS:
            writer.writerow([topic, TOPICS[topic]] + [counts[topic][y] for y in range(2015, 2026)])

    with (OUTPUT / "theme_evidence_to_2026.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "topic_id", "topic_name", "observed_2024", "partial_observed_2025",
            "estimated_2025_median", "estimated_2025_low80", "estimated_2025_high80",
            "forecast_2026_median", "forecast_2026_low80", "forecast_2026_high80",
        ])
        for topic in TOPICS:
            p25 = scores[topic]["projection"][2025]
            p26 = scores[topic]["projection"][2026]
            writer.writerow([
                topic, TOPICS[topic], counts[topic][2024], counts[topic][2025],
                p25["median"], p25["low80"], p25["high80"],
                p26["median"], p26["low80"], p26["high80"],
            ])

    with (OUTPUT / "theme_scores.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        fields = [
            "topic_id", "topic_name", "recent_count_2021_2024", "annualized_signal_growth",
            "network_raw", "convergence", "balanced_score", "market_score", "structural_score",
            "scenario_rank_min", "scenario_rank_max", "coverage_confidence",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for topic in sorted(scores, key=lambda t: scores[t]["balanced_score"], reverse=True):
            s = scores[topic]
            writer.writerow({
                "topic_id": topic,
                "topic_name": s["topic_name"],
                "recent_count_2021_2024": s["recent_count_2021_2024"],
                "annualized_signal_growth": round(s["annualized_signal_growth"], 4),
                "network_raw": round(s["network_raw"], 4),
                "convergence": s["convergence"],
                "balanced_score": round(s["balanced_score"], 2),
                "market_score": round(s["market_score"], 2),
                "structural_score": round(s["structural_score"], 2),
                "scenario_rank_min": s["scenario_rank_range"][0],
                "scenario_rank_max": s["scenario_rank_range"][1],
                "coverage_confidence": s["coverage_confidence"],
            })

    with (OUTPUT / "ipc_stage_metrics.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        fields = ["ipc", "stage", "degree", "betweenness", "closeness", "eigenvector", "eccentricity"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for stage in (1, 2, 3):
            for ipc, metrics in stages[stage].items():
                writer.writerow({"ipc": ipc, "stage": stage, **metrics})

    (OUTPUT / "forecast_results.json").write_text(
        json.dumps({"topics": scores, "network_nodes": node_scores}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def style_axes(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#D8DEE9", lw=0.6, alpha=0.8)
    ax.tick_params(labelsize=8, colors="#334155")


def save_figure(fig, stem: str, width_mm: float, height_mm: float) -> None:
    fig.set_size_inches(width_mm / 25.4, height_mm / 25.4)
    fig.savefig(FIGURES / f"{stem}.png", dpi=600, facecolor="white")
    fig.savefig(FIGURES / f"{stem}.pdf", facecolor="white")
    fig.savefig(FIGURES / f"{stem}.svg", facecolor="white")
    plt.close(fig)
    # Normalize the raster deliverable to opaque RGB while retaining physical DPI metadata.
    png_path = FIGURES / f"{stem}.png"
    with Image.open(png_path) as image:
        image.convert("RGB").save(png_path, dpi=(600, 600))


def plot_evidence(counts, stages, node_scores, scores) -> None:
    colors = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#000000", "#7A5195", "#6B7280"]
    fig = plt.figure()
    ax1_header = fig.add_axes([0.105, 0.825, 0.86, 0.09])
    ax1 = fig.add_axes([0.105, 0.48, 0.86, 0.33])
    ax2 = fig.add_axes([0.105, 0.115, 0.355, 0.275])
    ax3 = fig.add_axes([0.61, 0.115, 0.355, 0.275])
    ax1_header.set_axis_off()

    years = np.arange(2015, 2025)
    for (topic, name), color in zip(TOPICS.items(), colors):
        vals = np.array([counts[topic][int(y)] for y in years], dtype=float)
        transformed = np.log1p(vals)
        ax1.plot(years, transformed, lw=1.5, marker="o", ms=2.8, color=color, label=f"{topic} {name}")
        # 2025 is a right-censored observation; 2025 full-year and 2026 are model estimates.
        est_years = np.array([2024, 2025, 2026])
        est_medians = np.array([
            counts[topic][2024],
            scores[topic]["projection"][2025]["median"],
            scores[topic]["projection"][2026]["median"],
        ], dtype=float)
        low_2026 = np.log1p(scores[topic]["projection"][2026]["low80"])
        high_2026 = np.log1p(scores[topic]["projection"][2026]["high80"])
        ax1.plot(est_years, np.log1p(est_medians), lw=1.15, ls="-", marker="o", mfc=color, ms=3.0, color=color)
        ax1.vlines(2026, low_2026, high_2026, color=color, lw=0.8, alpha=0.65)
    ax1.axvspan(2021, 2024.2, color="#F1F5F9", zorder=-2)
    ax1.set_ylabel("ln（年度专利记录数 + 1）", fontproperties=ZH_FONT, fontsize=9)
    ax1.set_xlabel("申请年份", fontproperties=ZH_FONT, fontsize=9)
    ax1.set_xticks(np.arange(2015, 2027))
    ax1.set_xlim(2014.7, 2026.35)
    handles, labels = ax1.get_legend_handles_labels()
    ax1_header.text(0.0, 0.98, "A  九大主题年度专利活动（2015—2026）", transform=ax1_header.transAxes, ha="left", va="top", fontproperties=ZH_BOLD, fontsize=10, color="#0F172A")
    ax1_header.legend(
        handles,
        labels,
        prop=FontProperties(fname=FONT_PATH, size=6.7),
        ncol=3,
        frameon=False,
        mode="expand",
        loc="lower left",
        bbox_to_anchor=(0.0, 0.0, 0.88, 0.70),
        borderaxespad=0.0,
        handlelength=2.2,
        columnspacing=1.0,
    )
    style_axes(ax1)

    selected = ["B33Y70", "B25J11", "G06F30", "G06N3", "G01B11", "G01S17"]
    for i, ipc in enumerate(selected):
        pts = []
        for stage in (1, 2, 3):
            if ipc in stages[stage]:
                pts.append((stages[stage][ipc]["degree"], stages[stage][ipc]["betweenness"], stage))
        if not pts:
            continue
        xs, ys, ss = zip(*pts)
        ax2.plot(xs, ys, "-o", lw=1.3, ms=4, color=colors[i])
        ax2.annotate(ipc, (xs[-1], ys[-1]), xytext=(3, 2), textcoords="offset points", fontsize=7, color=colors[i])
        for x, y, s in pts:
            ax2.annotate(str(s), (x, y), ha="center", va="center", fontsize=5.5, color="white", weight="bold")
    ax2.set_xlabel("度中心度", fontproperties=ZH_FONT, fontsize=9)
    ax2.set_ylabel("中介中心度", fontproperties=ZH_FONT, fontsize=9)
    ax2.set_title("B  关键IPC节点的阶段迁移轨迹", loc="left", fontproperties=ZH_BOLD, fontsize=8.5)
    ax2.set_xlim(-0.01, 0.24)
    style_axes(ax2)

    order = sorted(TOPICS, key=lambda t: scores[t]["balanced_score"], reverse=True)
    label_offsets = {
        "T1": (-24, -17), "T2": (-8, 22), "T3": (0, -16), "T4": (-30, 18),
        "T5": (18, -14), "T6": (16, -23), "T7": (0, 13), "T8": (14, 0), "T9": (0, 15),
    }
    topic_colors = dict(zip(TOPICS, colors))
    for topic in order:
        color = topic_colors[topic]
        s = scores[topic]
        size = 0.12 * s["activity_2021_2026"]
        ax3.scatter(s["network_norm"], s["momentum_norm"], s=size, color=color, alpha=0.82, edgecolor="white", linewidth=0.7)
        dx, dy = label_offsets[topic]
        ax3.annotate(
            topic,
            (s["network_norm"], s["momentum_norm"]),
            xytext=(dx, dy),
            textcoords="offset points",
            ha="center",
            va="center",
            fontsize=7,
            color="#0F172A",
            weight="bold",
            bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.82),
        )
    ax3.axvline(0.5, color="#94A3B8", lw=0.8, ls="--")
    ax3.axhline(0.5, color="#94A3B8", lw=0.8, ls="--")
    ax3.set_xlim(-0.08, 1.18)
    ax3.set_ylim(-0.08, 1.25)
    ax3.set_xlabel("网络结构跃迁（归一化）", fontproperties=ZH_FONT, fontsize=9)
    ax3.set_ylabel("主题时序动量（归一化）", fontproperties=ZH_FONT, fontsize=9)
    ax3.set_title("C  多源证据融合优先级矩阵", loc="left", fontproperties=ZH_BOLD, fontsize=8.5)
    style_axes(ax3)

    for count in (100, 500, 1500):
        ax3.scatter([], [], s=0.12 * count, facecolor="#CBD5E1", edgecolor="#64748B", label=f"{count}")
    ax3.legend(title="2021–2026", fontsize=5.5, title_fontsize=6, loc="upper left", frameon=True, facecolor="white", framealpha=1, labelspacing=1.0)
    fig.suptitle("智能建造关键技术预测的证据融合结果", y=0.97, fontproperties=ZH_BOLD, fontsize=11, color="#0F172A")
    fig.text(0.01, 0.012, "注：A中2015–2024为观测，2025全年与2026为模型补充；2026竖线为80%探索性区间。B阶段1/2/3分别为2010–2014/2015–2020/2021–2025。\nC的气泡面积正比于2021–2026累计活动量（含模型补充）；横纵坐标仍据历史证据计算。主题间可能重叠，不宜相加为独立专利总数。", fontproperties=ZH_FONT, fontsize=6.15, color="#475569", linespacing=1.2)
    save_figure(fig, "figure_1_evidence_fusion", 180, 164)


def plot_roadmap(scores) -> None:
    fig = plt.figure()
    ax = fig.add_axes([0.235, 0.25, 0.74, 0.66])
    ax.set_xlim(2026.7, 2040.4)
    ax.set_ylim(-0.9, 9.9)
    ax.set_xticks(range(2027, 2041))
    ax.set_yticks([])
    ax.grid(axis="x", color="#E2E8F0", lw=0.5, zorder=-2)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.axvspan(2027, 2030.99, color="#EFF6FF", zorder=-3)
    ax.axvspan(2031, 2035.99, color="#F0FDF4", zorder=-3)
    ax.axvspan(2036, 2040.4, color="#FFF7ED", zorder=-3)
    ax.text(2029.0, 9.55, "奠基期（2027–2030）\n接口统一与项目级闭环", ha="center", va="center", fontproperties=ZH_BOLD, fontsize=8.3, color="#1D4ED8")
    ax.text(2033.5, 9.55, "扩展期（2031–2035）\n系统闭环与跨项目复制", ha="center", va="center", fontproperties=ZH_BOLD, fontsize=8.3, color="#15803D")
    ax.text(2038.0, 9.55, "转型期（2036–2040）\n受控自治与循环建造", ha="center", va="center", fontproperties=ZH_BOLD, fontsize=8.3, color="#C2410C")

    lanes = [
        (8.5, "T1 多专业协同平台", [(2027, 2031, "openBIM/CDE\n跨角色工作流"), (2031, 2036, "可信工程数据空间\n数字线程与跨项目复用"), (2036, 2040.2, "跨组织知识网络\n自治数据治理")], "#0072B2"),
        (7.55, "T6 建筑工程大模型", [(2027, 2031, "领域RAG/知识图谱\n受约束助手"), (2031, 2036, "多模态任务生成\n工具调用与可追溯执行"), (2036, 2040.2, "经验证智能体编排\n安全边界内自治")], "#CC79A7"),
        (6.60, "T5 智能规范审查", [(2027, 2031, "条款机器可读\n规则+模型双路径"), (2031, 2036, "多模态审查\n可追溯人机共审"), (2036, 2040.2, "设计—施工—运维\n持续合规")], "#6B7280"),
        (5.65, "T2 参数化与生成式设计", [(2027, 2031, "约束驱动生成\n多目标优化"), (2031, 2036, "DfMA模块库\n审查反馈闭环"), (2036, 2040.2, "全寿命/循环约束\n自适应设计")], "#D55E00"),
        (4.70, "T9 模块化与可重构设计", [(2027, 2031, "标准接口\n可重构原型"), (2031, 2036, "自动构型\n快速装拆"), (2036, 2040.2, "全寿命重构\n适应性空间")], "#7A5195"),
        (3.75, "T4 施工全过程数字孪生", [(2027, 2031, "感知—模型同步\n项目级控制闭环"), (2031, 2036, "质量/安全/进度\n预测性控制"), (2036, 2040.2, "项目群—资产连续孪生\n资源协同优化")], "#009E73"),
        (2.80, "T3 机器人集群协同", [(2027, 2031, "接口互操作\n高危工序多机试点"), (2031, 2036, "异构集群调度\n孪生驱动重规划"), (2036, 2040.2, "人机混编\n受控自治施工单元")], "#E69F00"),
        (1.85, "T7 装配式建筑", [(2027, 2031, "柔性制造\n构件全链追溯"), (2031, 2036, "机器人装配\n供应链协同"), (2036, 2040.2, "规模化定制\n拆解复用与循环建造")], "#56B4E9"),
        (0.90, "T8 建筑规模增材制造", [(2027, 2031, "材料—工艺—结构\n性能验证"), (2031, 2036, "搅拌—配送—打印\n质量闭环"), (2036, 2040.2, "增材×装配混合\n低碳制造")], "#A65E2E"),
    ]
    ax.set_yticks([lane[0] for lane in lanes])
    ax.set_yticklabels([lane[1] for lane in lanes], fontproperties=ZH_BOLD, fontsize=7.2, color="#0F172A")
    ax.tick_params(axis="y", length=0, pad=7)
    for y, label, bars, color in lanes:
        for start, end, text_label in bars:
            ax.barh(y, end - start - 0.24, left=start + 0.12, height=0.67, color=color, alpha=0.12, edgecolor=color, linewidth=0.6, zorder=2)
            ax.text((start + end) / 2, y, text_label, ha="center", va="center", fontproperties=ZH_FONT, fontsize=6.1, color="#172B40", linespacing=1.25, zorder=3)
    # Dependency arrows for the dominant evidence-supported chain.
    arrows = [
        ((2029.8, 8.5), (2030.2, 7.55)),   # T1 -> T6
        ((2029.2, 8.5), (2029.6, 6.60)),   # T1 -> T5
        ((2030.0, 8.5), (2030.4, 3.75)),   # T1 -> T4
        ((2033.0, 7.55), (2033.4, 5.65)),  # T6 -> T2
        ((2033.4, 7.55), (2033.8, 2.80)),  # T6 -> T3
        ((2034.4, 3.75), (2034.8, 2.80)),  # T4 -> T3
        ((2037.0, 5.65), (2037.4, 4.70)),  # T2 -> T9
        ((2037.8, 4.70), (2038.2, 1.85)),  # T9 -> T7
        ((2038.0, 5.65), (2038.4, 0.90)),  # T2 -> T8
    ]
    # Dependencies are shown separately to avoid crossing milestone text.
    dependency_groups = [
        (0.06, "数据支撑", "T1 → T6 / T5 / T4\n平台支撑推理、审查与孪生"),
        (0.38, "智能与控制", "T6 → T2 / T3；T4 → T3\n推理与现场状态支撑设计和调度"),
        (0.70, "设计与制造", "T2 → T9 / T8；T9 → T7\n设计与模块接口支撑制造和装配"),
    ]
    for x, heading, explanation in dependency_groups:
        fig.text(x, 0.158, heading, fontproperties=ZH_BOLD, fontsize=8, color="#183B56")
        fig.text(x, 0.145, explanation, va="top", fontproperties=ZH_FONT, fontsize=6.8, color="#334155", linespacing=1.6)

    ax.text(2033.5, -0.12, "跨主题约束：开放标准 · 数据权属 · 模型验证 · 网络安全 · 人机责任边界 · 全寿命碳核算", ha="center", va="center", fontproperties=ZH_BOLD, fontsize=6.2, color="#334155", bbox=dict(boxstyle="round,pad=0.3", fc="#F8FAFC", ec="#CBD5E1", lw=0.6))
    fig.suptitle("智能建造九大主题技术发展路线图（2027—2040）", y=0.97, fontproperties=ZH_BOLD, fontsize=12, color="#0F172A")
    ax.set_xlabel("目标时间窗口（预测性路线，非确定性承诺）", fontproperties=ZH_FONT, fontsize=8.5)
    ax.tick_params(axis="x", labelsize=7.5, colors="#334155")
    fig.text(0.06, 0.045, "关系说明：A → B 表示A为B提供数据、能力或接口支撑；属于路线规划假设，非已验证因果关系。\n依据：九主题、历史专利活动与IPC迁移；2025完整年及2026为模型估计。阶段时间窗需滚动更新。", fontproperties=ZH_FONT, fontsize=6.1, color="#475569", linespacing=1.5)
    save_figure(fig, "figure_2_technology_roadmap", 210, 190)


def main() -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "axes.unicode_minus": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "savefig.transparent": False,
    })
    records = load_patents()
    counts, topic_records = build_topic_counts(records)
    stages = parse_ipc_metrics()
    node_scores = network_node_scores(stages)
    scores = score_topics(counts, node_scores)
    write_tables(records, counts, stages, node_scores, scores)
    plot_evidence(counts, stages, node_scores, scores)
    plot_roadmap(scores)
    summary = {
        "records": len(records),
        "stage_counts": {s: sum(1 for r in records if r["stage"] == s) for s in (2, 3)},
        "network_nodes": {s: len(stages[s]) for s in (1, 2, 3)},
        "ranking": [
            {
                "topic": t,
                "name": scores[t]["topic_name"],
                "score": round(scores[t]["balanced_score"], 2),
                "rank_range": scores[t]["scenario_rank_range"],
                "growth": round(scores[t]["annualized_signal_growth"], 3),
                "recent": scores[t]["recent_count_2021_2024"],
            }
            for t in sorted(scores, key=lambda x: scores[x]["balanced_score"], reverse=True)
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
