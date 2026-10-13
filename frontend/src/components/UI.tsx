import { useEffect, useId, useRef, type ButtonHTMLAttributes, type ReactNode, type RefObject } from "react";

export function PageHeading({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description: string; actions?: ReactNode }) {
  return <div className="page-heading"><div>{eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}<h1>{title}</h1><p>{description}</p></div>{actions ? <div className="heading-actions">{actions}</div> : null}</div>;
}

export function Metric({ label, value, note, tone = "violet" }: { label: string; value: ReactNode; note: string; tone?: string }) {
  return <article className={`metric-card ${tone}`}><span className="metric-icon" /><small>{label}</small><strong>{value}</strong><p>{note}</p></article>;
}

export function StatusPill({ status }: { status: string }) {
  const labels: Record<string, string> = {
    active: "使用中", deprecated: "已废弃", draft: "草稿", published: "已发布", inactive: "已停用",
    candidate: "待校准", confirmed: "已确认", evidence_ready: "证据就绪", running: "运行中", queued: "排队中",
    cancelling: "取消中", cancelled: "已取消", completed: "已完成", partial_failed: "部分失败", failed: "失败",
    ready: "已解析", needs_review: "待复核", parsed: "已解析", fallback: "兜底结果", archived: "已归档",
    deleted: "已删除", merged: "已合并", material_ready: "材料就绪", topics_review: "主题审阅",
    evidence_review: "证据审阅", ready_to_forecast: "可预测", forecasting: "预测中", asset_failed: "产物缺失",
    available: "可进入", blocked: "未开放", hidden: "未显示", needs_mapping: "待映射",
    needs_split: "待拆分", legacy: "兼容数据",
  };
  return <span className={`status-pill ${status}`}>{labels[status] ?? status}</span>;
}

export function EmptyState({ title, note }: { title: string; note: string }) {
  return <div className="empty-panel"><span aria-hidden="true">+</span><strong>{title}</strong><p>{note}</p></div>;
}

export function InlineError({ message }: { message?: string }) {
  return message ? <div className="error-banner" role="alert">{message}</div> : null;
}

export function LoadError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div className="empty-panel" role="alert"><strong>加载失败</strong><p>{message}</p><button onClick={onRetry}>重试</button></div>;
}

export function DisabledReason({ id, children }: { id: string; children: ReactNode }) {
  return <p id={id} className="disabled-reason">{children}</p>;
}

export function PendingButton({ pending, pendingLabel = "处理中…", children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { pending?: boolean; pendingLabel?: string }) {
  return <button {...props} disabled={pending || props.disabled} aria-busy={pending || undefined}>{pending ? pendingLabel : children}</button>;
}

export function Modal({ title, onClose, children, wide = false, pending = false, initialFocusRef, restoreFocusRef }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean; pending?: boolean; initialFocusRef?: RefObject<HTMLElement | null>; restoreFocusRef?: RefObject<HTMLElement | null> }) {
  const titleId = useId();
  const cardRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    (initialFocusRef?.current ?? closeRef.current)?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !pending) onClose();
      if (event.key !== "Tab" || !cardRef.current) return;
      const focusable = [...cardRef.current.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])')];
      if (!focusable.length) return;
      const first = focusable[0]; const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); (restoreFocusRef?.current ?? previous)?.focus(); };
  }, [onClose, pending, initialFocusRef, restoreFocusRef]);
  return <div className="modal-layer" onMouseDown={() => { if (!pending) onClose(); }}>
    <section ref={cardRef} role="dialog" aria-modal="true" aria-labelledby={titleId} className={`modal-card ${wide ? "wide" : ""}`} onMouseDown={(event) => event.stopPropagation()}>
      <header><h2 id={titleId}>{title}</h2><button ref={closeRef} aria-label="关闭对话框" disabled={pending} onClick={onClose}>×</button></header>{children}
    </section>
  </div>;
}

export type ConfirmationPreview = { confirmation_token: string; impact?: Record<string, unknown>; before?: unknown; after?: unknown; warnings?: string[] };

export function ConfirmationDialog({ title, preview, pending, confirmLabel = "确认操作", onConfirm, onClose, children, restoreFocusRef }: { title: string; preview: ConfirmationPreview; pending?: boolean; confirmLabel?: string; onConfirm: () => void; onClose: () => void; children?: ReactNode; restoreFocusRef?: RefObject<HTMLElement | null> }) {
  return <Modal title={title} onClose={onClose} pending={pending} restoreFocusRef={restoreFocusRef}>
    <div className="confirmation-body">{children}{preview.warnings?.length ? <div className="warning-banner"><strong>请确认影响</strong><span>{preview.warnings.join("；")}</span></div> : null}
      {preview.impact && Object.keys(preview.impact).length ? <dl className="impact-list">{Object.entries(preview.impact).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{typeof value === "object" ? JSON.stringify(value) : String(value ?? "—")}</dd></div>)}</dl> : null}
    </div><div className="form-actions"><button onClick={onClose} disabled={pending}>返回</button><PendingButton className="primary-button" pending={pending} onClick={onConfirm}>{confirmLabel}</PendingButton></div>
  </Modal>;
}
