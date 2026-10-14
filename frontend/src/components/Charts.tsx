import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { TopicRoadmap } from "../types";

const YEARS = ["2030", "2035", "2040"];
const PALETTE = [
  "#2c5f8a", "#c0504d", "#4f8a5b", "#8a6d2c", "#6a4c8a",
  "#3a8a8a", "#a85a7a", "#5a6a8a", "#7a8a3c",
];

function avgTrl(roadmap: TopicRoadmap, year: string): number | null {
  const ms = roadmap.stages[year] || [];
  if (!ms.length) return null;
  return Math.round(
    (ms.reduce((s, m) => s + m.trl_level, 0) / ms.length) * 100
  ) / 100;
}

function uncertaintyScore(level: string): number {
  return level === "low" ? 1 : level === "high" ? 3 : 2;
}

export function TrlChart({ roadmaps }: { roadmaps: TopicRoadmap[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current);
    chart.setOption({
      color: PALETTE,
      tooltip: { trigger: "axis" },
      legend: {
        type: "scroll",
        bottom: 0,
        textStyle: { fontSize: 11, color: "#555" },
      },
      grid: { left: 40, right: 20, top: 30, bottom: 60 },
      xAxis: {
        type: "category",
        data: YEARS,
        axisLine: { lineStyle: { color: "#bbb" } },
        axisLabel: { color: "#555" },
      },
      yAxis: {
        type: "value",
        min: 1,
        max: 9,
        name: "TRL",
        nameTextStyle: { color: "#888" },
        splitLine: { lineStyle: { color: "#eee" } },
      },
      series: roadmaps.map((r) => ({
        name: r.topic_name,
        type: "line",
        smooth: true,
        symbolSize: 7,
        data: YEARS.map((y) => avgTrl(r, y)),
      })),
    });
    const onResize = () => chart.resize();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.dispose();
    };
  }, [roadmaps]);
  return <div ref={ref} style={{ width: "100%", height: 380 }} />;
}

export function UncertaintyHeatmap({ roadmaps }: { roadmaps: TopicRoadmap[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current);
    const data: [number, number, number][] = [];
    roadmaps.forEach((r, ti) => {
      YEARS.forEach((y, yi) => {
        const ms = r.stages[y] || [];
        const score = ms.length
          ? ms.reduce((s, m) => s + uncertaintyScore(m.uncertainty_level), 0) /
            ms.length
          : 2;
        data.push([yi, ti, Math.round(score * 100) / 100]);
      });
    });
    chart.setOption({
      tooltip: {
        formatter: (p: { value: [number, number, number] }) => {
          const label = ["低", "中", "高"];
          const v = p.value[2];
          return `${roadmaps[p.value[1]].topic_name} · ${YEARS[p.value[0]]}<br/>不确定性：${
            v < 1.5 ? label[0] : v < 2.5 ? label[1] : label[2]
          }（${v}）`;
        },
      },
      grid: { left: 130, right: 30, top: 20, bottom: 50 },
      xAxis: {
        type: "category",
        data: YEARS,
        splitArea: { show: true },
      },
      yAxis: {
        type: "category",
        data: roadmaps.map((r) => r.topic_name),
        axisLabel: { fontSize: 11, color: "#555" },
        splitArea: { show: true },
      },
      visualMap: {
        min: 1,
        max: 3,
        orient: "horizontal",
        bottom: 0,
        inRange: { color: ["#e8f0e8", "#f0e6c8", "#e8c8c0"] },
        text: ["高", "低"],
      },
      series: [
        {
          type: "heatmap",
          data,
          label: { show: false },
          emphasis: { itemStyle: { shadowBlur: 8, shadowColor: "rgba(0,0,0,0.3)" } },
        },
      ],
    });
    const onResize = () => chart.resize();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.dispose();
    };
  }, [roadmaps]);
  return <div ref={ref} style={{ width: "100%", height: 420 }} />;
}
