import { expect, test } from "@playwright/test";

// iPhone-12-class viewport with touch enabled.
test.use({ viewport: { width: 390, height: 844 }, hasTouch: true });

test("mobile: boots, calculates and does not scroll horizontally", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  await expect(page.getByTestId("output-w_nom")).toContainText("mm", {
    timeout: 60_000,
  });

  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
  expect(overflow, "page must not scroll horizontally").toBeLessThanOrEqual(1);
});

test("mobile: form controls use 16px to avoid iOS focus zoom", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  const fontSize = await page
    .locator("input.field-input")
    .first()
    .evaluate((el) => getComputedStyle(el).fontSize);
  expect(fontSize).toBe("16px");
});

test("mobile: info tip opens the details modal on tap", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  await expect(page.getByTestId("output-w_nom")).toContainText("mm", {
    timeout: 60_000,
  });
  await page.locator(".info-tip").first().click();
  await expect(page.locator(".modal.info-modal")).toBeVisible({
    timeout: 30_000,
  });
});
