import type { ReactNode } from "react";
import type { Readiness } from "../types";

export type PageKey =
  | "dashboard" | "technologies" | "library" | "projects"
  | "overview" | "materials" | "topics-evidence"
  | "topics" | "evidence" | "forecast" | "jobs" | "results"
  | "research-design" | "data-quality" | "network-evolution"
  | "fusion-forecast" | "technology-themes" | "roadmap-report";

type Props = {
  active: PageKey;
  onNavigate: (page: PageKey) => void;
  projectName?: string;
  projectId?: string;
  baselineYear?: number;
  targetYear?: number;
  projects?: Array<{ project_id: string; name: string; lifecycle_status?: string }>;
  workflowSteps?: Readiness["steps"];
  onSelectProject?: (projectId: string) => void;
  health: string;
  children: ReactNode;
};

const globalItems: Array<[PageKey, string, string]> = [
  ["dashboard", "工作台", "D"],
  ["technologies", "技术目录", "G"],
  ["library", "基础数据", "L"],
  ["projects", "预测项目", "P"],
];

const legacyProjectItems: Array<[PageKey, Readiness["steps"][number]["id"], string]> = [
  ["overview", "overview", "O"],
  ["materials", "materials", "M"],
  ["topics-evidence", "topics-evidence", "T"],
  ["forecast", "forecast", "F"],
  ["results", "results", "R"],
];

const researchProjectItems: Array<[PageKey, Readiness["steps"][number]["id"], string]> = [
  ["research-design", "research-design", "1"],
  ["data-quality", "data-quality", "2"],
  ["network-evolution", "network-evolution", "3"],
  ["fusion-forecast", "fusion-forecast", "4"],
  ["technology-themes", "technology-themes", "5"],
  ["roadmap-report", "roadmap-report", "6"],
];

export function AppShell({
  active, onNavigate, projectName, projectId, baselineYear, targetYear,
  projects = [], workflowSteps = [], onSelectProject, health, children,
}: Props) {
  const byId = new Map(workflowSteps.map((step) => [step.id, step]));
  const projectItems = workflowSteps.some((step) => step.id === "research-design")
    ? researchProjectItems : legacyProjectItems;
  return (
    <div className="app-frame">
      <header className="top-header">
        <button className="brand-lockup" onClick={() => onNavigate("dashboard")}>
          <span className="brand-symbol">TF</span>
          <span><strong>TechForecast</strong><small>证据约束技术预测平台</small></span>
        </button>
        <div className="header-context">
          {projectName ? (
            <label className="project-context">
              当前项目
              <select aria-label="切换当前项目" value={projectId} onChange={(event) => onSelectProject?.(event.target.value)}>
                {projects.filter((item) => item.lifecycle_status !== "archived").map((item) => (
                  <option value={item.project_id} key={item.project_id}>{item.name}</option>
                ))}
              </select>
              <small>{baselineYear} 基线 → {targetYear} 目标</small>
            </label>
          ) : null}
          <span className={`health-dot ${health === "已连接" ? "online" : ""}`}>{health}</span>
        </div>
      </header>
      <aside className="side-nav">
        <section>
          <p>全局工作区</p>
          {globalItems.map(([key, label, icon]) => (
            <button className={active === key ? "active" : ""} aria-current={active === key ? "page" : undefined} key={key} onClick={() => onNavigate(key)}>
              <span className="nav-icon">{icon}</span>{label}
            </button>
          ))}
        </section>
        {projectId ? (
          <section>
            <p>当前项目流程</p>
            {projectItems.map(([key, stepId, icon]) => {
              const step = byId.get(stepId);
              if (step && !step.visible) return null;
              return (
                <button
                  className={`${active === key ? "active" : ""} ${step?.state === "blocked" ? "blocked" : ""}`}
                  aria-current={active === key ? "page" : undefined}
                  aria-describedby={step?.state === "blocked" ? `nav-${stepId}-reason` : undefined}
                  key={key}
                  onClick={() => onNavigate(key)}
                >
                  <span className="nav-icon">{icon}</span>
                  {step?.label ?? {
                    overview: "项目概览", materials: "研究材料",
                    "topics-evidence": "主题与证据", forecast: "预测运行",
                    results: "结果与历史", "research-design": "研究设计",
                    "data-quality": "数据质量", "network-evolution": "网络演化",
                    "fusion-forecast": "融合预测", "technology-themes": "技术主题",
                    "roadmap-report": "路线图与报告",
                  }[stepId]}
                  {step?.state === "completed" ? <b className="nav-state">完成</b> : null}
                  {step?.state === "blocked" ? <span id={`nav-${stepId}-reason`} className="sr-only">{step.blocking_reasons.join("；")}</span> : null}
                </button>
              );
            })}
          </section>
        ) : null}
        <div className="nav-foot">
          <span>{projectId ? "当前预测范围" : "预测节点"}</span>
          <strong>{projectId ? `${baselineYear} → ${targetYear}` : "2030 · 2035 · 2040"}</strong>
          <small>{projectId ? projectName : "进入项目后展开预测流程"}</small>
        </div>
      </aside>
      <main className="page-canvas">{children}</main>
    </div>
  );
}
