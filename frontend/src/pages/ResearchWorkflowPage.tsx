import { useEffect, useState } from "react";
import { apiMutation, apiRequest } from "../api";
import { EvidenceBadge } from "../components/ResearchSemantics";
import { ScientificChartPanel, type ScientificChart } from "../components/ScientificChartPanel";
import type { DataQuality, FusionPrediction, NetworkRun, Project, ResearchDesign } from "../types";

type Step = "research-design" | "data-quality" | "network-evolution" |
  "fusion-forecast" | "technology-themes" | "roadmap-report";

type Props = { apiBase: string; project: Project; step: Step; onChanged: () => Promise<void>; notify: (message: string) => void };

const titles: Record<Step, [string, string]> = {
  "research-design": ["研究设计", "冻结研究问题、数据截止与预测目标，任何新版本都会显式标记下游产物过期。"],
  "data-quality": ["数据质量", "核查 2010—2025 覆盖、IPC 映射、论文类型与部分年度偏差。"],
  "network-evolution": ["网络演化", "比较年度与三阶段 IPC 共现网络，追踪中心性、社群与边缘—核心迁移。"],
  "fusion-forecast": ["融合预测", "分离首次出现与显著增强候选；概率仅由经验证模型提供。"],
  "technology-themes": ["技术主题", "将获批 IPC 融合对与专利、论文证据合成为可批判、可编辑的技术主题。"],
  "roadmap-report": ["路线图与报告", "在发布门通过后生成 2030 / 2035 / 2040 累积路线图和可复现研究包。"],
};

function Empty({ children }: { children: string }) { return <div className="table-empty">{children}</div>; }

