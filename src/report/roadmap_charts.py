# -*- coding:utf-8 -*-
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".matplotlib"))

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
from cycler import cycler
import seaborn as sns
from config.settings import OUTPUTS_REPORT, PER_TOPIC_ROADMAP_STAGES
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _available_fonts() -> set:
    return {font.name for font in font_manager.fontManager.ttflist}


def _choose_font(candidates: List[str], fallback: str) -> str:
    available = _available_fonts()
    for name in candidates:
        if name in available:
            return name
    return fallback


LATIN_FONT = _choose_font(
    ['Times New Roman', 'Times', 'PT Serif', 'DejaVu Serif'],
    'DejaVu Serif',
)
CJK_FONT = _choose_font(
    ['Songti SC', 'Hiragino Sans GB', 'PingFang SC', 'Heiti TC', 'Arial Unicode MS'],
    'DejaVu Sans',
)
SANS_FONT = _choose_font(
    ['Arial', 'Helvetica', 'PT Sans', 'DejaVu Sans'],
    'DejaVu Sans',
)
FONT_STACK = [LATIN_FONT, CJK_FONT, 'DejaVu Sans']

try:
    import scienceplots  # noqa: F401
    plt.style.use(['science', 'no-latex', 'nature'])
except Exception as exc:  # pragma: no cover - visual enhancement fallback
    logger.debug("SciencePlots style unavailable, using local publication theme: %s", exc)

plt.rcParams.update({
    'font.family': FONT_STACK,
    'font.serif': [LATIN_FONT, CJK_FONT, 'DejaVu Serif'],
    'font.sans-serif': [SANS_FONT, CJK_FONT, 'DejaVu Sans'],
    'axes.unicode_minus': False,
    'figure.dpi': 300,
    'savefig.dpi': 600,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.12,
    'savefig.transparent': False,
    'axes.linewidth': 0.8,
    'axes.labelsize': 8.5,
    'axes.titlesize': 9.5,
    'xtick.labelsize': 7.5,
    'ytick.labelsize': 7.5,
    'legend.fontsize': 7,
    'lines.linewidth': 1.45,
    'patch.linewidth': 0.6,
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
})

PALETTE = sns.color_palette(['#3B6FB6', '#D58A3A', '#4F9A6A', '#8A5FBF'])
ACCENT_PALETTE = sns.color_palette(['#5E81AC', '#D08770', '#A3BE8C', '#B48EAD', '#88C0D0'])
plt.rcParams['axes.prop_cycle'] = cycler(color=ACCENT_PALETTE)

STAGE_COLORS = {
    '2025': PALETTE[0],
    '2026': PALETTE[0],
    '2030': PALETTE[1],
    '2035': PALETTE[2],
    '2040': PALETTE[3]
}


def _roadmap_stages(roadmap: Dict[str, Any]) -> List[str]:
    stages = sorted(
        (str(stage) for stage in roadmap if str(stage).isdigit()),
        key=int,
    )
    return stages or list(PER_TOPIC_ROADMAP_STAGES)

UNCERTAINTY_COLORS = {
    'low': '#5E9F61',
    'medium': '#D99A3D',
    'high': '#B65F5F'
}

TEXT_COLOR = '#222222'
AXIS_COLOR = '#4E545B'
GRID_COLOR = '#E5E7EB'
BG_COLOR = '#ffffff'
PANEL_BG = '#FBFBFA'


def _get_stage_color(stage: str, alpha: float = 1.0) -> Tuple[float, float, float, float]:
    color = STAGE_COLORS.get(stage, PALETTE[-1])
    if alpha == 1.0:
        return color
    return (*color, alpha)


def _get_uncertainty_color(level: str) -> str:
    return UNCERTAINTY_COLORS.get(level, UNCERTAINTY_COLORS['medium'])


def _is_chinese(text: str) -> bool:
    return any('\u4e00' <= char <= '\u9fff' for char in text)


def _get_text_font(text: str) -> dict:
    if _is_chinese(text):
        return {'family': [CJK_FONT, LATIN_FONT, SANS_FONT]}
    return {'family': [LATIN_FONT, CJK_FONT, SANS_FONT]}


def _font_family(text: str):
    return _get_text_font(text)['family']


def _shorten_text(text: str, max_chars: int = 18) -> str:
    text = str(text or '')
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 1] + '…'


