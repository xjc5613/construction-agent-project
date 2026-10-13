import { useEffect, useState } from "react";
import { apiMutation, apiRequest } from "../api";
import type { Project, TechnologyNode } from "../types";
import { ConfirmationDialog, EmptyState, InlineError, Modal, PageHeading, StatusPill, type ConfirmationPreview } from "../components/UI";

export function ProjectsPage({
  apiBase, projects, onCreated, onSelect, onChanged,
}: {
  apiBase: string; projects: Project[];
  onCreated: (project: Project) => void; onSelect: (project: Project) => void; onChanged?: () => Promise<void>;
}) {
  const [roots, setRoots] = useState<TechnologyNode[]>([]);
  const [technologyId, setTechnologyId] = useState("");
  const [targetYear, setTargetYear] = useState<2030 | 2035 | 2040>(2040);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [editing, setEditing] = useState<Project | null>(null);
  const [confirmation, setConfirmation] = useState<{ project: Project; action: "archive" | "restore"; preview: ConfirmationPreview } | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  useEffect(() => {
    apiRequest<{ items: TechnologyNode[] }>(apiBase, "/technologies?flat=true&level=1")
      .then((data) => { setRoots(data.items); if (!technologyId && data.items.length) setTechnologyId(data.items[0].node_id); });
  }, [apiBase]);
  const create = async () => {
    if (!technologyId) return;
    const project = await apiRequest<Project>(apiBase, "/projects", {
      method: "POST", body: JSON.stringify({ technology_node_id: technologyId, target_year: targetYear, name, description }),
    });
    setName(""); setDescription(""); onCreated(project);
  };
  const saveEdit = async () => {
    if (!editing) return;
    setPending(true); setError("");
    try { await apiMutation(`project-edit:${editing.project_id}`, apiBase, `/projects/${editing.project_id}`, { method: "PATCH", body: JSON.stringify({ name: editing.name, description: editing.description }) }); setEditing(null); await onChanged?.(); }
    catch (cause) { setError((cause as Error).message); } finally { setPending(false); }
  };
  const previewLifecycle = async (project: Project) => {
    const action = project.lifecycle_status === "archived" ? "restore" : "archive";
    setPending(true); setError("");
    try { setConfirmation({ project, action, preview: await apiRequest<ConfirmationPreview>(apiBase, `/projects/${project.project_id}/actions/preview`, { method: "POST", body: JSON.stringify({ action, payload: {} }) }) }); }
    catch (cause) { setError((cause as Error).message); } finally { setPending(false); }
  };
  const commitLifecycle = async () => {
    if (!confirmation) return;
    setPending(true); setError("");
    try { await apiMutation(`project:${confirmation.project.project_id}:${confirmation.action}`, apiBase, `/projects/${confirmation.project.project_id}/actions/commit`, { method: "POST", body: JSON.stringify({ action: confirmation.action, payload: {}, confirmation_token: confirmation.preview.confirmation_token }) }); setConfirmation(null); await onChanged?.(); }
    catch (cause) { setError((cause as Error).message); } finally { setPending(false); }
  };
  const visibleProjects = projects.filter((project) => (
    showArchived ? project.lifecycle_status === "archived" : project.lifecycle_status !== "archived"
  ));
  return (
    <>
      <PageHeading eyebrow="PROJECT WORKSPACE" title="预测项目管理" description="选择一级技术与目标年份，系统按2026基线生成累计预测节点。" />
      <InlineError message={error} />
      <section className="surface form-surface">
        <div className="inline-form project-scope-form">
          <label>一级技术<select value={technologyId} onChange={(event) => setTechnologyId(event.target.value)}>{roots.map((item) => <option value={item.node_id} key={item.node_id}>{item.name}</option>)}</select></label>
          <label>目标年份<select value={targetYear} onChange={(event) => setTargetYear(Number(event.target.value) as typeof targetYear)}><option value={2030}>2030</option><option value={2035}>2035</option><option value={2040}>2040</option></select></label>
          <label>名称后缀（可选）<input value={name} onChange={(event) => setName(event.target.value)} placeholder="留空则自动生成" /></label>
          <label>研究说明<input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="研究范围或目标" /></label>
          <button className="primary-button" disabled={!technologyId} onClick={create}>新建项目</button>
        </div>
      </section>
      <section className="surface">
        <header className="surface-header"><div><h2>{showArchived ? "历史项目" : "进行中的项目"}</h2><p>共 {visibleProjects.length} 个预测项目</p></div><label className="inline-check"><input type="checkbox" checked={showArchived} onChange={(event) => setShowArchived(event.target.checked)} />查看归档项目</label></header>
        {visibleProjects.length ? <div className="data-table" role="table" aria-label="预测项目列表">
          <div className="table-head project-list" role="row"><span role="columnheader">项目名称</span><span role="columnheader">预测范围</span><span role="columnheader">状态</span><span role="columnheader">操作</span></div>
          {visibleProjects.map((project) => <div className="table-row project-list" role="row" key={project.project_id}>
            <div><strong>{project.name}</strong><small>{project.description || project.project_id}</small></div>
            <span>{project.legacy_mode ? "历史项目" : `${project.technology_name} · ${project.baseline_year} → ${project.target_year}`}<small>{project.forecast_nodes?.join(" / ")}</small></span>
            <div><StatusPill status={project.lifecycle_status === "archived" ? "archived" : project.status} /></div>
            <div className="row-actions"><button onClick={() => onSelect(project)}>{project.lifecycle_status === "archived" ? "查看历史" : "进入项目"}</button>{project.lifecycle_status !== "archived" ? <button onClick={() => setEditing({ ...project })}>编辑</button> : null}<button onClick={() => void previewLifecycle(project)}>{project.lifecycle_status === "archived" ? "恢复" : "归档"}</button></div>
          </div>)}
        </div> : <EmptyState title="尚未创建预测项目" note="新建项目后即可录入已分析材料并校准技术主题。" />}
      </section>
      {editing ? <Modal title="编辑项目" pending={pending} onClose={() => setEditing(null)}><div className="material-editor"><label>项目名称<input value={editing.name} onChange={(event) => setEditing({ ...editing, name: event.target.value })} /></label><label>研究说明<textarea value={editing.description} onChange={(event) => setEditing({ ...editing, description: event.target.value })} /></label></div><div className="form-actions"><button onClick={() => setEditing(null)}>取消</button><button className="primary-button" disabled={pending || !editing.name.trim()} onClick={() => void saveEdit()}>保存</button></div></Modal> : null}
      {confirmation ? <ConfirmationDialog title={confirmation.action === "archive" ? "确认归档项目" : "确认恢复项目"} preview={confirmation.preview} pending={pending} onClose={() => setConfirmation(null)} onConfirm={() => void commitLifecycle()} /> : null}
    </>
  );
}
