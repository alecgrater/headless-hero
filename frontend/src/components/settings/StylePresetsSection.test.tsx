import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { StylePresetsSection } from "./StylePresetsSection";

const longPresetPrompt =
  "Create a 16:9 scene inside a bright prison facility hallway with wildly varying ages and builds, matching a precise animated reference style across people, props, lighting, and background details.";
const longCharacterAppearance =
  "Slim, slightly awkward build with messy black hair, uneven bangs, pale skin, faint under-eye bags, oversized hoodie, worn sneakers, and expressive cartoon eyes that constantly look uneasy or distracted.";

vi.mock("../../api", () => ({
  default: {
    get: vi.fn(async () => ({
      ok: true,
      status: 200,
      data: {
        ELI_ENABLED_DEFAULT: { masked: "false" },
        STYLE_PRESET_ENABLED_DEFAULT: { masked: "true" },
      },
    })),
    put: vi.fn(async () => ({ ok: true, status: 200, data: {} })),
  },
  assetUrl: (path: string) => path,
  deleteStylePreset: vi.fn(),
  getActiveStylePreset: vi.fn(async () => ({
    id: "preset-1",
    name: "Epic Ossim 2",
    prompt: longPresetPrompt,
    image_url: "/preset.png",
    created_at: "2026-05-30T00:00:00Z",
  })),
  listStylePresetCharacters: vi.fn(async () => [
    {
      id: "character-1",
      style_preset_id: "preset-1",
      name: "Daniel Vale",
      appearance: longCharacterAppearance,
      vibe: "Nervous but observant.",
      reference_image_url: "/character.png",
      cutout_image_url: "",
      created_at: "2026-05-30T00:00:00Z",
      active: true,
    },
  ]),
  listStylePresets: vi.fn(async () => [
    {
      id: "preset-1",
      name: "Epic Ossim 2",
      prompt: longPresetPrompt,
      image_url: "/preset.png",
      created_at: "2026-05-30T00:00:00Z",
    },
  ]),
  selectStylePresetCharacter: vi.fn(),
  setActiveStylePreset: vi.fn(),
}));

vi.mock("../../contexts/StylePresetContext", () => ({
  useStylePreset: () => ({ refresh: vi.fn() }),
}));

describe("StylePresetsSection", () => {
  it("lets long style and character prompts expand inline", async () => {
    const user = userEvent.setup();

    render(<StylePresetsSection showDefaults={false} showHeader={false} />);

    expect(await screen.findByText("Epic Ossim 2")).toBeInTheDocument();
    expect(await screen.findByText("Daniel Vale")).toBeInTheDocument();

    const expandButtons = screen.getAllByRole("button", { name: /show full prompt/i });
    expect(expandButtons).toHaveLength(2);
    expect(expandButtons[0]).toHaveAttribute("aria-expanded", "false");
    expect(expandButtons[1]).toHaveAttribute("aria-expanded", "false");

    await user.click(expandButtons[0]);

    expect(screen.getByRole("button", { name: /collapse prompt/i })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(screen.getByText(longPresetPrompt)).toBeInTheDocument();
  });
});