def _panel_label(ax: plt.Axes, label: str, x: float = -0.16, y: float = 1.02) -> None:
    ax.text(x, y, label, fontsize=14, fontweight='bold', color='#111111',
            fontfamily=LATIN_FONT, transform=ax.transAxes, va='bottom', ha='left')


def _style_legend(legend) -> None:
    if legend is None:
        return
    legend.get_frame().set_facecolor('#FFFFFF')
    legend.get_frame().set_edgecolor('#D4D7DC')
    legend.get_frame().set_linewidth(0.6)
    legend.get_frame().set_alpha(0.92)


def _style_axes(ax: plt.Axes, hide_top_right: bool = True) -> None:
    ax.set_facecolor(PANEL_BG)
    if hide_top_right:
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color(AXIS_COLOR)
    ax.spines['left'].set_color(AXIS_COLOR)
    ax.spines['bottom'].set_linewidth(0.8)
    ax.spines['left'].set_linewidth(0.8)
    ax.tick_params(axis='both', colors=AXIS_COLOR, labelsize=8, width=0.75, length=3,
                   top=False, right=False)
    ax.grid(axis='y', linestyle='-', linewidth=0.45, color=GRID_COLOR, alpha=0.65)
    ax.set_axisbelow(True)


def generate_combined_topic_chart(roadmap_data: Dict[str, Any], output_path: str) -> str:
    topic_name = roadmap_data.get('topic_name', 'Technology Roadmap')
    roadmap = roadmap_data.get('roadmap', {})
    
    stages = _roadmap_stages(roadmap)
    
    fig = plt.figure(figsize=(11, 8), dpi=600)
    fig.patch.set_facecolor(BG_COLOR)
    
    gs = GridSpec(2, 3, figure=fig, wspace=0.35, hspace=0.3)
    
    ax_a = fig.add_subplot(gs[0, :2])
    ax_b = fig.add_subplot(gs[0, 2])
    ax_c = fig.add_subplot(gs[1, :2])
    ax_d = fig.add_subplot(gs[1, 2])
    
    x_indices = np.arange(len(stages))
    x_labels = [f'{s}' for s in stages]
    
    trl_means = []
    trl_mins = []
    trl_maxs = []
    ms_counts = []
    uncertainty_dist = {'low': [], 'medium': [], 'high': []}
    all_trls = []
    tech_counts = []
    
    for stage in stages:
        stage_data = roadmap.get(stage, {})
        milestones = stage_data.get('milestones', [])
        ms_counts.append(len(milestones))
        
        trls = [ms.get('trl_level', 0) for ms in milestones]
        if trls:
            trl_means.append(np.mean(trls))
            trl_mins.append(min(trls))
            trl_maxs.append(max(trls))
            all_trls.extend(trls)
        else:
            trl_means.append(0)
            trl_mins.append(0)
            trl_maxs.append(0)
        
        techs = set()
        low_count = 0
        med_count = 0
        high_count = 0
        for ms in milestones:
            for t in ms.get('key_technologies', []):
                techs.add(t)
            uc = ms.get('uncertainty_level', 'medium')
            if uc == 'low': low_count += 1
            elif uc == 'medium': med_count += 1
            else: high_count += 1
        tech_counts.append(len(techs))
        total_ms = len(milestones) or 1
        uncertainty_dist['low'].append(low_count / total_ms * 100)
        uncertainty_dist['medium'].append(med_count / total_ms * 100)
        uncertainty_dist['high'].append(high_count / total_ms * 100)
    
    ax_a.fill_between(x_indices, trl_mins, trl_maxs, alpha=0.12, color=PALETTE[0], edgecolor=None)
    ax_a.plot(x_indices, trl_means, '-o', color=PALETTE[0], linewidth=2.5,
              markersize=9, markerfacecolor='white', markeredgewidth=2.5,
              markeredgecolor=PALETTE[0], zorder=5)
    
    for i, stage in enumerate(stages):
        stage_data = roadmap.get(stage, {})
        milestones = stage_data.get('milestones', [])
        if milestones:
            jitter = np.linspace(-0.2, 0.2, len(milestones))
            for j, ms in enumerate(milestones):
                trl = ms.get('trl_level', 0)
                uc = ms.get('uncertainty_level', 'medium')
                uc_color = _get_uncertainty_color(uc)
                ax_a.scatter(i + jitter[j], trl, s=50, c=uc_color, edgecolors='white',
                            linewidths=1.2, alpha=0.85, zorder=4)
    
    ax_a.set_xticks(x_indices)
    ax_a.set_xticklabels(x_labels, fontsize=9, color=TEXT_COLOR, fontfamily=LATIN_FONT)
    ax_a.set_ylabel('TRL', fontsize=10, fontweight='bold', color=TEXT_COLOR,
                    fontfamily=LATIN_FONT, labelpad=8)
    ax_a.set_ylim(0, 10)
    ax_a.set_yticks(np.arange(0, 10, 2))
    ax_a.set_yticklabels([f'{i}' for i in range(0, 10, 2)], fontsize=8, color=AXIS_COLOR,
                         fontfamily=LATIN_FONT)
    _panel_label(ax_a, 'A')
    ax_a.set_title('TRL Development', fontsize=10, fontweight='bold',
                   color=TEXT_COLOR, fontfamily=LATIN_FONT, pad=8)
    _style_axes(ax_a)
    
    colors_pie = [_get_stage_color(s) for s in stages]
    wedges, texts, autotexts = ax_b.pie(
        ms_counts,
        colors=colors_pie,
        startangle=90,
        autopct='%1.0f%%',
        pctdistance=0.78,
        wedgeprops={'width': 0.42, 'edgecolor': 'white', 'linewidth': 1.2},
        textprops={'fontsize': 7, 'color': TEXT_COLOR, 'fontfamily': LATIN_FONT},
    )
    ax_b.text(0, 0, f'n={sum(ms_counts)}', ha='center', va='center', fontsize=9,
              color=AXIS_COLOR, fontfamily=LATIN_FONT)
    _style_legend(ax_b.legend(
        wedges,
        stages,
        loc='lower center',
        bbox_to_anchor=(0.5, -0.16),
        ncol=2,
        frameon=True,
        handlelength=1.0,
        columnspacing=0.8,
    ))
    for label in autotexts:
        label.set_fontfamily(LATIN_FONT)
    ax_b.set_title('Milestone\nDistribution', fontsize=10, fontweight='bold',
                   color=TEXT_COLOR, fontfamily=LATIN_FONT, pad=8)
    _panel_label(ax_b, 'B', x=-0.20)
    
    bar_width = 0.35
    x_bar = np.arange(len(stages))
    ax_c.bar(x_bar - bar_width/2, ms_counts, bar_width, label='Milestones',
             color=PALETTE[0], alpha=0.9)
    ax_c.bar(x_bar + bar_width/2, tech_counts, bar_width, label='Technologies',
             color=PALETTE[1], alpha=0.9)
    ax_c.set_xticks(x_bar)
    ax_c.set_xticklabels(x_labels, fontsize=9, color=TEXT_COLOR, fontfamily=LATIN_FONT)
    ax_c.set_ylabel('Count', fontsize=10, fontweight='bold', color=TEXT_COLOR,
                    fontfamily=LATIN_FONT, labelpad=8)
    _style_legend(ax_c.legend(fontsize=7, loc='upper left', frameon=True, framealpha=0.8))
    _panel_label(ax_c, 'C')
    ax_c.set_title('Content Analysis', fontsize=10, fontweight='bold',
                   color=TEXT_COLOR, fontfamily=LATIN_FONT, pad=8)
    _style_axes(ax_c)
    
    ax_d.bar(x_indices, uncertainty_dist['low'], label='Low',
             color=UNCERTAINTY_COLORS['low'], alpha=0.95)
    ax_d.bar(x_indices, uncertainty_dist['medium'], bottom=uncertainty_dist['low'],
             label='Medium', color=UNCERTAINTY_COLORS['medium'], alpha=0.95)
    high_bottom = [l + m for l, m in zip(uncertainty_dist['low'], uncertainty_dist['medium'])]
    ax_d.bar(x_indices, uncertainty_dist['high'], bottom=high_bottom,
             label='High', color=UNCERTAINTY_COLORS['high'], alpha=0.95)
    ax_d.set_xticks(x_indices)
    ax_d.set_xticklabels(x_labels, fontsize=9, color=TEXT_COLOR, fontfamily=LATIN_FONT)
    ax_d.set_ylabel('Percentage (%)', fontsize=10, fontweight='bold', color=TEXT_COLOR,
                    fontfamily=LATIN_FONT, labelpad=8)
    ax_d.set_ylim(0, 105)
    _style_legend(ax_d.legend(fontsize=7, loc='upper right', frameon=True, framealpha=0.8))
    _panel_label(ax_d, 'D', x=-0.20)
    ax_d.set_title('Uncertainty', fontsize=10, fontweight='bold',
                   color=TEXT_COLOR, fontfamily=LATIN_FONT, pad=8)
    _style_axes(ax_d)
    
    fig.suptitle(f'{topic_name}\nTechnology Roadmap Analysis', fontsize=13, fontweight='bold',
                 color=TEXT_COLOR, y=0.98, **_get_text_font(topic_name))
    
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.08, top=0.88, wspace=0.38, hspace=0.42)
    plt.savefig(output_path, facecolor=BG_COLOR, edgecolor='none', dpi=600)
    plt.close(fig)
    logger.info(f"Combined topic chart saved: {output_path}")
    return output_path


