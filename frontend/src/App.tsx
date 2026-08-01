import { useEffect, useState } from "react";
import { apiRequest } from "./api";
import { AppShell, type PageKey } from "./components/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { EvidencePage } from "./pages/EvidencePage";
import { ForecastPage } from "./pages/ForecastPage";
import { LibraryPage } from "./pages/LibraryPage";
import { MaterialsPage } from "./pages/MaterialsPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { ResultsPage } from "./pages/ResultsPage";
import { TopicsPage } from "./pages/TopicsPage";
import type {
  Asset, ChartData, Dataset, Job, Project, Result, ResultTopic, Topic,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api";

export function App() {
  const [active, setActive] = useState<PageKey>("dashboard");
  const [health, setHealth] = useState("未连接");
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [extractedTopics, setExtractedTopics] = useState<Topic[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [charts, setCharts] = useState<ChartData | null>(null);
  const [resultTopics, setResultTopics] = useState<ResultTopic[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [notice, setNotice] = useState("");

  const notify = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 3200);
  };
  const refreshDatasets = async () => {
    const data = await apiRequest<{ items: Dataset[] }>(API_BASE, "/library/datasets");
    setDatasets(data.items);
  };
  const refreshProjects = async () => {
    const data = await apiRequest<{ items: Project[] }>(API_BASE, "/projects");
    setProjects(data.items);
  };
  const selectProject = async (selected: Project, next: PageKey = "materials") => {
    const detail = await apiRequest<Project>(API_BASE, `/projects/${selected.project_id}`);
    setProject(detail); setExtractedTopics(detail.topics ?? []); setActive(next);
  };
  const refreshProject = async () => {
    if (!project) return;
    const detail = await apiRequest<Project>(API_BASE, `/projects/${project.project_id}`);
    setProject(detail); setExtractedTopics(detail.topics ?? []);
  };

  useEffect(() => {
    void Promise.all([
      apiRequest<{ ok: boolean }>(API_BASE, "/health").then((data) => setHealth(data.ok ? "已连接" : "已禁用")),
      refreshDatasets(),
      refreshProjects(),
    ]).catch((error) => {
      setHealth("未连接"); notify((error as Error).message);
    });
  }, []);

  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    const timer = window.setInterval(() => {
      void apiRequest<Job>(API_BASE, `/forecast/jobs/${job.job_id}`)
        .then(async (next) => {
          setJob(next);
          if (["completed", "partial_failed"].includes(next.status)) {
            const [resultData, chartData, topicData, assetData] = await Promise.all([
              apiRequest<Result>(API_BASE, `/forecast/jobs/${next.job_id}/results`),
              apiRequest<ChartData>(API_BASE, `/forecast/jobs/${next.job_id}/charts`),
              apiRequest<{ items: ResultTopic[] }>(API_BASE, `/forecast/jobs/${next.job_id}/topics`),
              apiRequest<{ items: Asset[] }>(API_BASE, `/forecast/jobs/${next.job_id}/assets`),
            ]);
            setResult(resultData); setCharts(chartData);
            setResultTopics(topicData.items); setAssets(assetData.items);
            setActive("results"); await refreshProjects();
          }
        })
        .catch((error) => notify((error as Error).message));
    }, 1800);
    return () => window.clearInterval(timer);
  }, [job?.job_id, job?.status]);

  const navigate = (page: PageKey) => {
    const projectPages: PageKey[] = ["materials", "topics", "evidence", "forecast", "results"];
    if (projectPages.includes(page) && !project) {
      setActive("projects"); notify("请先选择一个预测项目"); return;
    }
    if (page === "forecast") void refreshProject();
    setActive(page);
  };

  let content;
  if (active === "dashboard") {
    content = <DashboardPage datasets={datasets} projects={projects} onNavigate={navigate} onSelectProject={(item) => void selectProject(item)} />;
  } else if (active === "library") {
    content = <LibraryPage apiBase={API_BASE} datasets={datasets} onRefresh={refreshDatasets} />;
  } else if (active === "projects") {
    content = <ProjectsPage apiBase={API_BASE} projects={projects} onCreated={(created) => { setProjects((items) => [created, ...items]); void selectProject(created); }} onSelect={(item) => void selectProject(item)} />;
  } else if (active === "materials" && project) {
    content = <MaterialsPage apiBase={API_BASE} project={project} onTopics={(topics) => { setExtractedTopics(topics); void refreshProject(); setActive("topics"); }} />;
  } else if (active === "topics" && project) {
    content = <TopicsPage apiBase={API_BASE} project={project} initialTopics={extractedTopics} onEvidence={() => { void refreshProject(); setActive("evidence"); }} />;
  } else if (active === "evidence" && project) {
    content = <EvidencePage apiBase={API_BASE} project={project} onForecast={() => { void refreshProject(); setActive("forecast"); }} />;
  } else if (active === "forecast" && project) {
    content = <ForecastPage apiBase={API_BASE} project={project} topics={project.topics ?? extractedTopics} job={job} onJob={(next) => { setJob(next); setResult(null); setCharts(null); }} />;
  } else {
    content = <ResultsPage apiBase={API_BASE} job={job} result={result} charts={charts} topics={resultTopics} assets={assets} />;
  }

  return (
    <AppShell active={active} onNavigate={navigate} projectName={project?.name} health={health}>
      {content}
      <div className={`toast ${notice ? "show" : ""}`}>{notice}</div>
    </AppShell>
  );
}
