import { describe, expect, it } from "vitest";

import type { Scene } from "../../types/script";
import { sceneVisualAssetsComplete } from "./assetCompletion";

const baseScene: Scene = {
  id: "scene_001",
  narration: "A scene.",
  visual_prompt: "A visual.",
  duration_estimate_seconds: 6,
  is_title_card: false,
  image_url: "",
  audio_url: "",
  audio_duration_seconds: 6,
  visual_beat: "static",
  frame_directives: [],
  contains_person: false,
  frame_urls: [],
  visual_mode: "full_frame",
  visual_layers: [],
  caption_text: "",
  caption_emphasis: "",
};

describe("sceneVisualAssetsComplete", () => {
  it("counts generated layer images as complete for renderer-owned visual modes", () => {
    expect(
      sceneVisualAssetsComplete({
        ...baseScene,
        visual_mode: "popup_sequence",
        visual_layers: [
          { id: "item_1", type: "image", asset_kind: "cutout", image_url: "/static/projects/script/popup/item_1.png" },
          { id: "item_2", type: "image", asset_kind: "cutout", image_url: "/static/projects/script/popup/item_2.png" },
        ],
      }),
    ).toBe(true);
  });

  it("does not count ungenerated renderer-owned layers as complete", () => {
    expect(
      sceneVisualAssetsComplete({
        ...baseScene,
        visual_mode: "comparison_board",
        visual_layers: [
          { id: "left", type: "image", asset_kind: "cutout", image_url: "/static/projects/script/comparison/left.png" },
          { id: "right", type: "image", asset_kind: "cutout" },
        ],
      }),
    ).toBe(false);
  });
});
