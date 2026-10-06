import { expect, test } from "@playwright/test";

import { dataUrlToBase64 } from "../../src/lib/dataUrl";

test.describe("dataUrlToBase64", () => {
  test("extracts the Base64 payload of a PNG data URL", () => {
    expect(dataUrlToBase64("data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==")).toBe(
      "iVBORw0KGgoAAAANSUhEUg==",
    );
  });

  test("rejects non-PNG and malformed data URLs", () => {
    expect(dataUrlToBase64("data:image/jpeg;base64,AAAA")).toBeNull();
    expect(dataUrlToBase64("data:image/png")).toBeNull();
    expect(dataUrlToBase64("")).toBeNull();
  });
});
