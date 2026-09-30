import { describe, expect, it } from "vitest";

import configSource from "../../../../backend/config.py?raw";
import { GOOGLE_IMAGE_MODELS } from "./GeneralSection";

// The backend dict is the source of truth for which image models exist and
// what they cost; the dropdown is a hand-kept mirror of it.
function backendImagePrices(): [string, number][] {
  const constants = Object.fromEntries(
    [...configSource.matchAll(/^([A-Z_][A-Z0-9_]*) = "([^"]+)"/gm)].map(([, name, value]) => [name, value]),
  );
  const block = configSource.match(/GOOGLE_IMAGE_MODEL_PRICES[^{]*\{([\s\S]*?)\n\}/)?.[1] ?? "";
  const entries = block.split("\n").filter((line) => line.trim() && !line.trim().startsWith("#"));
  return entries.map((line): [string, number] => {
    const match = line.match(/^\s*([A-Z_][A-Z0-9_]*|"[^"]+"|'[^']+'):\s*([\d.]+)\s*,?\s*(#.*)?$/);
    if (!match) throw new Error(`Unparsed GOOGLE_IMAGE_MODEL_PRICES entry: ${line}`);
    const [, key, price] = match;
    const id = /^[A-Z_][A-Z0-9_]*$/.test(key) ? constants[key] : key.slice(1, -1);
    if (!id) throw new Error(`Unknown constant in GOOGLE_IMAGE_MODEL_PRICES: ${key}`);
    return [id, Number(price)];
  });
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
