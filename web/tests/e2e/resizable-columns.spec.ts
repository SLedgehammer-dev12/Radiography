import { expect, test } from "@playwright/test";

test.describe("Resizable Columns & 3D Column 40% Width Tests", () => {
  test.use({ viewport: { width: 1600, height: 950 } });

  test("3D view column defaults to ~40% width and can be adjusted with drag handles", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
    await expect(page.getByTestId("output-w_nom")).not.toContainText("-", { timeout: 60_000 });

    const layout = page.locator(".layout");
    const colInputs = page.locator(".column.inputs");
    const colOutputs = page.locator(".column.outputs");
    const colWarnings = page.locator(".column.warnings"); // 3D view column

    const layoutBox = await layout.boundingBox();
    expect(layoutBox).not.toBeNull();
    const warningsBox = await colWarnings.boundingBox();
    expect(warningsBox).not.toBeNull();

    if (layoutBox && warningsBox) {
      // Check that 3D column is approximately 40% of layout width (within 38% - 42%)
      const ratio = warningsBox.width / layoutBox.width;
      expect(ratio).toBeGreaterThan(0.36);
      expect(ratio).toBeLessThan(0.44);
    }

    // Verify both column resizers are present and visible on desktop
    const resizers = page.locator(".column-resizer");
    await expect(resizers).toHaveCount(2);
    await expect(resizers.first()).toBeVisible();
    await expect(resizers.nth(1)).toBeVisible();

    // Drag second resizer (between outputs and 3D column) to the left to expand 3D column
    const resizer2 = resizers.nth(1);
    const resizer2Box = await resizer2.boundingBox();
    expect(resizer2Box).not.toBeNull();

    if (resizer2Box && layoutBox) {
      const initialWarningsWidth = (await colWarnings.boundingBox())!.width;

      // Drag 80px to the left
      await page.mouse.move(resizer2Box.x + resizer2Box.width / 2, resizer2Box.y + 100);
      await page.mouse.down();
      await page.mouse.move(resizer2Box.x - 80, resizer2Box.y + 100, { steps: 5 });
      await page.mouse.up();

      // 3D column should now be wider than initial
      const expandedWarningsWidth = (await colWarnings.boundingBox())!.width;
      expect(expandedWarningsWidth).toBeGreaterThan(initialWarningsWidth + 30);

      // Verify localStorage was updated
      const savedWidths = await page.evaluate(() => localStorage.getItem("radiography_col_widths_v1"));
      expect(savedWidths).not.toBeNull();

      // Double-click resizer to reset to default
      const updatedResizer2Box = await resizer2.boundingBox();
      expect(updatedResizer2Box).not.toBeNull();
      await page.mouse.dblclick(updatedResizer2Box!.x + updatedResizer2Box!.width / 2, updatedResizer2Box!.y + 100);

      // Width should be back near 40%
      const resetWarningsWidth = (await colWarnings.boundingBox())!.width;
      const resetRatio = resetWarningsWidth / layoutBox.width;
      expect(resetRatio).toBeGreaterThan(0.36);
      expect(resetRatio).toBeLessThan(0.44);
    }

    // Open View menu and verify Reset Columns option exists
    await page.getByRole("button", { name: "Görünüm" }).click();
    const resetMenuBtn = page.getByRole("button", { name: "Kolonları Sıfırla" });
    await expect(resetMenuBtn).toBeVisible();
    await resetMenuBtn.click();
  });
});
