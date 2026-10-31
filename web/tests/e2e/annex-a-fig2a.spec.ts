import { expect, test } from "@playwright/test";

test("Verify ISO 17636-2 Figure 2a and Annex A chart", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 60_000 });

  // 1. Switch to SWSI
  const geoSelect = page.locator(".field", { hasText: "Geometri" }).locator("select").first();
  await geoSelect.selectOption("swsi");

  // 2. Switch to Curved (flexible) detector -> selects fig2a
  const curvedRadio = page.locator('input[value="curved"]');
  await curvedRadio.check();

  const figSelect = page.locator(".field", { hasText: "Standart ISO Şekli" }).locator("select").first();
  await expect(figSelect).toHaveValue("fig2a");

  // 3. Switch to ISO Figure tab
  const figTab = page.locator(".tab", { hasText: "ISO Figürü" });
  await figTab.click();

  const sketchText = await page.locator("#standard-sketch").innerText();
  console.log("Figure 2a sketch text:", sketchText);

  // Must contain "b = t" and NOT "b = b_ed + b_gap + k·t"
  expect(sketchText).toContain("b = t");
  expect(sketchText).not.toContain("b_ed + b_gap");

  // 4. Switch to Flat detector -> selects fig2b
  const flatRadio = page.locator('input[value="flat"]');
  await flatRadio.check();
  await expect(figSelect).toHaveValue("fig2b");

  const sketchText2b = await page.locator("#standard-sketch").innerText();
  console.log("Figure 2b sketch text:", sketchText2b);
  expect(sketchText2b).toContain("b_ed + b_gap");

  // 5. Test Annex A tab
  const annexTab = page.locator(".tab", { hasText: "Annex A" });
  await annexTab.click();

  const annexSvg = page.locator("svg.annex-a-svg");
  await expect(annexSvg).toBeVisible();

  // Zone text must be present inside the Annex A SVG (rendered from boundaries)
  const zoneTexts = await annexSvg.locator("text").allTextContents();
  console.log("Annex A SVG text count:", zoneTexts.length);
  console.log("Annex A SVG texts:", zoneTexts);
  const hasZoneExp = zoneTexts.some((txt) => /N\s*=\s*\d+/.test(txt));
  console.log("Has zone exposure text (N = X Poz):", hasZoneExp);
  expect(hasZoneExp).toBe(true);

  // 6. Test out-of-chart scenario (thick pipe)
  const tInput = page.locator(".field", { hasText: "Et Kalınlığı" }).locator("input").first();
  await tInput.fill("60");

  // Annex A chart must remain visible with inline warning alert
  await expect(annexSvg).toBeVisible();
  const alertText = await page.locator(".tab-pane .inline-alert, .group .inline-alert").innerText();
  console.log("Out-of-chart alert text:", alertText);
  expect(alertText).toContain("Annex A");
});

test("Verify ISO 17636-1 Figure 2 in 3D Setup tab", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 60_000 });

  // 1. Switch to Analog Film (ISO 17636-1)
  await page.locator(".radio-option", { hasText: "Analog Film" }).click();

  // 2. Switch to SWSI
  const geoSelect = page.locator(".field", { hasText: "Geometri" }).locator("select").first();
  await geoSelect.selectOption("swsi");

  // 3. Verify figure is fig2
  const figSelect = page.locator(".field", { hasText: "Standart ISO Şekli" }).locator("select").first();
  await expect(figSelect).toHaveValue("fig2");

  // 4. Switch to 3D Setup tab
  const tab3d = page.locator(".tab", { hasText: "3D Kurulum" });
  await tab3d.click();

  const canvas = page.locator("canvas.sketch-3d-canvas");
  await expect(canvas).toBeVisible();

  // Check canvas dimensions are nonzero
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.width).toBeGreaterThan(100);
  expect(box!.height).toBeGreaterThan(100);
});
