"""Package original sources and explicitly typed model supplements."""
import csv
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output'
results = json.loads((OUT / 'forecast_results.json').read_text())['topics']
with (OUT / 'theme_annual_counts.csv').open(encoding='utf-8-sig') as f:
    annual = {r['topic_id']: r for r in csv.DictReader(f)}
with (OUT / 'evidence_2015_2026_long.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(['topic_id', 'topic_name', 'year', 'count', 'source_type', 'low80', 'high80', 'used_in_full_year_series'])
    for t, s in results.items():
        for y in range(2015, 2025):
            w.writerow([t, s['topic_name'], y, annual[t][str(y)], 'observed', '', '', True])
        w.writerow([t, s['topic_name'], 2025, annual[t]['2025'], 'partial_observed', '', '', False])
        for y in (2025, 2026):
            p = s['projection'][str(y)]
            w.writerow([t, s['topic_name'], y, p['median'], 'model_supplement', p['low80'], p['high80'], True])
with (OUT / 'bubble_activity_2021_2026.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(['topic_id', 'topic_name', 'observed_2021_2024', 'supplement_2025', 'supplement_2026', 'total_2021_2026', 'bubble_area_points_squared'])
    for t, s in results.items():
        w.writerow([t, s['topic_name'], s['recent_count_2021_2024'], s['projection']['2025']['median'], s['projection']['2026']['median'], s['activity_2021_2026'], 0.12*s['activity_2021_2026']])
readme = '''# 智能建造技术预测交付包

## 证据口径
原始输入位于 original_inputs，保持原文件内容。模型补充为主题—年度汇总数量，不是新增逐条专利记录。
2015—2024为既有年度观测；2025部分年度观测单独保留；绘图采用2025全年与2026模型补充值。
2025部分年度观测不与2025全年估计重复相加。主题可重叠，不应相加为独立专利总数。

## 图表解释
A：年度主题活动，纵轴为ln（记录数+1）。2026误差线为80%探索性区间，未经覆盖率校准。
B：IPC节点的度中心度与中介中心度迁移；阶段1为2010—2014，阶段2为2015—2020，阶段3为2021—2025。未构建2026 IPC网络。
C：历史主题动量与历史网络跃迁；气泡面积=0.12×2021—2026累计活动量（含模型补充），不是技术成功概率。横纵坐标与综合排名保持历史证据口径。
路线图：2027—2040九主题三阶段目标；依赖关系集中在底部，属于规划假设。

## 模型与复核
2018—2024加权log1p趋势，近期权重0.72，斜率截断[-0.15,0.25]，以2024计数为基数，增长衰减0.88。
区间使用加权残差及预测步长构造，仅供探索。具体计算见 code/analyze_forecast.py。
evidence_2015_2026_long.csv：逐主题逐年的来源标签与绘图值。
theme_evidence_to_2026.csv：2025/2026补充值及区间。
bubble_activity_2021_2026.csv：累计活动量及面积映射。
manifest.json：包内文件SHA-256，便于核对原始输入是否改变。
'''
(OUT / '交付说明.md').write_text(readme, encoding='utf-8')
files = []
for p in (ROOT / 'inputs').iterdir():
    if p.is_file(): files.append((p, 'original_inputs/' + p.name))
for name in ['theme_annual_counts.csv', 'theme_evidence_to_2026.csv', 'evidence_2015_2026_long.csv', 'bubble_activity_2021_2026.csv', 'forecast_results.json', 'theme_scores.csv', 'ipc_stage_metrics.csv', 'data_audit.json', '交付说明.md', '智能建造关键技术预测成果与发展路线图.docx']:
    files.append((OUT / name, name))
for p in (ROOT / 'figures').iterdir():
    if p.suffix in ('.png', '.pdf', '.svg'): files.append((p, 'figures/' + p.name))
for name in ['analyze_forecast.py', 'build_report.py', 'package_results.py']:
    files.append((ROOT / name, 'code/' + name))
manifest = {name: hashlib.sha256(p.read_bytes()).hexdigest() for p, name in files}
with ZipFile(OUT / '智能建造预测_最终成果与证据包.zip', 'w', ZIP_DEFLATED) as z:
    for p, name in files: z.write(p, name)
    z.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
print(OUT / '智能建造预测_最终成果与证据包.zip')
