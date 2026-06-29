# -*- coding:utf-8 -*-
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
from config.settings import OUTPUTS_REPORT, PER_TOPIC_ROADMAP_STAGES
from src.utils.logger import get_logger

logger = get_logger(__name__)

plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'Heiti TC', 'PingFang SC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 150
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['savefig.bbox'] = 'tight'
plt.rcParams['savefig.pad_inches'] = 0.3

COLORS = {
    '2025': '#4A90D9',
    '2030': '#50C878',
    '2035': '#F4A460',
    '2040': '#CD5C5C',
    'trl_low': '#E8F4FD',
    'trl_mid': '#FFF8E7',
    'trl_high': '#FDE8E8',
    'uncertainty_low': '#50C878',
    'uncertainty_medium': '#F4A460',
    'uncertainty_high': '#CD5C5C',
    'bg': '#FAFAFA',
    'grid': '#E0E0E0',
    'text': '#2C3E50',
    'text_light': '#7F8C8D'
}


def _get_stage_color(stage: str) -> str:
    return COLORS.get(stage, '#666666')


def _get_uncertainty_color(level: str) -> str:
    mapping = {'low': COLORS['uncertainty_low'], 'medium': COLORS['uncertainty_medium'], 'high': COLORS['uncertainty_high']}
    return mapping.get(level, COLORS['text_light'])


def _wrap_text(text: str, max_chars: int = 15) -> str:
    if len(text) <= max_chars:
        return text
    lines = []
    current = ''
    for char in text:
        current += char
        if len(current) >= max_chars and char in ('，', '。', '、', ' '):
            lines.append(current)
            current = ''
    if current:
        lines.append(current)
    if not lines:
        return text[:max_chars] + '...'
    return '\n'.join(lines[:3])


def generate_timeline_chart(roadmap_data: Dict[str, Any], output_path: str) -> str:
    topic_name = roadmap_data.get('topic_name', '技术路线图')
    roadmap = roadmap_data.get('roadmap', {})

    stages = [s for s in PER_TOPIC_ROADMAP_STAGES if s in roadmap]
    if not stages:
        stages = PER_TOPIC_ROADMAP_STAGES

    fig, ax = plt.subplots(figsize=(14, max(6, len(stages) * 1.8)))
    fig.patch.set_facecolor(COLORS['bg'])
    ax.set_facecolor(COLORS['bg'])

    y_positions = list(range(len(stages)))
    y_positions.reverse()

    for i, stage in enumerate(stages):
        y = y_positions[i]
        color = _get_stage_color(stage)
        stage_data = roadmap.get(stage, {})
        milestones = stage_data.get('milestones', [])
        stage_desc = stage_data.get('stage_description', '')

        ax.barh(y, 1, left=0, height=0.6, color=color, alpha=0.15, edgecolor=color, linewidth=2, zorder=1)
        ax.text(0.02, y, f'{stage}年', va='center', ha='left', fontsize=13, fontweight='bold', color=color, zorder=2)

        if milestones:
            n = len(milestones)
            for j, ms in enumerate(milestones):
                x_pos = 0.25 + (j * 0.7 / max(n - 1, 1)) if n > 1 else 0.55
                ms_name = ms.get('name', '')
                trl = ms.get('trl_level', 0)
                uncertainty = ms.get('uncertainty_level', 'medium')
                uc_color = _get_uncertainty_color(uncertainty)

                bubble_size = 200 + trl * 80

                ax.scatter(x_pos, y, s=bubble_size, c=color, alpha=0.85, edgecolors='white', linewidths=2, zorder=3)

                label = _wrap_text(ms_name, 12)
                ax.annotate(label, xy=(x_pos, y), xytext=(x_pos, y + 0.38),
                            ha='center', va='bottom', fontsize=8.5, color=COLORS['text'],
                            zorder=4,
                            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor=color, alpha=0.9))

                ax.text(x_pos, y - 0.25, f'TRL {trl}', ha='center', va='top',
                        fontsize=7.5, fontweight='bold', color='white', zorder=5)

                ax.plot(x_pos, y - 0.35, marker='o', markersize=5, color=uc_color, zorder=5)

    for i in range(len(stages) - 1):
        y_from = y_positions[i]
        y_to = y_positions[i + 1]
        ax.annotate('', xy=(0.05, y_to + 0.25), xytext=(0.05, y_from - 0.25),
                    arrowprops=dict(arrowstyle='->', color=COLORS['grid'], lw=1.5))

    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.8, len(stages) - 0.2)
    ax.set_xlabel('技术成熟度方向 →', fontsize=11, color=COLORS['text_light'], labelpad=10)
    ax.set_title(f'{topic_name} - 技术发展路线图', fontsize=16, fontweight='bold',
                 color=COLORS['text'], pad=20)

    ax.set_yticks(y_positions)
    ax.set_yticklabels([])
    ax.set_xticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(left=False, bottom=False)

    legend_elements = [
        plt.scatter([], [], s=100, c=COLORS['uncertainty_low'], label='不确定性: 低'),
        plt.scatter([], [], s=100, c=COLORS['uncertainty_medium'], label='不确定性: 中'),
        plt.scatter([], [], s=100, c=COLORS['uncertainty_high'], label='不确定性: 高'),
    ]
    ax.legend(handles=legend_elements, loc='lower right', fontsize=9, framealpha=0.9,
              title='不确定性等级', title_fontsize=9)

    plt.tight_layout()
    plt.savefig(output_path, facecolor=COLORS['bg'], edgecolor='none')
    plt.close(fig)
    logger.info(f"时间轴图表已保存: {output_path}")
    return output_path


