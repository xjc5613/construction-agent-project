import type { Page, Route } from "@playwright/test";

export const project = {
  project_id: "project-2025", name: "2025 历史装配项目", description: "回归样本", status: "evidence_review",
  created_at: "2025-01-01T00:00:00Z", technology_node_id: "tech-1", technology_name: "装配式建造",
  baseline_year: 2025, target_year: 2040, forecast_nodes: [2030, 2035, 2040], scope_version: 1,
  legacy_mode: false, lifecycle_status: "active", materials: [], topics: [{
    topic_id: "topic-1", project_id: "project-2025", topic_name: "模块化施工", description: "", keywords: [],
    evidence: [], fusion_pairs: [], evidence_score: 45, requires_review: false, selected: true, status: "confirmed",
    technologies: [{ technology_node_id: "tech-3", name: "模块化", is_primary: true, relevance: 1, source: "manual" }],
  }],
};

export const readiness = {
  contract_version: 2, project_id: project.project_id, progress_percent: 72, current_stage: "evidence_review",
  lifecycle_status: "active",
  steps: [
    { id: "overview", label: "项目概览", state: "completed", visible: true, route: `/projects/${project.project_id}/overview`, blocking_reasons: [], remediation: [] },
    { id: "materials", label: "研究材料", state: "available", visible: true, route: `/projects/${project.project_id}/materials`, blocking_reasons: [], remediation: [] },
    { id: "topics-evidence", label: "主题与证据", state: "available", visible: true, route: `/projects/${project.project_id}/topics-evidence`, blocking_reasons: [], remediation: [] },
    { id: "forecast", label: "预测运行", state: "available", visible: true, route: `/projects/${project.project_id}/forecast`, blocking_reasons: [], remediation: [] },
    { id: "results", label: "结果与历史", state: "available", visible: true, route: `/projects/${project.project_id}/results`, blocking_reasons: [], remediation: [] },
  ],
  recommended_action: { step_id: "materials", label: "添加研究材料", route: `/projects/${project.project_id}/materials` },
  coverage: { complete: false, missing: ["2010-2015 缺少基础证据"], leaf_count: 1, periods: { "2010_2015": { ipc: 0, paper: 0, ipc_records: 0, paper_records: 0 }, "2016_2020": { ipc: 1, paper: 1, ipc_records: 3, paper_records: 2 }, "2021_2026": { ipc: 1, paper: 1, ipc_records: 4, paper_records: 3 } } },
  evidence: { score: 45, sufficient: false, state: "override_required" },
  forecast: { can_start: false, can_override: true, blocking_reasons: [], override_reasons: ["论文证据不足"], active_job_id: null },
};

export const job = {
  job_id: "job-1", project_id: project.project_id, status: "completed", current_stage: "completed", progress: 1,
  error: "", steps: [], created_at: "2026-08-01T08:00:00Z", evidence_limited: true,
  override_reason: "专家评审已补足", result_available: true, artifact_health: "degraded", missing_artifacts: ["charts.json"],
};

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

