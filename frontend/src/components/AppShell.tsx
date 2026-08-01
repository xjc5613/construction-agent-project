import type { ReactNode } from "react";

export type PageKey =
  | "dashboard" | "library" | "projects" | "materials"
  | "topics" | "evidence" | "forecast" | "results";

type Props = {
  active: PageKey;
  onNavigate: (page: PageKey) => void;
  projectName?: string;
  health: string;
  children: ReactNode;
};

const groups: Array<{ title: string; items: Array<[PageKey, string, string]> }> = [
  { title: "研究总览", items: [["dashboard", "工作台", "D"], ["library", "基础数据", "L"]] },
  { title: "预测项目", items: [["projects", "项目管理", "P"], ["materials", "输入材料", "M"], ["topics", "主题校准", "T"]] },
  { title: "证据与预测", items: [["evidence", "证据审阅", "E"], ["forecast", "启动预测", "F"], ["results", "结果分析", "R"]] },
];

export function AppShell({ active, onNavigate, projectName, health, children }: Props) {
  return (
    <div className="app-frame">
      <header className="top-header">
        <button className="brand-lockup" onClick={() => onNavigate("dashboard")}>
          <span className="brand-symbol">TF</span>
          <span><strong>TechForecast</strong><small>证据约束技术预测平台</small></span>
        </button>
        <div className="header-context">
          {projectName ? <span className="project-context">当前项目 <b>{projectName}</b></span> : null}
          <span className={`health-dot ${health === "已连接" ? "online" : ""}`}>{health}</span>
        </div>
      </header>
      <aside className="side-nav">
        {groups.map((group) => (
          <section key={group.title}>
            <p>{group.title}</p>
            {group.items.map(([key, label, icon]) => (
              <button
                className={active === key ? "active" : ""}
                key={key}
                onClick={() => onNavigate(key)}
              >
                <span className="nav-icon">{icon}</span>{label}
              </button>
            ))}
          </section>
        ))}
        <div className="nav-foot">
          <span>预测节点</span>
          <strong>2030 · 2035 · 2040</strong>
          <small>2025 作为基线</small>
        </div>
      </aside>
      <main className="page-canvas">{children}</main>
    </div>
  );
}
