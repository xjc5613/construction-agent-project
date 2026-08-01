import { useEffect, useState } from "react";
import { apiRequest } from "../api";
import type { Dataset, ImportRecord } from "../types";
import { Metric, PageHeading, StatusPill } from "../components/UI";

const kindLabel: Record<string, string> = {
  ipc_metrics: "IPC 趋势", ipc_fusions: "IPC 融合", papers: "论文数据", mixed: "综合数据",
};

export function LibraryPage({
  apiBase, datasets, onRefresh,
}: { apiBase: string; datasets: Dataset[]; onRefresh: () => Promise<void> }) {
  const [kind, setKind] = useState("ipc_metrics");
  const [name, setName] = useState("");
  const [version, setVersion] = useState("1.0");
  const [selectedId, setSelectedId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [staged, setStaged] = useState<ImportRecord | null>(null);
  const [message, setMessage] = useState("");
  const [paperQuery, setPaperQuery] = useState("");
  const [papers, setPapers] = useState<Array<{ paper_id: string; title: string; authors: string; year: number; abstract: string }>>([]);
  const [ipcCode, setIpcCode] = useState("E04B");
  const [ipcRows, setIpcRows] = useState<Array<{ metric_id: string; ipc_code: string; year: number; patent_count: number | null; degree_centrality: number | null }>>([]);

  useEffect(() => {
    if (!selectedId && datasets.length) setSelectedId(datasets[0].dataset_id);
  }, [datasets, selectedId]);

  const createDataset = async () => {
    const dataset = await apiRequest<Dataset>(apiBase, "/library/datasets", {
      method: "POST", body: JSON.stringify({ kind, name, version }),
    });
    setSelectedId(dataset.dataset_id); setName(""); await onRefresh();
  };
  const stage = async () => {
    if (!file) return;
    const form = new FormData();
    form.append("file", file); form.append("kind", kind); form.append("dataset_id", selectedId);
    const response = await apiRequest<{ import?: ImportRecord; duplicate?: boolean }>(
      apiBase, "/library/imports", { method: "POST", body: form },
    );
    if (response.duplicate) setMessage("文件已存在，未重复导入");
    else setStaged(response.import ?? null);
  };
  const commit = async () => {
    if (!staged || !selectedId) return;
    const result = await apiRequest<{ committed: number; errors: unknown[] }>(
      apiBase, `/library/imports/${staged.import_id}/commit`,
      { method: "POST", body: JSON.stringify({ dataset_id: selectedId, mapping: staged.mapping }) },
    );
    setMessage(`已提交 ${result.committed} 条记录`); setStaged(null); await onRefresh();
  };
  const publish = async (datasetId: string) => {
    await apiRequest(apiBase, `/library/datasets/${datasetId}/status`, {
      method: "PATCH", body: JSON.stringify({ status: "published" }),
    });
    await onRefresh();
  };
  const searchPapers = async () => {
    const data = await apiRequest<{ items: typeof papers }>(
      apiBase, `/library/papers?q=${encodeURIComponent(paperQuery)}&limit=20`,
    );
    setPapers(data.items);
  };
  const loadIpc = async () => {
    const data = await apiRequest<{ items: typeof ipcRows }>(
      apiBase, `/library/ipc/trends?codes=${encodeURIComponent(ipcCode)}`,
    );
    setIpcRows(data.items);
  };
  return (
    <>
      <PageHeading eyebrow="EVIDENCE LIBRARY" title="基础数据中心" description="统一管理 IPC 时间序列、技术融合关系和论文研究数据。" />
      <div className="metric-grid four compact">
        <Metric label="数据集版本" value={datasets.length} note="长期基础证据" />
        <Metric label="IPC 数据集" value={datasets.filter((item) => item.kind.startsWith("ipc")).length} note="趋势与融合关系" tone="green" />
        <Metric label="论文数据集" value={datasets.filter((item) => item.kind === "papers").length} note="全文与元数据" tone="amber" />
        <Metric label="已发布" value={datasets.filter((item) => item.status === "published").length} note="可进入证据检索" tone="red" />
      </div>
      <section className="surface form-surface">
        <header className="surface-header"><div><h2>新建数据集版本</h2><p>数据版本一经用于任务即保持可追溯</p></div></header>
        <div className="inline-form dataset-form">
          <label>数据类型<select value={kind} onChange={(event) => setKind(event.target.value)}>{Object.entries(kindLabel).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
          <label>数据集名称<input value={name} onChange={(event) => setName(event.target.value)} placeholder="数据集名称" /></label>
          <label>版本<input value={version} onChange={(event) => setVersion(event.target.value)} /></label>
          <button className="primary-button" disabled={!name.trim()} onClick={createDataset}>创建版本</button>
        </div>
      </section>
      <div className="two-column">
        <section className="surface">
          <header className="surface-header"><div><h2>数据集列表</h2><p>选择版本后导入对应文件</p></div></header>
          <div className="data-table">
            <div className="table-head dataset-list"><span>数据集</span><span>类型</span><span>状态</span><span>操作</span></div>
            {datasets.map((dataset) => (
              <div className={`table-row dataset-list ${selectedId === dataset.dataset_id ? "selected" : ""}`} key={dataset.dataset_id}>
                <button className="row-title" onClick={() => { setSelectedId(dataset.dataset_id); setKind(dataset.kind); }}><strong>{dataset.name}</strong><small>v{dataset.version}</small></button>
                <span>{kindLabel[dataset.kind]}</span><StatusPill status={dataset.status} />
                {dataset.status === "draft" ? <button className="text-action" onClick={() => publish(dataset.dataset_id)}>发布</button> : <span className="quiet-text">可检索</span>}
              </div>
            ))}
          </div>
        </section>
        <section className="surface import-panel">
          <header className="surface-header"><div><h2>导入数据</h2><p>支持 CSV / XLSX / JSON / PDF / DOCX</p></div></header>
          <label className="upload-drop">
            <input type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
            <span>选择文件</span><strong>{file?.name || "拖入或点击上传基础数据"}</strong>
            <small>先解析预览，确认后才写入数据集</small>
          </label>
          <button className="primary-button full" disabled={!file || !selectedId} onClick={stage}>解析并预览</button>
          {staged ? <div className="import-preview"><div><strong>{staged.preview.valid_count ?? staged.preview.text_preview?.length ?? 0}</strong><span>可导入</span></div><div><strong>{staged.preview.error_count ?? 0}</strong><span>错误</span></div><button onClick={commit}>确认提交</button></div> : null}
          {staged?.errors.length ? <div className="import-errors">{staged.errors.slice(0, 5).map((error) => <p key={`${error.row}-${error.message}`}>第 {error.row} 行：{error.message}</p>)}</div> : null}
          {message ? <p className="success-note">{message}</p> : null}
        </section>
      </div>
      <div className="two-column explorer-grid">
        <section className="surface">
          <header className="surface-header"><div><h2>论文检索</h2><p>检索题名、摘要、关键词与正文片段</p></div></header>
          <div className="search-row"><input value={paperQuery} onChange={(event) => setPaperQuery(event.target.value)} placeholder="输入技术方向或关键词" /><button className="primary-button" onClick={searchPapers}>检索</button></div>
          <div className="compact-list">{papers.map((paper) => <article key={paper.paper_id}><div><strong>{paper.title}</strong><small>{paper.authors || "作者未登记"} · {paper.year || "年份未知"}</small></div><p>{paper.abstract}</p></article>)}</div>
        </section>
        <section className="surface">
          <header className="surface-header"><div><h2>IPC 趋势预览</h2><p>查看原始年度指标</p></div></header>
          <div className="search-row"><input value={ipcCode} onChange={(event) => setIpcCode(event.target.value)} placeholder="例如 E04B" /><button className="primary-button" onClick={loadIpc}>查询</button></div>
          <div className="compact-list">{ipcRows.map((row) => <article key={row.metric_id}><div><strong>{row.ipc_code} · {row.year}</strong><small>专利量 {row.patent_count ?? "—"}</small></div><b>{row.degree_centrality ?? "—"}</b></article>)}</div>
        </section>
      </div>
    </>
  );
}
