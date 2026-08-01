import { useState } from "react";
import { assetUrl, apiRequest } from "../api";
import type { Asset, ChartData, EvidenceItem, Job, Result, ResultTopic } from "../types";
import { ForecastCharts } from "../components/ForecastCharts";
import { EmptyState, Metric, Modal, PageHeading, StatusPill } from "../components/UI";

export function ResultsPage({
  apiBase, job, result, charts, topics, assets,
}: {
  apiBase: string; job: Job | null; result: Result | null; charts: ChartData | null;
  topics: ResultTopic[]; assets: Asset[];
}) {
  const [tab, setTab] = useState<"roadmap" | "evidence" | "assets" | "conclusion">("roadmap");
  const [preview, setPreview] = useState<Asset | null>(null);
  const [evidence, setEvidence] = useState<EvidenceItem | null>(null);
  const [detail, setDetail] = useState<{
    topic_name: string;
    stages: Record<string, {
      stage_description?: string;
      milestones?: Array<{
        name?: string; description?: string; trl_level?: number;
        uncertainty_level?: string; evidence_ids?: string[];
      }>;
    }>;
  } | null>(null);
  const showEvidence = async (evidenceId: string) => {
    if (!result?.project_id) return;
    setDetail(null);
    setEvidence(await apiRequest<EvidenceItem>(apiBase, `/projects/${result.project_id}/evidence-items/${evidenceId}`));
  };
  const showTopic = async (topicId: string) => {
    setDetail(await apiRequest(apiBase, `/forecast/jobs/${job?.job_id}/topics/${topicId}`));
  };
  if (!job || !result) return <><PageHeading eyebrow="RESULT CENTER" title="结果分析" description="预测任务完成后在此查看路线图、双通道证据与报告资产。" /><EmptyState title="暂无可展示结果" note="请先完成证据审阅并启动预测任务。" /></>;
  return (
    <>
      <PageHeading
        eyebrow="ACADEMIC FORECAST RESULT" title="技术预测结果"
        description={`任务 ${job.job_id} · 预测节点 2030 / 2035 / 2040`}
        actions={<div className="heading-actions"><a className="outline-button" href={`${apiBase}/forecast/jobs/${job.job_id}/export?format=markdown`}>导出报告</a><a className="primary-button" href={`${apiBase}/forecast/jobs/${job.job_id}/export?format=json`}>导出 JSON</a></div>}
      />
      {result.evidence_limited ? <div className="warning-banner"><strong>证据受限预测</strong><span>{result.override_reason}</span></div> : null}
      {result.asset_summary.failed_count > 0 ? <div className="error-banner"><strong>图表资产生成不完整</strong><span><StatusPill status="asset_failed" /> 失败 {result.asset_summary.failed_count} 项，预测结论不受影响。</span></div> : null}
      <div className="metric-grid four compact">
        <Metric label="预测主题" value={topics.length} note="分主题路线已生成" />
        <Metric label="平均置信度" value={result.confidence_summary.average ?? "—"} note="基于有效模型结果" tone="green" />
        <Metric label="图表资产" value={result.asset_summary.count} note={`${result.asset_summary.failed_count} 个生成失败`} tone="amber" />
        <Metric label="任务状态" value={<StatusPill status={job.status} />} note="阶段状态独立记录" tone="red" />
      </div>
      <div className="tab-bar result-tabs">
        <button className={tab === "roadmap" ? "active" : ""} onClick={() => setTab("roadmap")}>路线与趋势</button>
        <button className={tab === "evidence" ? "active" : ""} onClick={() => setTab("evidence")}>证据解释</button>
        <button className={tab === "assets" ? "active" : ""} onClick={() => setTab("assets")}>图表资产</button>
        <button className={tab === "conclusion" ? "active" : ""} onClick={() => setTab("conclusion")}>方法与结论</button>
      </div>
      {tab === "roadmap" && charts ? <><ForecastCharts charts={charts} /><section className="surface roadmap-table"><header className="surface-header"><div><h2>分主题发展路线</h2><p>点击主题查看节点与证据引用</p></div></header><div className="data-table"><div className="table-head result-topic-list"><span>技术主题</span><span>节点</span><span>终期 TRL</span><span>不确定性</span><span>状态</span></div>{topics.map((topic) => <div className="table-row result-topic-list" key={topic.topic_id}><button className="row-title" onClick={() => showTopic(topic.topic_id)}><strong>{topic.topic_name}</strong><small>查看完整路线</small></button><span>{topic.available_years.join(" / ")}</span><span>{topic.terminal_trl ?? "—"}</span><span>{topic.dominant_uncertainty}</span><StatusPill status={result.stage_quality.roadmaps === "fallback" ? "fallback" : "completed"} /></div>)}</div></section></> : null}
      {tab === "evidence" && charts ? <div className="evidence-result-grid">{charts.evidence_matrix.map((item) => <section className="surface evidence-summary" key={item.topic}><header><strong>{item.topic}</strong><StatusPill status={item.status === "convergent" ? "published" : "needs_review"} /></header><div><span>IPC 证据<b>{item.ipc_count}</b></span><span>论文证据<b>{item.paper_count}</b></span></div><p>{charts.paper_directions.filter((direction) => direction.topic === item.topic).slice(0, 5).map((direction) => direction.keyword).join(" · ") || "暂无论文关键词"}</p></section>)}{charts.ipc_trends.slice(0, 20).map((item) => <button className="evidence-link" key={item.evidence_id} onClick={() => showEvidence(item.evidence_id)}><span>{item.ipc_code} · {item.year}</span><strong>查看证据</strong></button>)}{charts.representative_papers.slice(0, 10).map((paper) => <button className="evidence-link" key={paper.evidence_id} onClick={() => showEvidence(paper.evidence_id)}><span>{paper.title} · {paper.year}</span><strong>论文证据</strong></button>)}</div> : null}
      {tab === "assets" ? <div className="asset-gallery">{assets.map((asset) => <button key={asset.asset_id} onClick={() => setPreview(asset)}><span>{asset.kind}</span><strong>{asset.topic_name || "全主题比较"}</strong><small>{asset.title}</small></button>)}</div> : null}
      {tab === "conclusion" ? <section className="surface conclusion-panel"><span>综合结论</span><h2>{result.round2_result.new_paradigm_name || "尚未形成稳定范式"}</h2><p>{result.academic_conclusion}</p><div><strong>阶段质量</strong><code>{JSON.stringify(result.stage_quality, null, 2)}</code></div></section> : null}
      {preview ? <Modal title={`${preview.topic_name || "全主题"} · ${preview.title}`} wide onClose={() => setPreview(null)}><img className="asset-preview" src={assetUrl(apiBase, preview.url)} alt={preview.title} /><div className="modal-actions"><a className="primary-button" href={assetUrl(apiBase, preview.download_url)}>下载 PNG</a></div></Modal> : null}
      {evidence ? <Modal title="证据详情" onClose={() => setEvidence(null)}><div className="evidence-detail"><StatusPill status={evidence.evidence_type} /><h3>{evidence.title}</h3><p>{evidence.content}</p><code>{evidence.evidence_id}</code></div></Modal> : null}
      {detail ? <Modal title={detail.topic_name} wide onClose={() => setDetail(null)}><div className="roadmap-detail">{["2025", "2030", "2035", "2040"].map((year) => <section key={year}><header><strong>{year}</strong><span>{detail.stages[year]?.stage_description}</span></header>{detail.stages[year]?.milestones?.map((milestone, index) => <article key={index}><div><b>{milestone.name}</b><small>TRL {milestone.trl_level ?? "—"} · {milestone.uncertainty_level}</small></div><p>{milestone.description}</p><div>{milestone.evidence_ids?.map((id) => <button key={id} onClick={() => showEvidence(id)}>{id}</button>)}</div></article>)}</section>)}</div></Modal> : null}
    </>
  );
}
