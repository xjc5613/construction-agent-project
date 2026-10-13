import { expect, test } from "@playwright/test";
import { mockApi, project } from "./fixtures";

const legacyDataset = { dataset_id: "legacy-1", kind: "papers", public_kind: "", technology_node_id: null, technology_name: null, period_code: null, name: "历史论文", version: "legacy", status: "published", description: "", imported_at: "2025-01-01", migration_status: "unmapped", lifecycle_status: "active" };
const leaf = { node_id: "tech-3", parent_id: "tech-2", level: 3, name: "模块化", slug: "module", description: "", keywords: [], aliases: [], status: "active", sort_order: 0, taxonomy_version: 1, path_text: "智能建造 / 装配式 / 模块化", children: [] };

test("technology-first library imports without manual dataset creation", async ({ page }) => {
  await mockApi(page, { datasets: [legacyDataset], technologies: [leaf] });
  await page.goto("/library");
  await expect(page.getByRole("heading", { name: "基础数据" })).toBeVisible();
  await expect(page.getByText("新建阶段数据集")).toHaveCount(0);
  await page.locator('input[type="file"]').setInputFiles("../docs/templates/papers.csv");
  await page.getByRole("button", { name: "解析并预览" }).click();
  await expect(page.locator(".guided-plan").getByText("2021-2026", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "确认导入" }).click();
  await expect(page.getByText(/已导入 1 条记录/)).toBeVisible();
  await page.getByText("显示草稿、废弃和待映射数据").click();
  await page.getByRole("button", { name: "导入与版本" }).click();
  await page.getByRole("button", { name: "映射" }).click();
  const mapping = page.getByRole("dialog", { name: "映射旧数据" });
  await mapping.getByLabel("历史阶段").selectOption("2021_2026");
  await mapping.getByRole("button", { name: "确认映射" }).click();
  await expect(page.getByText("旧数据已完成技术、阶段和类型映射。")).toBeVisible();
});

test("dangerous project and topic actions disclose impact before commit", async ({ page }) => {
  await mockApi(page);
  await page.goto("/projects");
  await page.getByRole("button", { name: "归档" }).click();
  const projectDialog = page.getByRole("dialog", { name: "确认归档项目" });
  await expect(projectDialog).toContainText("归档后不会删除任务和结果");
  await page.keyboard.press("Escape");
  await page.goto(`/projects/${project.project_id}/topics`);
  await expect(page.getByRole("checkbox", { name: "选择主题 模块化施工" })).toBeVisible();
  await expect(page.locator("[contenteditable]")).toHaveCount(0);
  await page.getByRole("button", { name: "归档" }).click();
  await expect(page.getByRole("dialog", { name: "确认归档主题" })).toContainText("历史任务快照不会被修改");
});

test("taxonomy parent and fields remain draft until one unified save", async ({ page }) => {
  let saved: any = null;
  const parentA = { ...leaf, node_id: "parent-a", parent_id: null, level: 2, name: "装配式", path_text: "智能建造 / 装配式", children: [leaf] };
  const parentB = { ...leaf, node_id: "parent-b", parent_id: null, level: 2, name: "机器人", path_text: "智能建造 / 机器人", children: [] };
  await mockApi(page, { technologies: [parentA, parentB], onTechnologySave: (body) => { saved = body; } });
  await page.goto("/technologies");
  await page.locator(".tree-toggle").first().click();
  await page.getByRole("button", { name: /模块化/ }).click();
  await expect(page.locator(".technology-name-input")).toHaveValue("模块化");
  await page.getByRole("button", { name: "高级设置" }).click();
  await page.getByRole("textbox", { name: "技术描述" }).fill("统一保存后的描述");
  await page.getByLabel("上级技术").selectOption("parent-b");
  expect(saved).toBeNull();
  await page.getByRole("button", { name: "保存目录修改" }).click();
  await expect.poll(() => saved).toMatchObject({ description: "统一保存后的描述", parent_id: "parent-b" });
});