def generate_timeline_gantt(roadmap_data: Dict[str, Any], output_path: str) -> str:
    topic_name = roadmap_data.get('topic_name', 'Technology Roadmap')
    roadmap = roadmap_data.get('roadmap', {})
    
    stages = _roadmap_stages(roadmap)
    
    all_milestones = []
    for stage_idx, stage in enumerate(stages):
        stage_data = roadmap.get(stage, {})
        milestones = stage_data.get('milestones', [])
        for ms in milestones:
            all_milestones.append({
                'name': ms.get('name', ''),
                'stage': stage,
                'trl': ms.get('trl_level', 0),
                'uncertainty': ms.get('uncertainty_level', 'medium'),
                'stage_idx': stage_idx,
                'ms_idx': len(all_milestones)
            })
    
    n_milestones = len(all_milestones)
    fig_height = max(6, n_milestones * 0.35 + 2)
    fig, ax = plt.subplots(figsize=(10, fig_height), dpi=600)
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(PANEL_BG)
    
    y_positions = np.arange(n_milestones)
    
    for i, ms in enumerate(all_milestones):
        stage_color = _get_stage_color(ms['stage'])
        trl = ms['trl']
        bar_length = trl / 9.0 * 0.85 + 0.05
        
        ax.barh(i, bar_length, left=0.05, height=0.56, color=stage_color, alpha=0.82,
                edgecolor='white', linewidth=1.1)
        
        uc_color = _get_uncertainty_color(ms['uncertainty'])
        ax.scatter(bar_length + 0.05, i, s=34, c=uc_color, edgecolors='white',
                   linewidths=1.0, zorder=3)
        
        label_text = _shorten_text(ms['name'], 19)
        ax.text(0.02, i, label_text, va='center', ha='left', fontsize=7,
                color=TEXT_COLOR, fontfamily=_font_family(label_text), zorder=2)
        
        ax.text(bar_length + 0.08, i, f'TRL {trl}', va='center', ha='left', fontsize=6.5,
                fontweight='bold', color=AXIS_COLOR, fontfamily=LATIN_FONT, zorder=2)
    
    stage_lines = []
    for stage_idx, stage in enumerate(stages):
        ms_in_stage = [m for m in all_milestones if m['stage_idx'] == stage_idx]
        if ms_in_stage:
            min_y = min(m['ms_idx'] for m in ms_in_stage) - 0.5
            max_y = max(m['ms_idx'] for m in ms_in_stage) + 0.5
            stage_lines.append((stage, min_y, max_y))
    
    for stage, y_min, y_max in stage_lines:
        ax.axhspan(y_min, y_max, alpha=0.055, color=_get_stage_color(stage))
    
    ax.set_xlim(0, 1.15)
    ax.set_ylim(-0.8, n_milestones - 0.2)
    ax.set_yticks([])
    ax.set_xticks([0.05, 0.275, 0.5, 0.725, 0.95])
    ax.set_xticklabels(['TRL 1', 'TRL 3', 'TRL 5', 'TRL 7', 'TRL 9'], fontsize=8,
                       color=AXIS_COLOR, fontfamily=LATIN_FONT)
    ax.set_xlabel('Technology Readiness Level', fontsize=10, fontweight='bold',
                  color=TEXT_COLOR, fontfamily=LATIN_FONT, labelpad=10)
    
    for i, (stage, y_min, y_max) in enumerate(stage_lines):
        ax.text(0.015, (y_min + y_max) / 2, f'{stage}', va='center', ha='right',
                fontsize=9, fontweight='bold', color=_get_stage_color(stage),
                fontfamily=LATIN_FONT, zorder=2)
    
    legend_elements = [
        Line2D([0], [0], marker='s', color='w', markerfacecolor=_get_stage_color(s),
               markersize=10, label=f'{s}') for s in stages
    ] + [
        Line2D([0], [0], marker='o', color='w', markerfacecolor=UNCERTAINTY_COLORS[l],
               markersize=8, label=f'{l.title()}') for l in ['low', 'medium', 'high']
    ]
    _style_legend(ax.legend(handles=legend_elements, loc='upper right', fontsize=7, frameon=True,
                            framealpha=0.9, borderaxespad=1, ncol=2))
    
    ax.set_title(f'{topic_name}\nTimeline Roadmap', fontsize=12, fontweight='bold',
                 color=TEXT_COLOR, pad=15, **_get_text_font(topic_name))
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_color(AXIS_COLOR)
    ax.spines['bottom'].set_linewidth(0.8)
    ax.tick_params(axis='x', colors=AXIS_COLOR, width=0.75, length=3, top=False)
    ax.grid(axis='x', linestyle='-', linewidth=0.45, color=GRID_COLOR, alpha=0.65)
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    plt.savefig(output_path, facecolor=BG_COLOR, edgecolor='none', dpi=600)
    plt.close(fig)
    logger.info(f"Timeline Gantt chart saved: {output_path}")
    return output_path


