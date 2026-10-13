export type Uncertainty = "low" | "medium" | "high";

export interface TopicEvidence {
  topic_name: string;
  keywords: string[];
  example: string;
  ipc_trend: string;
}

export interface TopicForecast {
  topic_name: string;
  drivers: string[];
  bottlenecks_2030_2035: string[];
  breakthroughs_by_2040: string[];
  enabling_technologies: string[];
  confidence: number;
  uncertainty_notes: string;
}

export interface CriticFinding {
  topic_name: string;
  issues: string[];
  severity: "low" | "medium" | "high";
  revision_advice: string;
}

export interface RoadmapMilestone {
  name: string;
  trl_level: number;
  uncertainty_level: Uncertainty;
  note: string;
}

export interface TopicRoadmap {
  topic_name: string;
  stages: Record<string, RoadmapMilestone[]>;
  terminal_trl: number;
}

export interface Synthesis {
  new_paradigm_name: string;
  new_paradigm_description: string;
  cross_topic_fusions: string[];
  grand_challenges: string[];
  conclusion: string;
}

export interface ForecastResult {
  job_id: string;
  baseline_year: number;
  target_year: number;
  time_nodes: number[];
  forecasts: TopicForecast[];
  critiques: CriticFinding[];
  roadmaps: TopicRoadmap[];
  synthesis: Synthesis;
  stats: {
    topic_count: number;
    avg_confidence: number;
    revised: boolean;
  };
}

export type JobStatus = {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  stage: string;
  progress: number;
  log: string[];
  error: string;
};
