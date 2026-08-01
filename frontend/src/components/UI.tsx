import type { ReactNode } from "react";

export function PageHeading({
  eyebrow, title, description, actions,
}: {
  eyebrow?: string; title: string; description: string; actions?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>{eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}<h1>{title}</h1><p>{description}</p></div>
      {actions ? <div className="heading-actions">{actions}</div> : null}
    </div>
  );
}

export function Metric({
  label, value, note, tone = "violet",
}: { label: string; value: ReactNode; note: string; tone?: string }) {
  return (
    <article className={`metric-card ${tone}`}>
      <span className="metric-icon" />
      <small>{label}</small>
      <strong>{value}</strong>
      <p>{note}</p>
    </article>
  );
}

export function StatusPill({ status }: { status: string }) {
  const labels: Record<string, string> = {
    draft: "草稿", published: "已发布", inactive: "已停用",
    candidate: "待校准", confirmed: "已确认", evidence_ready: "证据就绪",
    running: "运行中", queued: "排队中", completed: "已完成",
    partial_failed: "部分失败", failed: "失败", ready: "已解析",
    needs_review: "待复核", parsed: "已解析", fallback: "兜底结果",
    archived: "已归档", deleted: "已删除", merged: "已合并",
    material_ready: "材料就绪", topics_review: "主题审阅",
    evidence_review: "证据审阅", ready_to_forecast: "可预测",
    forecasting: "预测中", asset_failed: "图表失败",
  };
  return <span className={`status-pill ${status}`}>{labels[status] ?? status}</span>;
}

export function EmptyState({ title, note }: { title: string; note: string }) {
  return <div className="empty-panel"><span>+</span><strong>{title}</strong><p>{note}</p></div>;
}

export function Modal({
  title, onClose, children, wide = false,
}: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  return (
    <div className="modal-layer" onMouseDown={onClose}>
      <section className={`modal-card ${wide ? "wide" : ""}`} onMouseDown={(event) => event.stopPropagation()}>
        <header><h2>{title}</h2><button onClick={onClose}>×</button></header>
        {children}
      </section>
    </div>
  );
}
