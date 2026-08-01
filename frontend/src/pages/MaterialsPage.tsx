import { useEffect, useState } from "react";
import { apiRequest } from "../api";
import type { Material, Project, Topic } from "../types";
import { EmptyState, PageHeading, StatusPill } from "../components/UI";

export function MaterialsPage({
  apiBase, project, onTopics,
}: { apiBase: string; project: Project; onTopics: (topics: Topic[]) => void }) {
  const [materials, setMaterials] = useState<Material[]>([]);
  const [title, setTitle] = useState("技术研究材料");
  const [content, setContent] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<"text" | "file">("text");
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    const data = await apiRequest<{ items: Material[] }>(apiBase, `/projects/${project.project_id}/materials`);
    setMaterials(data.items);
  };
  useEffect(() => { void refresh(); }, [project.project_id]);

  const save = async () => {
    setBusy(true);
    try {
      if (mode === "text") {
        await apiRequest(apiBase, `/projects/${project.project_id}/materials/text`, {
          method: "POST", body: JSON.stringify({ title, content }),
        });
        setContent("");
      } else if (file) {
        const form = new FormData(); form.append("file", file);
        await apiRequest(apiBase, `/projects/${project.project_id}/materials/upload`, {
          method: "POST", body: form,
        });
        setFile(null);
      }
      await refresh();
    } finally { setBusy(false); }
  };
  const extract = async () => {
    const topics = await apiRequest<Topic[]>(
      apiBase, `/projects/${project.project_id}/topics/extract`,
      { method: "POST", body: JSON.stringify({ material_ids: materials.map((item) => item.material_id) }) },
    );
    onTopics(topics);
  };
  return (
    <>
      <PageHeading
        eyebrow="PROJECT MATERIALS" title="输入研究材料"
        description="粘贴研究文本或上传论文文档，系统将保留原文位置并提取候选技术主题。"
        actions={<button className="primary-button" disabled={!materials.length} onClick={extract}>提取关键信息与主题</button>}
      />
      <section className="surface">
        <div className="tab-bar"><button className={mode === "text" ? "active" : ""} onClick={() => setMode("text")}>文本输入</button><button className={mode === "file" ? "active" : ""} onClick={() => setMode("file")}>文件上传</button></div>
        {mode === "text" ? (
          <div className="material-editor">
            <label>材料标题<input value={title} onChange={(event) => setTitle(event.target.value)} /></label>
            <label>研究材料<textarea value={content} onChange={(event) => setContent(event.target.value)} placeholder="粘贴包含研究方向、IPC 分类号、趋势描述或论文摘要的材料…" /></label>
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
        <header className="surface-header"><div><h2>项目材料</h2><p>{materials.length} 份材料已进入项目</p></div></header>
        {materials.length ? <div className="data-table">
          <div className="table-head material-list"><span>材料</span><span>格式</span><span>解析状态</span><span>录入时间</span></div>
          {materials.map((material) => <div className="table-row material-list" key={material.material_id}>
            <div><strong>{material.title}</strong><small>{material.original_filename || material.material_id}</small></div>
            <span>{material.source_type.toUpperCase()}</span><StatusPill status={material.parse_status} />
            <span>{new Date(material.created_at).toLocaleString("zh-CN")}</span>
          </div>)}
        </div> : <EmptyState title="暂无研究材料" note="录入材料后才能生成候选技术主题。" />}
      </section>
    </>
  );
}
