import { expect, test } from "@playwright/test";

test("investigate three vendors and inspect evidence", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/demo data: fictional vendors/i)).toBeVisible();
  await page.getByRole("button", { name: /load demo vendors/i }).click();
  await page.getByRole("button", { name: "Longest refund window" }).click();
  await page.getByRole("button", { name: /^investigate/i }).click();

  await expect(page).toHaveURL(/\/investigations\//);
  await expect(page.getByRole("link", { name: /view comparison/i })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/instructions to an AI/).first()).toBeVisible();
  await page.getByRole("link", { name: /view comparison/i }).click();

  await expect(page.getByRole("heading", { name: /studynest best matches/i })).toBeVisible();
  // CourseCove's refund pages disagree: shown as a conflict, never resolved silently.
  await expect(page.getByText("CourseCove: Refund window: Conflicting: 14 days vs 30 days.")).toBeVisible();

  await page.getByRole("button", { name: /show evidence for studynest refund window/i }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText(/full refund within 30 days of purchase/)).toBeVisible();
  await expect(dialog.getByText("Quote verified")).toBeVisible();
  await expect(dialog.getByRole("link").first()).toHaveAttribute("href", "https://studynest.example/help/refund-policy");
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
});

test("prompt injection does not change extracted values", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Vendor name").fill("SkillForge");
  await page.getByRole("button", { name: /^add$/i }).click();
  await page.getByLabel("Vendor name").fill("StudyNest");
  await page.getByRole("button", { name: /^add$/i }).click();
  await page.getByRole("button", { name: /^investigate/i }).click();
  await page.getByRole("link", { name: /view comparison/i }).click({ timeout: 30_000 });
  await page.getByRole("button", { name: /show evidence for skillforge refund window/i }).first().click();
  await expect(page.getByRole("dialog").getByText(/within 7 days of purchase/)).toBeVisible();
  await expect(page.getByText(/365 days/)).toHaveCount(0);
});

test("partial failure is reported honestly", async ({ page }) => {
  await page.goto("/");
  for (const name of ["StudyNest", "OfflineCo"]) {
    await page.getByLabel("Vendor name").fill(name);
    await page.getByRole("button", { name: /^add$/i }).click();
  }
  await page.getByRole("button", { name: /^investigate/i }).click();
  await expect(page.getByText("No policy pages could be retrieved for this vendor").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("link", { name: /view comparison/i })).toBeVisible();
  await expect(page.getByText(/1 of 2 vendors could not be investigated/)).toBeVisible();
});

test("layout has no horizontal overflow", async ({ page }) => {
  await page.goto("/");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
