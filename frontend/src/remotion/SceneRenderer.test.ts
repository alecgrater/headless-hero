import { describe, expect, it } from "vitest";

import { canApplyWholeSceneFx, isTitleCardScene } from "@remotion-src/scenes/SceneRenderer";
import type { SceneInput } from "@remotion-src/types";

describe("isTitleCardScene", () => {
  it("treats generated chapter-card scenes as title cards without a zoom target", () => {
    const scene = {
      id: "scene_001",
      narration: "Level one, the temporary.",
      duration_seconds: 3,
      is_title_card: true,
      image_path: "/static/projects/script/images/chapter_1.png",
      title_card_zoom_target: null,
      chapter_overlay: {
        level_number: 1,
        descriptor: "the temporary",
      },
      visual_mode: "full_frame",
    } satisfies SceneInput;

    expect(isTitleCardScene(scene)).toBe(true);
  });
});

describe("canApplyWholeSceneFx", () => {
  it("blocks whole-scene FX wrappers for renderer-owned layered boards", () => {
    expect(canApplyWholeSceneFx({ visual_mode: "comparison_board" })).toBe(false);
    expect(canApplyWholeSceneFx({ visual_mode: "popup_sequence" })).toBe(false);
  });

  it("keeps camera effects available for normal media-backed scenes", () => {
    expect(canApplyWholeSceneFx({ visual_mode: "full_frame" })).toBe(true);
    expect(canApplyWholeSceneFx({ visual_mode: "multi_frame" })).toBe(true);
    expect(canApplyWholeSceneFx({ visual_mode: "continuous" })).toBe(true);
  });
});
