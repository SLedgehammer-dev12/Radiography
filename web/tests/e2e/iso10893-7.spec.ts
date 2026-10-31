import { expect, test } from "@playwright/test";

test.describe("ISO 10893-7 Pipe Welds Digital RT Integration", () => {
  test("renders ISO 10893-7 in Muayene Standardı selector and enforces digital X-ray locking", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    const errors: string[] = [];
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(message.text());
    });

    await page.goto("/");
    await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
    await expect(page.getByTestId("output-w_nom")).toContainText("12.04 mm");

    // 1. Verify standard selector has ISO 10893-7 option
    const standardSelect = page.getByTestId("select-standard");
    await expect(standardSelect).toBeVisible();

    const iso10893Option = standardSelect.locator('option[value="iso10893_7"]');
    await expect(iso10893Option).toBeAttached();
    const optionText = await iso10893Option.textContent();
    expect(optionText).toContain("ISO 10893-7");

    // 2. Select ISO 10893-7
    await standardSelect.selectOption("iso10893_7");

    // 3. Verify technique locking: Digital is active, Analog is disabled
    const analogOption = page.locator(".radio-option", { hasText: "Analog Film" });
    await expect(analogOption).toHaveClass(/disabled/);

    const digitalRadio = page.locator('input[type="radio"][value="digital"]');
    await expect(digitalRadio).toBeChecked();

    // 4. Verify radiation source locking: X-ray is active, Isotopes are disabled in select
    const sourceSelect = page
      .locator(".field", { hasText: /Radyasyon Kaynağı|Radiation Source/i })
      .locator("select");
    await expect(sourceSelect).toHaveValue("x_ray");
    const irOption = sourceSelect.locator('option[value="isotope_ir192"]');
    await expect(irOption).toBeDisabled();

    // 5. Verify 3D Model: Seam type buttons and longitudinal default
    const tab3D = page.locator(".tab", { hasText: /3D Kurulum|3D Setup/i });
    await expect(tab3D).toBeVisible();
    await tab3D.click();

    const longitudinalBtn = page.getByRole("button", {
      name: /Boyuna Düz|Longitudinal/i,
    });
    await expect(longitudinalBtn).toBeVisible();
    await expect(longitudinalBtn).toHaveClass(/active/);

    const helicalBtn = page.getByRole("button", {
      name: /Helisel|Helical/i,
    });
    await expect(helicalBtn).toBeVisible();
    await helicalBtn.click();
    await expect(helicalBtn).toHaveClass(/active/);

    // Verify fluid pipe feed play button
    const feedPlayBtn = page.getByRole("button", {
      name: /Akıcı İlerleme|Fluid Feed/i,
    });
    await expect(feedPlayBtn).toBeVisible();
    await feedPlayBtn.click();
    await expect(page.getByRole("button", { name: /Durdur|Pause/i })).toBeVisible();
    await page.getByRole("button", { name: /Durdur|Pause/i }).click();

    // 6. Verify defect panel has ISO 10893
    const defectStdSelect = page.getByTestId("select-defect-standard");
    await expect(defectStdSelect).toBeVisible();
    await defectStdSelect.selectOption("iso10893");
    await expect(page.locator(".field", { hasText: /Kalite Seviyesi|Quality Level/i })).toBeVisible();

    // 7. Verify calculations calculate properly without unhandled errors
    await expect(page.getByTestId("output-sfd_min")).toContainText("mm");
    expect(errors, `console errors: ${errors.join(" | ")}`).toEqual([]);
  });
});
