import { describe, expect, it } from "vitest";

import { testLabPresetSubtitle } from "./TestLabPage";
import type { TestLabPreset } from "../../types/testLab";

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
});
