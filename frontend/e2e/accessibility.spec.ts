import { expect, test } from "@playwright/test";
import { mockApi, project } from "./fixtures";

test("navigation, native switches, dialog focus and dirty warning remain keyboard accessible", async ({ page }) => {
  await mockApi(page);
  await page.goto(`/projects/${project.project_id}/forecast`);
  await expect(page.getByRole("button", { name: /F 预测运行/ })).toHaveAttribute("aria-current", "page");
  const checkbox = page.getByRole("checkbox", { name: "推理链条" });
  await checkbox.focus(); await expect(checkbox).toBeFocused(); await page.keyboard.press("Space");
  await page.getByText("允许证据不足时继续").click();
  await page.getByLabel("证据门禁覆盖理由").fill("已人工复核");
  await page.waitForTimeout(100);
  page.once("dialog", async (dialog) => { expect(dialog.message()).toContain("未保存修改"); await dialog.dismiss(); });
  await page.getByRole("button", { name: "预测项目" }).click();
  await expect(page).toHaveURL(new RegExp("/forecast$"));
  await page.getByRole("button", { name: "检查并启动预测" }).click();
  const modal = page.getByRole("dialog"); await expect(modal).toBeVisible();
  await page.keyboard.press("Escape"); await expect(modal).toBeHidden();
  await expect(page.getByRole("button", { name: "检查并启动预测" })).toBeFocused();
});

for (const viewport of [{ width: 390, height: 844 }, { width: 1024, height: 768 }]) {
  test(`layout has no document overflow at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport); await mockApi(page); await page.goto(`/projects/${project.project_id}/forecast`);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });
}