def generate_technology_network(roadmap_data: Dict[str, Any], output_path: str) -> str:
    topic_name = roadmap_data.get('topic_name', 'Technology Roadmap')
    roadmap = roadmap_data.get('roadmap', {})
    
    stages = _roadmap_stages(roadmap)
    
    tech_counts = {}
    tech_by_stage = {}
    
    for stage in stages:
        stage_data = roadmap.get(stage, {})
        milestones = stage_data.get('milestones', [])
        tech_by_stage[stage] = set()
        for ms in milestones:
            for tech in ms.get('key_technologies', []):
                tech_counts[tech] = tech_counts.get(tech, 0) + 1
                tech_by_stage[stage].add(tech)
    
    sorted_techs = sorted(tech_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    tech_names = [t[0] for t in sorted_techs]
    tech_freq = [t[1] for t in sorted_techs]
    
    fig = plt.figure(figsize=(10, 7), dpi=600)
    fig.patch.set_facecolor(BG_COLOR)
    
    gs = GridSpec(1, 2, figure=fig, width_ratios=[1, 1.2], wspace=0.3)
    ax_left = fig.add_subplot(gs[0])
    ax_right = fig.add_subplot(gs[1])
    
    y_pos = np.arange(len(tech_names))
    bars = ax_left.barh(y_pos, tech_freq, color=PALETTE[0], alpha=0.9)
    
    for i, (bar, freq) in enumerate(zip(bars, tech_freq)):
        ax_left.text(freq + 0.3, i, str(freq), va='center', fontsize=7,
                     color=TEXT_COLOR, fontfamily=LATIN_FONT)
    
    ax_left.set_yticks(y_pos)
    ax_left.set_yticklabels([_shorten_text(t, 15) for t in tech_names], fontsize=7,
                            color=TEXT_COLOR)
    for label in ax_left.get_yticklabels():
        label.set_fontfamily(_font_family(label.get_text()))
    ax_left.invert_yaxis()
    ax_left.set_xlabel('Frequency', fontsize=10, fontweight='bold',
                       color=TEXT_COLOR, fontfamily=LATIN_FONT, labelpad=8)
    ax_left.set_title('Technology Frequency', fontsize=10, fontweight='bold',
                      color=TEXT_COLOR, fontfamily=LATIN_FONT, pad=8)
    _panel_label(ax_left, 'A', x=-0.18)
    _style_axes(ax_left)
    
    stage_colors = [_get_stage_color(s) for s in stages]
    for stage_idx, stage in enumerate(stages):
        techs_in_stage = tech_by_stage.get(stage, set())
        positions = []
        for i, tech in enumerate(tech_names):
            if tech in techs_in_stage:
                positions.append(i)
        if positions:
            ax_right.scatter([stage_idx] * len(positions), positions,
                            color=stage_colors[stage_idx], s=60, alpha=0.8,
                            edgecolor='white', linewidth=1)
    
    ax_right.set_xticks(range(len(stages)))
    ax_right.set_xticklabels(stages, fontsize=9, color=TEXT_COLOR, fontfamily=LATIN_FONT)
    ax_right.set_yticks(range(len(tech_names)))
    ax_right.set_yticklabels([_shorten_text(t, 12) for t in tech_names], fontsize=6.5,
                             color=TEXT_COLOR)
    for label in ax_right.get_yticklabels():
        label.set_fontfamily(_font_family(label.get_text()))
    ax_right.invert_yaxis()
    ax_right.set_xlabel('Phase', fontsize=10, fontweight='bold',
                        color=TEXT_COLOR, fontfamily=LATIN_FONT, labelpad=8)
    ax_right.set_title('Technology Evolution', fontsize=10, fontweight='bold',
                       color=TEXT_COLOR, fontfamily=LATIN_FONT, pad=8)
    _panel_label(ax_right, 'B', x=-0.13)
    _style_axes(ax_right)
    
    stage_legend = [Line2D([0], [0], marker='o', color='w', markerfacecolor=_get_stage_color(s),
                           markersize=10, label=f'{s}') for s in stages]
    _style_legend(ax_right.legend(handles=stage_legend, loc='upper right', fontsize=7, frameon=True,
                                  framealpha=0.8))
    
    fig.suptitle(f'{topic_name}\nTechnology Network Analysis', fontsize=12, fontweight='bold',
                 color=TEXT_COLOR, y=0.98, **_get_text_font(topic_name))
    
    fig.subplots_adjust(left=0.12, right=0.98, bottom=0.08, top=0.86, wspace=0.32)
    plt.savefig(output_path, facecolor=BG_COLOR, edgecolor='none', dpi=600)
    plt.close(fig)
    logger.info(f"Technology network chart saved: {output_path}")
    return output_path


def generate_comprehensive_radar(roadmap_data: Dict[str, Any], output_path: str) -> str:
    topic_name = roadmap_data.get('topic_name', 'Technology Roadmap')
    roadmap = roadmap_data.get('roadmap', {})
    
    stages = _roadmap_stages(roadmap)
    
    categories = ['TRL Level', 'Milestone\nDensity', 'Tech\nDiversity',
                  'Certainty', 'Scope', 'Innovation']
    N = len(categories)
    
    values_by_stage = []
    for stage in stages:
        stage_data = roadmap.get(stage, {})
        milestones = stage_data.get('milestones', [])
        n_ms = len(milestones)
        
        avg_trl = np.mean([ms.get('trl_level', 0) for ms in milestones]) if milestones else 0
        tech_count = len(set([t for ms in milestones for t in ms.get('key_technologies', [])]))
        
        unc_vals = [{'low': 3, 'medium': 2, 'high': 1}.get(ms.get('uncertainty_level', 'medium'), 2)
                    for ms in milestones]
        avg_unc = np.mean(unc_vals) if unc_vals else 2
        uncertainty_score = {3: 90, 2: 60, 1: 30}.get(int(avg_unc), 60)
        
        scope_score = min(100, 30 + n_ms * 15 + avg_trl * 4)
        innovation_score = min(100, 25 + n_ms * 12 + tech_count * 6)
        
        values = [
            min(100, avg_trl * 12),
            min(100, n_ms * 30),
            min(100, tech_count * 20),
            uncertainty_score,
            scope_score,
            innovation_score
        ]
        values_by_stage.append(values)
    
    angles = np.array([n / float(N) * 2 * np.pi for n in range(N)])
    angles = np.append(angles, angles[0])
    
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True), dpi=600)
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    
    for i, stage in enumerate(stages):
        values = values_by_stage[i]
        values = np.append(values, values[0])
        color = _get_stage_color(stage)
        ax.plot(angles, values, '-o', linewidth=2, label=f'{stage}', color=color,
                markersize=6, markerfacecolor='white', markeredgewidth=1.5, zorder=3)
        ax.fill(angles, values, alpha=0.12, color=color)
    
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=8, color=TEXT_COLOR, fontfamily=LATIN_FONT)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20', '40', '60', '80', '100'], fontsize=6.5, color=AXIS_COLOR,
                       fontfamily=LATIN_FONT)
    ax.grid(color=GRID_COLOR, linestyle=':', linewidth=0.5, alpha=0.6)
    ax.set_title(f'{topic_name}\nCapability Assessment', fontsize=12, fontweight='bold',
                 color=TEXT_COLOR, pad=25, **_get_text_font(topic_name))
    _style_legend(ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1.1), fontsize=8, frameon=True,
                            framealpha=0.8, borderaxespad=1))
    
    plt.tight_layout()
    plt.savefig(output_path, facecolor=BG_COLOR, edgecolor='none', dpi=600)
    plt.close(fig)
    logger.info(f"Comprehensive radar chart saved: {output_path}")
    return output_path


