import { expect, test } from "@playwright/test";

test("boots the Python core and calculates default DWSI", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });

  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });

  // Defaults: DWSI, digital, planar, t = 6.02 -> w_nom = 2t = 12.04 mm
  await expect(page.getByTestId("output-w_nom")).toContainText("12.04 mm");
  await expect(page.getByTestId("output-sfd_min")).toContainText("mm");
  await expect(page.getByTestId("output-calc_time")).not.toContainText("-");

  // Compliance badge must be rendered from the shared checker
  await expect(page.locator(".badge")).toBeVisible();

  expect(errors, `console errors: ${errors.join(" | ")}`).toEqual([]);
});

test("switches language and keeps calculating", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });

  const title = page.locator(".group-title").first();
  const turkishTitle = await title.textContent();
  await page.getByRole("button", { name: /English|EN/ }).click();
  await expect(title).not.toHaveText(turkishTitle ?? "", { timeout: 30_000 });
  await expect(page.getByTestId("output-w_nom")).toContainText("mm");
});

test("exports a PDF report via ReportLab in Pyodide", async ({ page }) => {
  test.setTimeout(300_000);
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  await expect(page.getByTestId("output-calc_time")).not.toContainText("-", {
    timeout: 60_000,
  });

  const downloadPromise = page.waitForEvent("download", { timeout: 240_000 });
  await page.locator("header button.primary").click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toContain("RT_Inspection_Report");
  const path = await download.path();
  expect(path).toBeTruthy();
  const { statSync } = await import("node:fs");
  // The two embedded sketches make the PDF substantially larger than a
  // text-only report.
  expect(statSync(path!).size).toBeGreaterThan(20_000);
});

test("evaluates a defect with the shared engine", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  await page
    .locator(".group", { hasText: "Kusur" })
    .getByRole("button", { name: /Değerlendir|Evaluate/ })
    .click();
  await expect(page.locator(".defect-reason")).toBeVisible({ timeout: 30_000 });
});

test("round-trips a desktop-compatible preset", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  await expect(page.getByTestId("output-w_nom")).toContainText("12.04 mm");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: /Şablon Kaydet|Save Preset/ }).click();
  const download = await downloadPromise;
  const path = await download.path();
  expect(path).toBeTruthy();

  const geometry = page
    .locator(".field", { hasText: "Geometri" })
    .locator("select")
    .first();
  await geometry.selectOption("swsi");
  await expect(page.getByTestId("output-w_nom")).toContainText("6.02 mm");

  await page.locator('input[type="file"]').first().setInputFiles(path!);
  await expect(page.getByTestId("output-w_nom")).toContainText("12.04 mm", {
    timeout: 30_000,
  });
});

test("renders the dynamic sketch for every geometry and all figures", async ({
  page,
}) => {
  test.setTimeout(240_000);
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });

  const geometry = page
    .locator(".field", { hasText: "Geometri" })
    .locator("select")
    .first();
  for (const value of ["dwsi", "swsi", "dwdi_elliptic", "dwdi_super"]) {
    await geometry.selectOption(value);
    await expect(page.locator("svg.sketch-svg")).toHaveCount(2, {
      timeout: 30_000,
    });
  }

  const figure = page
    .locator(".field", { hasText: "Standart ISO Şekli" })
    .locator("select")
    .first();
  await expect
    .poll(async () => figure.locator("option").count(), { timeout: 30_000 })
    .toBeGreaterThan(0);
  const values = await figure
    .locator("option")
    .evaluateAll((options) => options.map((option) => (option as HTMLOptionElement).value));
  for (const value of values) {
    await figure.selectOption(value);
    await expect(page.locator("svg.sketch-svg")).toHaveCount(2, {
      timeout: 30_000,
    });
  }
});

test("updates outputs when the geometry changes", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  await expect(page.getByTestId("output-w_nom")).toContainText("12.04 mm");

  const geometry = page
    .locator(".field", { hasText: "Geometri" })
    .locator("select")
    .first();
  await geometry.selectOption("swsi");
  await expect(page.getByTestId("output-w_nom")).toContainText("6.02 mm");
});


test("shows the SFD_min/SDD_min calculation provenance", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  const hero = page.locator(".hero-card", { hasText: "Minimum Odak-Dedekt" });
  await expect(hero.locator(".hero-sub")).toContainText("Kaynak", {
    timeout: 60_000,
  });
  await expect(hero.locator(".hero-sub")).toContainText("1,4·dd");

  // Changing the panel size changes the governing coverage value.
  const panelWidth = page
    .locator(".field", { hasText: "Panel Aktif Genişliği" })
    .locator("input")
    .first();
  await panelWidth.fill("500");
  await expect(hero.locator(".hero-sub")).toContainText("753.9 mm", {
    timeout: 30_000,
  });
});


test("shows the required exposure-count provenance", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  const hero = page.locator(".hero-card", { hasText: "Gerekli Minimum Poz" });
  await expect(hero.locator(".hero-sub")).toContainText("Annex A Şekil A2", {
    timeout: 60_000,
  });
  await expect(hero.locator(".hero-sub")).toContainText("N=");
});


test("shows the f_min provenance (base formula, Level 3 reductions)", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  const hero = page.locator(".hero-card", { hasText: "Minimum Odak-Nesne" });
  await expect(hero.locator(".hero-sub")).toContainText("Temel f_min", {
    timeout: 60_000,
  });
  await expect(hero.locator(".hero-sub")).toContainText("Formül");

  // Enable the Level 3 double-wall reduction -> reduced value is shown.
  await page.getByRole("button", { name: /Seviye 3/ }).click();
  await page
    .locator(".modal .field", { hasText: "%20 f_min" })
    .locator('input[type="checkbox"]')
    .check();
  await page.getByRole("button", { name: "Tamam" }).click();
  await expect(hero.locator(".hero-sub")).toContainText("Level 3", {
    timeout: 30_000,
  });
  await expect(hero.locator(".hero-sub")).toContainText("uygulanan f_min");
});
