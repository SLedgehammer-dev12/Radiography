import { expect, test } from "@playwright/test";

async function applyPreset(page: import("@playwright/test").Page) {
  await page.getByRole("button", { name: /Dosya|File/i }).click();
  await page
    .locator("select.menu-select")
    .selectOption({ label: "16 inç DWSI Ir-192 Saha" });
}

test("applying a preset shows a success toast that can be dismissed", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  await applyPreset(page);

  const toast = page.locator(".toast.toast-success");
  await expect(toast).toBeVisible();
  await expect(toast).toContainText(/uygulandı|Applied/);

  await toast.locator(".toast-close").click();
  await expect(page.locator(".toast")).toHaveCount(0);
});

test("toast auto-dismisses after a few seconds", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  await applyPreset(page);

  await expect(page.locator(".toast")).toBeVisible();
  await expect(page.locator(".toast")).toHaveCount(0, { timeout: 8_000 });
});

test("topbar reset restores the default form", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });

  const source = page
    .locator(".field", { hasText: "Radyasyon Kaynağı" })
    .locator("select");
  await source.selectOption("isotope_ir192");
  await expect(source).toHaveValue("isotope_ir192");

  await page.getByRole("button", { name: /Sıfırla|Reset/ }).click();
  await expect(page.locator(".toast")).toContainText(/sıfırlandı|reset/i);
  await expect(source).toHaveValue("x_ray");
});

test("sticky header keeps the primary action reachable when scrolled", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  await expect(page.locator(".topbar-action.primary")).toBeVisible();

  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await expect(page.locator(".topbar-action.primary")).toBeInViewport();
});

test("header exposes an idle indeterminate progress bar", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  await expect(page.getByTestId("output-w_nom")).toContainText("mm", {
    timeout: 60_000,
  });
  await expect(page.locator(".app-progress")).toHaveAttribute(
    "aria-hidden",
    "true",
  );
});

test("keyboard: Ctrl+S saves a preset", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  const downloadPromise = page.waitForEvent("download");
  await page.keyboard.press("Control+s");
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toContain("rt_preset");
});

test("keyboard: Ctrl+Enter exports the PDF", async ({ page }) => {
  test.setTimeout(300_000);
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  await expect(page.getByTestId("output-calc_time")).not.toContainText("-", {
    timeout: 60_000,
  });
  const downloadPromise = page.waitForEvent("download", { timeout: 240_000 });
  await page.keyboard.press("Control+Enter");
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toContain("RT_Inspection_Report");
});



