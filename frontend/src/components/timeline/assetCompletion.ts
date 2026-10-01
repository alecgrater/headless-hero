import type { Scene } from "../../types/script";

const REQUIRED_LAYER_MODES = new Set(["popup_sequence", "blink", "comparison_board"]);
const IMAGE_BACKED_MODES = new Set(["full_frame", "multi_frame", "continuous"]);

// Scenes the images stage must produce assets for. An image-backed scene with no
// visual_prompt still counts (a captions/comparison scene demoted to full_frame has
// none): the batch endpoint backfills one from the narration. Skipping it left the
// render to generate it late, after the shorts, which then all re-rendered.
export function sceneNeedsImageGeneration(scene: Scene): boolean {
  if (scene.is_title_card) return false;
  if (scene.visual_prompt) return true;
  return IMAGE_BACKED_MODES.has(scene.visual_mode ?? "full_frame") && Boolean(scene.narration || scene.caption_text);
}

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
  // A failed generation leaves an "Image generation failed" placeholder; it must
  // read as missing so YOLO and "Generate missing" retry it instead of shipping it.
  if (scene.visual_source_metadata?.source_type === "placeholder") return false;
  if (scene.image_url || scene.frame_urls?.length || scene.video_url) return true;
  const visualMode = scene.visual_mode ?? "full_frame";
  if (REQUIRED_LAYER_MODES.has(visualMode)) return generatedLayersComplete(scene);
  if (visualMode === "stat_card") {
    const layers = scene.visual_layers ?? [];
    return layers.length === 0 || generatedLayersComplete(scene);
  }
  return visualMode === "captions";
}
