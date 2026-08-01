import type { Dataset, Project } from "../types";
import { Metric, PageHeading, StatusPill } from "../components/UI";
import type { PageKey } from "../components/AppShell";

export function DashboardPage({
  datasets, projects, onNavigate, onSelectProject,
}: {
  datasets: Dataset[];
  projects: Project[];
  onNavigate: (page: PageKey) => void;
  onSelectProject: (project: Project) => void;
}) {
  const published = datasets.filter((item) => item.status === "published").length;
  const running = projects.filter((item) => ["forecasting", "running"].includes(item.status)).length;
  return (
    <>
      <section className="hero-banner">
        <div>
          <span className="hero-tag">Evidence Forecast Center</span>
          <h1>面向 2040 的技术预测工作台</h1>
          <p>把 IPC 时间趋势、论文研究方向和人工判断组织成可追溯的预测证据链。</p>
          <div className="hero-chips"><span>2030 技术验证</span><span>2035 规模应用</span><span>2040 范式演化</span></div>
        </div>
        <div className="hero-action">
          <small>研究流程完整度</small><strong>{projects.length ? "72%" : "20%"}</strong>
          <div className="progress-line"><i style={{ width: projects.length ? "72%" : "20%" }} /></div>
          <button onClick={() => onNavigate("projects")}>进入项目管理</button>
        </div>
      </section>
      <div className="metric-grid four">
        <Metric label="基础数据集" value={datasets.length} note={`${published} 个已发布版本`} />
        <Metric label="预测项目" value={projects.length} note={`${running} 个任务正在运行`} tone="green" />
        <Metric label="证据通道" value="2" note="IPC 趋势与论文研究" tone="amber" />
        <Metric label="预测节点" value="3" note="2030 / 2035 / 2040" tone="red" />
      </div>
      <div className="dashboard-grid">
        <section className="surface">
          <header className="surface-header"><div><h2>最近预测项目</h2><p>从材料输入到结果分析的项目进度</p></div><button className="link-button" onClick={() => onNavigate("projects")}>查看全部</button></header>
          <div className="data-table">
            <div className="table-head projects"><span>项目</span><span>阶段</span><span>状态</span><span>操作</span></div>
            {projects.slice(0, 5).map((project) => (
              <div className="table-row projects" key={project.project_id}>
                <div><strong>{project.name}</strong><small>{project.description || project.project_id}</small></div>
                <span>{project.status === "draft" ? "材料准备" : "证据与预测"}</span>
                <StatusPill status={project.status} />
                <button className="text-action" onClick={() => onSelectProject(project)}>进入项目</button>
              </div>
            ))}
            {!projects.length ? <div className="table-empty">暂无项目，从“项目管理”创建第一个研究项目。</div> : null}
          </div>
        </section>
        <section className="surface quick-entry">
          <header className="surface-header"><div><h2>快捷入口</h2><p>常用研究操作</p></div></header>
          {[
            ["基础数据", "导入 IPC 表格与论文文件", "library"],
            ["新建项目", "定义本次技术预测范围", "projects"],
            ["证据审阅", "确认模型实际使用的依据", "evidence"],
          ].map(([title, note, page]) => (
            <button key={title} onClick={() => onNavigate(page as PageKey)}>
              <span>{title.slice(0, 1)}</span><div><strong>{title}</strong><small>{note}</small></div><b>›</b>
            </button>
          ))}
        </section>
      </div>
    </>
  );
}
