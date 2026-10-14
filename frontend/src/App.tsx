import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "./api";
import type { ForecastResult, JobStatus, TopicEvidence } from "./types";
import { TrlChart, UncertaintyHeatmap } from "./components/Charts";
import { ThesisResultPanel, type ThesisResult } from "./components/ThesisResultPanel";

const STAGE_LABEL: Record<string, string> = {
  prepare: "载入证据",
  execute: "主题预测（执行器）",
  think: "科学评审（思考者）",
  revise: "根据评审修正",
  roadmap: "绘制技术路线图",
  synthesize: "全局综合",
  done: "完成",
};

function confidenceColor(c: number) {
  return c >= 75 ? "#2f7d4f" : c >= 55 ? "#b08a2c" : "#b5483f";
}

export function App() {
  const [health, setHealth] = useState<boolean | null>(null);
  const [topics, setTopics] = useState<TopicEvidence[]>([]);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [result, setResult] = useState<ForecastResult | null>(null);
  const [error, setError] = useState("");
  const [thesisJobId, setThesisJobId] = useState("");
  const [thesisResult, setThesisResult] = useState<ThesisResult | null>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    apiRequest<{ ok: boolean }>("/health")
      .then((d) => setHealth(d.ok))
      .catch(() => setHealth(false));
    apiRequest<{ items: TopicEvidence[] }>("/seed-topics")
      .then((d) => setTopics(d.items))
      .catch(() => undefined);
  }, []);

  const poll = useCallback((jobId: string) => {
    if (timer.current) window.clearInterval(timer.current);
    timer.current = window.setInterval(async () => {
      try {
        const j = await apiRequest<JobStatus>(`/forecast/${jobId}`);
        setJob(j);
        if (j.status === "completed") {
          window.clearInterval(timer.current!);
          setResult(await apiRequest<ForecastResult>(`/forecast/${jobId}/result`));
        } else if (j.status === "failed") {
          window.clearInterval(timer.current!);
          setError(j.error || "预测失败");
        }
      } catch {
        /* keep polling */
      }
    }, 2000);
  }, []);

  const run = async () => {
    setError("");
    setResult(null);
    try {
      const j = await apiRequest<JobStatus>("/forecast", { method: "POST" });
      setJob(j);
      poll(j.job_id);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const loadThesisResult = async () => {
    if (!thesisJobId.trim()) return;
    setError("");
    try {
      setThesisResult(await apiRequest<ThesisResult>(`/thesis/jobs/${encodeURIComponent(thesisJobId.trim())}/result`));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const running = job && ["queued", "running"].includes(job.status);

  return (
    <div className="page">
      <header className="hero">
        <div className="eyebrow">TECHNOLOGY FORECAST · 2025 – 2040</div>
        <h1>智能建造技术发展路线图</h1>
        <p className="subtitle">
          基于 IPC 专利网络证据，采用 Think-and-Execute 反思式编排，
          对 9 个核心技术主题进行 2030 / 2035 / 2040 年趋势预测。
        </p>
        <div className="hero-actions">
          <button className="primary" onClick={run} disabled={!!running}>
            {running ? "预测进行中…" : "运行预测"}
          </button>
          <span className="conn">
            {health === null ? "连接中…" : health ? "● 后端已连接" : "● 后端未连接"}
          </span>
        </div>
        {error && <p className="error">{error}</p>}
      </header>

      <section className="topics-preview">
        <h2>打开论文演化研判任务</h2>
        <div className="hero-actions">
          <input aria-label="论文研判任务 ID" value={thesisJobId}
            onChange={(event) => setThesisJobId(event.target.value)} placeholder="thesis_…" />
          <button className="primary" onClick={loadThesisResult} disabled={!thesisJobId.trim()}>查看证据与命题链</button>
        </div>
      </section>

      {thesisResult ? <ThesisResultPanel result={thesisResult} /> : null}

      {!result && !running && (
        <section className="topics-preview">
          <h2>纳入预测的技术主题（{topics.length}）</h2>
          <div className="topic-chips">
            {topics.map((t) => (
              <span key={t.topic_name} className="chip">
                {t.topic_name}
              </span>
            ))}
          </div>
        </section>
      )}

      {running && job && (
        <section className="progress-panel">
          <div className="progress-head">
            <strong>{STAGE_LABEL[job.stage] || job.stage}</strong>
            <span>{Math.round(job.progress * 100)}%</span>
          </div>
          <div className="bar">
            <div className="bar-fill" style={{ width: `${job.progress * 100}%` }} />
          </div>
          <ul className="log">
            {job.log.slice(-5).map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </section>
      )}

      {result && (
        <main className="result">
          <section className="stat-row">
            <div className="stat">
              <div className="stat-num">{result.stats.topic_count}</div>
              <div className="stat-label">预测主题</div>
            </div>
            <div className="stat">
              <div className="stat-num">{result.stats.avg_confidence}</div>
              <div className="stat-label">平均置信度</div>
            </div>
            <div className="stat">
              <div className="stat-num">{result.stats.revised ? "已修正" : "通过"}</div>
              <div className="stat-label">科学评审</div>
            </div>
            <div className="stat paradigm-stat">
              <div className="stat-num small">{result.synthesis.new_paradigm_name}</div>
              <div className="stat-label">2040 新范式</div>
            </div>
          </section>

          <section className="card">
            <h2>技术成熟度（TRL）演进</h2>
            <TrlChart roadmaps={result.roadmaps} />
          </section>

          <section className="card">
            <h2>不确定性分布</h2>
            <UncertaintyHeatmap roadmaps={result.roadmaps} />
          </section>

          <section className="card">
            <h2>主题预测</h2>
            <div className="forecast-grid">
              {result.forecasts.map((f) => (
                <article key={f.topic_name} className="forecast-card">
                  <div className="fc-head">
                    <h3>{f.topic_name}</h3>
                    <span
                      className="conf"
                      style={{ color: confidenceColor(f.confidence) }}
                    >
                      {f.confidence}%
                    </span>
                  </div>
                  <p className="fc-section">
                    <b>2030–2035 瓶颈</b>
                  </p>
                  <ul>
                    {f.bottlenecks_2030_2035.map((b, i) => (
                      <li key={i}>{b}</li>
                    ))}
                  </ul>
                  <p className="fc-section">
                    <b>2040 突破</b>
                  </p>
                  <ul>
                    {f.breakthroughs_by_2040.map((b, i) => (
                      <li key={i}>{b}</li>
                    ))}
                  </ul>
                  {f.uncertainty_notes && (
                    <p className="fc-note">⚠ {f.uncertainty_notes}</p>
                  )}
                </article>
              ))}
            </div>
          </section>

          <section className="card paradigm-card">
            <h2>新范式与重大挑战</h2>
            <p className="paradigm-desc">{result.synthesis.new_paradigm_description}</p>
            <div className="two-col">
              <div>
                <h3>跨主题融合方向</h3>
                <ul>
                  {result.synthesis.cross_topic_fusions.map((x, i) => (
                    <li key={i}>{x}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h3>重大挑战</h3>
                <ul>
                  {result.synthesis.grand_challenges.map((x, i) => (
                    <li key={i}>{x}</li>
                  ))}
                </ul>
              </div>
            </div>
            {result.synthesis.conclusion && (
              <p className="conclusion">{result.synthesis.conclusion}</p>
            )}
          </section>
        </main>
      )}

      <footer className="foot">
        智能建造 2040 技术预测系统 · Think-and-Execute / LangGraph 编排
      </footer>
    </div>
  );
}
