import type { Project } from "../types";

export type EvidenceState = "observed" | "derived" | "predicted" | "agent" | "reviewed";

const labels: Record<EvidenceState, [string, string]> = {
  observed: ["实测", "●"], derived: ["推导", "◆"], predicted: ["预测", "△"],
  agent: ["Agent 生成", "✦"], reviewed: ["人工已审", "✓"],
};

export function EvidenceBadge({ state }: { state: EvidenceState }) {
  const [label, symbol] = labels[state];
  return <span className={`evidence-badge ${state}`}><b aria-hidden="true">{symbol}</b>{label}</span>;
}

export function ProjectScopeBar({ project, mode, onMode }: {
  project: Project; mode: "researcher" | "advanced"; onMode: (mode: "researcher" | "advanced") => void;
}) {
  const contract = project.research_contract;
  return <section className="scope-bar" aria-label="冻结研究范围">
    <div><small>研究契约</small><strong>v{contract?.version ?? project.research_contract_version ?? 2}</strong></div>
    <div><small>数据截止</small><strong>{contract?.default_cutoff ?? "历史契约"}</strong></div>
    <div><small>覆盖说明</small><strong>{contract?.incomplete_years?.includes(2025) ? "2025 部分年度" : "完整年度"}</strong></div>
    <div><small>技术范围</small><strong>{project.technology_name || "未指定"}</strong></div>
    <div><small>基线 / 节点</small><strong>{project.baseline_year} → {(contract?.target_years ?? project.forecast_nodes).join(" / ")}</strong></div>
    <label>视图
      <select value={mode} onChange={(event) => onMode(event.target.value as "researcher" | "advanced")}>
        <option value="researcher">研究者</option><option value="advanced">高级</option>
      </select>
    </label>
  </section>;
}
