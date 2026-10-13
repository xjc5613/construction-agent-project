import { expect, test, type Page, type Route } from "@playwright/test";

const project = { project_id: "v3-project", name: "智能建造 2040", description: "", status: "active",
  created_at: "2026-09-04", technology_node_id: "tech_smart_construction", technology_name: "智能建造",
  baseline_year: 2025, target_year: 2040, forecast_nodes: [2030, 2035, 2040], scope_version: 1,
  legacy_mode: false, lifecycle_status: "active", research_contract_version: 3, active_research_design_id: null,
  research_contract: {version: 3, baseline_year: 2025, target_years: [2030, 2035, 2040],
    periods: {}, default_cutoff: "2025-10-01", incomplete_years: [2025]}, topics: [] };
const ids = ["research-design", "data-quality", "network-evolution", "fusion-forecast", "technology-themes", "roadmap-report"];
const labels = ["研究设计", "数据质量", "网络演化", "融合预测", "技术主题", "路线图与报告"];

function respond(route: Route, body: unknown, status = 200) {
  return route.fulfill({status, contentType: "application/json", body: JSON.stringify(body)});
}

async function mockV3(page: Page, options: {archived?: boolean; interrupted?: boolean; onReview?: () => void; onDesign?: (body: any) => void} = {}) {
  const current = {...project, lifecycle_status: options.archived ? "archived" : "active"};
  const steps = ids.map((id, index) => ({id, label: labels[index], state: index === 0 ? "available" : "blocked", visible: true,
    route: `/projects/${project.project_id}/${id}`, blocking_reasons: index ? ["请先确认研究设计"] : [], remediation: "继续"}));
  if (options.interrupted) steps.forEach((step) => { step.state = "available"; step.blocking_reasons = []; });
  const readiness = {contract_version: 3, project_id: project.project_id, progress_percent: 16, current_stage: "research-design",
    steps, recommended_action: {step_id: "research-design", label: "确认研究设计", route: `/projects/${project.project_id}/research-design`},
    coverage: {complete: false, missing: [], leaf_count: 1, periods: {}}, evidence: {score: 0, sufficient: false, state: "blocked"},
    forecast: {can_start: false, can_override: false, blocking_reasons: [], override_reasons: [], active_job_id: null},
    graph_checkpoint: options.interrupted ? {job_id: "v3-job", thread_id: "thread", current_node: "fusion_review", status: "interrupted"} : null};
  await page.route("http://127.0.0.1:8000/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api", "");
    if (path === "/health") return respond(route, {ok: true});
    if (path === "/library/datasets") return respond(route, {items: [], total: 0});
    if (path === "/projects") return respond(route, {items: [current], total: 1});
    if (path === `/projects/${project.project_id}`) return respond(route, current);
    if (path === `/projects/${project.project_id}/readiness`) return respond(route, readiness);
    if (path === `/projects/${project.project_id}/research-designs`) {
      if (route.request().method() === "POST") { const body = JSON.parse(route.request().postData() || "{}"); options.onDesign?.(body); return respond(route, {...body, design_id: "d1", project_id: project.project_id, version: 1, status: "draft", checksum: "abcdef123456", paper_types: [], parameters: {}}, 201); }
      return respond(route, {items: [], total: 0});
    }
    if (path === `/projects/${project.project_id}/stale-artifacts`) return respond(route, {network_runs: 1, graph_threads: 1, exports: 1});
    if (path === `/research/projects/${project.project_id}/model-runs`) return respond(route, {items: [], total: 0});
    if (path === `/research/projects/${project.project_id}/chart-data`) return respond(route, {items: [], total: 0});
    if (path === "/research/graph/jobs/v3-job") return respond(route, {status: "interrupted", current_node: "fusion_review"});
    if (path === "/research/graph/jobs/v3-job/events") return respond(route, {items: [{event_id: "e1", event_type: "interrupt", node_name: "fusion_review", created_at: "2026-09-04"}]});
    if (path === "/research/graph/jobs/v3-job/reviews/fusion_review") { options.onReview?.(); return respond(route, {status: "running", current_node: "fusion_review"}); }
    return respond(route, {detail: `unmocked ${path}`}, 404);
  });
}

test("v3 shell exposes six scientific steps, scope, blocker, advanced mode and design defaults", async ({page}) => {
  let design: any;
  await mockV3(page, {onDesign: (body) => design = body});
  await page.goto(`/projects/${project.project_id}/research-design`);
  await expect(page.getByRole("heading", {name: "研究设计", exact: true})).toBeVisible();
  await expect(page.getByLabel("冻结研究范围")).toContainText("2025-10-01");
  await expect(page.getByRole("button", {name: "路线图与报告"})).toBeVisible();
  await page.getByLabel("视图").selectOption("advanced");
  await expect(page.getByLabel("视图")).toHaveValue("advanced");
  await page.getByRole("button", {name: "数据质量"}).click();
  await expect(page.getByRole("status")).toContainText("请先确认研究设计");
  await page.getByRole("button", {name: /^1 研究设计$/, exact: true}).click();
  await page.getByRole("button", {name: "保存新版本"}).press("Enter");
  await expect.poll(() => design?.data_cutoff).toBe("2025-10-01");
  expect(design.parameters.sensitivity_partial_2025).toBe(true);
});

test("archived v3 project is visibly read only and interrupted graph requires explicit review", async ({page}) => {
  let reviewed = false;
  await mockV3(page, {archived: true, interrupted: true, onReview: () => reviewed = true});
  await page.goto(`/projects/${project.project_id}/fusion-forecast`);
  await expect(page.getByText("归档项目")).toBeVisible();
  await expect(page.getByText("当前节点 fusion_review")).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept("已核验证据与限制"));
  await page.getByRole("button", {name: "批准继续"}).click();
  await expect.poll(() => reviewed).toBe(true);
});