export function ResearchWorkflowPage({ apiBase, project, step, onChanged, notify }: Props) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [question, setQuestion] = useState("哪些 IPC 技术融合将在 2040 年前形成智能建造领域的新兴关键技术？");
  const [target, setTarget] = useState("both");
  const [cutoff, setCutoff] = useState("2025-10-01");
  const [ipcLevel, setIpcLevel] = useState("main_group");
  const [completeness, setCompleteness] = useState("include_partial_with_sensitivity");
  const [selectedRun, setSelectedRun] = useState<string>("");
  const [networkView, setNetworkView] = useState("period:2020_2025");
  const [networkDetail, setNetworkDetail] = useState<any>(null);
  const [edgeThreshold, setEdgeThreshold] = useState(0);
  const [edgeEvidence, setEdgeEvidence] = useState<any>(null);
  const [candidateDetail, setCandidateDetail] = useState<any>(null);
  const [error, setError] = useState("");
  const [exportResult, setExportResult] = useState<any>(null);
  const [provenanceDetail, setProvenanceDetail] = useState<any>(null);

  const load = async () => {
    setLoading(true); setError("");
    try {
      if (step === "research-design") {
        const [versions, stale] = await Promise.all([
          apiRequest<{items: ResearchDesign[]}>(apiBase, `/projects/${project.project_id}/research-designs`),
          apiRequest<Record<string, number>>(apiBase, `/projects/${project.project_id}/stale-artifacts`),
        ]); setData({...versions, stale});
      }
      if (step === "data-quality") setData(await apiRequest<DataQuality>(apiBase, `/research/projects/${project.project_id}/data-quality`));
      if (step === "network-evolution") {
        const [runs, charts] = await Promise.all([
          apiRequest<{items: NetworkRun[]}>(apiBase, `/research/projects/${project.project_id}/network-runs`),
          apiRequest<{items: ScientificChart[]}>(apiBase, `/research/projects/${project.project_id}/chart-data`),
        ]); setData({...runs, charts: charts.items});
      }
      if (["fusion-forecast", "technology-themes", "roadmap-report"].includes(step)) {
        const readiness = await apiRequest<any>(apiBase, `/projects/${project.project_id}/readiness`);
        const jobId = readiness.graph_checkpoint?.job_id;
        if (step === "fusion-forecast") {
          const models = await apiRequest<any>(apiBase, `/research/projects/${project.project_id}/model-runs`);
          const predictions = models.items?.[0] ? await apiRequest<any>(apiBase, `/research/model-runs/${models.items[0].model_run_id}/predictions`) : {items: []};
          const charts = await apiRequest<any>(apiBase, `/research/projects/${project.project_id}/chart-data`);
          const graph = jobId ? await apiRequest<any>(apiBase, `/research/graph/jobs/${jobId}`) : null;
          const events = jobId ? await apiRequest<any>(apiBase, `/research/graph/jobs/${jobId}/events`) : {items: []};
          setData({items: predictions.items, models: models.items, charts: charts.items, jobId, graph, events: events.items, missingJob: !jobId}); return;
        }
        if (!jobId) { setData({items: [], missingJob: true}); return; }
        const path = step === "technology-themes" ? "themes" : step === "roadmap-report" ? "dossiers" : "manifest";
        const [payload, graph, events] = await Promise.all([
          apiRequest<any>(apiBase, `/research/graph/jobs/${jobId}/${path}`),
          apiRequest<any>(apiBase, `/research/graph/jobs/${jobId}`),
          apiRequest<any>(apiBase, `/research/graph/jobs/${jobId}/events`),
        ]); setData({...payload, jobId, graph, events: events.items});
      }
    } catch (cause) { setError((cause as Error).message); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, [project.project_id, step]);

  const createDesign = async () => {
    try {
      const design = await apiMutation<ResearchDesign>(`design:${project.project_id}`, apiBase, `/projects/${project.project_id}/research-designs`, {
        method: "POST", body: JSON.stringify({research_question: question, candidate_target: target,
          data_cutoff: cutoff, ipc_analysis_level: ipcLevel, completeness_policy: completeness,
          parameters: {forecast_nodes: [2030, 2035, 2040], sensitivity_partial_2025: true}}),
      });
      notify(`研究设计 v${design.version} 已保存，确认后方可冻结数据`); await load();
    } catch (cause) { setError((cause as Error).message); }
  };
  const confirmDesign = async (id: string) => {
    try { await apiMutation(`confirm:${id}`, apiBase, `/projects/${project.project_id}/research-designs/${id}/confirm`, {method: "POST"}); notify("研究设计已确认"); await load(); await onChanged(); }
    catch (cause) { setError((cause as Error).message); }
  };
  const createNetwork = async () => {
    try { const response = await apiMutation<any>(`network:${project.project_id}`, apiBase, `/research/projects/${project.project_id}/network-runs`, {method: "POST", body: "{}"}); setSelectedRun(response.run?.network_run_id ?? ""); notify("确定性网络运行已完成"); await load(); await onChanged(); }
    catch (cause) { setError((cause as Error).message); }
  };
  const inspectNetwork = async (runId: string, view = networkView) => {
    const [kind, key] = view.split(":");
    const edgeQuery = kind === "annual" ? `year=${key}` : `period_code=${key}`;
    const nodeQuery = `observation_kind=${kind === "annual" ? "year" : "period"}&observation_key=${key}`;
    try { const [status, nodes, edges, transitions, communities] = await Promise.all([
      apiRequest<any>(apiBase, `/research/network-runs/${runId}`),
      apiRequest<any>(apiBase, `/research/network-runs/${runId}/nodes?${nodeQuery}`),
      apiRequest<any>(apiBase, `/research/network-runs/${runId}/edges?${edgeQuery}`),
      apiRequest<any>(apiBase, `/research/network-runs/${runId}/trajectories`),
      apiRequest<any>(apiBase, `/research/network-runs/${runId}/communities`),
    ]); setSelectedRun(runId); setNetworkView(view); setNetworkDetail({status, nodes: nodes.items, edges: edges.items, transitions: transitions.items, communities: communities.items}); }
    catch (cause) { setError((cause as Error).message); }
  };
  const inspectEdge = async (edge: any) => {
    try { setEdgeEvidence(await apiRequest(apiBase, `/research/network-runs/${selectedRun}/edge-evidence?ipc1=${encodeURIComponent(edge.ipc1)}&ipc2=${encodeURIComponent(edge.ipc2)}`)); }
    catch (cause) { setError((cause as Error).message); }
  };
  const reviewCandidate = async (item: FusionPrediction, decision: "approve" | "edit" | "reject") => {
    if (!data.jobId) { setError("请先启动图任务，候选评审必须写入持久检查点"); return; }
    const note = decision === "edit" ? window.prompt("输入候选解释或标签注释（不会修改模型概率和排名）", "") : "";
    if (decision === "edit" && note === null) return;
    try { await apiMutation(`candidate:${item.candidate_id}:${decision}`, apiBase, `/research/fusion-candidates/${item.candidate_id}/review`, {method: "POST", body: JSON.stringify({job_id: data.jobId, decision, after: decision === "edit" ? {researcher_note: note} : {}, reason: decision === "approve" ? "证据与模型输出已核验" : decision === "edit" ? "补充研究者元数据" : "证据不足"})}); notify(decision === "approve" ? "候选已批准" : decision === "edit" ? "元数据注释已保存" : "候选已拒绝"); setCandidateDetail(await apiRequest(apiBase, `/research/fusion-candidates/${item.candidate_id}`)); }
    catch (cause) { setError((cause as Error).message); }
  };
  const inspectCandidate = async (candidateId: string) => {
    try { setCandidateDetail(await apiRequest(apiBase, `/research/fusion-candidates/${candidateId}`)); }
    catch (cause) { setError((cause as Error).message); }
  };
  const graphAction = async (action: string) => {
    if (!data.jobId) return;
    try { await apiMutation(`graph:${data.jobId}:${action}`, apiBase, `/research/graph/jobs/${data.jobId}/${action}`, {method: "POST"}); notify(`图任务操作：${action}`); await load(); }
    catch (cause) { setError((cause as Error).message); }
  };
  const graphReview = async (decision: "approve" | "edit" | "reject") => {
    const node = data?.graph?.current_node;
    if (!data?.jobId || !["fusion_review", "theme_review", "publication_review"].includes(node)) return;
    const reason = window.prompt("填写评审理由", decision === "approve" ? "已核验当前证据、限制与结构化结果" : "") ?? "";
    if (!reason.trim()) { setError("评审理由不能为空"); return; }
    try { await apiMutation(`interrupt:${data.jobId}:${node}:${decision}`, apiBase, `/research/graph/jobs/${data.jobId}/reviews/${node}`, {method: "POST", body: JSON.stringify({decision, reason, after: {reviewed_from: step}})}); notify("中断点评审已提交"); await load(); }
    catch (cause) { setError((cause as Error).message); }
  };
  const reviewTheme = async (item: any, decision: "approve" | "edit" | "reject", operation = "") => {
    const themeId = item.theme_id ?? item.id ?? "theme";
    let after: Record<string, unknown> = {}, themeIds: string[] = [];
    if (operation === "rename") { const name = window.prompt("输入新的主题名称", item.theme_name ?? item.concept_name ?? ""); if (!name) return; after = {operation, theme_name: name}; }
    if (operation === "merge") { const ids = window.prompt("输入至少两个待合并主题 ID，以逗号分隔", themeId); if (!ids) return; themeIds = ids.split(",").map((value) => value.trim()).filter(Boolean); after = {operation}; }
    try { await apiMutation(`theme:${themeId}:${decision}:${operation}`, apiBase, `/research/graph/jobs/${data.jobId}/themes/${themeId}/review`, {method: "POST", body: JSON.stringify({job_id: data.jobId, decision, after, theme_ids: themeIds, reason: decision === "approve" ? "主题定义及证据链已核验" : decision === "edit" ? `执行主题${operation}` : "主题证据不足"})}); notify("主题评审已记录"); await load(); }
    catch (cause) { setError((cause as Error).message); }
  };
  const exportBundle = async () => {
    try { const result = await apiMutation<any>(`export:${data.jobId}`, apiBase, `/research/graph/jobs/${data.jobId}/exports`, {method: "POST", body: JSON.stringify({bibliography: []})}); setExportResult(result); notify("可复现研究包已生成"); await onChanged(); }
    catch (cause) { setError((cause as Error).message); }
  };
  const regenerateAssets = async () => {
    try { const result = await apiMutation<any>(`regenerate:${project.project_id}`, apiBase, `/research/projects/${project.project_id}/assets/regenerate`, {method: "POST"}); notify(`已从冻结输入重生成 ${result.items.length} 组图件，未重跑模型或 Agent`); }
    catch (cause) { setError((cause as Error).message); }
  };
  const inspectProvenance = async (themeId: string, evidenceId: string) => {
    try { setProvenanceDetail(await apiRequest(apiBase, `/research/graph/jobs/${data.jobId}/provenance?theme_id=${encodeURIComponent(themeId)}&evidence_id=${encodeURIComponent(evidenceId)}`)); }
    catch (cause) { setError((cause as Error).message); }
  };

  const [title, subtitle] = titles[step];
  return <>
    <header className="page-heading"><div><span className="eyebrow">RESEARCH CONTRACT v3</span><h1>{title}</h1><p>{subtitle}</p></div><div className="semantic-legend"><EvidenceBadge state="observed"/><EvidenceBadge state="derived"/><EvidenceBadge state="predicted"/><EvidenceBadge state="agent"/><EvidenceBadge state="reviewed"/></div></header>
    {error ? <div className="error-banner">{error}</div> : null}
    {loading ? <section className="surface"><Empty>正在读取冻结研究上下文…</Empty></section> : null}
    {!loading && step === "research-design" ? <div className="research-grid">
      <section className="surface form-surface"><div className="surface-header"><div><h2>创建研究设计版本</h2><p>默认取自《第四章 面向2040的智能建造关键技术》的研究边界</p></div><EvidenceBadge state="reviewed"/></div><div className="research-form"><label>研究问题<textarea value={question} onChange={(e) => setQuestion(e.target.value)}/></label><div className="design-options"><label>候选目标<select value={target} onChange={(e) => setTarget(e.target.value)}><option value="both">首次出现 + 显著增强</option><option value="emergence">首次出现</option><option value="strengthening">显著增强</option></select></label><label>数据截止<input type="date" value={cutoff} max="2025-12-31" onChange={(e) => setCutoff(e.target.value)}/></label><label>IPC 层级<select value={ipcLevel} onChange={(e) => setIpcLevel(e.target.value)}><option value="main_group">主组</option><option value="subclass">小类</option><option value="subgroup">分组</option></select></label><label>完整性策略<select value={completeness} onChange={(e) => setCompleteness(e.target.value)}><option value="include_partial_with_sensitivity">纳入部分 2025，并做敏感性分析</option><option value="exclude_partial">排除部分年度</option></select></label></div><div className="integrity-note">影响预览：确认新版本后，已有网络 {data?.stale?.network_runs ?? 0}、图任务 {data?.stale?.graph_threads ?? 0}、导出 {data?.stale?.exports ?? 0} 将保留但标记为过期。</div><button className="primary-button" onClick={createDesign}>保存新版本</button></div></section>
      <section className="surface"><div className="surface-header"><h2>版本历史</h2></div>{data?.items?.length ? data.items.map((item: ResearchDesign) => <article className="research-list-row" key={item.design_id}><div><strong>v{item.version} · {item.status === "confirmed" ? "已确认" : "草稿"}</strong><p>{item.research_question}</p><small>{item.data_cutoff} · {item.ipc_analysis_level} · {item.checksum.slice(0, 12)}</small></div>{item.status !== "confirmed" ? <button className="outline-button" onClick={() => confirmDesign(item.design_id)}>确认并冻结边界</button> : <EvidenceBadge state="reviewed"/>}</article>) : <Empty>尚无研究设计版本</Empty>}</section>
    </div> : null}
    {!loading && step === "data-quality" ? <div className="research-grid"><section className="surface"><div className="surface-header"><div><h2>时间覆盖与重建等级</h2><p>重建等级：{data.reconstruction_grade} · 重复专利 {data.duplicate_count ?? 0} · 未解析映射 {data.unresolved_mapping_count ?? 0}</p></div><EvidenceBadge state="observed"/></div>{data.partial_year_warnings?.map((text: string) => <div className="warning-banner" key={text}>{text}</div>)}<div className="metric-grid four"><div className="metric-card"><small>叶节点</small><strong>{data.coverage?.leaf_count ?? 0}</strong><p>纳入技术范围</p></div><div className="metric-card green"><small>论文类型</small><strong>{data.paper_types?.length ?? 0}</strong><p>受控分类</p></div><div className="metric-card amber"><small>IPC 映射状态</small><strong>{data.ipc_mappings?.length ?? 0}</strong><p>原始值保留</p></div><div className="metric-card red"><small>异常导入</small><strong>{data.invalid_records?.length ?? 0}</strong><p>需人工复核</p></div></div><div className="coverage-calendar">{Object.entries(data.coverage?.periods ?? {}).map(([period, values]: [string, any]) => <article key={period}><strong>{period.replace("_", "—")}</strong><span>{values.patent_records ?? values.ipc_records ?? 0} 专利/IPC</span><span>{values.paper_records ?? 0} 论文</span></article>)}</div><a className="outline-button remediation-link" href={`/library?scope_node_id=${project.technology_node_id ?? ""}`}>前往基础数据修复</a></section><section className="surface"><div className="surface-header"><h2>论文类型分布</h2></div>{data.paper_types?.length ? data.paper_types.map((item: any) => <article className="research-list-row" key={item.paper_type}><strong>{item.paper_type}</strong><span>{item.count} 条</span></article>) : <Empty>尚无已映射论文数据</Empty>}</section></div> : null}
    {!loading && step === "network-evolution" ? <><section className="surface"><div className="surface-header"><div><h2>确定性动态 IPC 网络</h2><p>布局只用于跨期比较，不进入模型特征</p></div><button className="primary-button" onClick={createNetwork}>构建 / 复用网络</button></div>{data.items?.length ? data.items.map((item: NetworkRun) => <article className={`research-list-row ${selectedRun === item.network_run_id ? "selected" : ""}`} key={item.network_run_id}><button className="row-title" onClick={() => inspectNetwork(item.network_run_id)}><strong>{item.algorithm_version} · {item.status}</strong><small>{item.network_run_id} · {item.result_checksum?.slice(0, 12)}</small></button><div><EvidenceBadge state="derived"/><span className="grade-label">{item.evidence_grade}</span></div></article>) : <Empty>确认研究设计并发布数据后，可构建网络</Empty>}</section>{networkDetail ? <section className="surface"><div className="surface-header"><div><h2>联动观测与来源溯源</h2><p>{networkDetail.status.network_run_id} · 算法 {networkDetail.status.algorithm_version}</p></div><div className="network-controls"><select value={networkView} onChange={(e) => inspectNetwork(selectedRun, e.target.value)}><optgroup label="报告期"><option value="period:2010_2014">2010—2014</option><option value="period:2015_2019">2015—2019</option><option value="period:2020_2025">2020—2025</option></optgroup><optgroup label="年度"><option value="annual:2023">2023</option><option value="annual:2024">2024</option><option value="annual:2025">2025（部分）</option></optgroup></select><label>最小关联强度 {edgeThreshold.toFixed(2)}<input type="range" min="0" max="1" step="0.05" value={edgeThreshold} onChange={(e) => setEdgeThreshold(Number(e.target.value))}/></label></div></div><div className="data-table"><div className="table-head network-v3"><span>IPC 边</span><span>支持数</span><span>关联 / Jaccard / PMI</span><span>证据等级</span></div>{networkDetail.edges?.filter((edge: any) => Number(edge.association_strength ?? 0) >= edgeThreshold).slice(0, 100).map((edge: any) => <button className="table-row network-v3 network-edge-row" key={edge.edge_id} onClick={() => inspectEdge(edge)}><code>{edge.ipc1} × {edge.ipc2}</code><span>{edge.supporting_patent_count}</span><span>{Number(edge.association_strength ?? 0).toFixed(3)} / {Number(edge.jaccard ?? 0).toFixed(3)} / {Number(edge.pmi ?? 0).toFixed(3)}</span><span>{edge.evidence_grade}</span></button>)}</div><div className="network-summary"><span>节点 {networkDetail.nodes?.length ?? 0}</span><span>社群记录 {networkDetail.communities?.length ?? 0}</span><span>迁移记录 {networkDetail.transitions?.length ?? 0}</span></div>{edgeEvidence ? <aside className="provenance-drawer"><div><h3>边证据</h3><button className="text-action" onClick={() => setEdgeEvidence(null)}>关闭</button></div><pre>{JSON.stringify(edgeEvidence, null, 2)}</pre></aside> : null}</section> : null}<div className="chart-grid">{data.charts?.map((chart: ScientificChart) => <ScientificChartPanel chart={chart} key={chart.checksum}/>)}</div></> : null}
    {!loading && step === "fusion-forecast" ? <><section className="surface"><div className="surface-header"><h2>模型权威融合候选</h2><EvidenceBadge state="predicted"/></div><div className="integrity-note">排名、概率和区间只能由确定性模型写入；Agent 仅解释证据，人工仅编辑元数据。</div>{data.items?.length ? <div className="data-table"><div className="table-head fusion-v3"><span>排名 / 类型</span><span>IPC 融合对</span><span>概率状态 / 区间</span><span>稳定性</span><span>人工评审</span></div>{data.items.map((item: FusionPrediction) => <div className="table-row fusion-v3" key={item.candidate_id}><span><strong>#{item.rank}</strong><small>{item.target_type}</small></span><button className="row-title" onClick={() => inspectCandidate(item.candidate_id)}><code>{item.ipc1} × {item.ipc2}</code><small>查看特征与证据链</small></button><span>{item.calibrated_probability == null ? `分数 ${item.raw_score.toFixed(3)}` : `${(item.calibrated_probability * 100).toFixed(1)}%`}<small>{item.interval_low == null ? "区间不可估计" : `[${item.interval_low.toFixed(2)}, ${item.interval_high?.toFixed(2)}]`}</small></span><span>{item.stability_status}</span><div className="row-actions"><button className="text-action" onClick={() => reviewCandidate(item, "approve")}>批准</button><button className="text-action" onClick={() => reviewCandidate(item, "edit")}>注释</button><button className="text-action danger" onClick={() => reviewCandidate(item, "reject")}>拒绝</button></div></div>)}</div> : <Empty>尚无完成的模型候选；先生成特征并完成历史标签验证</Empty>}</section>{candidateDetail ? <section className="surface"><div className="surface-header"><div><h2>{candidateDetail.ipc1} × {candidateDetail.ipc2} 溯源</h2><p>截断 {candidateDetail.cutoff_year} · {candidateDetail.target_type} · {candidateDetail.schema_version}</p></div><button className="text-action" onClick={() => setCandidateDetail(null)}>关闭</button></div><div className="feature-contributions">{candidateDetail.features?.map((feature: any) => <article key={feature.feature_name}><strong>{feature.feature_name}</strong><b>{feature.feature_value == null ? "NA" : Number(feature.feature_value).toFixed(4)}</b><small>{feature.feature_status} · {feature.lineage?.source_kind} · cutoff {feature.lineage?.cutoff_year}</small></article>)}</div>{candidateDetail.reviews?.map((review: any) => <div className="integrity-note" key={review.review_id}>人工 {review.decision} · {review.reason}</div>)}</section> : null}<div className="chart-grid">{data.charts?.filter((chart: ScientificChart) => chart.chart_kind === "fusion_ranking").map((chart: ScientificChart) => <ScientificChartPanel chart={chart} key={chart.checksum}/>)}</div></> : null}
    {!loading && step === "technology-themes" ? <><section className="surface"><div className="surface-header"><div><h2>技术主题、证据与语义簇</h2><p>已批准 IPC 融合对 {data.approved_pairs?.length ?? 0} · 专利/论文分析 {data.evidence_results?.length ?? 0}</p></div><EvidenceBadge state="agent"/></div>{data.approved_pairs?.length ? <div className="approved-pairs">{data.approved_pairs.map((pair: any) => <code key={pair.candidate_id}>{pair.ipc1} × {pair.ipc2} · {pair.target_type}</code>)}</div> : null}{data.missingJob || !data.items?.length ? <Empty>融合候选评审通过后生成主题</Empty> : data.items.map((item: any, index: number) => <article className="theme-card" key={item.theme_id ?? item.id ?? index}><span className="theme-index">T{index + 1}</span><div><h3>{item.theme_name ?? item.concept_name ?? item.name ?? `技术主题 ${index + 1}`}</h3><p>{item.description ?? item.summary ?? item.mechanism ?? "结构化主题结果"}</p><small>IPC：{(item.ipc_pairs ?? []).join(" · ")} · 证据：{(item.evidence_ids ?? []).join("、")}</small></div><div className="theme-actions"><EvidenceBadge state={data.confirmed ? "reviewed" : "agent"}/><button className="text-action" onClick={() => reviewTheme(item, "approve")}>确认</button><button className="text-action" onClick={() => reviewTheme(item, "edit", "rename")}>重命名</button><button className="text-action" onClick={() => reviewTheme(item, "edit", "merge")}>合并</button><button className="text-action danger" onClick={() => reviewTheme(item, "reject")}>拒绝</button></div></article>)}</section>{data.critic_findings?.length ? <section className="surface"><div className="surface-header"><h2>科学批评</h2></div>{data.critic_findings.map((item: any, index: number) => <article className="research-list-row" key={index}><strong>{item.category} · {item.severity}</strong><p>{item.message}</p></article>)}</section> : null}{data.reviews?.length ? <section className="surface"><div className="surface-header"><h2>主题评审历史</h2></div>{data.reviews.map((review: any) => <article className="research-list-row" key={review.review_id}><strong>{review.decision} · {review.target_id}</strong><span>{review.reason}</span><small>{review.reviewer} · {review.created_at}</small></article>)}</section> : null}</> : null}
    {!loading && step === "roadmap-report" ? <><section className="surface"><div className="surface-header"><div><h2>2030—2040 累积技术路线图</h2><p>基准 / 加速 / 约束情景，里程碑均链接到主题与证据</p></div><div className="row-actions"><button className="outline-button" onClick={regenerateAssets}>重生成图件</button><button className="primary-button" onClick={exportBundle}>生成研究包</button></div></div>{data.missingJob || (!data.items?.length && !data.roadmaps?.length) ? <Empty>需完成主题评审和发布门评审</Empty> : <div className="roadmap-v3">{data.items?.map((theme: any) => <article key={theme.theme_id}><header><EvidenceBadge state="agent"/><h3>{theme.theme_name}</h3><p>{theme.summary}</p></header><div className="milestone-row">{theme.milestones?.map((milestone: any) => <section key={milestone.year}><b>{milestone.year}</b><strong>{milestone.name}</strong><span>TRL {milestone.trl ?? "不可估计"} · 不确定性 {milestone.uncertainty}</span><p>{milestone.description}</p><small>证据：{milestone.evidence_ids?.join("、")}</small>{milestone.evidence_ids?.[0] ? <button className="text-action" onClick={() => inspectProvenance(theme.theme_id, milestone.evidence_ids[0])}>追溯到来源与图节点</button> : null}</section>)}</div>{theme.limitations?.map((value: string) => <div className="warning-banner" key={value}>{value}</div>)}</article>)}{data.roadmaps?.map((roadmap: any) => <article key={roadmap.theme_id}><h3>情景比较 · {roadmap.theme_id}</h3><div className="scenario-grid">{roadmap.scenarios?.map((scenario: any) => <section key={scenario.name}><strong>{scenario.name}</strong><small>{scenario.assumptions?.join("；")}</small>{scenario.milestones?.map((milestone: any) => <p key={milestone.year}><b>{milestone.year}</b> {milestone.name} · TRL {milestone.trl ?? "NA"}</p>)}</section>)}</div></article>)}</div>}</section>{provenanceDetail ? <section className="surface"><div className="surface-header"><div><h2>端到端溯源</h2><p>里程碑 → 主题 → IPC/特征 → 网络 → 来源 → 图节点 → 人工评审</p></div><button className="text-action" onClick={() => setProvenanceDetail(null)}>关闭</button></div><div className="provenance-chain"><span>主题 {provenanceDetail.theme?.theme_name ?? "—"}</span><span>来源 {provenanceDetail.sources?.length ?? 0}</span><span>科学产物 {provenanceDetail.artifact_refs?.length ?? 0}</span><span>节点事件 {provenanceDetail.events?.length ?? 0}</span><span>评审 {provenanceDetail.reviews?.length ?? 0}</span></div><pre className="scientific-json">{JSON.stringify(provenanceDetail, null, 2)}</pre></section> : null}<section className="surface"><div className="surface-header"><div><h2>发布门与导出</h2><p>只有人工发布评审完成后才能导出</p></div><EvidenceBadge state="reviewed"/></div><pre className="scientific-json">{JSON.stringify(data.publication_gates ?? {}, null, 2)}</pre>{exportResult?.download_url ? <a className="primary-button bundle-download" href={`${apiBase.replace(/\/api\/?$/, "")}${exportResult.download_url}`}>下载研究包 · {exportResult.manifest?.checksum?.slice(0, 12)}</a> : null}</section></> : null}
    {data?.jobId ? <section className="surface graph-panel"><div className="surface-header"><div><h2>LangGraph 执行与审计</h2><p>任务 {data.jobId} · {data.graph?.status ?? "unknown"} · 当前节点 {data.graph?.current_node ?? "—"}</p></div><div className="row-actions">{data.graph?.status === "interrupted" ? <><button className="primary-button" onClick={() => graphReview("approve")}>批准继续</button><button className="outline-button" onClick={() => graphReview("edit")}>编辑后继续</button><button className="outline-button" onClick={() => graphReview("reject")}>拒绝</button></> : null}{data.graph?.status === "failed" ? <button className="outline-button" onClick={() => graphAction("retry")}>重试失败节点</button> : null}<button className="outline-button" onClick={() => graphAction("resume")}>继续</button><button className="outline-button" onClick={() => graphAction("cancel")}>取消</button><button className="outline-button" onClick={() => graphAction("abandon")}>放弃</button></div></div><div className="graph-events">{data.events?.slice(-12).map((event: any) => <article key={event.event_id}><span>{event.event_type}</span><strong>{event.node_name}</strong><small>{event.created_at}</small></article>)}</div></section> : null}
  </>;
}
