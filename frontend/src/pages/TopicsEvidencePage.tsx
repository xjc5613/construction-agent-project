import { useState } from "react";
import type { Project, Topic } from "../types";
import { EvidencePage } from "./EvidencePage";
import { TopicsPage } from "./TopicsPage";

export function TopicsEvidencePage({
  apiBase, project, topics, initialStage = "topics", onForecast, onChanged,
}: {
  apiBase: string;
  project: Project;
  topics: Topic[];
  initialStage?: "topics" | "evidence";
  onForecast: () => void;
  onChanged?: () => Promise<void>;
}) {
  const [stage, setStage] = useState<"topics" | "evidence">(initialStage);
  return (
    <>
      <div className="tab-bar workflow-subtabs" aria-label="主题与证据阶段">
        <button className={stage === "topics" ? "active" : ""} onClick={() => setStage("topics")}>1. 主题校准</button>
        <button className={stage === "evidence" ? "active" : ""} onClick={() => setStage("evidence")}>2. 证据审阅</button>
      </div>
      {stage === "topics" ? (
        <TopicsPage apiBase={apiBase} project={project} initialTopics={topics} onEvidence={() => { void onChanged?.(); setStage("evidence"); }} />
      ) : (
        <EvidencePage apiBase={apiBase} project={project} onForecast={onForecast} />
      )}
    </>
  );
}
