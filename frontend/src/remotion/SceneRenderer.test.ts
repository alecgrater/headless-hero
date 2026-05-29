import { describe, expect, it } from "vitest";

import { isTitleCardScene } from "@remotion-src/scenes/SceneRenderer";
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
