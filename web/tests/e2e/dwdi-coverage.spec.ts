import { expect, test } from "@playwright/test";

test.describe("DWDI Small Receptor Coverage Tests", () => {
  test("Scenario 1: Analog DWDI Elliptic with 10x10 mm film", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
    await expect(page.getByTestId("output-w_nom")).not.toContainText("-", { timeout: 60_000 });

    // Switch to Analog Film
    await page.locator(".radio-option", { hasText: "Analog Film" }).click();

    // Custom Pipe OD: 60.3 (2" pipe)
    const odInput = page.locator(".field", { hasText: "Boru Çapı (OD)" }).locator("input");
    await odInput.fill("60.3");

    // Custom Thickness: 5.5
    const tInput = page.locator(".field", { hasText: "Et Kalınlığı (t)" }).locator("input");
    await tInput.fill("5.5");

    // Geometry DWDI Elliptic
    const geoSelect = page.locator(".field", { hasText: "Geometri" }).locator("select");
    await geoSelect.selectOption("dwdi_elliptic");

    // Source Ir-192
    const sourceSelect = page.locator(".field", { hasText: "Radyasyon Kaynağı" }).locator("select");
    await sourceSelect.selectOption("isotope_ir192");

    // Custom film size 10x10
    const filmSizeSelect = page.locator(".field", { hasText: "Film Boyutu" }).locator("select");
    await filmSizeSelect.selectOption("custom");

    const wInput = page.locator(".field", { hasText: "Film Genişliği" }).locator("input");
    await wInput.fill("10");

    const hInput = page.locator(".field", { hasText: "Film Yüksekliği" }).locator("input");
    await hInput.fill("10");

    // Wait for calculation
    await page.waitForTimeout(2000);

    // 1. Check Hero Card Badge and inline alert banner
    const reqCard = page.locator(".hero-card", { hasText: "Gerekli Minimum Poz Sayısı" });
    await expect(reqCard.locator(".hero-status")).toContainText("Boyut Yetersiz");
    await expect(reqCard.locator(".hero-alert-banner")).toContainText("Boyut Yetersiz");

    // 2. Check Group 2 Inline Field Help
    await expect(page.locator(".field-help.warn")).toContainText("kurtarmıyor");

    // 3. Check Warnings Panel
    const warnings = await page.$$eval(".warning-list li", els => els.map(e => e.innerText));
    expect(warnings.some(w => w.includes("GEOMETRİ/BOYUT UYARISI"))).toBe(true);

    // 4. Check Compliance Panel
    const checks = await page.$$eval(".check-list li", els => els.map(e => e.innerText));
    expect(checks.some(c => c.includes("DWDI BOYUT YETERSİZ"))).toBe(true);
  });

  test("Scenario 2: Analog DWDI Superimposed with 10x10 mm film", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
    await expect(page.getByTestId("output-w_nom")).not.toContainText("-", { timeout: 60_000 });

    await page.locator(".radio-option", { hasText: "Analog Film" }).click();

    const odInput = page.locator(".field", { hasText: "Boru Çapı (OD)" }).locator("input");
    await odInput.fill("60.3");

    const tInput = page.locator(".field", { hasText: "Et Kalınlığı (t)" }).locator("input");
    await tInput.fill("5.5");

    const geoSelect = page.locator(".field", { hasText: "Geometri" }).locator("select");
    await geoSelect.selectOption("dwdi_super");

    const sourceSelect = page.locator(".field", { hasText: "Radyasyon Kaynağı" }).locator("select");
    await sourceSelect.selectOption("isotope_ir192");

    const filmSizeSelect = page.locator(".field", { hasText: "Film Boyutu" }).locator("select");
    await filmSizeSelect.selectOption("custom");

    const wInput = page.locator(".field", { hasText: "Film Genişliği" }).locator("input");
    await wInput.fill("10");

    const hInput = page.locator(".field", { hasText: "Film Yüksekliği" }).locator("input");
    await hInput.fill("10");

    await page.waitForTimeout(2000);

    const reqCard = page.locator(".hero-card", { hasText: "Gerekli Minimum Poz Sayısı" });
    await expect(reqCard.locator(".hero-status")).toContainText("Boyut Yetersiz");
    await expect(reqCard.locator(".hero-alert-banner")).toContainText("Boyut Yetersiz");

    const warnings = await page.$$eval(".warning-list li", els => els.map(e => e.innerText));
    expect(warnings.some(w => w.includes("GEOMETRİ/BOYUT UYARISI"))).toBe(true);
  });

  test("Scenario 3: Digital DWDI Elliptic with 10x10 mm panel", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
    await expect(page.getByTestId("output-w_nom")).not.toContainText("-", { timeout: 60_000 });

    const odInput = page.locator(".field", { hasText: "Boru Çapı (OD)" }).locator("input");
    await odInput.fill("60.3");

    const tInput = page.locator(".field", { hasText: "Et Kalınlığı (t)" }).locator("input");
    await tInput.fill("5.5");

    const geoSelect = page.locator(".field", { hasText: "Geometri" }).locator("select");
    await geoSelect.selectOption("dwdi_elliptic");

    const sourceSelect = page.locator(".field", { hasText: "Radyasyon Kaynağı" }).locator("select");
    await sourceSelect.selectOption("isotope_ir192");

    // Group 2 panel inputs
    const panelW = page.locator(".field", { hasText: "Panel Aktif Genişliği" }).locator("input").first();
    await panelW.fill("10");

    const panelH = page.locator(".field", { hasText: "Panel Aktif Yüksekliği" }).locator("input").first();
    await panelH.fill("10");

    await page.waitForTimeout(2000);

    const reqCard = page.locator(".hero-card", { hasText: "Gerekli Minimum Poz Sayısı" });
    await expect(reqCard.locator(".hero-status")).toContainText("Boyut Yetersiz");
    await expect(reqCard.locator(".hero-alert-banner")).toContainText("Boyut Yetersiz");

    const warnings = await page.$$eval(".warning-list li", els => els.map(e => e.innerText));
    expect(warnings.some(w => w.includes("GEOMETRİ/BOYUT UYARISI"))).toBe(true);
  });

  test("Scenario 4: Digital DWDI Superimposed with 10x10 mm panel", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
    await expect(page.getByTestId("output-w_nom")).not.toContainText("-", { timeout: 60_000 });

    const odInput = page.locator(".field", { hasText: "Boru Çapı (OD)" }).locator("input");
    await odInput.fill("60.3");

    const tInput = page.locator(".field", { hasText: "Et Kalınlığı (t)" }).locator("input");
    await tInput.fill("5.5");

    const geoSelect = page.locator(".field", { hasText: "Geometri" }).locator("select");
    await geoSelect.selectOption("dwdi_super");

    const sourceSelect = page.locator(".field", { hasText: "Radyasyon Kaynağı" }).locator("select");
    await sourceSelect.selectOption("isotope_ir192");

    const panelW = page.locator(".field", { hasText: "Panel Aktif Genişliği" }).locator("input").first();
    await panelW.fill("10");

    const panelH = page.locator(".field", { hasText: "Panel Aktif Yüksekliği" }).locator("input").first();
    await panelH.fill("10");

    await page.waitForTimeout(2000);

    const reqCard = page.locator(".hero-card", { hasText: "Gerekli Minimum Poz Sayısı" });
    await expect(reqCard.locator(".hero-status")).toContainText("Boyut Yetersiz");
    await expect(reqCard.locator(".hero-alert-banner")).toContainText("Boyut Yetersiz");

    const warnings = await page.$$eval(".warning-list li", els => els.map(e => e.innerText));
    expect(warnings.some(w => w.includes("GEOMETRİ/BOYUT UYARISI"))).toBe(true);
  });
});
