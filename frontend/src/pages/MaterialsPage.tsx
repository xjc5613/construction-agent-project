import { useEffect, useState } from "react";
import { apiMutation, apiRequest } from "../api";
import type { Material, Project, Topic } from "../types";
import { ConfirmationDialog, EmptyState, InlineError, PageHeading, StatusPill, type ConfirmationPreview } from "../components/UI";
import { useDirtyForm } from "../dirty";

export function MaterialsPage({
  apiBase, project, onTopics, onChanged,
}: { apiBase: string; project: Project; onTopics: (topics: Topic[]) => void; onChanged?: () => Promise<void> }) {
  const [materials, setMaterials] = useState<Material[]>([]);
  const [title, setTitle] = useState("技术研究材料");
  const [content, setContent] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<"text" | "file">("text");
  const [analysisKind, setAnalysisKind] = useState<Material["analysis_kind"]>("integrated_analysis");
  const [busy, setBusy] = useState(false);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [error, setError] = useState("");
  const [confirmation, setConfirmation] = useState<{ material: Material; action: "deactivate" | "restore"; preview: ConfirmationPreview } | null>(null);
  useDirtyForm(`materials:${project.project_id}`, Boolean(content.trim() || file));

  const refresh = async () => {
    const data = await apiRequest<{ items: Material[] }>(apiBase, `/projects/${project.project_id}/materials?include_inactive=${includeInactive}`);
    setMaterials(data.items);
  };
  useEffect(() => { void refresh(); }, [project.project_id, includeInactive]);

  const save = async () => {
    setBusy(true);
    try {
      if (mode === "text") {
        await apiRequest(apiBase, `/projects/${project.project_id}/materials/text`, {
          method: "POST", body: JSON.stringify({ title, content, analysis_kind: analysisKind }),
          headers: { "Content-Type": "application/json" },
        });
        setContent("");
      } else if (file) {
        const form = new FormData(); form.append("file", file); form.append("analysis_kind", analysisKind);
        await apiRequest(apiBase, `/projects/${project.project_id}/materials/upload`, {
          method: "POST", body: form,
        });
        setFile(null);
      }
      await refresh();
      await onChanged?.();
    } catch (cause) { setError((cause as Error).message); } finally { setBusy(false); }
  };
  const extract = async () => {
    const topics = await apiRequest<Topic[]>(
      apiBase, `/projects/${project.project_id}/topics/extract`,
      { method: "POST", body: JSON.stringify({ material_ids: materials.map((item) => item.material_id) }) },
    );
    onTopics(topics);
  };
  const previewLifecycle = async (material: Material) => {
    const action = material.lifecycle_status === "inactive" ? "restore" : "deactivate";
    setBusy(true); setError("");
    try { setConfirmation({ material, action, preview: await apiRequest<ConfirmationPreview>(apiBase, `/projects/${project.project_id}/materials/${material.material_id}/actions/preview`, { method: "POST", body: JSON.stringify({ action, payload: {} }) }) }); }
    catch (cause) { setError((cause as Error).message); } finally { setBusy(false); }
  };
  const commitLifecycle = async () => {
    if (!confirmation) return;
    setBusy(true); setError("");
    try { await apiMutation(`material:${confirmation.material.material_id}:${confirmation.action}`, apiBase, `/projects/${project.project_id}/materials/${confirmation.material.material_id}/actions/commit`, { method: "POST", body: JSON.stringify({ action: confirmation.action, payload: {}, confirmation_token: confirmation.preview.confirmation_token }) }); setConfirmation(null); await refresh(); }
    catch (cause) { setError((cause as Error).message); } finally { setBusy(false); }
  };
  return (
    <>
      <PageHeading
        eyebrow="PROJECT MATERIALS" title="输入研究材料"
        description="输入已经完成分析的 IPC、论文或综合报告，并结合三阶段基础数据提取主题。"
        actions={<button className="primary-button" disabled={!materials.length} onClick={extract}>提取关键信息与主题</button>}
      />
      <InlineError message={error} />
      {project.coverage?.missing?.length ? <div className="warning-banner"><strong>项目基础数据不完整</strong><span>{project.coverage.missing.join("；")}</span><a className="outline-button" href={`/library?scope_node_id=${project.technology_node_id ?? ""}`}>补充基础数据</a></div> : null}
      <section className="surface">
        <div className="material-kind-select"><label>分析材料类型<select value={analysisKind} onChange={(event) => setAnalysisKind(event.target.value as Material["analysis_kind"])}><option value="ipc_analysis">IPC 分析</option><option value="paper_analysis">论文分析</option><option value="integrated_analysis">综合分析</option></select></label></div>
        <div className="tab-bar"><button className={mode === "text" ? "active" : ""} onClick={() => setMode("text")}>文本输入</button><button className={mode === "file" ? "active" : ""} onClick={() => setMode("file")}>文件上传</button></div>
        {mode === "text" ? (
          <div className="material-editor">
            <label>材料标题<input value={title} onChange={(event) => setTitle(event.target.value)} /></label>
            <label>分析内容<textarea value={content} onChange={(event) => setContent(event.target.value)} placeholder="粘贴包含阶段、IPC指标、论文方向和变化结论的已分析材料…" /></label>
          </div>
        ) : (
          <label className="upload-drop large">
            <input type="file" accept=".txt,.md,.json,.pdf,.docx" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
            <span>文档</span><strong>{file?.name || "选择 PDF、DOCX、TXT 或 Markdown"}</strong>
            <small>扫描版 PDF 会标记为需要 OCR，不会作为空证据使用</small>
          </label>
        )}
        <div className="form-actions"><button className="primary-button" disabled={busy || (mode === "text" ? !content.trim() : !file)} onClick={save}>{busy ? "正在解析…" : "保存材料"}</button></div>
      </section>
      <section className="surface">
        <header className="surface-header"><div><h2>项目材料</h2><p>{materials.length} 份材料已进入项目</p></div><label className="inline-check"><input type="checkbox" checked={includeInactive} onChange={(event) => setIncludeInactive(event.target.checked)} />显示已停用材料</label></header>
        {materials.length ? <div className="data-table" role="table" aria-label="项目材料列表">
          <div className="table-head material-list" role="row"><span role="columnheader">材料</span><span role="columnheader">分析类型</span><span role="columnheader">解析状态</span><span role="columnheader">操作</span></div>
          {materials.map((material) => <div className="table-row material-list" role="row" key={material.material_id}>
            <div><strong>{material.title}</strong><small>{material.original_filename || material.material_id}</small></div>
            <span>{{ ipc_analysis: "IPC分析", paper_analysis: "论文分析", integrated_analysis: "综合分析" }[material.analysis_kind]}</span><div><StatusPill status={material.parse_status} /> {material.review_status === "needs_review" ? <StatusPill status="needs_review" /> : null}</div>
            <div><span>{new Date(material.created_at).toLocaleString("zh-CN")}</span><button className="text-action" onClick={() => void previewLifecycle(material)}>{material.lifecycle_status === "inactive" ? "恢复" : "停用"}</button></div>
          </div>)}
        </div> : <EmptyState title="暂无研究材料" note="录入材料后才能生成候选技术主题。" />}
      </section>
      {confirmation ? <ConfirmationDialog title={confirmation.action === "deactivate" ? "确认停用材料" : "确认恢复材料"} preview={confirmation.preview} pending={busy} onClose={() => setConfirmation(null)} onConfirm={() => void commitLifecycle()} /> : null}
    </>
  );
}
