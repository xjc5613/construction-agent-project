import { useState } from "react";
import { apiRequest } from "../api";
import type { Job, Project, Topic } from "../types";
import { PageHeading, StatusPill } from "../components/UI";

export function ForecastPage({
  apiBase, project, topics, job, onJob,
}: {
  apiBase: string; project: Project; topics: Topic[]; job: Job | null;
  onJob: (job: Job) => void;
}) {
  const [options, setOptions] = useState({
    reasoning: true, roadmap: true, consistency: false, debate: false, multi: false,
  });
  const [override, setOverride] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const eligible = topics.filter((topic) => ["confirmed", "evidence_ready"].includes(topic.status));
  const start = async () => {
    setError("");
    try {
      const next = await apiRequest<Job>(apiBase, `/projects/${project.project_id}/forecast-jobs`, {
        method: "POST",
        body: JSON.stringify({
          topic_ids: eligible.map((topic) => topic.topic_id),
          time_nodes: ["2030", "2035", "2040"],
          override_evidence_gate: override,
          override_reason: reason,
          options: {
            enable_reasoning_chain: options.reasoning,
            enable_per_topic_roadmap: options.roadmap,
            enable_self_consistency: options.consistency,
            enable_multi_agent_debate: options.debate,
            enable_multi_model: options.multi,
            force_rerun: false,
          },
        }),
      });
      onJob(next);
    } catch (cause) { setError((cause as Error).message); }
  };
  return (
    <>
      <PageHeading eyebrow="FORECAST RUN" title="启动证据约束预测" description="证据快照冻结后依次执行主题预测、范式归纳、全局路线和分主题路线图。" />
      <section className="surface forecast-overview">
        <header className="surface-header"><div><h2>预测范围</h2><p>{eligible.length} 个已确认主题</p></div><div className="year-nodes"><span>2030</span><span>2035</span><span>2040</span></div></header>
        <div className="workflow-strip">
          {["证据快照", "主题预测", "范式归纳", "路线图", "报告图表"].map((item, index) => <div key={item}><span>{index + 1}</span><strong>{item}</strong><small>{index ? "待执行" : "启动时冻结"}</small></div>)}
        </div>
      </section>
      <section className="surface">
        <header className="surface-header"><div><h2>增强配置</h2><p>默认开启推理链和分主题路线图</p></div></header>
        <div className="option-grid">
          {([
            ["reasoning", "推理链条", "记录结论与证据关联"],
            ["roadmap", "分主题路线图", "生成三节点发展路径"],
            ["consistency", "自洽性验证", "多次采样一致性评估"],
            ["debate", "多 Agent 辩论", "技术、产业与风险交叉评审"],
            ["multi", "多模型集成", "需要配置额外模型"],
          ] as const).map(([key, label, note]) => <label key={key}><input type="checkbox" checked={options[key]} onChange={(event) => setOptions({ ...options, [key]: event.target.checked })} /><span /><div><strong>{label}</strong><small>{note}</small></div></label>)}
        </div>
        <label className="override-row"><input type="checkbox" checked={override} onChange={(event) => setOverride(event.target.checked)} /><span>允许证据不足时继续</span><input value={reason} disabled={!override} onChange={(event) => setReason(event.target.value)} placeholder="必须填写覆盖理由" /></label>
        {error ? <div className="error-banner">{error}</div> : null}
        <div className="form-actions"><button className="primary-button large-button" disabled={!eligible.length || job?.status === "running" || (override && !reason.trim())} onClick={start}>冻结证据并启动预测</button></div>
      </section>
      {job ? <section className="surface job-progress">
        <header className="surface-header"><div><h2>任务 {job.job_id}</h2><p>当前阶段：{job.current_stage}</p></div><StatusPill status={job.status} /></header>
        <div className="progress-line large"><i style={{ width: `${Math.round(job.progress * 100)}%` }} /></div>
        <div className="step-list">{job.steps.map((step) => <div className={step.status} key={step.name}><span /><strong>{step.name}</strong><small>{step.message || step.status}</small></div>)}</div>
        {job.error ? <div className="error-banner">{job.error}</div> : null}
      </section> : null}
    </>
  );
}
