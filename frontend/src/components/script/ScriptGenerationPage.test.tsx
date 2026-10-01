import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ScriptGenerationPage from "./ScriptGenerationPage";
import type { ScriptContent } from "../../types/script";

const ratedScript: ScriptContent = {
  title: "Life as a Castle Guard",
  intro_hook: "You think the gate is the boring part. It is not.",
  outro_cta: "",
  format_id: "life-as-a",
  script_rating: {
    overall: 8.2,
    model: "claude-sonnet-5-5",
    version: "2026-09-30",
    scores: { flow: 8, clarity: 8, human_sounding: 7, continuity: 9, format_fit: 8 },
    problems: [
      {
        category: "ai_tells",
        scene: "scene-1",
        quote: "The job starts before sunrise.",
        problem: "Flat opener.",
        severity: "minor",
      },
    ],
    worst_problem: "A flat opener.",
  },
  segments: [
    {
      name: "The First Watch",
      scenes: [
        {
          id: "scene-1",
          narration: "The job starts before sunrise.",
          visual_prompt: "A sleepy castle gate at dawn.",
          duration_estimate_seconds: 6,
          is_title_card: false,
        },
      ],
    },
  ],
};

vi.mock("../../api", () => ({
  default: {
    get: vi.fn().mockResolvedValue({
      ok: true,
      data: { SCRIPT_LLM_PROVIDER: { masked: "openai" }, SCRIPT_MODEL: { masked: "gpt-5.6-terra" } },
    }),
  },
  assetUrl: (path: string) => path,
  getFormats: vi.fn().mockResolvedValue([
    { id: "life-as-a", label: "Life As A", supports_cold_open: false, level_label: "level" },
  ]),
  getProjectConfig: vi.fn().mockResolvedValue({
    ok: true,
    data: { eli_enabled: true, main_character_reference_url: "" },
  }),
}));

vi.mock("./useScriptGeneration", () => ({
  default: () => ({
    script: ratedScript,
    scriptId: "script-1",
    loading: false,
    error: null,
    selectedModel: "gpt-5.6-terra",
    segmented: true,
    generationStarted: true,
    settingsLoaded: true,
    estimatedSeconds: null,
    elapsedSeconds: null,
    genSegments: null,
    genCompletedSegments: [],
    phase: "idle",
    coldOpenResult: null,
    setScript: vi.fn(),
    handleGenerate: vi.fn(),
    handleCancelGeneration: vi.fn(),
    handleModelChange: vi.fn(),
    handleColdOpenSelect: vi.fn(),
    setSegmented: vi.fn(),
  }),
}));

vi.mock("./useSceneEditing", () => ({
  default: () => ({
    editingKey: null,
    editNarration: "",
    editHookText: "",
    editedScenes: new Set<string>(),
    refiningScene: null,
    saving: false,
    setEditNarration: vi.fn(),
    setEditHookText: vi.fn(),
    startEditScene: vi.fn(),
    cancelEdit: vi.fn(),
    saveSceneEdit: vi.fn(),
    startEditIntro: vi.fn(),
    saveIntroEdit: vi.fn(),
    startEditOutro: vi.fn(),
    saveOutroEdit: vi.fn(),
    refineScene: vi.fn(),
  }),
}));

vi.mock("./useTitleCardGeneration", () => ({
  default: () => ({
    titleCardGenerating: false,
    titleCardGenerated: false,
    titleCardError: null,
    titleCardCompleted: [],
    titleCardTotal: 0,
    generateTitleCards: vi.fn(),
  }),
}));

describe("ScriptGenerationPage", () => {
  it("shows the script rating prominently and keeps thumbnail generation out of review", async () => {
    render(
      <ScriptGenerationPage
        brandId="brand-1"
        idea={{
          title: "Life as a Castle Guard",
          description: "A day at the gate.",
          format_id: "life-as-a",
          segments_est: 8,
          keywords: ["history"],
        }}
        onBack={vi.fn()}
        onContinue={vi.fn()}
      />,
    );

    expect(await screen.findByText("Script Rating")).toBeInTheDocument();
    expect(screen.getByText("8.2")).toBeInTheDocument();
    expect(screen.queryByText("Thumbnail & Title Slide")).not.toBeInTheDocument();
  });
});
