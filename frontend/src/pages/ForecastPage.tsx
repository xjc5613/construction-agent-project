import { useMemo, useRef, useState } from "react";
import { apiMutation, apiRequest } from "../api";
import type { Job, Project, Readiness, Topic } from "../types";
import { ConfirmationDialog, DisabledReason, InlineError, PageHeading, StatusPill, type ConfirmationPreview } from "../components/UI";
import { useDirtyForm } from "../dirty";

type StartPreview = ConfirmationPreview & { readiness: Readiness; workload: { estimated_model_calls?: number; pricing_estimate?: number | null } };

export function ForecastPage({ apiBase, project, topics, job, readiness, onJob }: {
  apiBase: string; project: Project; topics: Topic[]; job: Job | null; readiness: Readiness | null; onJob: (job: Job) => void;
}) {
  const [options, setOptions] = useState({ reasoning: true, roadmap: true, consistency: false, debate: false, multi: false });
  const [override, setOverride] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<StartPreview | null>(null);
  const [pending, setPending] = useState(false);
  const startButtonRef = useRef<HTMLButtonElement>(null);
  useDirtyForm(`forecast:${project.project_id}`, override || Boolean(reason) || !options.reasoning || !options.roadmap || options.consistency || options.debate || options.multi);
  const eligible = topics.filter((topic) => ["confirmed", "evidence_ready"].includes(topic.status) && !topic.requires_review);
  const active = Boolean(job && ["queued", "running", "cancelling"].includes(job.status)) || Boolean(readiness?.forecast.active_job_id);
  const request = useMemo(() => ({
    topic_ids: eligible.map((topic) => topic.topic_id), time_nodes: project.forecast_nodes.map(String),
    override_evidence_gate: override, override_reason: reason.trim(),
    options: { enable_reasoning_chain: options.reasoning, enable_per_topic_roadmap: options.roadmap, enable_self_consistency: options.consistency, enable_multi_agent_debate: options.debate, enable_multi_model: options.multi, force_rerun: false },
  }), [eligible.map((item) => item.topic_id).join(","), project.forecast_nodes.join(","), override, reason, options]);
  const disabledReason = active ? "已有任务正在排队、运行或取消，请等待状态结束。"
    : !readiness ? "正在加载项目预测条件。"
      : readiness.forecast.blocking_reasons.length ? readiness.forecast.blocking_reasons.join("；")
        : readiness.forecast.override_reasons.length && (!override || !reason.trim()) ? "证据不足：勾选覆盖并填写理由后才能继续。" : "";

  const openPreview = async () => {
    setPending(true); setError("");
    try {
      setPreview(await apiRequest<StartPreview>(apiBase, `/projects/${project.project_id}/forecast-jobs/preview`, { method: "POST", body: JSON.stringify(request) }));
    } catch (cause) { setError((cause as Error).message); }
    finally { setPending(false); }
  };
  const start = async () => {
    if (!preview) return;
    setPending(true); setError("");
    try {
      const next = await apiMutation<Job>(`forecast-start:${project.project_id}`, apiBase, `/projects/${project.project_id}/forecast-jobs`, {
        method: "POST", body: JSON.stringify({ ...request, confirmation_token: preview.confirmation_token, idempotency_key: crypto.randomUUID() }),
      });
      setPreview(null); onJob(next);
    } catch (cause) { setError((cause as Error).message); }
    finally { setPending(false); }
  };
  return <>
    <PageHeading eyebrow="FORECAST RUN" title="启动证据约束预测" description="确认证据、模型调用量和增强配置后，冻结快照并创建唯一任务。" />
    <section className="surface forecast-overview"><header className="surface-header"><div><h2>{project.technology_name || "历史项目"} · 目标 {project.target_year}</h2><p>{project.baseline_year} 基线 · {eligible.length} 个已确认主题</p></div><div className="year-nodes">{project.forecast_nodes.map((year) => <span key={year}>{year}</span>)}</div></header>
      <div className="workflow-strip">{["证据快照", "主题预测", "范式归纳", "路线图", "报告图表"].map((item, index) => <div key={item}><span>{index + 1}</span><strong>{item}</strong><small>{index ? "待执行" : "启动时冻结"}</small></div>)}</div>
    </section>
    {readiness ? <section className="surface readiness-panel"><header className="surface-header"><div><h2>证据门禁</h2><p>完整性 {readiness.evidence.score}% · {readiness.evidence.sufficient ? "证据充分" : "证据不足"}</p></div><StatusPill status={readiness.evidence.sufficient ? "ready_to_forecast" : "needs_review"} /></header>
      {[...readiness.forecast.blocking_reasons, ...readiness.forecast.override_reasons].length ? <ul>{[...readiness.forecast.blocking_reasons, ...readiness.forecast.override_reasons].map((item) => <li key={item}>{item}</li>)}</ul> : <p className="success-note">所有预测启动条件均已满足。</p>}
    </section> : null}
    <section className="surface"><header className="surface-header"><div><h2>增强配置</h2><p>默认开启推理链和分主题路线图</p></div></header>
      <div className="option-grid">{([ ["reasoning", "推理链条", "记录结论与证据关联"], ["roadmap", "分主题路线图", "按目标年份生成累计路径"], ["consistency", "自洽性验证", "多次采样一致性评估"], ["debate", "多 Agent 辩论", "技术、产业与风险交叉评审"], ["multi", "多模型集成", "需要配置额外模型"] ] as const).map(([key, label, note]) => <label key={key}><input type="checkbox" checked={options[key]} onChange={(event) => setOptions({ ...options, [key]: event.target.checked })} /><span aria-hidden="true" /><div><strong>{label}</strong><small>{note}</small></div></label>)}</div>
      <label className="override-row"><input type="checkbox" checked={override} onChange={(event) => setOverride(event.target.checked)} /><span>允许证据不足时继续</span><input aria-label="证据门禁覆盖理由" value={reason} disabled={!override} onChange={(event) => setReason(event.target.value)} placeholder="必须填写覆盖理由" /></label>
      <InlineError message={error} />
      <div className="form-actions"><button ref={startButtonRef} className="primary-button large-button" aria-describedby={disabledReason ? "forecast-disabled-reason" : undefined} disabled={pending || Boolean(disabledReason)} onClick={() => void openPreview()}>{pending ? "正在检查…" : "检查并启动预测"}</button></div>
      {disabledReason ? <DisabledReason id="forecast-disabled-reason">{disabledReason}</DisabledReason> : null}
    </section>
    {job ? <section className="surface job-progress"><header className="surface-header"><div><h2>任务 {job.job_id}</h2><p>当前阶段：{job.current_stage}</p></div><StatusPill status={job.status} /></header><div className="progress-line large"><i style={{ width: `${Math.round(job.progress * 100)}%` }} /></div><div className="step-list">{job.steps.map((step) => <div className={step.status} key={step.name}><span /><strong>{step.name}</strong><small>{step.message || step.status}</small></div>)}</div>{job.error ? <InlineError message={job.error} /> : null}</section> : null}
    {preview ? <ConfirmationDialog title="确认启动预测" preview={preview} pending={pending} confirmLabel="冻结证据并启动" restoreFocusRef={startButtonRef} onClose={() => setPreview(null)} onConfirm={() => void start()}>
      <p>将为 {eligible.length} 个主题创建任务，预计模型调用 <strong>{preview.workload.estimated_model_calls ?? "—"}</strong> 次；{preview.workload.pricing_estimate == null ? "当前未配置价格，无法估算费用" : `预计费用 ${preview.workload.pricing_estimate}`}。</p>
      {override ? <p className="warning-banner"><strong>证据覆盖理由</strong><span>{reason}</span></p> : null}
    </ConfirmationDialog> : null}
  </>;
}