export async function mockApi(page: Page, overrides: { readiness?: any; onStart?: () => void; datasets?: unknown[]; technologies?: any[]; jobs?: any[]; evidenceItems?: boolean; onTechnologySave?: (body: any) => void } = {}) {
  const materials: unknown[] = [];
  await page.route("http://127.0.0.1:8000/api/**", async (route) => {
    const url = new URL(route.request().url()); const path = url.pathname.replace("/api", "");
    if (path === "/health") return json(route, { ok: true });
    if (path === "/library/datasets") {
      if (route.request().method() === "POST") return json(route, { ...(overrides.datasets?.[0] as object ?? {}), dataset_id: "dataset-new", version: "1.0", status: "draft" }, 201);
      return json(route, { items: overrides.datasets ?? [], total: overrides.datasets?.length ?? 0 });
    }
    if (path === "/library/papers") return json(route, { items: [], total: 0, page: 1, page_size: 20 });
    if (path === "/library/ipc/trends") return json(route, { items: [], total: 0, page: 1, page_size: 20 });
    if (path === "/library/files" || path === "/library/imports") return json(route, { items: [], total: 0 });
    if (/^\/library\/coverage\/[^/]+$/.test(path)) return json(route, readiness.coverage);
    if (/^\/library\/technologies\/[^/]+\/summary$/.test(path)) return json(route, { node_id: "tech-3", name: "模块化", path_text: "智能建造 / 装配式 / 模块化", level: 3, status: "active", effective_status: "active", child_count: 0, datasets: 0, papers: 0, ipc_records: 0, source_files: 0, projects: 1, references: {} });
    if (path === "/library/imports/guided/stage") return json(route, { import: { import_id: "import-1", kind: "papers", mapping: {}, preview: { valid_count: 1 }, errors: [] }, plan: { technology_node_id: "tech-3", technology_path: "智能建造 / 装配式 / 模块化", public_kind: "paper", component_kind: "papers", periods: ["2021_2026"], generated_versions: { "2021_2026": "20260803.1" }, split_required: false } }, 201);
    if (/^\/library\/imports\/[^/]+\/guided-commit$/.test(path)) return json(route, { items: [{ committed: 1, dataset: { dataset_id: "dataset-new", status: "draft" } }], total: 1, split: false });
    if (/^\/library\/datasets\/[^/]+\/actions\/preview$/.test(path)) return json(route, { confirmation_token: "dataset-token", before: { migration_status: "unmapped" }, after: JSON.parse(route.request().postData() || "{}").payload, impact: { evidence_packages: 0 }, warnings: [] });
    if (/^\/library\/datasets\/[^/]+\/actions\/commit$/.test(path)) return json(route, { ok: true, resource: {} });
    if (/^\/library\/datasets\/[^/]+\/classification$/.test(path)) return json(route, { ...legacyDatasetFallback(overrides.datasets), migration_status: "mapped" });
    if (path === "/projects") {
      if (route.request().method() === "POST") return json(route, project, 201);
      return json(route, { items: [project], total: 1 });
    }
    if (path === `/projects/${project.project_id}`) return json(route, project);
    if (path === `/projects/${project.project_id}/readiness`) return json(route, overrides.readiness ?? readiness);
    if (path === `/projects/${project.project_id}/technology-scope`) return json(route, { root: { node_id: "tech-1", name: "智能建造" }, nodes: project.topics[0].technologies.map((item) => ({ ...item, node_id: item.technology_node_id, level: 3 })), legacy_mode: false });
    if (path === `/projects/${project.project_id}/materials`) return json(route, { items: materials, total: materials.length });
    if (path === `/projects/${project.project_id}/materials/text`) { materials.push({ material_id: "material-1", project_id: project.project_id, title: "技术研究材料", source_type: "text", original_filename: "", parse_status: "parsed", analysis_kind: "integrated_analysis", review_status: "ready", created_at: new Date().toISOString(), lifecycle_status: "active" }); return json(route, materials[0], 201); }
    if (path === `/projects/${project.project_id}/topics/extract`) return json(route, project.topics);
    if (path === `/projects/${project.project_id}/topics`) return json(route, { items: project.topics, total: 1 });
    if (path.endsWith("/confirm")) return json(route, project.topics[0]);
    if (path === `/projects/${project.project_id}/evidence-packages`) return json(route, { package_id: "package-1", project_id: project.project_id, topic_id: "topic-1", status: "ready", query: {}, quality: { score: 100, sufficient: true, missing: [], ipc_record_count: 10, year_count: 3, paper_count: 5, paper_fragment_count: 5, data_cutoff: 2025 }, items: overrides.evidenceItems ? [{ evidence_id: "ev-1", evidence_type: "paper", source_id: "paper-1", title: "模块化论文", content: "论文证据", relevance: .9, excluded: false, exclusion_reason: "", metadata: {} }] : [] }, 201);
    if (path === `/projects/${project.project_id}/evidence-items/ev-1`) return json(route, { item: { evidence_id: "ev-1", excluded: true }, package: { package_id: "package-1", project_id: project.project_id, topic_id: "topic-1", status: "ready", query: {}, quality: { score: 75, sufficient: false, missing: ["论文证据不足"], ipc_record_count: 10, year_count: 3, paper_count: 0, paper_fragment_count: 0, data_cutoff: 2025 }, items: [{ evidence_id: "ev-1", evidence_type: "paper", source_id: "paper-1", title: "模块化论文", content: "论文证据", relevance: .9, excluded: true, exclusion_reason: "人工审阅排除", metadata: {} }] }, readiness });
    if (path === `/projects/${project.project_id}/stage-analysis`) return json(route, { items: [] });
    if (path === `/projects/${project.project_id}/topics/actions/preview`) return json(route, { confirmation_token: "topic-token", impact: { snapshots: 1 }, warnings: ["历史任务快照不会被修改"] });
    if (path === `/projects/${project.project_id}/topics/actions/commit`) return json(route, { ok: true, resource: {} });
    if (path === `/projects/${project.project_id}/actions/preview`) return json(route, { confirmation_token: "project-token", impact: { jobs: 1 }, warnings: ["归档后不会删除任务和结果"] });
    if (path === `/projects/${project.project_id}/actions/commit`) return json(route, { ok: true, resource: project });
    if (path === `/projects/${project.project_id}/forecast-jobs`) {
      if (route.request().method() === "POST") { overrides.onStart?.(); return json(route, { ...job, status: "queued", progress: 0, result_available: false }, 202); }
      return json(route, { items: overrides.jobs ?? [job], total: overrides.jobs?.length ?? 1 });
    }
    if (path === `/projects/${project.project_id}/forecast-jobs/preview`) return json(route, { confirmation_token: "signed-token", impact: { estimated_model_calls: 4, pricing_estimate: null }, workload: { estimated_model_calls: 4, pricing_estimate: null }, warnings: ["论文证据不足"], readiness: overrides.readiness ?? readiness });
    if (path === `/projects/${project.project_id}/forecast-jobs/${job.job_id}` || path === `/forecast/jobs/${job.job_id}`) return json(route, job);
    if (/^\/forecast\/jobs\/[^/]+\/(cancel|retry)\/preview$/.test(path)) return json(route, { confirmation_token: "job-action-token", impact: { partial_artifacts_preserved: true }, warnings: ["在安全阶段边界处理"] });
    if (/^\/forecast\/jobs\/[^/]+\/cancel$/.test(path)) return json(route, { ok: true, job: { ...job, status: "cancelling" } });
    if (/^\/forecast\/jobs\/[^/]+\/retry$/.test(path)) return json(route, { ...job, job_id: "job-retry", status: "queued", parent_job_id: "job-failed", result_available: false }, 202);
    if (path === `/forecast/jobs/${job.job_id}/results`) return json(route, { project_id: project.project_id, time_nodes: ["2030", "2035", "2040"], topics: [], round1_results: [], round2_result: {}, per_topic_roadmaps: [], confidence_summary: { average: .8 }, academic_conclusion: "结论", evidence_limited: true, override_reason: "专家评审已补足", stage_quality: {}, asset_summary: { count: 0, failed_count: 1, status: "partial" }, baseline_year: 2025, target_year: 2040, taxonomy: {}, historical_periods: [], stage_analysis: [] });
    if (path === `/forecast/jobs/${job.job_id}/charts`) return json(route, { message: "missing" }, 404);
    if (path === `/forecast/jobs/${job.job_id}/topics` || path === `/forecast/jobs/${job.job_id}/assets`) return json(route, { items: [] });
    if (path === "/technologies") return json(route, { items: overrides.technologies ?? [{ node_id: "tech-1", parent_id: null, level: 1, name: "智能建造", slug: "smart", description: "", keywords: [], aliases: [], status: "active", sort_order: 0, taxonomy_version: 1, path_text: "智能建造", children: [] }] });
    if (/^\/technologies\/[^/]+\/summary$/.test(path)) return json(route, { node_id: path.split("/")[2], name: "技术", path_text: "智能建造 / 技术", level: 3, status: "active", effective_status: "active", child_count: 0, datasets: 0, papers: 0, ipc_records: 0, source_files: 0, projects: 0, references: {} });
    if (/^\/technologies\/[^/]+$/.test(path)) {
      const id = path.split("/").pop(); const flat = (overrides.technologies ?? []).flatMap((item) => [item, ...(item.children ?? [])]); const node = flat.find((item) => item.node_id === id);
      if (route.request().method() === "PATCH") { const body = JSON.parse(route.request().postData() || "{}"); overrides.onTechnologySave?.(body); return json(route, { ...node, ...body }); }
      if (node) return json(route, { ...node, relations: [], references: {}, changes: [] });
    }
    return json(route, { detail: { code: "unmocked", message: `Unmocked ${path}` } }, 404);
  });
}

function legacyDatasetFallback(datasets?: unknown[]) {
  return (datasets?.[0] as Record<string, unknown> | undefined) ?? { dataset_id: "legacy-1" };
}
