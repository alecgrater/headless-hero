/**
 * Maps a frontend Scene to the Remotion SceneInput format.
 * Converts web-relative paths to full HTTP URLs via assetUrl().
 */
import { assetUrl } from "../api";
import type { Scene } from "../types/script";
import type { SceneInput } from "@remotion-src/types";

export function sceneToRemotionInput(scene: Scene): SceneInput {
  const duration =
    scene.audio_duration_seconds || scene.duration_estimate_seconds || 5;

  return {
    id: scene.id,
    narration: scene.narration,
    duration_seconds: duration,
    is_title_card: scene.is_title_card,
    image_path: scene.image_url ? assetUrl(scene.image_url) : null,
    frame_paths: scene.frame_urls?.map(assetUrl) ?? null,
    audio_path: scene.audio_url ? assetUrl(scene.audio_url) : null,
    title_card_zoom_target: scene.title_card_zoom_target ?? null,
    fx: scene.fx
      ? {
          zoom_punch: scene.fx.zoom_punch ?? null,
        }
      : null,
    visual_beat: scene.visual_beat,
    frame_directives: scene.frame_directives?.map((d) => ({
      prompt: d.prompt,
      source: d.source,
      transition: d.transition,
      reference_previous: d.reference_previous,
      search_query: d.search_query,
    })) ?? null,
    word_timestamps: scene.word_timestamps ?? null,
    frame_timings: scene.frame_timings ?? null,
    visual_in_seconds: scene.visual_in_seconds ?? 0,
    visual_out_seconds: scene.visual_out_seconds ?? 0,
  };
}