def generate_all_charts(roadmap_data: Dict[str, Any], output_dir: str = None) -> Dict[str, str]:
    topic_name = roadmap_data.get('topic_name', 'unknown')
    safe_name = topic_name.replace('/', '_').replace('\\', '_').replace(' ', '_')
    
    if output_dir is None:
        chart_dir = OUTPUTS_REPORT / 'per_topic_roadmaps' / 'charts'
    else:
        chart_dir = Path(output_dir) / 'charts'
    chart_dir.mkdir(parents=True, exist_ok=True)
    
    chart_paths = {}
    
    try:
        combined_path = str(chart_dir / f'{safe_name}_combined.png')
        generate_combined_topic_chart(roadmap_data, combined_path)
        chart_paths['combined'] = combined_path
    except Exception as e:
        logger.warning(f"Failed to generate combined chart: {e}")
    
    try:
        timeline_path = str(chart_dir / f'{safe_name}_timeline.png')
        generate_timeline_gantt(roadmap_data, timeline_path)
        chart_paths['timeline'] = timeline_path
    except Exception as e:
        logger.warning(f"Failed to generate timeline chart: {e}")
    
    try:
        radar_path = str(chart_dir / f'{safe_name}_radar.png')
        generate_comprehensive_radar(roadmap_data, radar_path)
        chart_paths['radar'] = radar_path
    except Exception as e:
        logger.warning(f"Failed to generate radar chart: {e}")
    
    return chart_paths


