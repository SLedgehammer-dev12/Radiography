import { expect, test } from "@playwright/test";

test.describe("Web Usability Iteration 2: Outdoor Theme & Calculation History", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("Outdoor high-contrast theme cycles and persists across page reloads", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
    await expect(page.getByTestId("output-w_nom")).not.toContainText("-", { timeout: 60_000 });

    const themeToggle = page.getByTestId("topbar-theme-toggle");
    await expect(themeToggle).toBeVisible();

    // Verify initial theme is set on html root
    const initialTheme = await page.evaluate(() => document.documentElement.getAttribute("data-theme"));
    expect(["dark", "light", "outdoor"]).toContain(initialTheme);

    // Click toggle to cycle until outdoor mode is active
    let currentTheme = initialTheme;
    for (let i = 0; i < 3; i++) {
      if (currentTheme === "outdoor") break;
      await themeToggle.click();
      currentTheme = await page.evaluate(() => document.documentElement.getAttribute("data-theme"));
    }
    expect(currentTheme).toBe("outdoor");

    // In outdoor mode, verify high-contrast styling tokens
    const outdoorBg = await page.evaluate(() =>
      window.getComputedStyle(document.documentElement).getPropertyValue("--bg").trim(),
    );
    expect(outdoorBg.toLowerCase()).toBe("#ffffff");

    const outdoorText = await page.evaluate(() =>
      window.getComputedStyle(document.documentElement).getPropertyValue("--text").trim(),
    );
    expect(outdoorText.toLowerCase()).toBe("#000000");

    // Verify high-contrast 2px border on groups and inputs
    const groupBorderWidth = await page.evaluate(() => {
      const el = document.querySelector(".group");
      return el ? window.getComputedStyle(el).borderWidth : "";
    });
    expect(groupBorderWidth).toBe("2px");

    // Verify persistence in localStorage using retrying poll
    await expect
      .poll(async () => {
        return page.evaluate(() => {
          const state = localStorage.getItem("radiography_web_state_v1");
          return state ? JSON.parse(state).theme : null;
        });
      })
      .toBe("outdoor");

    // Reload page and confirm outdoor theme is retained
    await page.reload();
    await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
    const reloadedTheme = await page.evaluate(() => document.documentElement.getAttribute("data-theme"));
    expect(reloadedTheme).toBe("outdoor");

    // Next click cycles back to dark mode
    await page.getByTestId("topbar-theme-toggle").click();
    const cycledTheme = await page.evaluate(() => document.documentElement.getAttribute("data-theme"));
    expect(cycledTheme).toBe("dark");
  });

  test("Calculation history records snapshots, restores state, and clears correctly", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
    await expect(page.getByTestId("output-w_nom")).not.toContainText("-", { timeout: 60_000 });

    const historyBtn = page.getByTestId("topbar-history");
    await expect(historyBtn).toBeVisible();

    // Initial calculation should be captured in history
    await page.waitForTimeout(300);
    await historyBtn.click();

    const historyModal = page.getByTestId("history-modal");
    await expect(historyModal).toBeVisible();

    // Verify at least 1 history item exists with real calculated values (not 0 sn)
    const initialRestoreBtns = page.getByTestId("history-restore-btn");
    await expect(initialRestoreBtns).toHaveCount(1);
    await expect(historyModal).not.toContainText("Süre: 0 sn");

    // Close modal
    await page.getByTestId("history-close-btn").click();
    await expect(historyModal).not.toBeVisible();

    // Click quick preset chip "4 inç" to trigger a distinct calculation
    const preset4 = page.locator(".preset-chips-bar button").filter({ hasText: "4 inç" });
    await expect(preset4).toBeVisible();
    await preset4.click();

    // Wait for calculation and history update
    await expect
      .poll(async () => {
        const raw = await page.evaluate(() => localStorage.getItem("radiography_calc_history_v1"));
        return raw ? JSON.parse(raw).length : 0;
      })
      .toBe(2);

    // Click quick preset chip "16 inç" to trigger another calculation
    const preset16 = page.locator(".preset-chips-bar button").filter({ hasText: "16 inç" });
    await expect(preset16).toBeVisible();
    await preset16.click();

    await expect
      .poll(async () => {
        const raw = await page.evaluate(() => localStorage.getItem("radiography_calc_history_v1"));
        return raw ? JSON.parse(raw).length : 0;
      })
      .toBe(3);

    // Open history modal again
    await historyBtn.click();
    await expect(historyModal).toBeVisible();

    // Verify 3 history cards exist
    const restoreBtns = page.getByTestId("history-restore-btn");
    await expect(restoreBtns).toHaveCount(3);

    // Click restore on the oldest/last entry (the initial 2" setup)
    await restoreBtns.last().click();
    await expect(historyModal).not.toBeVisible();

    // Toast notification should show restoration feedback
    await expect(page.locator(".toast-message, .toast")).toBeVisible({ timeout: 5000 });

    // Open history modal again and test clearing
    await historyBtn.click();
    await expect(historyModal).toBeVisible();

    const clearBtn = page.getByTestId("history-clear-btn");
    await expect(clearBtn).toBeVisible();
    await clearBtn.click();

    // Verify empty state is rendered
    await expect(page.getByTestId("history-restore-btn")).toHaveCount(0);
    await expect(historyModal).toContainText("kayıtlı bir hesaplama geçmişi bulunmuyor", { ignoreCase: true });

    // Close modal with Escape key
    await page.keyboard.press("Escape");
    await expect(historyModal).not.toBeVisible();
  });

  test("Corrupted localStorage entries in history do not crash the application", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });

    // Inject corrupted and partial records into localStorage
    await page.evaluate(() => {
      localStorage.setItem(
        "radiography_calc_history_v1",
        JSON.stringify([null, { id: "bad1" }, { id: "bad2", form: {} }, 12345]),
      );
    });

    // Reload page to test loadHistory resilience
    await page.reload();
    await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
    await expect(page.getByTestId("output-w_nom")).not.toContainText("-", { timeout: 60_000 });

    // Open history modal - should not crash and should render safely
    const historyBtn = page.getByTestId("topbar-history");
    await historyBtn.click();
    const historyModal = page.getByTestId("history-modal");
    await expect(historyModal).toBeVisible();

    // Corrupted records are filtered out, only valid (or empty) rendered
    await page.getByTestId("history-close-btn").click();
    await expect(historyModal).not.toBeVisible();
  });

  test("Keyboard quick-jump (Alt+1..4, Alt+H) expands collapsed sections and opens history", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
    await expect(page.getByTestId("output-w_nom")).not.toContainText("-", { timeout: 60_000 });

    // Collapse section-standards (<details id="section-standards">)
    await page.evaluate(() => {
      const el = document.getElementById("section-standards") as HTMLDetailsElement | null;
      if (el) el.open = false;
    });
    const isInitiallyOpen = await page.evaluate(
      () => (document.getElementById("section-standards") as HTMLDetailsElement | null)?.open,
    );
    expect(isInitiallyOpen).toBe(false);

    // Press Alt+3 to jump to and auto-expand section-standards
    await page.keyboard.press("Alt+Digit3");
    const isOpenedByShortcut = await page.evaluate(
      () => (document.getElementById("section-standards") as HTMLDetailsElement | null)?.open,
    );
    expect(isOpenedByShortcut).toBe(true);

    // Verify focus moved inside #section-standards
    const focusInsideStandards = await page.evaluate(() => {
      const section = document.getElementById("section-standards");
      return Boolean(section && section.contains(document.activeElement));
    });
    expect(focusInsideStandards).toBe(true);

    // Press Alt+H to open the Recent Calculations History modal
    await page.keyboard.press("Alt+KeyH");
    const historyModal = page.getByTestId("history-modal");
    await expect(historyModal).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(historyModal).not.toBeVisible();
  });

  test("Shareable setup URL (?setup=...) hydrates form parameters and cleans address bar", async ({ page }) => {
    const customSetup = encodeURIComponent(
      JSON.stringify({ od: 406.4, t: 10.0, geometry: "swsi" }),
    );
    await page.goto(`/?setup=${customSetup}`);
    await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
    await expect(page.getByTestId("output-w_nom")).not.toContainText("-", { timeout: 60_000 });

    // SWSI with t = 10.0 mm produces w_nom = 10.0 mm
    await expect(page.getByTestId("output-w_nom")).toContainText("10");

    // Address bar query string should be cleaned after hydration
    const searchAfterLoad = await page.evaluate(() => window.location.search);
    expect(searchAfterLoad).toBe("");

    // Clicking topbar-share shows confirmation toast
    const shareBtn = page.getByTestId("topbar-share");
    await expect(shareBtn).toBeVisible();
    await shareBtn.click();
    await expect(page.locator(".toast")).toBeVisible({ timeout: 5000 });
  });
});
