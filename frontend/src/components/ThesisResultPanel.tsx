type ThesisResult = {
  job: {job_id: string};
  packet: {
    packet_version_id?: string; checksum?: string;
    validation_summary?: Record<string, unknown>;
    mapping_attachments?: Array<{attachment_id: string; mapping_state: string; row_count?: number}>;
  };
  state: {
    waiting_for?: string; coverage?: Record<string, number>;
    roadmaps?: Array<{milestone_id: string; object_id: string; period: string; capability: string;
      prerequisites: string[]; evidence_ids: string[]; retained_objections: string[]}>;
    synthesis?: {unresolved_gaps?: string[]};
  };
  trace: {
    claims?: Array<{claim_version_id: string; claim: {claim_id: string; version: number;
      statement: string; support_level: string; evidence_ids: string[]; parent_version_id?: string}}>;
    findings?: Array<{finding_id: string; claim_id: string; reviewer_role: string;
      severity: string; status: string; message: string; closed_by_version_id?: string}>;
    adjudications?: Array<{adjudication_id: string; claim_id: string; decision: string; reason: string}>;
    states?: Array<{claim_id: string; status: string}>;
  };
  semantic_note: string;
};

export function ThesisResultPanel({result}: {result: ThesisResult}) {
  const coverage = result.state.coverage ?? {};
  return <section className="thesis-result" aria-label="演化证据约束研判结果">
    <header className="panel-head">
      <div><div className="eyebrow">CHAPTER 4 → CHAPTER 5</div><h2>演化证据约束的多智能体研判</h2></div>
      <a className="primary" href={`/api/thesis/jobs/${encodeURIComponent(result.job.job_id)}/export`}>导出研究包</a>
    </header>
    <p className="subtitle">{result.semantic_note}</p>
    <div className="stat-row">
      <div className="stat"><div className="stat-num">{String(coverage.accepted ?? 0)}</div><div className="stat-label">已接受命题</div></div>
      <div className="stat"><div className="stat-num">{String(coverage.downgraded ?? 0)}</div><div className="stat-label">降级保留</div></div>
      <div className="stat"><div className="stat-num">{String(coverage.deferred ?? 0)}</div><div className="stat-label">延后判断</div></div>
      <div className="stat"><div className="stat-num">{String(coverage.revision_exhausted ?? 0)}</div><div className="stat-label">修订耗尽</div></div>
    </div>
    <details open><summary>冻结证据包</summary>
      <code>{result.packet.packet_version_id} · {result.packet.checksum}</code>
      {(result.packet.mapping_attachments ?? []).map(item => <p key={item.attachment_id}>
        映射：{item.mapping_state}{item.row_count != null ? ` · 报告 ${item.row_count} 条` : ""}
      </p>)}
    </details>
    <details open><summary>命题版本、支持等级与引用</summary>
      {(result.trace.claims ?? []).map(item => <article className="forecast-card" key={item.claim_version_id}>
        <strong>{item.claim.claim_id} · v{item.claim.version} · {item.claim.support_level}</strong>
        <p>{item.claim.statement}</p><small>证据：{item.claim.evidence_ids.join("、") || "证据不足"}</small>
      </article>)}
    </details>
    <details><summary>双重评审、闭环与裁决</summary>
      {(result.trace.findings ?? []).map(item => <article className="forecast-card" key={item.finding_id}>
        <strong>{item.reviewer_role} · {item.severity} · {item.status}</strong><p>{item.message}</p>
      </article>)}
      {(result.trace.adjudications ?? []).map(item => <p key={item.adjudication_id}>
        {item.claim_id} → {item.decision}：{item.reason}
      </p>)}
    </details>
    <details><summary>路线图前置条件与未解决缺口</summary>
      {(result.state.roadmaps ?? []).map(item => <article className="forecast-card" key={item.milestone_id}>
        <strong>{item.object_id} · {item.period}</strong><p>{item.capability}</p>
        <small>前置：{item.prerequisites.join("、") || "无"} · 证据：{item.evidence_ids.join("、")}</small>
      </article>)}
      <p>未解决缺口：{result.state.synthesis?.unresolved_gaps?.join("；") || "无"}</p>
    </details>
  </section>;
}

export type {ThesisResult};
