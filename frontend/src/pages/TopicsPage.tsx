import { useEffect, useState } from "react";
import { apiRequest } from "../api";
import type { Project, Topic } from "../types";
import { EmptyState, PageHeading, StatusPill } from "../components/UI";

export function TopicsPage({
  apiBase, project, initialTopics = [], onEvidence,
}: { apiBase: string; project: Project; initialTopics?: Topic[]; onEvidence: () => void }) {
  const [topics, setTopics] = useState<Topic[]>(initialTopics);
  const [selected, setSelected] = useState<string[]>([]);
  const [newName, setNewName] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);

  const refresh = async () => {
    const data = await apiRequest<{ items: Topic[] }>(
      apiBase,
      `/projects/${project.project_id}/topics?include_deleted=${includeInactive}`,
    );
    setTopics(data.items);
  };
  useEffect(() => { void refresh(); }, [project.project_id, includeInactive]);

  const confirm = async (topicId: string) => {
    await apiRequest(apiBase, `/projects/${project.project_id}/topics/${topicId}/confirm`, { method: "POST" });
    await refresh();
  };
  const remove = async (topicId: string) => {
    await apiRequest(apiBase, `/projects/${project.project_id}/topics/${topicId}`, { method: "DELETE" });
    await refresh();
  };
  const archive = async (topicId: string) => {
    await apiRequest(apiBase, `/projects/${project.project_id}/topics/${topicId}/archive`, { method: "POST" });
    await refresh();
  };
  const restore = async (topicId: string) => {
    await apiRequest(apiBase, `/projects/${project.project_id}/topics/${topicId}/restore`, { method: "POST" });
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
    if (!newName.trim()) return;
    await apiRequest(apiBase, `/projects/${project.project_id}/topics`, {
      method: "POST", body: JSON.stringify({ topic_name: newName, keywords: [] }),
    });
    setNewName(""); await refresh();
  };
  const merge = async () => {
    if (selected.length < 2 || !newName.trim()) return;
    await apiRequest(apiBase, `/projects/${project.project_id}/topics/merge`, {
      method: "POST", body: JSON.stringify({ topic_ids: selected, topic_name: newName }),
    });
    setSelected([]); setNewName(""); await refresh();
  };
  return (
    <>
      <PageHeading
        eyebrow="TOPIC CALIBRATION" title="技术主题校准"
        description="删除噪声主题、合并同义方向或补充新主题，确认后才能检索基础证据。"
        actions={<button className="primary-button" disabled={!topics.some((topic) => topic.status === "confirmed")} onClick={onEvidence}>进入证据审阅</button>}
      />
      <section className="surface form-surface">
        <div className="inline-form topic-create">
          <label>主题名称<input value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="输入新增或合并后的主题名称" /></label>
          <button className="outline-button" onClick={add}>新增主题</button>
          <button className="primary-button" disabled={selected.length < 2} onClick={merge}>合并已选 ({selected.length})</button>
        </div>
      </section>
      <section className="surface">
        <header className="surface-header">
          <div><h2>候选主题</h2><p>共 {topics.length} 个，已确认 {topics.filter((item) => item.status === "confirmed" || item.status === "evidence_ready").length} 个</p></div>
          <label className="inline-check"><input type="checkbox" checked={includeInactive} onChange={(event) => setIncludeInactive(event.target.checked)} />显示已删除/归档</label>
        </header>
        {topics.length ? <div className="data-table">
          <div className="table-head topic-list"><span>选择</span><span>技术主题</span><span>关键词与证据</span><span>状态</span><span>操作</span></div>
          {topics.map((topic) => <div className="table-row topic-list" key={topic.topic_id}>
            <input type="checkbox" checked={selected.includes(topic.topic_id)} onChange={(event) => setSelected((items) => event.target.checked ? [...items, topic.topic_id] : items.filter((id) => id !== topic.topic_id))} />
            <div><strong contentEditable suppressContentEditableWarning onBlur={(event) => void rename(topic, event.currentTarget.textContent || "")}>{topic.topic_name}</strong><small>证据评分 {Math.round(topic.evidence_score)} · 点击名称可编辑</small></div>
            <div className="topic-evidence"><div>{topic.keywords.slice(0, 4).map((keyword) => <span key={keyword}>{keyword}</span>)}</div><details><summary>{topic.evidence[0]?.content || "等待证据检索"}</summary>{topic.evidence.map((item, index) => <p key={index}>{item.content || item.quote} <b>{item.location}</b></p>)}</details></div>
            <StatusPill status={topic.status} />
            <div className="row-actions">
              {topic.status === "candidate" ? <button onClick={() => confirm(topic.topic_id)}>确认</button> : null}
              {["archived", "deleted"].includes(topic.status) ? <button onClick={() => restore(topic.topic_id)}>恢复</button> : null}
              {!["archived", "deleted", "merged"].includes(topic.status) ? <button onClick={() => archive(topic.topic_id)}>归档</button> : null}
              {!["deleted", "merged"].includes(topic.status) ? <button className="danger" onClick={() => remove(topic.topic_id)}>删除</button> : null}
            </div>
          </div>)}
        </div> : <EmptyState title="暂无候选主题" note="请先在输入材料页面执行主题提取。" />}
      </section>
    </>
  );
}