def generate_trl_curve(roadmap_data: Dict[str, Any], output_path: str) -> str:
    topic_name = roadmap_data.get('topic_name', '技术路线图')
    roadmap = roadmap_data.get('roadmap', {})

    stages = [s for s in PER_TOPIC_ROADMAP_STAGES if s in roadmap]
    if not stages:
        stages = PER_TOPIC_ROADMAP_STAGES

    fig, ax = plt.subplots(figsize=(11, 6.5))
    fig.patch.set_facecolor(COLORS['bg'])
    ax.set_facecolor(COLORS['bg'])

    x_indices = list(range(len(stages)))
    x_labels = [f'{s}年' for s in stages]

    all_trls = []
    ms_names = []
    ms_colors = []
    trl_means = []
    trl_mins = []
    trl_maxs = []

    for stage in stages:
        stage_data = roadmap.get(stage, {})
        milestones = stage_data.get('milestones', [])
        trls = [ms.get('trl_level', 0) for ms in milestones]
        if trls:
            trl_means.append(np.mean(trls))
            trl_mins.append(min(trls))
            trl_maxs.append(max(trls))
            all_trls.extend(trls)
            ms_names.extend([ms.get('name', '') for ms in milestones])
            ms_colors.extend([_get_stage_color(stage)] * len(milestones))
        else:
            trl_means.append(0)
            trl_mins.append(0)
            trl_maxs.append(0)

    ax.fill_between(x_indices, trl_mins, trl_maxs, alpha=0.15, color=COLORS['2030'], label='TRL范围')

    ax.plot(x_indices, trl_means, 'o-', color=COLORS['2030'], linewidth=2.5,
            markersize=9, markerfacecolor='white', markeredgewidth=2.5,
            label='平均TRL', zorder=5)

    for i, stage in enumerate(stages):
        stage_data = roadmap.get(stage, {})
        milestones = stage_data.get('milestones', [])
        if milestones:
            jitter = np.linspace(-0.15, 0.15, len(milestones))
            for j, ms in enumerate(milestones):
                trl = ms.get('trl_level', 0)
                uncertainty = ms.get('uncertainty_level', 'medium')
                uc_color = _get_uncertainty_color(uncertainty)
                ax.scatter(i + jitter[j], trl, s=80, c=uc_color, edgecolors='white',
                           linewidths=1.5, alpha=0.85, zorder=4)

    ax.set_xticks(x_indices)
    ax.set_xticklabels(x_labels, fontsize=11, color=COLORS['text'])
    ax.set_ylabel('TRL (技术就绪水平)', fontsize=12, color=COLORS['text'], labelpad=10)
    ax.set_ylim(0, 10)
    ax.set_yticks(range(0, 10, 2))
    ax.set_yticklabels([f'Level {i}' for i in range(0, 10, 2)], fontsize=10, color=COLORS['text_light'])

    ax.set_title(f'{topic_name} - TRL发展趋势', fontsize=15, fontweight='bold',
                 color=COLORS['text'], pad=15)

    ax.grid(axis='y', linestyle='--', alpha=0.4, color=COLORS['grid'])
    ax.set_axisbelow(True)

    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    for spine in ['left', 'bottom']:
        ax.spines[spine].set_color(COLORS['grid'])

    trl_labels = ['基础原理', '概念形成', '实验室验证', '组件验证', '相关环境', '原型验证', '系统演示', '实际运行', '完全成熟']
    for i, label in enumerate(trl_labels[::2]):
        ax.text(-0.7, i * 2 + 1, label, fontsize=7.5, color=COLORS['text_light'],
                ha='right', va='center', style='italic')

    legend_elements = [
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=COLORS['uncertainty_low'], markersize=9, label='不确定性: 低'),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=COLORS['uncertainty_medium'], markersize=9, label='不确定性: 中'),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=COLORS['uncertainty_high'], markersize=9, label='不确定性: 高'),
        plt.Line2D([0], [0], color=COLORS['2030'], linewidth=2, marker='o', label='平均TRL'),
    ]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=9, framealpha=0.9)

    plt.tight_layout()
    plt.savefig(output_path, facecolor=COLORS['bg'], edgecolor='none')
    plt.close(fig)
    logger.info(f"TRL曲线图表已保存: {output_path}")
    return output_path


