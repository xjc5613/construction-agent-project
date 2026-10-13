import { useEffect, useMemo, useState } from "react";
import { apiMutation, apiRequest } from "../api";
import type { TechnologyNode, TechnologySummary } from "../types";
import { ConfirmationDialog, EmptyState, InlineError, Metric, PageHeading, StatusPill, type ConfirmationPreview } from "../components/UI";
import { useDirtyForm } from "../dirty";

function flatten(nodes: TechnologyNode[]): TechnologyNode[] {
  return nodes.flatMap((node) => [node, ...flatten(node.children ?? [])]);
}

function TreeNode({ node, selectedId, expanded, onSelect, onToggle }: {
  node: TechnologyNode; selectedId: string; expanded: Set<string>;
  onSelect: (node: TechnologyNode) => void; onToggle: (id: string) => void;
}) {
  const children = node.children ?? [];
  const state = node.effective_status ?? (node.status === "active" ? "active" : "inactive");
  return <div className={`technology-tree-node level-${node.level}`}>
    <div className={selectedId === node.node_id ? "selected" : ""}>
      <button className="tree-toggle" disabled={!children.length} onClick={() => onToggle(node.node_id)}>{children.length ? (expanded.has(node.node_id) ? "−" : "+") : "·"}</button>
      <button className="tree-label" onClick={() => onSelect(node)}><strong>{node.name}</strong><small>{node.level}级 · {children.length} 个下级</small></button>
      <StatusPill status={state} />
    </div>
    {children.length && expanded.has(node.node_id) ? <div className="technology-tree-children">{children.map((child) => <TreeNode key={child.node_id} node={child} selectedId={selectedId} expanded={expanded} onSelect={onSelect} onToggle={onToggle} />)}</div> : null}
  </div>;
}

