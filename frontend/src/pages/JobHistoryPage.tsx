import { useEffect, useState } from "react";
import { apiMutation, apiRequest } from "../api";
import type { Job, Project } from "../types";
import { ConfirmationDialog, EmptyState, InlineError, PageHeading, StatusPill, type ConfirmationPreview } from "../components/UI";

export function JobHistoryPage({
  apiBase, project, onOpen,
}: { apiBase: string; project: Project; onOpen: (job: Job) => void }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [confirmation, setConfirmation] = useState<{ job: Job; kind: "cancel" | "retry"; preview: ConfirmationPreview } | null>(null);
  const load = async () => {
    try {
      const data = await apiRequest<{ items: Job[] }>(apiBase, `/projects/${project.project_id}/forecast-jobs`);
      setJobs(data.items); setError("");
    } catch (cause) { setError((cause as Error).message); }
  };
  useEffect(() => { void load(); }, [project.project_id]);
  const previewAction = async (job: Job, kind: "cancel" | "retry") => {
    setBusy(job.job_id); setError("");
    try {
      const preview = await apiRequest<{ confirmation_token: string; warnings: string[]; impact: Record<string, unknown> }>(apiBase, `/forecast/jobs/${job.job_id}/${kind}/preview`, { method: "POST", body: JSON.stringify({}) });
      setConfirmation({ job, kind, preview });
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(""); }
  };
  const commitAction = async () => {
    if (!confirmation) return;
    const { job, kind, preview } = confirmation;
    setBusy(job.job_id); setError("");
    try {
      const next = await apiMutation<{ job: Job } | Job>(`job-${kind}:${job.job_id}`, apiBase, `/forecast/jobs/${job.job_id}/${kind}`, {
        method: "POST", body: JSON.stringify({ confirmation_token: preview.confirmation_token, payload: {}, idempotency_key: crypto.randomUUID() }),
      });
      setConfirmation(null);
      if (kind === "retry") onOpen(next as Job); else await load();
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(""); }
  };
  return <>
    <PageHeading eyebrow="FORECAST HISTORY" title="预测任务历史" description="恢复结果、查看证据限制，并管理取消与重试。" />
    <InlineError message={error} />
    <section className="surface">
      <header className="surface-header"><div><h2>{project.name}</h2><p>共 {jobs.length} 个任务</p></div></header>
      {jobs.length ? <div className="data-table" role="table" aria-label="预测任务历史">
        <div className="table-head job-list" role="row"><span role="columnheader">任务</span><span role="columnheader">状态</span><span role="columnheader">时间</span><span role="columnheader">操作</span></div>
        {jobs.map((job) => <div className="table-row job-list" role="row" key={job.job_id}>
          <div role="cell"><strong>{job.job_id}</strong><small>{job.parent_job_id ? `重试自 ${job.parent_job_id}` : job.evidence_limited ? `证据受限：${job.override_reason}` : "标准证据门禁"}</small>{job.missing_artifacts?.length ? <small>缺少产物：{job.missing_artifacts.join("、")}</small> : null}</div>
          <div role="cell"><StatusPill status={job.status} />{job.artifact_health === "degraded" ? <StatusPill status="asset_failed" /> : null}</div>
          <span role="cell">{job.created_at ? new Date(job.created_at).toLocaleString("zh-CN") : "—"}</span>
          <div role="cell" className="row-actions"><button onClick={() => onOpen(job)}>{job.result_available ? "打开结果" : "查看进度"}</button>{["queued", "running"].includes(job.status) ? <button disabled={busy === job.job_id} onClick={() => void previewAction(job, "cancel")}>取消</button> : null}{["failed", "partial_failed", "cancelled"].includes(job.status) ? <button disabled={busy === job.job_id} onClick={() => void previewAction(job, "retry")}>重试</button> : null}</div>
        </div>)}
      </div> : <EmptyState title="暂无预测任务" note="在启动预测页面确认配置后，任务会记录在这里。" />}
    </section>
    {confirmation ? <ConfirmationDialog title={confirmation.kind === "cancel" ? "确认取消预测任务" : "确认重试预测任务"} preview={confirmation.preview} pending={busy === confirmation.job.job_id} confirmLabel={confirmation.kind === "cancel" ? "确认取消" : "创建重试任务"} onConfirm={() => void commitAction()} onClose={() => setConfirmation(null)} /> : null}
  </>;
}
