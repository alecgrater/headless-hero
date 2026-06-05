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

  it("uses a compact brand workspace layout for preset, character, and defaults", async () => {
    render(<StylePresetsSection showHeader={false} />);

    expect(await screen.findByText("Epic Ossim 2")).toBeInTheDocument();
    expect(await screen.findByText("Daniel Vale")).toBeInTheDocument();

    expect(screen.getByTestId("brand-style-workspace")).toHaveClass("lg:grid-cols-2");
    expect(screen.getByTestId("style-preset-preview")).toHaveClass("max-h-[220px]");
    expect(screen.getByTestId("main-character-preview")).toHaveClass("max-h-[220px]");
    expect(screen.getByTestId("brand-defaults-panel")).toHaveClass("lg:col-span-2");
  });

  it("uses one visual identity picker for new project defaults", async () => {
    const user = userEvent.setup();

    render(<StylePresetsSection showHeader={false} />);

    expect(await screen.findByRole("heading", { name: "New Project Visual Identity", level: 3 })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Style preset and main character/i })).toBeChecked();
    expect(screen.getByRole("radio", { name: /Eli host overlay/i })).not.toBeChecked();
    expect(screen.getByRole("radio", { name: /No global style preset/i })).not.toBeChecked();
    expect(screen.queryByRole("switch", { name: /Enable Eli host overlay by default for new projects/i })).toBeNull();
    expect(screen.queryByRole("checkbox", { name: /Style preset/i })).toBeNull();
    const selectedVisualIdentity = screen.getByText("Style preset and main character").closest("label");
    expect(selectedVisualIdentity).toHaveClass("border-l-2", "border-violet-400");
    expect(selectedVisualIdentity).not.toHaveClass("rounded-lg", "border", "bg-violet-500/10");

    await user.click(screen.getByRole("radio", { name: /Eli host overlay/i }));

    expect(screen.getByRole("radio", { name: /Eli host overlay/i })).toBeChecked();
    expect(screen.getByText("You have unsaved brand defaults")).toBeInTheDocument();
  });
});