def generate_all_topics_comparison(all_roadmaps: List[Dict[str, Any]], output_path: str) -> str:
    if not all_roadmaps:
        return ''
    
    topics = [rm.get('topic_name', f'Topic {i}') for i, rm in enumerate(all_roadmaps)]
    stages = sorted({
        stage
        for roadmap in all_roadmaps
        for stage in _roadmap_stages(roadmap.get('roadmap', {}))
    }, key=int)
    
    fig = plt.figure(figsize=(14, 10), dpi=600)
    fig.patch.set_facecolor(BG_COLOR)
    
    gs = GridSpec(2, 2, figure=fig, wspace=0.3, hspace=0.35)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[1, 0])
    ax4 = fig.add_subplot(gs[1, 1])
    
    n_topics = len(topics)
    x = np.arange(n_topics)
    width = 0.18
    
    for i, stage in enumerate(stages):
        trl_means = []
        for rm in all_roadmaps:
            roadmap = rm.get('roadmap', {})
            stage_data = roadmap.get(stage, {})
            milestones = stage_data.get('milestones', [])
            trls = [ms.get('trl_level', 0) for ms in milestones]
            trl_means.append(np.mean(trls) if trls else 0)
        ax1.bar(x + i * width - width * 1.5, trl_means, width, label=f'{stage}',
                color=_get_stage_color(stage), alpha=0.9)
    
    ax1.set_ylabel('Mean TRL', fontsize=10, fontweight='bold', color=TEXT_COLOR,
                   fontfamily=LATIN_FONT, labelpad=8)
    ax1.set_title('TRL Comparison', fontsize=11, fontweight='bold',
                  color=TEXT_COLOR, fontfamily=LATIN_FONT, pad=10)
    ax1.set_xticks(x)
    xtick_labels = [_shorten_text(t, 7) for t in topics]
    ax1.set_xticklabels(xtick_labels, fontsize=7.5, rotation=30, ha='right', color=TEXT_COLOR)
    for label in ax1.get_xticklabels():
        label.set_fontfamily(_get_text_font(label.get_text())['family'])
    _style_legend(ax1.legend(fontsize=7, loc='upper left', frameon=True, framealpha=0.8))
    _panel_label(ax1, 'A')
    _style_axes(ax1)
    
    total_ms = []
    for rm in all_roadmaps:
        roadmap = rm.get('roadmap', {})
        count = sum([len(roadmap.get(s, {}).get('milestones', [])) for s in stages])
        total_ms.append(count)
    
    colors_pie = sns.color_palette('Set2', n_topics)
    wedges, texts, autotexts = ax2.pie(
        total_ms,
        labels=[_shorten_text(t, 8) for t in topics],
        autopct='%1.0f%%',
        colors=colors_pie,
        startangle=90,
        pctdistance=0.80,
        wedgeprops={'width': 0.42, 'edgecolor': 'white', 'linewidth': 1.0},
        textprops={'fontsize': 7, 'color': TEXT_COLOR},
    )
    for label in texts:
        label.set_fontfamily(_get_text_font(label.get_text())['family'])
    for label in autotexts:
        label.set_fontfamily(LATIN_FONT)
    ax2.set_title('Milestone Distribution', fontsize=11, fontweight='bold',
                  color=TEXT_COLOR, fontfamily=LATIN_FONT, pad=10)
    ax2.text(0, 0, f'n={sum(total_ms)}', ha='center', va='center', fontsize=9,
             color=AXIS_COLOR, fontfamily=LATIN_FONT)
    _panel_label(ax2, 'B', x=-0.18)
    
    tech_counts = []
    for rm in all_roadmaps:
        roadmap = rm.get('roadmap', {})
        all_techs = set()
        for s in stages:
            for ms in roadmap.get(s, {}).get('milestones', []):
                for t in ms.get('key_technologies', []):
                    all_techs.add(t)
        tech_counts.append(len(all_techs))
    
    bars = ax3.barh(x, tech_counts, color=PALETTE[0], alpha=0.9)
    ax3.set_yticks(x)
    ytick_labels = [_shorten_text(t, 9) for t in topics]
    ax3.set_yticklabels(ytick_labels, fontsize=7.5, color=TEXT_COLOR)
    for label in ax3.get_yticklabels():
        label.set_fontfamily(_get_text_font(label.get_text())['family'])
    ax3.set_xlabel('Number of Technologies', fontsize=10, fontweight='bold',
                   color=TEXT_COLOR, fontfamily=LATIN_FONT, labelpad=8)
    ax3.set_title('Technology Diversity', fontsize=11, fontweight='bold',
                  color=TEXT_COLOR, fontfamily=LATIN_FONT, pad=10)
    for i, v in enumerate(tech_counts):
        ax3.text(v + 0.5, i, str(v), va='center', fontsize=7, color=TEXT_COLOR,
                 fontfamily=LATIN_FONT)
    _panel_label(ax3, 'C')
    _style_axes(ax3)
    
    uncertainty_data = {'low': [], 'medium': [], 'high': []}
    for rm in all_roadmaps:
        roadmap = rm.get('roadmap', {})
        all_ms = []
        for s in stages:
            all_ms.extend(roadmap.get(s, {}).get('milestones', []))
        total = len(all_ms) if all_ms else 1
        for level in ['low', 'medium', 'high']:
            count = sum(1 for ms in all_ms if ms.get('uncertainty_level', 'medium') == level)
            uncertainty_data[level].append(count / total * 100)
    
    ax4.bar(x, uncertainty_data['low'], label='Low', color=UNCERTAINTY_COLORS['low'], alpha=0.95)
    ax4.bar(x, uncertainty_data['medium'], bottom=uncertainty_data['low'],
            label='Medium', color=UNCERTAINTY_COLORS['medium'], alpha=0.95)
    high_bottom = [l + m for l, m in zip(uncertainty_data['low'], uncertainty_data['medium'])]
    ax4.bar(x, uncertainty_data['high'], bottom=high_bottom,
            label='High', color=UNCERTAINTY_COLORS['high'], alpha=0.95)
    
    ax4.set_ylabel('Percentage (%)', fontsize=10, fontweight='bold', color=TEXT_COLOR,
                   fontfamily=LATIN_FONT, labelpad=8)
    ax4.set_title('Uncertainty Distribution', fontsize=11, fontweight='bold',
                  color=TEXT_COLOR, fontfamily=LATIN_FONT, pad=10)
    ax4.set_xticks(x)
    xtick_labels = [_shorten_text(t, 7) for t in topics]
    ax4.set_xticklabels(xtick_labels, fontsize=7.5, rotation=30, ha='right', color=TEXT_COLOR)
    for label in ax4.get_xticklabels():
        label.set_fontfamily(_get_text_font(label.get_text())['family'])
    _style_legend(ax4.legend(fontsize=7, loc='upper right', frameon=True, framealpha=0.8))
    _panel_label(ax4, 'D')
    _style_axes(ax4)
    
    fig.suptitle('Technology Roadmap Comparison', fontsize=14, fontweight='bold',
                 color=TEXT_COLOR, fontfamily=LATIN_FONT, y=0.98)
    
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.08, top=0.90, wspace=0.30, hspace=0.42)
    plt.savefig(output_path, facecolor=BG_COLOR, edgecolor='none', dpi=600)
    plt.close(fig)
    logger.info(f"Comparison chart saved: {output_path}")
    return output_path
