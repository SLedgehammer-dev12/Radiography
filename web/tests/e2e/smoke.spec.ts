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
  const settingsMenu = page.getByRole("button", { name: /Ayarlar|Settings/i });
  if (await settingsMenu.isVisible()) {
    await settingsMenu.click();
  }
  await page.locator(".dropdown-menu").getByRole("button", { name: /Dil|English|Türkçe/i }).click();
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
  const fileMenu = page.getByRole("button", { name: /Dosya|File/i });
  if (await fileMenu.isVisible()) {
    await fileMenu.click();
  }
  await page.getByRole("button", { name: /PDF/i }).first().click();
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

test("applying an isotope preset re-validates the exposure chart", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });

  // Analog + X-ray + Type X chart
  await page
    .locator(".field", { hasText: "RT Teknolojisi" })
    .getByRole("radio")
    .first()
    .check();
  await page
    .locator(".field", { hasText: "Radyasyon Kaynağı" })
    .locator("select")
    .selectOption("x_ray");
  const chart = page.locator(".field", { hasText: "Chart Kaynağı" }).locator("select");
  await chart.selectOption("type_x");
  await expect(chart).toHaveValue("type_x");

  // Apply an Ir-192 preset from the File menu
  await page.getByRole("button", { name: /Dosya|File/i }).click();
  await page
    .locator("select.menu-select")
    .selectOption({ label: "16 inç DWSI Ir-192 Saha" });

  // The chart must be sanitized to a valid analog-isotope chart, not type_x.
  const chartValue = await chart.inputValue();
  expect(["model", "AA400", "MX125", "T200", "HS800", "M100"]).toContain(
    chartValue,
  );
});

test("round-trips a desktop-compatible preset", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  await expect(page.getByTestId("output-w_nom")).toContainText("12.04 mm");

  const downloadPromise = page.waitForEvent("download");
  const menuTrigger = page.getByRole("button", {
    name: /Dosya|File/i,
  });
  if (await menuTrigger.isVisible()) {
    await menuTrigger.click();
  }
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

test("SWSI defaults to the film-inside figure (fig2), not panoramic fig5", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  const geometry = page
    .locator(".field", { hasText: "Geometri" })
    .locator("select")
    .first();
  await geometry.selectOption("swsi");
  const figure = page
    .locator(".field", { hasText: "Standart ISO Şekli" })
    .locator("select")
    .first();
  await expect
    .poll(async () => figure.inputValue(), { timeout: 30_000 })
    .toMatch(/^fig2/);
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


test("activity label does not duplicate the unit", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  await page
    .locator(".field", { hasText: "Radyasyon Kaynağı" })
    .locator("select")
    .selectOption("isotope_ir192");
  await page.getByRole("button", { name: /Ci\s*→\s*GBq/ }).click();
  const label = page
    .locator(".field", { hasText: "Kaynak Aktivitesi" })
    .locator(".field-label");
  await expect(label).toContainText("(GBq)");
  await expect(label).not.toContainText("(Ci):");
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
  const authMenu = page.getByRole("button", { name: /Yetki|Authority/i });
  if (await authMenu.isVisible()) {
    await authMenu.click();
  }
  await page.getByRole("button", { name: /Seviye 3|Level 3/ }).click();
  await page
    .locator(".modal .field", { hasText: "%20 f_min" })
    .locator('input[type="checkbox"]')
    .check();
  await page.locator(".modal-actions").getByRole("button", { name: /Tamam|OK/i }).click();
  await expect(hero.locator(".hero-sub")).toContainText("Level 3", {
    timeout: 30_000,
  });
  await expect(hero.locator(".hero-sub")).toContainText("uygulanan f_min");
});

test("renders interactive 3D shooting geometry, Annex A chart, and syncs isotope base_e", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  await expect(page.getByTestId("output-w_nom")).not.toContainText("-", {
    timeout: 60_000,
  });

  // 3D canvas is visible by default on the "3D Kurulum" tab
  const canvas3d = page.locator("canvas.sketch-3d-canvas");
  await expect(canvas3d).toBeVisible();
  await page.getByRole("button", { name: /Boyuna \(Eliptik\)/ }).click();
  await page.getByRole("button", { name: /Işın Gözü/ }).click();

  // Switch to Annex A tab and verify chart SVG
  await page.locator(".tab", { hasText: "Annex A" }).click();
  await expect(page.locator("svg.annex-a-svg")).toBeVisible();

  // Switching radiation source to Ir-192 updates base_e to 30
  const sourceSelect = page
    .locator(".field", { hasText: "Radyasyon Kaynağı" })
    .locator("select")
    .first();
  await sourceSelect.selectOption("isotope_ir192");
  const baseEInput = page
    .locator(".field", { hasText: "Pozlama Tablosu Sabiti" })
    .locator("input");
  await expect(baseEInput).toHaveValue("30");
});

