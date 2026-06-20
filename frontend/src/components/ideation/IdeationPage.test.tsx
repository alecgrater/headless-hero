import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  selectStylePresetCharacter,
  setActiveStylePreset,
} from "../../api";
import IdeationPage from "./IdeationPage";

const presets = [
  {
    id: "preset-1",
    name: "Friendly Editorial Cartoon",
    prompt: "Warm editorial cartoon style with varied characters.",
    image_url: "/preset-1.png",
    created_at: "2026-06-20T00:00:00Z",
  },
  {
    id: "preset-2",
    name: "Bold Documentary Collage",
    prompt: "High contrast documentary collage.",
    image_url: "/preset-2.png",
    created_at: "2026-06-20T00:00:00Z",
  },
];

const charactersByPreset = {
  "preset-1": [
    {
      id: "character-1",
      style_preset_id: "preset-1",
      name: "Tyler",
      appearance: "Early 20s, red cap, blue polo, approachable cartoon posture.",
      vibe: "Warm and curious.",
      reference_image_url: "/tyler.png",
      cutout_image_url: "/tyler-cutout.png",
      created_at: "2026-06-20T00:00:00Z",
      active: true,
    },
  ],
  "preset-2": [
    {
      id: "character-2",
      style_preset_id: "preset-2",
      name: "Mara",
      appearance: "Sharp silhouette with documentary host styling.",
      vibe: "Analytical.",
      reference_image_url: "/mara.png",
      cutout_image_url: "",
      created_at: "2026-06-20T00:00:00Z",
      active: false,
    },
  ],
};

let activeStylePreset = presets[0] as (typeof presets)[number] | null;
const refreshStylePreset = vi.fn(async () => undefined);

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
    post: vi.fn(async () => ({ ok: true, status: 200, data: { ideas: [] } })),
  },
  assetUrl: (path: string) => path,
  fetchGenerationEstimate: vi.fn(async () => ({ average_seconds: 8 })),
  getFormats: vi.fn(async () => [
    {
      id: "youtube-listicle",
      label: "Educational Listicle",
      description: "Listicle",
      idea_title_placeholder: "",
      idea_niche_placeholder: "",
      segment_label: "segments",
      default_segments: 8,
    },
  ]),
  getActiveStylePreset: vi.fn(async () => activeStylePreset),
  listStylePresetCharacters: vi.fn(async (presetId: "preset-1" | "preset-2") => charactersByPreset[presetId]),
  listStylePresets: vi.fn(async () => presets),
  selectStylePresetCharacter: vi.fn(async (_presetId: string, characterId: string) => {
    const presetCharacters = Object.values(charactersByPreset).flat();
    return presetCharacters.find((character) => character.id === characterId);
  }),
  setActiveStylePreset: vi.fn(async () => undefined),
}));

vi.mock("../../contexts/StylePresetContext", () => ({
  useStylePreset: () => ({
    activePreset: presets[0],
    loading: false,
    refresh: refreshStylePreset,
  }),
}));

describe("IdeationPage", () => {
  beforeEach(() => {
    activeStylePreset = presets[0];
    vi.clearAllMocks();
  });

  it("shows the style preset and main character selector only when style identity is selected", async () => {
    const user = userEvent.setup();

    render(<IdeationPage onUseIdea={vi.fn()} />);

    expect(await screen.findByText("Friendly Editorial Cartoon")).toBeInTheDocument();
    expect(await screen.findByText("Tyler")).toBeInTheDocument();

    const selector = screen.getByTestId("ideation-style-character-selector");
    expect(within(selector).getByRole("heading", { name: "Style Preset" })).toBeInTheDocument();
    expect(within(selector).getByRole("heading", { name: "Main Character" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /View Bold Documentary Collage/i }));

    await waitFor(() => {
      expect(setActiveStylePreset).toHaveBeenCalledWith("preset-2");
    });
    expect(await screen.findByText("Mara")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /View Mara/i }));

    await waitFor(() => {
      expect(selectStylePresetCharacter).toHaveBeenCalledWith("preset-2", "character-2");
    });

    await user.click(screen.getByRole("radio", { name: /No global style preset/i }));

    expect(screen.queryByTestId("ideation-style-character-selector")).not.toBeInTheDocument();
  });

  it("persists the first saved style preset before showing it as active when no active preset exists", async () => {
    activeStylePreset = null;

    render(<IdeationPage onUseIdea={vi.fn()} />);

    expect(await screen.findByText("Friendly Editorial Cartoon")).toBeInTheDocument();

    await waitFor(() => {
      expect(setActiveStylePreset).toHaveBeenCalledWith("preset-1");
    });
  });
});
