import type { Scene } from "../../types/script";

const REQUIRED_LAYER_MODES = new Set(["popup_sequence", "blink", "comparison_board"]);

// Layered modes whose per-scene layer specs are filled by the post-voiceover
// visual-treatment analyzer (not script generation). Until those specs exist, batch
// image generation produces no assets for the scene, so sceneVisualAssetsComplete
// can never return true. "blink" is excluded — it's a renderer overlay on a normal
// full_frame image, not an analyzer-filled layered mode.
export const LAYERED_PREP_MODES = new Set(["popup_sequence", "comparison_board"]);

function generatedLayersComplete(scene: Scene): boolean {
  const layers = scene.visual_layers ?? [];
  return layers.length > 0 && layers.every((layer) => Boolean(layer.image_url));
}

export function sceneVisualAssetsComplete(scene: Scene): boolean {
  if (scene.image_url || scene.frame_urls?.length || scene.video_url) return true;
  const visualMode = scene.visual_mode ?? "full_frame";
  if (REQUIRED_LAYER_MODES.has(visualMode)) return generatedLayersComplete(scene);
  if (visualMode === "stat_card") {
    const layers = scene.visual_layers ?? [];
    return layers.length === 0 || generatedLayersComplete(scene);
  }
  return visualMode === "captions";
}
