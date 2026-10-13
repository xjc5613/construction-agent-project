type Series = { series_id: string; label: string; evidence_status: string; color?: string; values: Array<Record<string, any>> };
export type ScientificChart = { checksum: string; figure_number: string; chart_kind: string; title: string; caption: string; source_note: string; sample_size: number; cutoff: string; series: Series[] };

const colors = ["#216869", "#4D6CFA", "#B7673C", "#7251A3", "#008A8C"];

function flatten(chart: ScientificChart) {
  return chart.series.flatMap((series) => series.values.map((value) => ({series: series.label, status: series.evidence_status, ...value})));
}

export function ScientificChartPanel({ chart }: { chart: ScientificChart }) {
  const rows = flatten(chart);
  const points = chart.series.flatMap((series, seriesIndex) => series.values.map((value, index) => ({
    x: Number(value.x ?? value.year ?? value.rank ?? index + 1),
    y: Number(value.y ?? value.value ?? value.score ?? 0), series, seriesIndex,
  }))).filter((item) => Number.isFinite(item.x) && Number.isFinite(item.y));
  const xValues = points.map((item) => item.x), yValues = points.map((item) => item.y);
  const xMin = Math.min(...xValues, 0), xMax = Math.max(...xValues, 1), yMin = Math.min(...yValues, 0), yMax = Math.max(...yValues, 1);
  const px = (x: number) => 42 + (x - xMin) / Math.max(1e-9, xMax - xMin) * 700;
  const py = (y: number) => 242 - (y - yMin) / Math.max(1e-9, yMax - yMin) * 190;
  const csv = [Object.keys(rows[0] ?? {series: ""}).join(","), ...rows.map((row) => Object.values(row).map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`).join(","))].join("\n");
  const network = chart.chart_kind === "network_small_multiples";
  return <figure className="scientific-chart">
    <figcaption><div><b>{chart.figure_number}</b><strong>{chart.title}</strong><p>{chart.caption}</p></div><a className="outline-button" download={`${chart.figure_number}.csv`} href={`data:text/csv;charset=utf-8,${encodeURIComponent(csv)}`}>CSV</a></figcaption>
    {network ? <svg viewBox="0 0 780 270" role="img" aria-label={`${chart.title}。${chart.caption}`}>
      {chart.series.map((series, panel) => <g key={series.series_id} transform={`translate(${panel * 260} 0)`}>
        <rect x="8" y="16" width="244" height="238" fill="#f8faf9" stroke="#dde6e2"/><text x="130" y="34" textAnchor="middle" fontSize="11" fontWeight="700">{series.label}</text>
        {series.values.map((edge, index) => <g key={index}><line x1={130 + Number(edge.x1) * 100} y1={140 + Number(edge.y1) * 92} x2={130 + Number(edge.x2) * 100} y2={140 + Number(edge.y2) * 92} stroke={colors[panel % colors.length]} strokeWidth={Math.max(.6, Number(edge.weight ?? 1))} opacity=".55"/><circle cx={130 + Number(edge.x1) * 100} cy={140 + Number(edge.y1) * 92} r="3.3" fill={colors[(String(edge.community1 ?? "").length + panel) % colors.length]}/><circle cx={130 + Number(edge.x2) * 100} cy={140 + Number(edge.y2) * 92} r="3.3" fill={colors[(String(edge.community2 ?? "").length + panel) % colors.length]}/></g>)}
      </g>)}
    </svg> : points.length ? <svg viewBox="0 0 780 270" role="img" aria-label={`${chart.title}。${chart.caption}`}>
      <path className="axis" d="M42 22V242H752"/>
      {chart.series.map((series, seriesIndex) => {
        const own = points.filter((point) => point.series === series);
        const path = own.map((point, index) => `${index ? "L" : "M"}${px(point.x)} ${py(point.y)}`).join(" ");
        return <g key={series.series_id}><path d={path} fill="none" stroke={series.color || colors[seriesIndex % colors.length]} strokeWidth="2" strokeDasharray={series.evidence_status === "predicted" ? "7 5" : undefined}/>{own.map((point, index) => <path key={index} transform={`translate(${px(point.x)} ${py(point.y)})`} d={series.evidence_status === "predicted" ? "M0 -5L5 4H-5Z" : "M-4 -4H4V4H-4Z"} fill={series.color || colors[seriesIndex % colors.length]}/>)}</g>;
      })}
    </svg> : <div className="chart-placeholder">该图为网络空间或当前没有可估计数值，请下载表格或查看静态出版图。</div>}
    <div className="chart-meta"><span>n={chart.sample_size}</span><span>截止 {chart.cutoff}</span><span>{chart.source_note}</span><code>{chart.checksum.slice(0, 12)}</code></div>
    <details className="chart-alternative"><summary>查看可访问数据表</summary><div className="data-table"><div className="table-head"><span>序列</span><span>状态</span><span>数值</span></div>{rows.slice(0, 100).map((row, index) => <div className="table-row" key={index}><span>{row.series}</span><span>{row.status}</span><code>{JSON.stringify(row)}</code></div>)}</div></details>
  </figure>;
}