def generate_dependency_chart(roadmap_data: Dict[str, Any], output_path: str) -> str:
    topic_name = roadmap_data.get('topic_name', '技术路线图')
    roadmap = roadmap_data.get('roadmap', {})

    stages = [s for s in PER_TOPIC_ROADMAP_STAGES if s in roadmap]
    if not stages:
        stages = PER_TOPIC_ROADMAP_STAGES

    all_milestones = []
    milestone_positions = {}
    milestone_data = {}

    for stage_idx, stage in enumerate(stages):
        stage_data = roadmap.get(stage, {})
        milestones = stage_data.get('milestones', [])
        n = len(milestones)
        for ms_idx, ms in enumerate(milestones):
            ms_id = f'{stage}_{ms_idx}'
            x_pos = stage_idx
            y_pos = (ms_idx - (n - 1) / 2) * 1.2 if n > 1 else 0
            all_milestones.append(ms_id)
            milestone_positions[ms_id] = (x_pos, y_pos)
            milestone_data[ms_id] = {
                'name': ms.get('name', ''),
                'trl': ms.get('trl_level', 0),
                'stage': stage,
                'uncertainty': ms.get('uncertainty_level', 'medium'),
                'dependencies': ms.get('dependencies', [])
            }

    fig, ax = plt.subplots(figsize=(max(12, len(stages) * 3), max(7, len(all_milestones) * 0.6)))
    fig.patch.set_facecolor(COLORS['bg'])
    ax.set_facecolor(COLORS['bg'])

    for i, stage in enumerate(stages):
        ax.axvline(x=i, color=COLORS['grid'], linestyle='--', alpha=0.5, zorder=0)
        ax.text(i, -3.5, f'{stage}年', ha='center', va='top', fontsize=11,
                fontweight='bold', color=_get_stage_color(stage))

    for ms_id in all_milestones:
        x, y = milestone_positions[ms_id]
        data = milestone_data[ms_id]
        deps = data.get('dependencies', [])

        for dep in deps:
            for other_id in all_milestones:
                other_data = milestone_data[other_id]
                if dep and dep in other_data.get('name', ''):
                    ox, oy = milestone_positions[other_id]
                    if ox < x:
                        arrow = FancyArrowPatch((ox + 0.15, oy), (x - 0.15, y),
                                                arrowstyle='->', color=COLORS['text_light'],
                                                lw=1.2, alpha=0.6, zorder=2,
                                                connectionstyle="arc3,rad=0.1")
                        ax.add_patch(arrow)

    for ms_id in all_milestones:
        x, y = milestone_positions[ms_id]
        data = milestone_data[ms_id]
        color = _get_stage_color(data['stage'])
        trl = data['trl']
        size = 0.55 + trl * 0.04

        box = FancyBboxPatch((x - size / 2, y - size / 3), size, size * 0.66,
                             boxstyle="round,pad=0.08",
                             facecolor=color, edgecolor='white', linewidth=2, alpha=0.9, zorder=4)
        ax.add_patch(box)

        ax.text(x, y + 0.05, _wrap_text(data['name'], 8), ha='center', va='center',
                fontsize=7.5, color='white', fontweight='bold', zorder=5)
        ax.text(x, y - size / 3 - 0.08, f'TRL {trl}', ha='center', va='top',
                fontsize=6.5, color=color, fontweight='bold', zorder=5)

    x_margin = 0.8
    y_min = min([pos[1] for pos in milestone_positions.values()] + [0]) - 1.5
    y_max = max([pos[1] for pos in milestone_positions.values()] + [0]) + 1.5

    ax.set_xlim(-x_margin, len(stages) - 1 + x_margin)
    ax.set_ylim(y_min, y_max)
    ax.set_title(f'{topic_name} - 技术依赖与演进路径', fontsize=15, fontweight='bold',
                 color=COLORS['text'], pad=20)
    ax.set_xticks(range(len(stages)))
    ax.set_xticklabels([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    stage_patches = [mpatches.Patch(color=_get_stage_color(s), label=f'{s}年') for s in stages]
    ax.legend(handles=stage_patches, loc='upper right', fontsize=9, framealpha=0.9,
              title='发展阶段', title_fontsize=9)

    plt.tight_layout()
    plt.savefig(output_path, facecolor=COLORS['bg'], edgecolor='none')
    plt.close(fig)
    logger.info(f"依赖关系图表已保存: {output_path}")
    return output_path


def generate_summary_radar(roadmap_data: Dict[str, Any], output_path: str) -> str:
    topic_name = roadmap_data.get('topic_name', '技术路线图')
    roadmap = roadmap_data.get('roadmap', {})

    stages = [s for s in PER_TOPIC_ROADMAP_STAGES if s in roadmap]
    if not stages:
        stages = PER_TOPIC_ROADMAP_STAGES

    categories = ['技术成熟度\n(平均TRL)', '里程碑数量', '技术多样性', '不确定性\n(逆向)', '应用广度', '创新程度']
    N = len(categories)

    values_by_stage = []
    for stage in stages:
        stage_data = roadmap.get(stage, {})
        milestones = stage_data.get('milestones', [])
        n_ms = len(milestones)

        avg_trl = np.mean([ms.get('trl_level', 0) for ms in milestones]) if milestones else 0
        tech_count = len(set([t for ms in milestones for t in ms.get('key_technologies', [])]))
        uncertainty_score = {
            'low': 90, 'medium': 60, 'high': 30
        }.get(np.mean([{'low': 3, 'medium': 2, 'high': 1}.get(ms.get('uncertainty_level', 'medium'), 2)
                        for ms in milestones]) if milestones else 2, 60)
        scope_score = min(100, 40 + n_ms * 12 + avg_trl * 3)
        innovation_score = min(100, 30 + n_ms * 10 + tech_count * 5)

        values = [
            avg_trl * 11,
            min(100, n_ms * 25),
            min(100, tech_count * 15),
            uncertainty_score,
            scope_score,
            innovation_score
        ]
        values_by_stage.append(values)

    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(9, 9), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor(COLORS['bg'])

    for i, stage in enumerate(stages):
        values = values_by_stage[i] + values_by_stage[i][:1]
        color = _get_stage_color(stage)
        ax.plot(angles, values, 'o-', linewidth=2, label=f'{stage}年', color=color, markersize=6)
        ax.fill(angles, values, alpha=0.12, color=color)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=10, color=COLORS['text'])
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20', '40', '60', '80', '100'], fontsize=8, color=COLORS['text_light'])
    ax.grid(color=COLORS['grid'], linestyle='--', alpha=0.5)

    ax.set_title(f'{topic_name} - 综合能力雷达图', fontsize=15, fontweight='bold',
                 color=COLORS['text'], pad=30)
    ax.legend(loc='upper right', bbox_to_anchor=(1.25, 1.1), fontsize=9, framealpha=0.9)

    plt.tight_layout()
    plt.savefig(output_path, facecolor=COLORS['bg'], edgecolor='none')
    plt.close(fig)
    logger.info(f"雷达图已保存: {output_path}")
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
        timeline_path = str(chart_dir / f'{safe_name}_时间轴路线图.png')
        generate_timeline_chart(roadmap_data, timeline_path)
        chart_paths['timeline'] = timeline_path
    except Exception as e:
        logger.warning(f"生成时间轴图表失败: {e}")

    try:
        trl_path = str(chart_dir / f'{safe_name}_TRL发展曲线.png')
        generate_trl_curve(roadmap_data, trl_path)
        chart_paths['trl_curve'] = trl_path
    except Exception as e:
        logger.warning(f"生成TRL曲线失败: {e}")

    try:
        dep_path = str(chart_dir / f'{safe_name}_技术依赖图.png')
        generate_dependency_chart(roadmap_data, dep_path)
        chart_paths['dependency'] = dep_path
    except Exception as e:
        logger.warning(f"生成依赖图失败: {e}")

    try:
        radar_path = str(chart_dir / f'{safe_name}_综合雷达图.png')
        generate_summary_radar(roadmap_data, radar_path)
        chart_paths['radar'] = radar_path
    except Exception as e:
        logger.warning(f"生成雷达图失败: {e}")

    return chart_paths


def generate_all_topics_comparison(all_roadmaps: List[Dict[str, Any]], output_path: str) -> str:
    if not all_roadmaps:
        return ''

    topics = [rm.get('topic_name', f'主题{i}') for i, rm in enumerate(all_roadmaps)]
    stages = PER_TOPIC_ROADMAP_STAGES

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.patch.set_facecolor(COLORS['bg'])

    n_topics = len(topics)
    x = np.arange(n_topics)
    width = 0.2

    ax1 = axes[0, 0]
    ax1.set_facecolor(COLORS['bg'])

    for i, stage in enumerate(stages):
        trl_means = []
        for rm in all_roadmaps:
            roadmap = rm.get('roadmap', {})
            stage_data = roadmap.get(stage, {})
            milestones = stage_data.get('milestones', [])
            trls = [ms.get('trl_level', 0) for ms in milestones]
            trl_means.append(np.mean(trls) if trls else 0)
        ax1.bar(x + i * width - width * 1.5, trl_means, width, label=f'{stage}年',
                color=_get_stage_color(stage), alpha=0.85)

    ax1.set_ylabel('平均 TRL', fontsize=11, color=COLORS['text'])
    ax1.set_title('各主题TRL对比', fontsize=13, fontweight='bold', color=COLORS['text'])
    ax1.set_xticks(x)
    ax1.set_xticklabels([t[:6] for t in topics], fontsize=8.5, rotation=20, ha='right', color=COLORS['text'])
    ax1.legend(fontsize=8.5, loc='upper left')
    ax1.grid(axis='y', linestyle='--', alpha=0.3, color=COLORS['grid'])
    for spine in ['top', 'right']:
        ax1.spines[spine].set_visible(False)

    ax2 = axes[0, 1]
    ax2.set_facecolor(COLORS['bg'])

    total_ms = []
    for rm in all_roadmaps:
        roadmap = rm.get('roadmap', {})
        count = sum([len(roadmap.get(s, {}).get('milestones', [])) for s in stages])
        total_ms.append(count)

    colors = plt.cm.Set3(np.linspace(0, 1, n_topics))
    wedges, texts, autotexts = ax2.pie(total_ms, labels=[t[:8] for t in topics],
                                        autopct='%1.0f%%', colors=colors, startangle=90,
                                        textprops={'fontsize': 8.5, 'color': COLORS['text']})
    ax2.set_title('各主题里程碑数量占比', fontsize=13, fontweight='bold', color=COLORS['text'])

    ax3 = axes[1, 0]
    ax3.set_facecolor(COLORS['bg'])

    tech_counts = []
    for rm in all_roadmaps:
        roadmap = rm.get('roadmap', {})
        all_techs = set()
        for s in stages:
            for ms in roadmap.get(s, {}).get('milestones', []):
                for t in ms.get('key_technologies', []):
                    all_techs.add(t)
        tech_counts.append(len(all_techs))

    bars = ax3.barh(x, tech_counts, color=COLORS['2030'], alpha=0.8)
    ax3.set_yticks(x)
    ax3.set_yticklabels([t[:10] for t in topics], fontsize=8.5, color=COLORS['text'])
    ax3.set_xlabel('关键技术数量', fontsize=11, color=COLORS['text'])
    ax3.set_title('各主题技术多样性', fontsize=13, fontweight='bold', color=COLORS['text'])
    for i, v in enumerate(tech_counts):
        ax3.text(v + 0.3, i, str(v), va='center', fontsize=9, color=COLORS['text'])
    ax3.grid(axis='x', linestyle='--', alpha=0.3, color=COLORS['grid'])
    for spine in ['top', 'right']:
        ax3.spines[spine].set_visible(False)

    ax4 = axes[1, 1]
    ax4.set_facecolor(COLORS['bg'])

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

    ax4.bar(x, uncertainty_data['low'], label='低', color=COLORS['uncertainty_low'], alpha=0.8)
    ax4.bar(x, uncertainty_data['medium'], bottom=uncertainty_data['low'],
            label='中', color=COLORS['uncertainty_medium'], alpha=0.8)
    high_bottom = [l + m for l, m in zip(uncertainty_data['low'], uncertainty_data['medium'])]
    ax4.bar(x, uncertainty_data['high'], bottom=high_bottom,
            label='高', color=COLORS['uncertainty_high'], alpha=0.8)

    ax4.set_ylabel('占比 (%)', fontsize=11, color=COLORS['text'])
    ax4.set_title('各主题不确定性分布', fontsize=13, fontweight='bold', color=COLORS['text'])
    ax4.set_xticks(x)
    ax4.set_xticklabels([t[:6] for t in topics], fontsize=8.5, rotation=20, ha='right', color=COLORS['text'])
    ax4.legend(fontsize=8.5, loc='upper right')
    ax4.grid(axis='y', linestyle='--', alpha=0.3, color=COLORS['grid'])
    for spine in ['top', 'right']:
        ax4.spines[spine].set_visible(False)

    fig.suptitle('智能建造2040 - 分主题技术路线图综合对比', fontsize=16, fontweight='bold',
                 color=COLORS['text'], y=0.98)
    plt.tight_layout()
    plt.savefig(output_path, facecolor=COLORS['bg'], edgecolor='none')
    plt.close(fig)
    logger.info(f"综合对比图表已保存: {output_path}")
    return output_path
