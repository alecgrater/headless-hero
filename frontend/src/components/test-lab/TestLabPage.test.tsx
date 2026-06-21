import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import TestLabPage, { testLabPresetSubtitle } from "./TestLabPage";
import type { TestLabPreset } from "../../types/testLab";

vi.mock("../../api", () => ({
  default: {
    get: vi.fn().mockResolvedValue({ ok: true, data: { runs: [] } }),
    post: vi.fn(),
  },
  getTestLabPresets: vi.fn().mockResolvedValue({
    presets: [],
    default_main_character: null,
    voice_summary: undefined,
    subtitle_summary: undefined,
    visual_treatment_defaults: {},
  }),
  getTestLabRun: vi.fn(),
  getTestLabRuns: vi.fn().mockResolvedValue([]),
  startTestLabRun: vi.fn(),
  assetUrl: (path: string) => path,
  analyzeBlinkDebugAsset: vi.fn(),
  bumpAssetVersion: vi.fn(),
  createBlinkFixtureAsset: vi.fn(),
  getBlinkDebugAssets: vi.fn().mockResolvedValue([]),
  getBlinkAuditReports: vi.fn().mockResolvedValue([]),
  renderBlinkFixturePreview: vi.fn(),
  runBlinkAudit: vi.fn(),
  runTestLabSmokeTest: vi.fn(),
}));

describe("testLabPresetSubtitle", () => {
  it("uses the description for blank presets with no narration", () => {
    const preset: TestLabPreset = {
      id: "blank",
      title: "Blank",
      description: "Write your own test script",
      format_id: "youtube-listicle",
      segment_name: "Custom scene",
      narration: "",
      visual_prompt: "",
      background_color: "#111111",
      visual_mode: "full_frame",
      caption_text: "",
      caption_emphasis: "",
      duration_estimate_seconds: 7,
      main_character: null,
    };

    expect(testLabPresetSubtitle(preset)).toBe("Write your own test script");
  });

  it("labels the blink tab without debug wording", async () => {
    render(<TestLabPage />);

    expect(await screen.findByRole("button", { name: "Blink" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Blink Debug" })).not.toBeInTheDocument();
  });

  it("shows the smoke test tab next to the focused diagnostics", async () => {
    render(<TestLabPage />);

    expect(await screen.findByRole("button", { name: "Smoke Test" })).toBeInTheDocument();
  });

  it("shows the Blink Audit tab", async () => {
    render(<TestLabPage />);

    expect(await screen.findByRole("button", { name: "Blink Audit" })).toBeInTheDocument();
  });
});
