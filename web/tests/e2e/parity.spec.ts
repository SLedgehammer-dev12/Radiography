import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

interface Fixture {
  id: string;
  form: Record<string, unknown>;
  expected: Record<string, number | null>;
}

const fixtures = JSON.parse(
  readFileSync(join(dirname(fileURLToPath(import.meta.url)), "parity-fixtures.json"), "utf-8"),
) as Fixture[];

test("web engine matches the shared-core fixture for all scenarios", async ({
  page,
}) => {
  test.setTimeout(600_000);
  await page.goto("/");
  await expect(page.locator(".layout")).toBeVisible({ timeout: 150_000 });
  await expect(page.getByTestId("output-w_nom")).not.toContainText("-", {
    timeout: 60_000,
  });

  const mismatches: string[] = [];
  for (const fixture of fixtures) {
    const calculated = await page.evaluate(async (form) => {
      const hook = (
        window as unknown as {
          __radiography: {
            request: (
              action: string,
              payload: Record<string, unknown>,
            ) => Promise<{ calculated: Record<string, unknown> }>;
          };
        }
      ).__radiography;
      const result = await hook.request("calculate", {
        form,
        lvl3: {},
        lang: "tr",
      });
      return result.calculated;
    }, fixture.form);

    for (const [key, expected] of Object.entries(fixture.expected)) {
      const actual = calculated[key];
      if (expected === null || actual === null || actual === undefined) {
        if ((expected ?? null) !== (actual ?? null)) {
          mismatches.push(`${fixture.id}.${key}: ${actual} != ${expected}`);
        }
        continue;
      }
      if (typeof expected === "number" && typeof actual === "number") {
        const tolerance = Math.max(1e-6, Math.abs(expected) * 1e-6);
        if (Math.abs(actual - expected) > tolerance) {
          mismatches.push(`${fixture.id}.${key}: ${actual} != ${expected}`);
        }
        continue;
      }
      if (actual !== expected) {
        mismatches.push(`${fixture.id}.${key}: ${actual} != ${expected}`);
      }
    }
  }

  expect(fixtures.length).toBeGreaterThanOrEqual(100);
  expect(mismatches.slice(0, 10)).toEqual([]);
  expect(mismatches).toHaveLength(0);
});
