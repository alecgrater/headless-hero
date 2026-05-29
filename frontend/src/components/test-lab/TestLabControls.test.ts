import { describe, expect, it } from "vitest";

import { settingsWithVisualTreatmentDefaults } from "./TestLabControls";
import type { TestLabPreset, TestLabScenes, TestLabSettings } from "../../types/testLab";

const preset: TestLabPreset = {
  id: "coffee-brain",
  title: "Coffee Brain",
  description: "Preset",
  format_id: "youtube-listicle",
  segment_name: "Segment",
  narration: "Default narration.",
  visual_prompt: "Default prompt.",
  background_color: "#111111",
  visual_mode: "full_frame",
  caption_text: "",
  caption_emphasis: "",
  duration_estimate_seconds: 7,
  main_character: null,
};

const defaults: TestLabScenes["visual_treatment_defaults"] = {
  multi_frame: {
    narration: "First the warning signs were tiny, then they were everywhere.",
    visual_prompt: "[CONTRAST] Escalating warning signs.",
  },
  captions: {
    narration: "Spending big in one area can hide how far behind you are in another.",
    visual_prompt: "A receipt beside overdue bills.",
    caption_text: "Spending big while falling behind",
    caption_emphasis: "falling behind",
  },
};

describe("settingsWithVisualTreatmentDefaults", () => {
  it("does not inject canned caption text when switching custom narration to captions", () => {
    const settings: TestLabSettings = {
      stages: {
        character: false,
        audio: true,
        visual: true,
        treatment_assets: false,
        fx: true,
        eli: false,
        render: true,
      },
      eli_enabled: false,
      style_preset_enabled: true,
      visual_mode: "captions",
      visual_layers: [],
      narration: "The tiny crack spreads across the wall until the whole room feels like it is holding its breath.",
      visual_prompt: "[CLOSE-UP] A cracked cartoon wall.",
      caption_text: undefined,
      caption_emphasis: undefined,
      segment_timer_enabled: true,
      subtitle_highlight_enabled: true,
    };

    const next = settingsWithVisualTreatmentDefaults(settings, preset, "captions", defaults);

    expect(next.narration).toBe(settings.narration);
    expect(next.caption_text).toBeUndefined();
    expect(next.caption_emphasis).toBeUndefined();
  });

  it("does not replace preset narration or visual prompt when switching visual modes", () => {
    const settings: TestLabSettings = {
      stages: {
        character: false,
        audio: true,
        visual: true,
        treatment_assets: false,
        fx: true,
        eli: false,
        render: true,
      },
      eli_enabled: false,
      style_preset_enabled: true,
      visual_mode: "multi_frame",
      visual_layers: [],
      narration: preset.narration,
      visual_prompt: preset.visual_prompt,
      segment_timer_enabled: true,
      subtitle_highlight_enabled: true,
    };

    const next = settingsWithVisualTreatmentDefaults(settings, preset, "multi_frame", defaults);

    expect(next.narration).toBe(preset.narration);
    expect(next.tts_narration).toBeUndefined();
    expect(next.visual_prompt).toBe(preset.visual_prompt);
  });
});
