import type { Project, Readiness } from "../types";
import { Metric, PageHeading, StatusPill } from "../components/UI";

const periodLabels: Record<string, string> = {
  "2010_2015": "2010-2015",
  "2016_2020": "2016-2020",
  "2021_2026": "2021-2026",
};

export function ProjectOverviewPage({
  project, readiness, onOpen, onOpenLibrary,
}: {
  project: Project;
  readiness: Readiness;
  onOpen: (route: string) => void;
  onOpenLibrary: () => void;
}) {
  const coverage = readiness.coverage ?? project.coverage;
  return (
    <>
      <PageHeading
        eyebrow="PROJECT OVERVIEW"
        title={project.name}
        description={`${project.technology_name || "历史项目"} · ${project.baseline_year} 基线 → ${project.target_year} 目标`}
        actions={<button className="primary-button" onClick={() => onOpen(readiness.recommended_action.route)}>{readiness.recommended_action.label}</button>}
      />
      <div className="metric-grid four compact">
        <Metric label="流程完整度" value={`${readiness.progress_percent}%`} note={readiness.current_stage} />
        <Metric label="技术范围" value={project.technology_name || "历史"} note={project.legacy_mode ? "旧范围合同" : `目录版本 ${project.scope_version}`} tone="green" />
        <Metric label="预测节点" value={project.forecast_nodes.length} note={project.forecast_nodes.join(" / ")} tone="amber" />
        <Metric label="基础数据" value={coverage?.complete ? "完整" : "待补充"} note={coverage?.missing?.join("；") || "三个历史阶段均有记录"} tone="red" />
      </div>
      <section className="surface project-flow-overview">
        <header className="surface-header"><div><h2>预测流程</h2><p>系统根据真实材料、主题、证据和任务状态计算</p></div></header>
        <div className="project-step-grid">
          {readiness.steps.filter((step) => step.visible).map((step, index) => (
            <button key={step.id} className={step.state} onClick={() => onOpen(step.route)}>
              <span>{index + 1}</span>
              <div><strong>{step.label}</strong><small>{step.state === "completed" ? "已完成" : step.blocking_reasons[0] || "可进入"}</small></div>
              <StatusPill status={step.state} />
            </button>
          ))}
        </div>
      </section>
      <section className="surface">
        <header className="surface-header">
          <div><h2>基础数据预检</h2><p>只统计项目范围内已映射、有效、已发布且包含记录的数据</p></div>
          {!coverage?.complete ? <button className="outline-button" onClick={onOpenLibrary}>补充基础数据</button> : null}
        </header>
        <div className="coverage-grid">
          {Object.entries(coverage?.periods ?? {}).map(([period, values]) => (
            <article key={period}>
              <strong>{periodLabels[period] ?? period}</strong>
              <span>IPC {values.ipc_records ?? values.ipc ?? 0}</span>
              <span>论文 {values.paper_records ?? values.paper ?? 0}</span>
            </article>
          ))}
        </div>
        {coverage?.missing?.length ? <div className="warning-banner"><strong>存在数据缺口</strong><span>{coverage.missing.join("；")}</span></div> : null}
      </section>
    </>
  );
}
