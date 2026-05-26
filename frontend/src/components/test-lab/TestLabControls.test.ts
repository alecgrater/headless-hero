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
  media_source: "ai",
  caption_text: "",
  caption_emphasis: "",
  duration_estimate_seconds: 7,
};

const defaults: TestLabScenes["visual_treatment_defaults"] = {
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
      visual_mode: "captions",
      media_source: "ai",
      visual_treatment: "full_frame",
      narration: "The tiny crack spreads across the wall until the whole room feels like it is holding its breath.",
      visual_prompt: "[CLOSE-UP] A cracked cartoon wall.",
      caption_text: undefined,
      caption_emphasis: undefined,
    };

    const next = settingsWithVisualTreatmentDefaults(settings, preset, "captions", defaults);

    expect(next.narration).toBe(settings.narration);
    expect(next.caption_text).toBeUndefined();
    expect(next.caption_emphasis).toBeUndefined();
  });
});
