import { useEffect, useState } from "react";
import { apiMutation, apiRequest } from "../api";
import type { Project, TechnologyNode, Topic } from "../types";
import { ConfirmationDialog, EmptyState, InlineError, PageHeading, StatusPill, type ConfirmationPreview } from "../components/UI";

export function TopicsPage({
  apiBase, project, initialTopics = [], onEvidence,
}: { apiBase: string; project: Project; initialTopics?: Topic[]; onEvidence: () => void }) {
  const [topics, setTopics] = useState<Topic[]>(initialTopics);
  const [selected, setSelected] = useState<string[]>([]);
  const [newName, setNewName] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [technologies, setTechnologies] = useState<TechnologyNode[]>([]);
  const [newTechnologyId, setNewTechnologyId] = useState("");
  const [editing, setEditing] = useState<{ id: string; name: string } | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [eligibility, setEligibility] = useState<Record<string, {
    eligible_dataset_count: number;
    coverage: { missing_periods: string[]; complete: boolean };
  }>>({});
  const [confirmation, setConfirmation] = useState<{ action: string; payload: Record<string, unknown>; preview: ConfirmationPreview } | null>(null);

  const refresh = async () => {
    const data = await apiRequest<{ items: Topic[] }>(
      apiBase,
      `/projects/${project.project_id}/topics?include_deleted=${includeInactive}`,
    );
    setTopics(data.items);
    const readiness = await Promise.all(data.items.map(async (topic) => {
      try {
        const value = await apiRequest<{ eligibility: typeof eligibility[string] }>(
          apiBase, `/projects/${project.project_id}/topics/${topic.topic_id}/readiness`,
        );
        return [topic.topic_id, value.eligibility] as const;
      } catch {
        return [topic.topic_id, { eligible_dataset_count: 0, coverage: { missing_periods: [], complete: false } }] as const;
      }
    }));
    setEligibility(Object.fromEntries(readiness));
  };
  useEffect(() => { void refresh(); }, [project.project_id, includeInactive]);
  useEffect(() => {
    apiRequest<{ nodes: TechnologyNode[] }>(apiBase, `/projects/${project.project_id}/technology-scope`)
      .then((data) => {
        const leaves = data.nodes.filter((item) => item.level === 3 && item.effective_status !== "inactive");
        setTechnologies(leaves);
        if (!newTechnologyId && leaves.length) setNewTechnologyId(leaves[0].node_id);
      });
  }, [apiBase, project.project_id]);

  const confirm = async (topicId: string) => {
    await apiRequest(apiBase, `/projects/${project.project_id}/topics/${topicId}/confirm`, { method: "POST" });
    await refresh();
  };
  const rename = async (topic: Topic, topicName: string) => {
    if (!topicName.trim() || topicName === topic.topic_name) return;
    await apiRequest(apiBase, `/projects/${project.project_id}/topics/${topic.topic_id}`, {
      method: "PATCH", body: JSON.stringify({ topic_name: topicName.trim(), requires_review: true, status: "candidate" }),
    });
    await refresh();
  };
  const add = async () => {
    if (!newName.trim() || !newTechnologyId) return;
    await apiRequest(apiBase, `/projects/${project.project_id}/topics`, {
      method: "POST", body: JSON.stringify({
        topic_name: newName, keywords: [],
        technologies: [{ technology_node_id: newTechnologyId, is_primary: true, relevance: 1, source: "manual" }],
      }),
    });
    setNewName(""); await refresh();
  };
  const setPrimaryTechnology = async (topic: Topic, technologyNodeId: string) => {
    const current = topic.technologies.length ? topic.technologies : [{
      technology_node_id: technologyNodeId, name: "", is_primary: true, relevance: 1, source: "manual",
    }];
    const next = current.some((item) => item.technology_node_id === technologyNodeId)
      ? current.map((item) => ({ ...item, is_primary: item.technology_node_id === technologyNodeId }))
      : [...current.map((item) => ({ ...item, is_primary: false })), { technology_node_id: technologyNodeId, is_primary: true, relevance: 1, source: "manual" }];
    await apiRequest(apiBase, `/projects/${project.project_id}/topics/${topic.topic_id}/technologies`, {
      method: "PUT", body: JSON.stringify(next.map(({ technology_node_id, is_primary, relevance, source }) => ({ technology_node_id, is_primary, relevance, source }))),
    });
    await refresh();
  };
  const previewAction = async (action: string, payload: Record<string, unknown>) => {
    setPending(true); setError("");
    try { setConfirmation({ action, payload, preview: await apiRequest<ConfirmationPreview>(apiBase, `/projects/${project.project_id}/topics/actions/preview`, { method: "POST", body: JSON.stringify({ action, payload }) }) }); }
    catch (cause) { setError((cause as Error).message); }
    finally { setPending(false); }
  };
  const commitAction = async () => {
    if (!confirmation) return;
    setPending(true); setError("");
    try {
      await apiMutation(`topic:${project.project_id}:${confirmation.action}`, apiBase, `/projects/${project.project_id}/topics/actions/commit`, { method: "POST", body: JSON.stringify({ ...confirmation, confirmation_token: confirmation.preview.confirmation_token, preview: undefined }) });
      if (confirmation.action === "merge") { setSelected([]); setNewName(""); }
      setConfirmation(null); await refresh();
    } catch (cause) { setError((cause as Error).message); }
    finally { setPending(false); }
  };
  return (
    <>
      <PageHeading
        eyebrow="TOPIC CALIBRATION" title="技术主题校准"
        description="删除噪声主题、合并同义方向或补充新主题，确认后才能检索基础证据。"
        actions={<button className="primary-button" disabled={!topics.some((topic) => topic.status === "confirmed")} onClick={onEvidence}>进入证据审阅</button>}
      />
      <InlineError message={error} />
      <section className="surface form-surface">
        <div className="inline-form topic-create">
          <label>主题名称<input value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="输入新增或合并后的主题名称" /></label>
          <label>主技术<select value={newTechnologyId} onChange={(event) => setNewTechnologyId(event.target.value)}>{technologies.map((item) => <option value={item.node_id} key={item.node_id}>{item.path_text || item.name}</option>)}</select></label>
          <button className="outline-button" onClick={add}>新增主题</button>
          <button className="primary-button" disabled={selected.length < 2 || !newName.trim() || pending} onClick={() => void previewAction("merge", { topic_ids: selected, topic_name: newName })}>合并已选 ({selected.length})</button>
        </div>
      </section>
      <section className="surface">
        <header className="surface-header">
          <div><h2>候选主题</h2><p>共 {topics.length} 个，已确认 {topics.filter((item) => item.status === "confirmed" || item.status === "evidence_ready").length} 个</p></div>
          <label className="inline-check"><input type="checkbox" checked={includeInactive} onChange={(event) => setIncludeInactive(event.target.checked)} />显示已删除/归档</label>
        </header>
        {topics.length ? <div className="data-table" role="table" aria-label="候选主题列表">
          <div className="table-head topic-list" role="row"><span role="columnheader">选择</span><span role="columnheader">技术主题</span><span role="columnheader">关键词与证据</span><span role="columnheader">状态</span><span role="columnheader">操作</span></div>
          {topics.map((topic) => <div className="table-row topic-list" role="row" key={topic.topic_id}>
            <input aria-label={`选择主题 ${topic.topic_name}`} type="checkbox" checked={selected.includes(topic.topic_id)} onChange={(event) => setSelected((items) => event.target.checked ? [...items, topic.topic_id] : items.filter((id) => id !== topic.topic_id))} />
            <div role="cell">{editing?.id === topic.topic_id ? <div className="inline-edit"><label>主题名称<input value={editing.name} onChange={(event) => setEditing({ ...editing, name: event.target.value })} /></label><button onClick={() => { void rename(topic, editing.name); setEditing(null); }}>保存</button><button onClick={() => setEditing(null)}>取消</button></div> : <><strong>{topic.topic_name}</strong><button className="text-action" onClick={() => setEditing({ id: topic.topic_id, name: topic.topic_name })}>编辑名称</button></>}<small>证据评分 {Math.round(topic.evidence_score)}</small><small>可用数据集 {eligibility[topic.topic_id]?.eligible_dataset_count ?? 0} 个{eligibility[topic.topic_id]?.coverage.missing_periods.length ? ` · 缺少 ${eligibility[topic.topic_id].coverage.missing_periods.join("、")}` : ""}</small></div>
            <div className="topic-evidence"><div>{topic.technologies.map((technology) => <span key={technology.technology_node_id}>{technology.is_primary ? "主 · " : ""}{technology.name}</span>)}</div><select value={topic.technologies.find((item) => item.is_primary)?.technology_node_id ?? ""} onChange={(event) => void setPrimaryTechnology(topic, event.target.value)}><option value="">选择主技术</option>{technologies.map((item) => <option value={item.node_id} key={item.node_id}>{item.name}</option>)}</select><details><summary>{topic.evidence[0]?.content || "等待证据检索"}</summary>{topic.evidence.map((item, index) => <p key={index}>{item.content || item.quote} <b>{item.location}</b></p>)}</details></div>
            <StatusPill status={topic.status} />
            <div className="row-actions">
              {topic.status === "candidate" ? <button onClick={() => confirm(topic.topic_id)}>确认</button> : null}
              {["archived", "deleted"].includes(topic.status) ? <button onClick={() => void previewAction("restore", { topic_id: topic.topic_id })}>恢复</button> : null}
              {!["archived", "deleted", "merged"].includes(topic.status) ? <button onClick={() => void previewAction("archive", { topic_id: topic.topic_id })}>归档</button> : null}
              {!["deleted", "merged"].includes(topic.status) ? <button className="danger" onClick={() => void previewAction("delete", { topic_id: topic.topic_id })}>删除</button> : null}
            </div>
          </div>)}
        </div> : <EmptyState title="暂无候选主题" note="请先在输入材料页面执行主题提取。" />}
      </section>
      {confirmation ? <ConfirmationDialog title={{ merge: "确认合并主题", archive: "确认归档主题", delete: "确认删除主题", restore: "确认恢复主题" }[confirmation.action] ?? "确认主题操作"} preview={confirmation.preview} pending={pending} onClose={() => setConfirmation(null)} onConfirm={() => void commitAction()} /> : null}
    </>
  );
}
