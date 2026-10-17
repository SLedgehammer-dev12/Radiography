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
