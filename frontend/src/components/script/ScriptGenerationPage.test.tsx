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
    model: "gpt-5-mini",
    version: "2026-05-25",
    viewer_retention: {
      average: 8.0,
      explanation: "Strong opening tension.",
      criteria: {
        hook_strength: { score: 8 },
        curiosity_gaps: { score: 8 },
        pacing_variance: { score: 8 },
      },
    },
    narrative_quality: {
      average: 8.0,
      explanation: "Clear progression.",
      criteria: {
        coherence: { score: 8 },
        throughline: { score: 8 },
      },
    },
    script_craft: {
      average: 8.3,
      explanation: "Specific and economical.",
      criteria: {
        sentence_variety: { score: 8 },
        specificity: { score: 9 },
        redundancy: { score: 8 },
        word_economy: { score: 8 },
      },
    },
    audience_fit: {
      average: 8.0,
      explanation: "Easy to follow.",
      criteria: {
        assumed_knowledge_level: { score: 8 },
        relatability: { score: 8 },
        tone_consistency: { score: 8 },
        emotional_range: { score: 8 },
      },
    },
    seo_alignment: {
      average: 8.0,
      explanation: "Title and hook align.",
      criteria: {
        title_hook_match: { score: 8 },
        search_intent_match: { score: 8 },
        rewatch_value: { score: 8 },
      },
    },
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
      data: { SCRIPT_LLM_PROVIDER: { masked: "openai" }, SCRIPT_MODEL: { masked: "gpt-5-mini" } },
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
    selectedModel: "gpt-5-mini",
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