export function TechnologyPage({ apiBase }: { apiBase: string }) {
  const [tree, setTree] = useState<TechnologyNode[]>([]);
  const [selected, setSelected] = useState<TechnologyNode | null>(null);
  const [savedSelected, setSavedSelected] = useState<TechnologyNode | null>(null);
  const [summary, setSummary] = useState<TechnologySummary | null>(null);
  const [expanded, setExpanded] = useState(new Set<string>());
  const [query, setQuery] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const [newName, setNewName] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [confirmation, setConfirmation] = useState<{ action: "archive" | "restore"; payload: Record<string, unknown>; preview: ConfirmationPreview } | null>(null);
  const editable = (value: TechnologyNode | null) => value ? {
    name: value.name, description: value.description, keywords: value.keywords,
    aliases: value.aliases, sort_order: value.sort_order, parent_id: value.parent_id,
  } : null;
  useDirtyForm("technology-edit", JSON.stringify(editable(selected)) !== JSON.stringify(editable(savedSelected)));

  const loadDetail = async (nodeId: string) => {
    const [detail, metrics] = await Promise.all([
      apiRequest<TechnologyNode>(apiBase, `/technologies/${nodeId}`),
      apiRequest<TechnologySummary>(apiBase, `/technologies/${nodeId}/summary`),
    ]);
    setSelected(detail); setSavedSelected(detail); setSummary(metrics);
    setExpanded((items) => new Set([...items, ...(detail.path?.map((item) => item.node_id) ?? [])]));
  };
  const load = async (keepId = selected?.node_id) => {
    const response = await apiRequest<{ items: TechnologyNode[] }>(apiBase, `/technologies?include_archived=${includeInactive}&q=${encodeURIComponent(query)}`);
    setTree(response.items);
    const all = flatten(response.items);
    const next = all.find((item) => item.node_id === keepId) ?? all[0] ?? null;
    if (next) await loadDetail(next.node_id); else { setSelected(null); setSummary(null); }
  };
  useEffect(() => { void load(); }, [includeInactive]);
  const allNodes = useMemo(() => flatten(tree), [tree]);

  const save = async () => {
    if (!selected) return;
    setPending(true); setError("");
    try {
      await apiRequest(apiBase, `/technologies/${selected.node_id}`, {
        method: "PATCH", body: JSON.stringify({
          name: selected.name, description: selected.description,
          keywords: selected.keywords, aliases: selected.aliases,
          sort_order: selected.sort_order, parent_id: selected.parent_id,
        }),
      });
      setMessage("技术目录已更新"); await load(selected.node_id);
    } catch (cause) { setError((cause as Error).message); } finally { setPending(false); }
  };
  const createChild = async () => {
    if (!selected || selected.level >= 3 || !newName.trim()) return;
    const child = await apiRequest<TechnologyNode>(apiBase, "/technologies", {
      method: "POST", body: JSON.stringify({ name: newName, level: selected.level + 1, parent_id: selected.node_id }),
    });
    setNewName(""); await load(child.node_id);
  };
  const previewLifecycle = async () => {
    if (!selected) return;
    const action = selected.status === "active" ? "archive" : "restore";
    const payload = action === "archive" ? { cascade: true } : {};
    setPending(true); setError("");
    try {
      setConfirmation({
        action, payload,
        preview: await apiRequest<ConfirmationPreview>(apiBase, `/technologies/${selected.node_id}/actions/preview`, { method: "POST", body: JSON.stringify({ action, payload }) }),
      });
    } catch (cause) { setError((cause as Error).message); } finally { setPending(false); }
  };
  const commitLifecycle = async () => {
    if (!selected || !confirmation) return;
    setPending(true); setError("");
    try {
      await apiMutation(`technology:${selected.node_id}:${confirmation.action}`, apiBase, `/technologies/${selected.node_id}/actions/commit`, {
        method: "POST", body: JSON.stringify({ action: confirmation.action, payload: confirmation.payload, confirmation_token: confirmation.preview.confirmation_token }),
      });
      setConfirmation(null); setMessage("技术状态已更新"); await load(selected.node_id);
    } catch (cause) { setError((cause as Error).message); } finally { setPending(false); }
  };

  return <>
    <PageHeading eyebrow="TECHNOLOGY CATALOG" title="技术目录" description="维护三级技术结构，并查看每项技术对应的论文、IPC 数据和项目引用。" actions={<button className="primary-button" disabled={!selected || pending} onClick={save}>保存目录修改</button>} />
    <InlineError message={error} />
    <div className="technology-layout">
      <section className="surface technology-directory">
        <header className="surface-header"><div><h2>三级技术目录</h2><p>{allNodes.length} 个可见节点</p></div></header>
        <div className="technology-search"><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索名称、关键词或别名" /><button onClick={() => void load()}>搜索</button></div>
        <label className="inline-check directory-check"><input type="checkbox" checked={includeInactive} onChange={(event) => setIncludeInactive(event.target.checked)} />显示已停用技术</label>
        <div className="technology-tree">{tree.map((node) => <TreeNode key={node.node_id} node={node} selectedId={selected?.node_id ?? ""} expanded={expanded} onSelect={(item) => void loadDetail(item.node_id)} onToggle={(id) => setExpanded((items) => { const next = new Set(items); next.has(id) ? next.delete(id) : next.add(id); return next; })} />)}{!tree.length ? <EmptyState title="没有匹配技术" note="请调整搜索条件。" /> : null}</div>
      </section>
      {selected ? <div className="technology-detail">
        <section className="surface technology-title-card">
          <div><small>{selected.path_text}</small><input aria-label="技术名称" className="technology-name-input" value={selected.name} onChange={(event) => setSelected({ ...selected, name: event.target.value })} /><StatusPill status={selected.effective_status ?? selected.status} /></div>
          <div className="row-actions"><button onClick={() => setAdvanced((value) => !value)}>{advanced ? "收起高级设置" : "高级设置"}</button><button onClick={() => void previewLifecycle()}>{selected.status === "active" ? "停用技术" : "恢复技术"}</button></div>
        </section>
        {summary ? <div className="metric-grid four compact"><Metric label="数据集" value={summary.datasets} note="有效已发布版本" /><Metric label="论文" value={summary.papers} note="可用于新预测" tone="green" /><Metric label="IPC 指标" value={summary.ipc_records} note="聚合专利指标记录" tone="amber" /><Metric label="项目引用" value={summary.projects} note={`${summary.child_count} 个直接下级`} tone="red" /></div> : null}
        {selected.level < 3 ? <section className="surface add-child"><header className="surface-header"><div><h2>新增下级技术</h2><p>添加 {selected.level + 1} 级目录节点</p></div></header><div><input value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="输入技术名称" /><button className="primary-button" onClick={() => void createChild()}>新增</button></div></section> : null}
        {advanced ? <div className="technology-detail-grid">
          <section className="surface technology-form">
            <header className="surface-header"><div><h2>匹配设置</h2><p>用于材料主题自动匹配</p></div></header>
            <label>技术描述<textarea value={selected.description} onChange={(event) => setSelected({ ...selected, description: event.target.value })} /></label>
            <label>关键词<input value={selected.keywords.join("，")} onChange={(event) => setSelected({ ...selected, keywords: event.target.value.split(/[，,]/).filter(Boolean) })} /></label>
            <label>别名<input value={selected.aliases.join("，")} onChange={(event) => setSelected({ ...selected, aliases: event.target.value.split(/[，,]/).filter(Boolean) })} /></label>
            <label>同级排序<input type="number" value={selected.sort_order} onChange={(event) => setSelected({ ...selected, sort_order: Number(event.target.value) })} /></label>
            {selected.level > 1 ? <label>上级技术<select value={selected.parent_id ?? ""} onChange={(event) => setSelected({ ...selected, parent_id: event.target.value || null })}>{allNodes.filter((item) => item.level === selected.level - 1 && item.effective_status !== "inactive").map((item) => <option value={item.node_id} key={item.node_id}>{item.path_text || item.name}</option>)}</select></label> : null}
          </section>
          <section className="surface technology-references">
            <header className="surface-header"><div><h2>治理信息</h2><p>稳定 ID、关联与不可修改记录</p></div></header>
            <code>{selected.node_id}</code>
            <div className="reference-metrics">{Object.entries(selected.references ?? {}).map(([key, value]) => <span key={key}><b>{value}</b>{key}</span>)}</div>
            <div className="relation-list">{selected.relations?.map((relation) => <p key={relation.relation_id}>{relation.source_name} <b>{relation.relation_type}</b> {relation.target_name}</p>)}</div>
            <details><summary>变更记录（{selected.changes?.length ?? 0}）</summary>{selected.changes?.map((change) => <p key={change.change_id}>{change.action} · {new Date(change.created_at).toLocaleString("zh-CN")}</p>)}</details>
          </section>
        </div> : null}
        {message ? <p className="success-note">{message}</p> : null}
      </div> : <EmptyState title="暂无技术节点" note="请初始化或新增技术目录。" />}
    </div>
    {confirmation ? <ConfirmationDialog title={confirmation.action === "archive" ? "确认停用技术" : "确认恢复技术"} preview={confirmation.preview} pending={pending} onClose={() => setConfirmation(null)} onConfirm={() => void commitLifecycle()} /> : null}
  </>;
}
