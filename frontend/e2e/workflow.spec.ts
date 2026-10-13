import { expect, test } from "@playwright/test";
import { job, mockApi, project, readiness } from "./fixtures";

test("global navigation hides project steps until a project is entered", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await expect(page.getByRole("button", { name: /研究材料/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /主题与证据/ })).toHaveCount(0);
  await page.goto(`/projects/${project.project_id}/overview`);
  await expect(page.getByRole("button", { name: /^M 研究材料/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: project.name })).toBeVisible();
});

test("direct unavailable step shows backend readiness reason", async ({ page }) => {
  const blocked = {
    ...readiness,
    steps: readiness.steps.map((step) => step.id === "forecast" ? {
      ...step, state: "blocked" as const,
      blocking_reasons: ["主题尚未确认"], remediation: ["先完成主题校准"],
    } : step),
    recommended_action: { step_id: "topics-evidence", label: "校准主题", route: `/projects/${project.project_id}/topics-evidence` },
  };
  await mockApi(page, { readiness: blocked });
  await page.goto(`/projects/${project.project_id}/forecast`);
  await expect(page.getByText("预测运行尚不可进入")).toBeVisible();
  await expect(page.locator(".empty-panel").getByText("主题尚未确认")).toBeVisible();
});

test("deep link restores job history and degraded result", async ({ page }) => {
  await mockApi(page);
  await page.goto(`/projects/${project.project_id}/jobs`);
  await expect(page.getByRole("heading", { name: "预测任务历史" })).toBeVisible();
  await expect(page.getByText("缺少产物：charts.json")).toBeVisible();
  await page.getByRole("button", { name: "打开结果" }).click();
  await expect(page).toHaveURL(new RegExp(`/jobs/${job.job_id}/results`));
  await expect(page.getByRole("heading", { name: "技术预测结果" })).toBeVisible();
  await page.reload();
  await expect(page.getByText(/任务 job-1 · 2025 基线/)).toBeVisible();
});

test("evidence gate requires explicit override and confirmed start is deduplicated", async ({ page }) => {
  let starts = 0; await mockApi(page, { onStart: () => { starts += 1; } });
  await page.goto(`/projects/${project.project_id}/forecast`);
  const start = page.getByRole("button", { name: "检查并启动预测" });
  await expect(start).toBeDisabled();
  await expect(page.getByText(/勾选覆盖并填写理由/)).toBeVisible();
  await page.getByText("允许证据不足时继续").click();
  await page.getByLabel("证据门禁覆盖理由").fill("由领域专家完成线下复核");
  await start.click();
  const dialog = page.getByRole("dialog", { name: "确认启动预测" });
  await expect(dialog).toContainText("预计模型调用 4 次");
  await expect(dialog).toContainText("当前未配置价格");
  const confirm = dialog.getByRole("button", { name: "冻结证据并启动" });
  await confirm.dblclick();
  await expect.poll(() => starts).toBe(1);
});

test("unknown project has a recoverable not-found state", async ({ page }) => {
  await mockApi(page);
  await page.goto("/projects/unknown/materials");
  await expect(page.getByText("无法恢复当前页面")).toBeVisible();
  await expect(page.getByRole("button", { name: "返回项目列表" })).toBeVisible();
});

test("evidence exclusion recomputes score and history supports cancel and retry lineage", async ({ page }) => {
  const queued = { ...job, job_id: "job-queued", status: "queued", result_available: false };
  const failed = { ...job, job_id: "job-failed", status: "failed", result_available: false, parent_job_id: "job-parent" };
  await mockApi(page, { evidenceItems: true, jobs: [queued, failed] });
  await page.goto(`/projects/${project.project_id}/evidence`);
  await page.getByRole("button", { name: "检索 IPC 与论文证据" }).click();
  await expect(page.getByText("100").first()).toBeVisible();
  await page.getByRole("button", { name: "排除证据" }).click();
  await expect(page.getByText("75").first()).toBeVisible();
  await expect(page.getByText("论文证据不足")).toBeVisible();
  await page.goto(`/projects/${project.project_id}/jobs`);
  await page.getByRole("button", { name: "取消" }).click();
  await expect(page.getByRole("dialog", { name: "确认取消预测任务" })).toContainText("partial_artifacts_preserved");
  await page.getByRole("dialog").getByRole("button", { name: "确认取消" }).click();
  await page.getByRole("button", { name: "重试" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "创建重试任务" }).click();
  await expect(page).toHaveURL(/\/jobs\/job-retry\/results/);
});
