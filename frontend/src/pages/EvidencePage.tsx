import { useEffect, useMemo, useState } from "react";
import { apiRequest } from "../api";
import type { Dataset, EvidencePackage, Project, Topic } from "../types";
import { EmptyState, Metric, PageHeading, StatusPill } from "../components/UI";

export function EvidencePage({
  apiBase, project, onForecast,
}: { apiBase: string; project: Project; onForecast: () => void }) {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [activeTopic, setActiveTopic] = useState("");
  const [evidence, setEvidence] = useState<EvidencePackage | null>(null);
  const [loading, setLoading] = useState(false);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [startYear, setStartYear] = useState(2000);
  const [endYear, setEndYear] = useState(2025);
  const [paperLimit, setPaperLimit] = useState(20);
  const [minRelevance, setMinRelevance] = useState(0.2);

  useEffect(() => {
    apiRequest<{ items: Topic[] }>(apiBase, `/projects/${project.project_id}/topics`)
      .then((data) => {
        const confirmed = data.items.filter((item) => ["confirmed", "evidence_ready"].includes(item.status));
        setTopics(confirmed); if (!activeTopic && confirmed.length) setActiveTopic(confirmed[0].topic_id);
      });
  }, [project.project_id]);
  useEffect(() => {
    apiRequest<{ items: Dataset[] }>(apiBase, "/library/datasets")
      .then((data) => setDatasets(data.items.filter((item) => item.status === "published")));
  }, [apiBase]);

  const retrieve = async () => {
    if (!activeTopic) return;
    setLoading(true);
    try {
      const data = await apiRequest<EvidencePackage>(apiBase, `/projects/${project.project_id}/evidence-packages`, {
        method: "POST",
        body: JSON.stringify({
          topic_id: activeTopic, start_year: startYear, end_year: endYear,
          paper_limit: paperLimit, min_relevance: minRelevance,
          dataset_ids: datasetId ? [datasetId] : [],
        }),
      });
      setEvidence(data);
    } finally { setLoading(false); }
  };
  const toggle = async (evidenceId: string, excluded: boolean) => {
    await apiRequest(apiBase, `/projects/${project.project_id}/evidence-items/${evidenceId}`, {
      method: "PATCH", body: JSON.stringify({ excluded, reason: excluded ? "人工审阅排除" : "" }),
    });
    if (evidence) setEvidence({ ...evidence, items: evidence.items.map((item) => item.evidence_id === evidenceId ? { ...item, excluded } : item) });
  };
  const groups = useMemo(() => ({
    ipc: evidence?.items.filter((item) => item.evidence_type.startsWith("ipc")) ?? [],
    papers: evidence?.items.filter((item) => item.evidence_type === "paper") ?? [],
    materials: evidence?.items.filter((item) => item.evidence_type === "material") ?? [],
  }), [evidence]);
  return (
    <>
      <PageHeading
        eyebrow="EVIDENCE REVIEW" title="双通道证据审阅"
        description="针对最终主题检索 IPC 时间趋势与论文研究方向，确认后冻结为不可变任务快照。"
        actions={<button className="primary-button" disabled={!evidence} onClick={onForecast}>配置预测任务</button>}
      />
      <section className="surface evidence-filter">
        <div className="filter-bar">
          <label>技术主题<select value={activeTopic} onChange={(event) => { setActiveTopic(event.target.value); setEvidence(null); }}>{topics.map((topic) => <option value={topic.topic_id} key={topic.topic_id}>{topic.topic_name}</option>)}</select></label>
          <button className="primary-button" disabled={!activeTopic || loading} onClick={retrieve}>{loading ? "正在检索…" : "检索 IPC 与论文证据"}</button>
          {evidence ? <StatusPill status={evidence.quality.sufficient ? "published" : "needs_review"} /> : null}
        </div>
        <details className="retrieval-options">
          <summary>检索范围与复现参数</summary>
          <div>
            <label>数据集版本<select value={datasetId} onChange={(event) => setDatasetId(event.target.value)}><option value="">全部已发布版本</option>{datasets.map((item) => <option value={item.dataset_id} key={item.dataset_id}>{item.name} · v{item.version}</option>)}</select></label>
            <label>起始年份<input type="number" value={startYear} onChange={(event) => setStartYear(Number(event.target.value))} /></label>
            <label>截止年份<input type="number" value={endYear} onChange={(event) => setEndYear(Number(event.target.value))} /></label>
            <label>论文上限<input type="number" min="1" max="100" value={paperLimit} onChange={(event) => setPaperLimit(Number(event.target.value))} /></label>
            <label>最低相关性<input type="number" min="0" max="1" step="0.1" value={minRelevance} onChange={(event) => setMinRelevance(Number(event.target.value))} /></label>
          </div>
        </details>
      </section>
      {evidence ? <>
        <div className="metric-grid four compact">
          <Metric label="完整性评分" value={evidence.quality.score} note={evidence.quality.sufficient ? "满足默认预测门槛" : "需要补充或说明"} />
          <Metric label="IPC 记录" value={evidence.quality.ipc_record_count} note={`${evidence.quality.year_count} 个年份`} tone="green" />
          <Metric label="相关论文" value={evidence.quality.paper_count} note={`${evidence.quality.paper_fragment_count} 个证据片段`} tone="amber" />
          <Metric label="数据截止" value={evidence.quality.data_cutoff ?? "—"} note="任务将冻结该范围" tone="red" />
        </div>
        {!evidence.quality.sufficient ? <div className="warning-banner"><strong>证据门槛未通过</strong><span>{evidence.quality.missing.join("；")}</span></div> : null}
        <div className="evidence-columns">
          {([
            ["IPC 趋势与融合", groups.ipc],
            ["论文研究方向", groups.papers],
            ["项目输入材料", groups.materials],
          ] as const).map(([title, items]) => <section className="surface evidence-column" key={title}>
            <header className="surface-header"><div><h2>{title}</h2><p>{items.length} 条证据</p></div></header>
            {items.map((item) => <article className={`evidence-item ${item.excluded ? "excluded" : ""}`} key={item.evidence_id}>
              <div><StatusPill status={item.evidence_type} /><small>{Math.round(item.relevance * 100)}%</small></div>
              <strong>{item.title}</strong><p>{item.content.replace(/<[^>]+>/g, "")}</p>
              <button onClick={() => toggle(item.evidence_id, !item.excluded)}>{item.excluded ? "恢复证据" : "排除证据"}</button>
            </article>)}
          </section>)}
        </div>
      </> : <EmptyState title="尚未形成证据包" note="选择确认主题后检索，结果将分为 IPC、论文和项目材料三类。" />}
    </>
  );
}
