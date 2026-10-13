import { useEffect, useMemo, useState } from "react";
import { apiRequest } from "../api";
import type { Dataset, ImportRecord, IpcRecord, Paginated, PaperRecord, TechnologyNode, TechnologySummary } from "../types";
import { EmptyState, InlineError, Metric, Modal, PageHeading, StatusPill } from "../components/UI";
import { useDirtyForm } from "../dirty";

const periodLabels: Record<string, string> = {
  "2010_2015": "2010-2015", "2016_2020": "2016-2020", "2021_2026": "2021-2026",
};
const componentLabels: Record<string, string> = {
  ipc_metrics: "IPC 年度指标", ipc_fusions: "IPC 融合关系",
  papers: "论文数据", analysis_document: "综合分析报告",
};
type Tab = "papers" | "ipc" | "files" | "imports" | "coverage";
type GuidedStage = { import: ImportRecord; plan: NonNullable<ImportRecord["plan"]> };

export function LibraryPage({ apiBase, datasets, onRefresh }: {
  apiBase: string; datasets: Dataset[]; onRefresh: () => Promise<void>;
}) {
  const initialScope = new URLSearchParams(window.location.search).get("scope_node_id") ?? "";
  const [technologies, setTechnologies] = useState<TechnologyNode[]>([]);
  const [technologyId, setTechnologyId] = useState(initialScope);
  const [summary, setSummary] = useState<TechnologySummary | null>(null);
  const [tab, setTab] = useState<Tab>("papers");
  const [query, setQuery] = useState("");
  const [period, setPeriod] = useState("");
  const [page, setPage] = useState(1);
  const [papers, setPapers] = useState<Paginated<PaperRecord>>({ items: [], total: 0, page: 1, page_size: 20 });
  const [ipcRows, setIpcRows] = useState<Paginated<IpcRecord>>({ items: [], total: 0, page: 1, page_size: 20 });
  const [files, setFiles] = useState<Array<Record<string, unknown>>>([]);
  const [imports, setImports] = useState<Array<Record<string, unknown>>>([]);
  const [coverage, setCoverage] = useState<{ periods: Record<string, Record<string, number>>; missing: string[]; complete: boolean } | null>(null);
  const [includeIneligible, setIncludeIneligible] = useState(false);
  const [detail, setDetail] = useState<PaperRecord | IpcRecord | null>(null);
  const [publicKind, setPublicKind] = useState<"ipc" | "paper" | "integrated">("paper");
  const [componentKind, setComponentKind] = useState("papers");
  const [documentYear, setDocumentYear] = useState(2026);
  const [file, setFile] = useState<File | null>(null);
  const [staged, setStaged] = useState<GuidedStage | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [governance, setGovernance] = useState<{
    dataset: Dataset; technologyId: string; period: string;
    kind: "ipc" | "paper" | "integrated";
  } | null>(null);
  useDirtyForm("library-guided-import", Boolean(file || staged));

  const selectedTechnology = technologies.find((item) => item.node_id === technologyId);
  const leafTechnologies = technologies.filter((item) => item.level === 3);
  const allowedComponents = useMemo(() => (
    publicKind === "ipc" ? ["ipc_metrics", "ipc_fusions"]
      : publicKind === "paper" ? ["papers"]
        : ["ipc_metrics", "ipc_fusions", "papers", "analysis_document"]
  ), [publicKind]);

  useEffect(() => {
    apiRequest<{ items: TechnologyNode[] }>(apiBase, "/technologies?flat=true")
      .then((data) => {
        setTechnologies(data.items);
        if (!technologyId && data.items.length) setTechnologyId(data.items[0].node_id);
      }).catch((cause) => setError((cause as Error).message));
  }, [apiBase]);
  useEffect(() => {
    if (!allowedComponents.includes(componentKind)) setComponentKind(allowedComponents[0]);
  }, [allowedComponents]);

  const load = async () => {
    if (!technologyId) return;
    const scope = encodeURIComponent(technologyId);
    const common = `scope_node_id=${scope}&period_code=${period}&include_ineligible=${includeIneligible}`;
    setError("");
    try {
      const metrics = await apiRequest<TechnologySummary>(apiBase, `/library/technologies/${scope}/summary`);
      setSummary(metrics);
      if (tab === "papers") {
        setPapers(await apiRequest<Paginated<PaperRecord>>(apiBase, `/library/papers?${common}&q=${encodeURIComponent(query)}&page=${page}&page_size=20`));
      } else if (tab === "ipc") {
        setIpcRows(await apiRequest<Paginated<IpcRecord>>(apiBase, `/library/ipc/trends?${common}&codes=${encodeURIComponent(query)}&page=${page}&page_size=20`));
      } else if (tab === "files") {
        setFiles((await apiRequest<{ items: Array<Record<string, unknown>> }>(apiBase, `/library/files?scope_node_id=${scope}&include_ineligible=${includeIneligible}`)).items);
      } else if (tab === "imports") {
        setImports((await apiRequest<{ items: Array<Record<string, unknown>> }>(apiBase, `/library/imports?scope_node_id=${scope}&include_ineligible=${includeIneligible}`)).items);
      } else {
        setCoverage(await apiRequest(apiBase, `/library/coverage/${scope}`));
      }
    } catch (cause) { setError((cause as Error).message); }
  };
  useEffect(() => { void load(); }, [technologyId, tab, page, includeIneligible, period]);

  const stageImport = async () => {
    if (!file || !technologyId || selectedTechnology?.level !== 3) return;
    setPending(true); setError("");
    const form = new FormData();
    form.append("file", file);
    form.append("technology_node_id", technologyId);
    form.append("public_kind", publicKind);
    form.append("component_kind", componentKind);
    if (componentKind === "papers") form.append("document_year", String(documentYear));
    try {
      const response = await apiRequest<GuidedStage>(apiBase, "/library/imports/guided/stage", { method: "POST", body: form });
      setStaged(response);
    } catch (cause) { setError((cause as Error).message); } finally { setPending(false); }
  };
  const commitImport = async () => {
    if (!staged) return;
    setPending(true); setError("");
    try {
      const result = await apiRequest<{ items: Array<{ committed: number; dataset: Dataset }> }>(apiBase, `/library/imports/${staged.import.import_id}/guided-commit`, {
        method: "POST",
        body: JSON.stringify({
          technology_node_id: technologyId, public_kind: publicKind,
          mapping: staged.import.mapping, versions: staged.plan.generated_versions,
        }),
      });
      setMessage(`已导入 ${result.items.reduce((sum, item) => sum + item.committed, 0)} 条记录，生成 ${result.items.length} 个阶段版本，请确认后发布。`);
      setStaged(null); setFile(null); await onRefresh(); setTab("imports"); await load();
    } catch (cause) { setError((cause as Error).message); } finally { setPending(false); }
  };
  const publish = async (datasetId: string) => {
    setPending(true); setError("");
    try {
      await apiRequest(apiBase, `/library/datasets/${datasetId}/status`, { method: "PATCH", body: JSON.stringify({ status: "published" }) });
      setMessage("数据集已发布，可进入项目证据检索。"); await onRefresh(); await load();
    } catch (cause) { setError((cause as Error).message); } finally { setPending(false); }
  };
  const applyGovernance = async () => {
    if (!governance?.technologyId) return;
    setPending(true); setError("");
    try {
      if (governance.dataset.migration_status === "needs_split") {
        await apiRequest(apiBase, `/library/datasets/${governance.dataset.dataset_id}/split`, {
          method: "POST", body: JSON.stringify({ technology_node_id: governance.technologyId, kind: governance.kind }),
        });
        setMessage("旧数据已按历史阶段拆分为新的草稿版本，原数据保持不变。");
      } else {
        await apiRequest(apiBase, `/library/datasets/${governance.dataset.dataset_id}/classification`, {
          method: "PATCH", body: JSON.stringify({ technology_node_id: governance.technologyId, period_code: governance.period, kind: governance.kind }),
        });
        setMessage("旧数据已完成技术、阶段和类型映射。");
      }
      setGovernance(null); await onRefresh(); await load();
    } catch (cause) { setError((cause as Error).message); } finally { setPending(false); }
  };
  const scopedDatasets = datasets.filter((item) => {
    if (!technologyId) return false;
    if (includeIneligible && item.migration_status !== "mapped") return true;
    if (selectedTechnology?.level === 3) return item.technology_node_id === technologyId;
    return true;
  });

  return <>
    <PageHeading eyebrow="TECHNOLOGY DATA" title="基础数据" description="先选择技术，再直接查看和导入该技术下的论文与 IPC 聚合指标。" />
    <InlineError message={error} />
    <section className="surface data-scope-bar">
      <label>技术范围<select value={technologyId} onChange={(event) => { setTechnologyId(event.target.value); setPage(1); }}>{technologies.map((item) => <option value={item.node_id} key={item.node_id}>{item.path_text || item.name}</option>)}</select></label>
      <label>历史阶段<select value={period} onChange={(event) => { setPeriod(event.target.value); setPage(1); }}><option value="">全部阶段</option>{Object.entries(periodLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
      <label className="inline-check"><input type="checkbox" checked={includeIneligible} onChange={(event) => setIncludeIneligible(event.target.checked)} />显示草稿、废弃和待映射数据</label>
    </section>
    {summary ? <div className="metric-grid four compact"><Metric label="数据集" value={summary.datasets} note="有效已发布版本" /><Metric label="论文记录" value={summary.papers} note={summary.path_text} tone="green" /><Metric label="IPC 指标" value={summary.ipc_records} note="年度聚合专利指标" tone="amber" /><Metric label="来源文件" value={summary.source_files} note={`${summary.projects} 个项目引用`} tone="red" /></div> : null}
    <div className="tab-bar data-tabs">
      {([["papers", "论文列表"], ["ipc", "IPC 指标列表"], ["files", "来源文件"], ["imports", "导入与版本"], ["coverage", "阶段覆盖"]] as const).map(([key, label]) => <button key={key} className={tab === key ? "active" : ""} onClick={() => { setTab(key); setPage(1); }}>{label}</button>)}
    </div>
    {(tab === "papers" || tab === "ipc") ? <section className="surface">
      <div className="search-row"><input aria-label={tab === "papers" ? "论文检索词" : "IPC 分类号"} value={query} onChange={(event) => setQuery(event.target.value)} placeholder={tab === "papers" ? "题名、作者、摘要或关键词" : "留空查看全部，或输入 E04B"} /><button className="primary-button" onClick={() => void load()}>筛选</button></div>
      {tab === "papers" ? <div className="data-table"><div className="table-head paper-record-list"><span>论文</span><span>年份</span><span>所属技术</span><span>来源</span></div>{papers.items.map((paper) => <button className="table-row paper-record-list record-button" key={paper.paper_id} onClick={() => setDetail(paper)}><span><strong>{paper.title}</strong><small>{paper.authors || "作者未知"}</small></span><span>{paper.year ?? "—"}</span><span>{paper.technology_path || "待映射"}</span><span>{paper.dataset_name} · v{paper.dataset_version}</span></button>)}{!papers.items.length ? <EmptyState title="暂无论文记录" note="当前技术范围没有可浏览论文，可通过下方导入向导补充。" /> : null}</div>
        : <div className="data-table"><div className="table-head ipc-record-list"><span>IPC 与年份</span><span>专利量</span><span>增长/中心度</span><span>来源</span></div>{ipcRows.items.map((row) => <button className="table-row ipc-record-list record-button" key={row.metric_id} onClick={() => setDetail(row)}><span><strong>{row.ipc_code}</strong><small>{row.year}</small></span><span>{row.patent_count ?? "—"}</span><span>{row.growth_rate ?? "—"} / {row.degree_centrality ?? "—"}</span><span>{row.technology_path || "待映射"} · v{row.dataset_version}</span></button>)}{!ipcRows.items.length ? <EmptyState title="暂无 IPC 指标" note="这里展示年度聚合专利指标，不代表逐件专利文献。" /> : null}</div>}
      <div className="pagination"><button disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>上一页</button><span>第 {page} 页 · 共 {tab === "papers" ? papers.total : ipcRows.total} 条</span><button disabled={page * 20 >= (tab === "papers" ? papers.total : ipcRows.total)} onClick={() => setPage((value) => value + 1)}>下一页</button></div>
    </section> : null}
    {tab === "files" ? <section className="surface compact-list">{files.map((item) => <article key={String(item.file_id)}><div><strong>{String(item.filename)}</strong><small>{String(item.dataset_name)} · {String(item.parse_status)}</small></div><StatusPill status={String(item.parse_status)} /></article>)}{!files.length ? <EmptyState title="暂无来源文件" note="完成导入后会在此显示文件与解析状态。" /> : null}</section> : null}
    {tab === "imports" ? <section className="surface"><div className="compact-list">{imports.map((item) => <article key={String(item.import_id)}><div><strong>{String(item.filename)}</strong><small>{String(item.dataset_name)} · v{String(item.dataset_version)} · {String(item.migration_status)}</small></div><StatusPill status={String(item.status)} /></article>)}</div><div className="data-table"><div className="table-head dataset-list"><span>阶段版本</span><span>类型</span><span>状态</span><span>操作</span></div>{scopedDatasets.map((dataset) => <div className="table-row dataset-list" key={dataset.dataset_id}><span><strong>{dataset.name}</strong><small>{dataset.period_code ? periodLabels[dataset.period_code] : "待映射"} · v{dataset.version}</small></span><span>{dataset.public_kind || dataset.kind}</span><StatusPill status={dataset.migration_status !== "mapped" ? dataset.migration_status : dataset.status} /><span className="row-actions">{dataset.migration_status !== "mapped" ? <button onClick={() => setGovernance({ dataset, technologyId: selectedTechnology?.level === 3 ? technologyId : "", period: "", kind: "ipc" })}>{dataset.migration_status === "needs_split" ? "拆分" : "映射"}</button> : null}{dataset.status === "draft" ? <button disabled={pending} onClick={() => void publish(dataset.dataset_id)}>发布</button> : null}</span></div>)}</div></section> : null}
    {tab === "coverage" ? <section className="surface"><div className="coverage-grid">{Object.entries(coverage?.periods ?? {}).map(([key, values]) => <article key={key}><strong>{periodLabels[key]}</strong><span>IPC {values.ipc_records ?? 0}</span><span>论文 {values.paper_records ?? 0}</span></article>)}</div>{coverage?.missing?.length ? <div className="warning-banner"><strong>数据缺口</strong><span>{coverage.missing.join("；")}</span></div> : <p className="success-note">三个历史阶段均有有效记录。</p>}</section> : null}
    <section className="surface guided-import">
      <header className="surface-header"><div><h2>导入论文或 IPC 数据</h2><p>系统自动推断阶段并生成底层版本，无需先创建数据集</p></div></header>
      {selectedTechnology?.level !== 3 ? <div className="warning-banner"><strong>请选择三级技术</strong><span>父级范围可用于浏览，导入必须落到具体三级技术。</span></div> : null}
      <div className="inline-form guided-import-form">
        <label>三级技术<select value={selectedTechnology?.level === 3 ? technologyId : ""} onChange={(event) => setTechnologyId(event.target.value)}><option value="">请选择</option>{leafTechnologies.map((item) => <option value={item.node_id} key={item.node_id}>{item.path_text}</option>)}</select></label>
        <label>数据类型<select value={publicKind} onChange={(event) => setPublicKind(event.target.value as typeof publicKind)}><option value="paper">论文</option><option value="ipc">IPC</option><option value="integrated">综合数据</option></select></label>
        <label>文件内容<select value={componentKind} onChange={(event) => setComponentKind(event.target.value)}>{allowedComponents.map((item) => <option value={item} key={item}>{componentLabels[item]}</option>)}</select></label>
        {componentKind === "papers" ? <label>文档年份<input type="number" value={documentYear} onChange={(event) => setDocumentYear(Number(event.target.value))} /></label> : null}
      </div>
      <label className="upload-drop"><input type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /><span>文件</span><strong>{file?.name || "选择 CSV、XLSX、JSON、PDF 或 DOCX"}</strong><small>提交前会显示有效记录、错误和阶段拆分计划</small></label>
      <button className="primary-button full" disabled={pending || !file || selectedTechnology?.level !== 3} onClick={() => void stageImport()}>{pending ? "正在解析…" : "解析并预览"}</button>
      {staged ? <div className="import-preview guided-plan"><div><strong>{staged.import.preview.valid_count ?? 1}</strong><span>可导入记录</span></div><div><strong>{staged.plan.periods.map((item) => periodLabels[item]).join(" / ")}</strong><span>{staged.plan.split_required ? "将拆分多个阶段版本" : "历史阶段"}</span></div><button disabled={pending} onClick={() => void commitImport()}>确认导入</button></div> : null}
      {message ? <p className="success-note">{message}</p> : null}
    </section>
    {detail ? <Modal title={"title" in detail ? detail.title : `${detail.ipc_code} · ${detail.year}`} wide onClose={() => setDetail(null)}><div className="record-detail">{Object.entries(detail).filter(([, value]) => value != null && typeof value !== "object").map(([key, value]) => <p key={key}><strong>{key}</strong><span>{String(value)}</span></p>)}</div></Modal> : null}
    {governance ? <Modal title={governance.dataset.migration_status === "needs_split" ? "拆分跨阶段旧数据" : "映射旧数据"} pending={pending} onClose={() => setGovernance(null)}><div className="material-editor"><label>三级技术<select value={governance.technologyId} onChange={(event) => setGovernance({ ...governance, technologyId: event.target.value })}><option value="">请选择</option>{leafTechnologies.map((item) => <option value={item.node_id} key={item.node_id}>{item.path_text}</option>)}</select></label>{governance.dataset.migration_status !== "needs_split" ? <label>历史阶段<select value={governance.period} onChange={(event) => setGovernance({ ...governance, period: event.target.value })}><option value="">请选择</option>{Object.entries(periodLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label> : null}<label>数据类型<select value={governance.kind} onChange={(event) => setGovernance({ ...governance, kind: event.target.value as typeof governance.kind })}><option value="ipc">IPC</option><option value="paper">论文</option><option value="integrated">综合数据</option></select></label></div><div className="form-actions"><button onClick={() => setGovernance(null)}>取消</button><button className="primary-button" disabled={pending || !governance.technologyId || (governance.dataset.migration_status !== "needs_split" && !governance.period)} onClick={() => void applyGovernance()}>确认{governance.dataset.migration_status === "needs_split" ? "拆分" : "映射"}</button></div></Modal> : null}
  </>;
}
