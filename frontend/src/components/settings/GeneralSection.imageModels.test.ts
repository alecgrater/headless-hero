import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { GOOGLE_IMAGE_MODELS } from "./GeneralSection";

// The backend dict is the source of truth for which image models exist and
// what they cost; the dropdown is a hand-kept mirror of it.
function backendImagePrices(): [string, number][] {
  const config = readFileSync(resolve(process.cwd(), "../backend/config.py"), "utf8");
  const defaultModel = config.match(/^DEFAULT_IMAGE_MODEL = "([^"]+)"/m)?.[1];
  const block = config.match(/GOOGLE_IMAGE_MODEL_PRICES[^{]*\{([\s\S]*?)\n\}/)?.[1] ?? "";
  return [...block.matchAll(/^\s*(DEFAULT_IMAGE_MODEL|"[^"]+"):\s*([\d.]+)/gm)].map(([, key, price]) => [
    key === "DEFAULT_IMAGE_MODEL" ? (defaultModel ?? key) : key.slice(1, -1),
    Number(price),
  ]);
}

describe("image model dropdown", () => {
  it("lists exactly the backend's models, in the same order", () => {
    const backend = backendImagePrices();
    expect(backend.length).toBeGreaterThan(0);
    expect(GOOGLE_IMAGE_MODELS.map((m) => m.value)).toEqual(backend.map(([id]) => id));
  });

  it("shows each model's backend price, rounded to the tenth of a cent", () => {
    for (const [id, price] of backendImagePrices()) {
      const option = GOOGLE_IMAGE_MODELS.find((m) => m.value === id);
      expect(option?.label).toContain(`$${price.toFixed(3)}/image`);
    }
  });
});
