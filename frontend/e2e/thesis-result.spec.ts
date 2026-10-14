import {expect, test} from "@playwright/test";

test("shows packet qualification, claim lineage, findings, and mixed coverage", async ({page}) => {
  await page.route("**/api/health", route => route.fulfill({json: {ok: true}}));
  await page.route("**/api/seed-topics", route => route.fulfill({json: {items: []}}));
  await page.route("**/api/thesis/jobs/thesis-demo/result", route => route.fulfill({json: {
    job: {job_id: "thesis-demo"},
    packet: {
      packet_version_id: "chapter4:v1", checksum: "checksum-1", validation_summary: {},
      mapping_attachments: [{attachment_id: "mapping", mapping_state: "reported_but_not_supplied", row_count: 926}],
    },
    state: {
      coverage: {accepted: 1, downgraded: 0, deferred: 0, revision_exhausted: 1},
      roadmaps: [{milestone_id: "m1", object_id: "T03", period: "2026_2030",
        capability: "受控工况机器人协同", prerequisites: ["现场验证"],
        evidence_ids: ["Q03"], retained_objections: []}],
      synthesis: {unresolved_gaps: ["室外复杂工况尚未验证"]},
    },
    trace: {
      claims: [{claim_version_id: "thesis-demo:robot:v2", claim: {claim_id: "robot", version: 2,
        parent_version_id: "robot:v1", statement: "仅在受控工况推进", support_level: "conditional_support",
        evidence_ids: ["Q03"]}}],
      findings: [{finding_id: "f1", claim_id: "robot", reviewer_role: "engineering_reviewer",
        severity: "warning", status: "closed", message: "需要限定工况", closed_by_version_id: "robot:v2"}],
      adjudications: [{adjudication_id: "a1", claim_id: "robot", decision: "accept", reason: "条件已补充"}],
      states: [{claim_id: "robot", status: "accepted"}],
    },
    semantic_note: "support_level、概率、评审一致性与TRL是相互独立的量。",
  }}));

  await page.goto("/");
  await page.getByLabel("论文研判任务 ID").fill("thesis-demo");
  await page.getByRole("button", {name: "查看证据与命题链"}).click();
  await expect(page.getByText("reported_but_not_supplied")).toBeVisible();
  await expect(page.getByText("报告 926 条")).toBeVisible();
  await expect(page.getByText("仅在受控工况推进")).toBeVisible();
  await expect(page.getByText("修订耗尽").locator("..").getByText("1")).toBeVisible();
  await page.getByText("双重评审、闭环与裁决").click();
  await expect(page.getByText("需要限定工况")).toBeVisible();
});
