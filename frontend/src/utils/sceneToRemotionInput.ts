/**
 * Maps a frontend Scene to the Remotion SceneInput format.
 * Converts web-relative paths to full HTTP URLs via assetUrl().
 */
import { assetUrl } from "../api";
import type { Scene, ZoomPunchFX, WordTimestamp } from "../types/script";
import type { SceneInput } from "@remotion-src/types";

const FPS = 30;

/**
 * Resolve trigger_word → trigger_frame for the preview player.
 * Remotion still receives trigger_frame — this converts word-based FX.
 */
function resolveZoomPunchFrame(
  zp: ZoomPunchFX,
  wordTimestamps: WordTimestamp[] | undefined | null,
  durationSeconds: number,
): ZoomPunchFX {
  if (!zp.trigger_word) return zp;

  if (wordTimestamps && wordTimestamps.length > 0) {
    const lower = zp.trigger_word.toLowerCase().replace(/[^a-z0-9]/g, "");
    const match = wordTimestamps.find(
      (wt) => wt.word.toLowerCase().replace(/[^a-z0-9]/g, "") === lower,
    );
    if (match) {
      return { ...zp, trigger_frame: Math.round(match.start_ms / 1000 * FPS) };
    }
  }

  // Fallback: mid-scene
  return { ...zp, trigger_frame: Math.round(durationSeconds / 2 * FPS) };
}

export function sceneToRemotionInput(scene: Scene): SceneInput {
  const duration =
    scene.audio_duration_seconds || scene.duration_estimate_seconds || 5;

  // Resolve zoom punch trigger_word → trigger_frame for Remotion
  const resolvedZoomPunch = scene.fx?.zoom_punch
    ? resolveZoomPunchFrame(scene.fx.zoom_punch, scene.word_timestamps, duration)
    : null;

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
          zoom_punch: resolvedZoomPunch,
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
