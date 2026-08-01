export type Dataset = {
  dataset_id: string;
  kind: "ipc_metrics" | "ipc_fusions" | "papers" | "mixed";
  name: string;
  version: string;
  status: string;
  description: string;
  imported_at: string;
};

export type ImportRecord = {
  import_id: string;
  kind: string;
  mapping: Record<string, string>;
  preview: {
    columns?: string[];
    rows?: Record<string, unknown>[];
    valid_count?: number;
    error_count?: number;
    text_preview?: string;
    warnings?: string[];
  };
  errors: { row: number; message: string }[];
};

export type Project = {
  project_id: string;
  name: string;
  description: string;
  status: string;
  created_at: string;
  materials?: Material[];
  topics?: Topic[];
};

export type Material = {
  material_id: string;
  project_id: string;
  title: string;
  source_type: string;
  original_filename: string;
  parse_status: string;
  created_at: string;
};

export type Topic = {
  topic_id: string;
  project_id: string;
  topic_name: string;
  description: string;
  keywords: string[];
  evidence: Array<Record<string, string>>;
  fusion_pairs: Array<Record<string, string | number>>;
  evidence_score: number;
  requires_review: boolean;
  selected: boolean;
  status: string;
};

export type EvidenceItem = {
  evidence_id: string;
  evidence_type: "ipc_metric" | "ipc_fusion" | "paper" | "material";
  source_id: string;
  title: string;
  content: string;
  relevance: number;
  excluded: boolean;
  exclusion_reason: string;
  metadata: Record<string, unknown>;
};

export type EvidencePackage = {
  package_id: string;
  project_id: string;
  topic_id: string;
  status: string;
  query: Record<string, unknown>;
  quality: {
    score: number;
    sufficient: boolean;
    missing: string[];
    ipc_record_count: number;
    year_count: number;
    paper_count: number;
    paper_fragment_count: number;
    data_cutoff: number | null;
  };
  items: EvidenceItem[];
};

export type Job = {
  job_id: string;
  status: "queued" | "running" | "completed" | "partial_failed" | "failed";
  current_stage: string;
  progress: number;
  error: string;
  steps: Array<{ name: string; status: string; message: string }>;
};

export type Result = {
  project_id: string;
  time_nodes: string[];
  topics: Topic[];
  round1_results: Array<Record<string, unknown>>;
  round2_result: { new_paradigm_name?: string };
  per_topic_roadmaps: Array<Record<string, unknown>>;
  confidence_summary: { average: number | null };
  academic_conclusion: string;
  evidence_limited: boolean;
  override_reason: string;
  stage_quality: Record<string, unknown>;
  asset_summary: { count: number; failed_count: number; status: string };
};

export type ChartData = {
  trl_series: Array<{ name: string; data: Array<{ year: string; value: number | null }> }>;
  fusion_network: Array<{ topic: string; source: string; target: string; weight: number }>;
  uncertainty_heatmap: Array<{ topic: string; year: string; value: number }>;
  ipc_trends: Array<{
    topic: string; ipc_code: string; year: number; patent_count: number | null;
    degree_centrality: number | null; growth_rate: number | null; evidence_id: string;
  }>;
  paper_trends: Array<{ topic: string; year: number; count: number }>;
  paper_directions: Array<{ topic: string; keyword: string; count: number }>;
  representative_papers: Array<{
    topic: string; paper_id: string; title: string; year: number;
    evidence_id: string; relevance: number;
  }>;
  evidence_matrix: Array<{ topic: string; ipc_count: number; paper_count: number; status: string }>;
  fusion_sankey: Array<{ source: string; target: string; value: number; topic: string }>;
};

export type ResultTopic = {
  topic_id: string;
  topic_name: string;
  keywords: string[];
  milestone_count: number;
  terminal_trl: number | null;
  dominant_uncertainty: string;
  asset_count: number;
  available_years: string[];
};

export type Asset = {
  asset_id: string;
  topic_id: string | null;
  topic_name: string | null;
  kind: string;
  title: string;
  url: string;
  download_url: string;
};
