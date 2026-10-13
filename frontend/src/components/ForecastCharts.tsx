import { useEffect, useRef } from "react";
import type { ChartData } from "../types";

function ChartAlternative({ summary, headers, rows }: { summary: string; headers: string[]; rows: Array<Array<string | number | null>> }) {
  return <details className="chart-alternative"><summary>{summary}</summary><table><caption>{summary}</caption><thead><tr>{headers.map((item) => <th scope="col" key={item}>{item}</th>)}</tr></thead><tbody>{rows.length ? rows.map((row, index) => <tr key={index}>{row.map((value, cell) => <td key={cell}>{value ?? "—"}</td>)}</tr>) : <tr><td colSpan={headers.length}>暂无数据</td></tr>}</tbody></table></details>;
}

export function ForecastCharts({ charts }: { charts: ChartData }) {
  const trlRef = useRef<HTMLDivElement>(null);
  const ipcRef = useRef<HTMLDivElement>(null);
  const papersRef = useRef<HTMLDivElement>(null);
  const matrixRef = useRef<HTMLDivElement>(null);
  const fusionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let disposed = false;
    const instances: Array<{ resize: () => void; dispose: () => void }> = [];
    void import("echarts").then((echarts) => {
      if (disposed || !trlRef.current || !ipcRef.current || !papersRef.current || !matrixRef.current || !fusionRef.current) return;
      const trl = echarts.init(trlRef.current);
      const baselineYear = charts.baseline_year ?? 2025;
      const forecastNodes = charts.forecast_nodes?.length
        ? charts.forecast_nodes : ["2030", "2035", "2040"];
      const roadmapYears = [String(baselineYear), ...forecastNodes];
      trl.setOption({
        color: ["#635bff", "#19a874", "#e6a23c", "#ef6461"],
        tooltip: { trigger: "axis" },
        legend: { bottom: 0, textStyle: { color: "#6b7280" } },
        grid: { left: 44, right: 18, top: 26, bottom: 48 },
        xAxis: { type: "category", data: roadmapYears },
        yAxis: { type: "value", min: 0, max: 9, name: "TRL" },
        series: charts.trl_series.map((series) => ({
          type: "line", name: series.name, smooth: true, symbolSize: 7,
          lineStyle: { width: 3 }, data: series.data.map((item) => item.value),
        })),
      });
      const ipcCodes = [...new Set(charts.ipc_trends.map((item) => item.ipc_code))];
      const ipc = echarts.init(ipcRef.current);
      ipc.setOption({
        color: ["#635bff", "#18a67b", "#4e83db"],
        tooltip: { trigger: "axis" }, legend: { bottom: 0 },
        grid: { left: 48, right: 15, top: 25, bottom: 46 },
        xAxis: { type: "category", data: [...new Set(charts.ipc_trends.map((item) => item.year))].sort() },
        yAxis: { type: "value", name: "指标值" },
        series: ipcCodes.map((code) => ({
          name: code, type: "line", smooth: true,
          data: charts.ipc_trends.filter((item) => item.ipc_code === code)
            .map((item) => item.patent_count ?? item.degree_centrality),
        })),
      });
      const paperYears = [...new Set(charts.paper_trends.map((item) => item.year))].sort();
      const papers = echarts.init(papersRef.current);
      papers.setOption({
        color: ["#4f7ee8"], tooltip: { trigger: "axis" },
        grid: { left: 44, right: 14, top: 22, bottom: 32 },
        xAxis: { type: "category", data: paperYears },
        yAxis: { type: "value", minInterval: 1 },
        series: [{ type: "bar", barWidth: "45%", data: paperYears.map((year) => charts.paper_trends.filter((item) => item.year === year).reduce((sum, item) => sum + item.count, 0)), itemStyle: { borderRadius: [5, 5, 0, 0] } }],
      });
      const matrix = echarts.init(matrixRef.current);
      matrix.setOption({
        tooltip: {},
        grid: { left: 110, right: 20, top: 22, bottom: 35 },
        xAxis: { type: "category", data: ["IPC", "论文"] },
        yAxis: { type: "category", data: charts.evidence_matrix.map((item) => item.topic) },
        visualMap: { min: 0, max: Math.max(5, ...charts.evidence_matrix.flatMap((item) => [item.ipc_count, item.paper_count])), show: false, inRange: { color: ["#f0f2ff", "#635bff"] } },
        series: [{ type: "heatmap", label: { show: true }, data: charts.evidence_matrix.flatMap((item, index) => [[0, index, item.ipc_count], [1, index, item.paper_count]]) }],
      });
      const fusion = echarts.init(fusionRef.current);
      fusion.setOption({
        color: ["#635bff", "#4e83db", "#18a67b", "#e6a23c"],
        tooltip: { trigger: "item" },
        series: [{
          type: "sankey",
          data: [...new Set(charts.fusion_sankey.flatMap((item) => [item.source, item.target]))].map((name) => ({ name })),
          links: charts.fusion_sankey,
          lineStyle: { color: "gradient", curveness: .5, opacity: .35 },
          emphasis: { focus: "adjacency" },
          label: { color: "#4e566b", fontSize: 10 },
        }],
      });
      instances.push(trl, ipc, papers, matrix, fusion);
    });
    const resize = () => instances.forEach((item) => item.resize());
    window.addEventListener("resize", resize);
    return () => {
      disposed = true; window.removeEventListener("resize", resize);
      instances.forEach((item) => item.dispose());
    };
  }, [charts]);

  return (
    <div className="analysis-grid">
      <section className="surface chart-surface wide"><header><h2>技术成熟度路线</h2><span>{charts.baseline_year ?? 2025} 基线 → {charts.target_year ?? 2040}</span></header><div ref={trlRef} className="chart-box" role="img" aria-label={`技术成熟度从 ${charts.baseline_year} 基线到 ${charts.target_year} 目标年`} /><ChartAlternative summary="技术成熟度数据表" headers={["主题", "年份", "TRL"]} rows={charts.trl_series.flatMap((series) => series.data.map((item) => [series.name, item.year, item.value]))} /></section>
      <section className="surface chart-surface"><header><h2>IPC 指标趋势</h2><span>确定性计算</span></header><div ref={ipcRef} className="chart-box" role="img" aria-label="IPC 年度指标趋势" /><ChartAlternative summary="IPC 趋势数据表" headers={["主题", "IPC", "年份", "专利量", "中心度"]} rows={charts.ipc_trends.map((item) => [item.topic, item.ipc_code, item.year, item.patent_count, item.degree_centrality])} /></section>
      <section className="surface chart-surface"><header><h2>论文年度方向</h2><span>证据数量</span></header><div ref={papersRef} className="chart-box" role="img" aria-label="论文年度数量趋势" /><ChartAlternative summary="论文趋势数据表" headers={["主题", "年份", "数量"]} rows={charts.paper_trends.map((item) => [item.topic, item.year, item.count])} /></section>
      <section className="surface chart-surface wide"><header><h2>双通道证据矩阵</h2><span>IPC × 论文</span></header><div ref={matrixRef} className="chart-box small" role="img" aria-label="各主题 IPC 与论文证据数量矩阵" /><ChartAlternative summary="证据矩阵数据表" headers={["主题", "IPC 数量", "论文数量", "状态"]} rows={charts.evidence_matrix.map((item) => [item.topic, item.ipc_count, item.paper_count, item.status])} /></section>
      <section className="surface chart-surface wide"><header><h2>IPC 技术融合演化</h2><span>融合概率 Sankey</span></header><div ref={fusionRef} className="chart-box small" role="img" aria-label="IPC 技术融合关系" /><ChartAlternative summary="技术融合数据表" headers={["主题", "来源", "目标", "权重"]} rows={charts.fusion_sankey.map((item) => [item.topic, item.source, item.target, item.value])} /></section>
    </div>
  );
}
