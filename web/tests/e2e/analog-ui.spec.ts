import { expect, test } from "@playwright/test";

async function switchToAnalog(page: import("@playwright/test").Page) {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  await expect(page.getByTestId("output-w_nom")).not.toContainText("-", {
    timeout: 60_000,
  });
  await page
    .locator(".radio-option", { hasText: "Analog Film" })
    .click();
  await expect(page.getByTestId("output-w_nom")).toContainText("12.04 mm");
}

test("analog mode exposes the applied exposure count", async ({ page }) => {
  await switchToAnalog(page);
  await expect(
    page.locator(".field", { hasText: "Uygulanan Poz Sayısı" }).locator("input"),
  ).toBeVisible();
});

test("analog mode shows SFD_min (source-to-film), not SDD_min", async ({
  page,
}) => {
  await switchToAnalog(page);
  const sfdRow = page.getByTestId("output-sfd_min");
  await expect(sfdRow).toContainText("Minimum Odak-Film Mesafesi");
  await expect(sfdRow).not.toContainText("Dedektör");
});

test("digital mode keeps the SDD_min label and hides the film size", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  await expect(page.getByTestId("output-sfd_min")).toContainText(
    "Minimum Odak-Dedektör Mesafesi",
  );
  await expect(
    page.locator(".field", { hasText: "Film Boyutu" }),
  ).toHaveCount(0);
});

test("analog custom film size reveals manual width/height inputs", async ({
  page,
}) => {
  await switchToAnalog(page);
  const filmSize = page
    .locator(".field", { hasText: "Film Boyutu" })
    .locator("select")
    .first();
  await filmSize.selectOption("custom");
  const width = page
    .locator(".field", { hasText: "Film Genişliği" })
    .locator("input");
  const height = page
    .locator(".field", { hasText: "Film Yüksekliği" })
    .locator("input");
  await expect(width).toBeVisible();
  await expect(height).toBeVisible();
  await width.fill("250");
  await height.fill("350");
  await expect(width).toHaveValue("250");
  await expect(height).toHaveValue("350");
});
