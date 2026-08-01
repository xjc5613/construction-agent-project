import { useState } from "react";
import { apiRequest } from "../api";
import type { Project } from "../types";
import { EmptyState, PageHeading, StatusPill } from "../components/UI";

export function ProjectsPage({
  apiBase, projects, onCreated, onSelect,
}: {
  apiBase: string;
  projects: Project[];
  onCreated: (project: Project) => void;
  onSelect: (project: Project) => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const create = async () => {
    if (!name.trim()) return;
    const project = await apiRequest<Project>(apiBase, "/projects", {
      method: "POST", body: JSON.stringify({ name, description }),
    });
    setName(""); setDescription(""); onCreated(project);
  };
  return (
    <>
      <PageHeading eyebrow="PROJECT WORKSPACE" title="预测项目管理" description="每个项目独立保存材料、主题、证据快照和预测结果。" />
      <section className="surface form-surface">
        <div className="inline-form">
          <label>项目名称<input value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：装配式建筑技术演化研究" /></label>
          <label>研究说明<input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="填写研究范围或目标" /></label>
          <button className="primary-button" onClick={create}>新建项目</button>
        </div>
      </section>
      <section className="surface">
        <header className="surface-header"><div><h2>项目列表</h2><p>共 {projects.length} 个预测项目</p></div></header>
        {projects.length ? (
          <div className="data-table">
            <div className="table-head project-list"><span>项目名称</span><span>创建时间</span><span>状态</span><span>操作</span></div>
            {projects.map((project) => (
              <div className="table-row project-list" key={project.project_id}>
                <div><strong>{project.name}</strong><small>{project.description || project.project_id}</small></div>
                <span>{new Date(project.created_at).toLocaleDateString("zh-CN")}</span>
                <StatusPill status={project.status} />
                <button className="outline-button" onClick={() => onSelect(project)}>进入工作流</button>
              </div>
            ))}
          </div>
        ) : <EmptyState title="尚未创建预测项目" note="新建项目后即可录入材料并校准技术主题。" />}
      </section>
    </>
  );
}
