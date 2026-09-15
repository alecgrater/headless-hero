import type { ScriptContent } from "../../types/script";
import { LAYERED_PREP_MODES, sceneVisualAssetsComplete } from "./assetCompletion";

export type ProductionTask = "lf-seo" | "sf-thumbnails" | "sf-seo" | "sf-renders" | "thumbnails-combined" | "seo-combined" | "export-combined";

/** Layered scenes whose cutout assets the analysis still has to specify. */
export function scenesNeedingVisualModePrep(content: ScriptContent): number {
  return content.segments
    .flatMap((seg) => seg.scenes)
    .filter(
      (sc) =>
        !sc.is_title_card &&
        LAYERED_PREP_MODES.has(sc.visual_mode ?? "full_frame") &&
        !sceneVisualAssetsComplete(sc),
    ).length;
}

/** True when the whole-script visual mode analysis still needs to run.
 *
 * Counting layered scenes that lack assets is not enough on its own: the
 * analysis also fills scene timing, confirms video eligibility, and can promote
 * scenes *into* the layered modes. A script that generated none of those modes
 * skipped the stage entirely and never got any of it, which made "Prepare
 * Visual Modes" a button the operator had to know to press first.
 */
export function needsVisualModePrep(content: ScriptContent): boolean {
  if (!content.visual_modes_prepared) return true;
  return scenesNeedingVisualModePrep(content) > 0;
}

/** Whether the analysis can run yet — it reads word-level voiceover timing. */
export function canPrepareVisualModes(content: ScriptContent): boolean {
  const nonTitle = content.segments.flatMap((seg) => seg.scenes).filter((sc) => !sc.is_title_card);
  if (nonTitle.length === 0) return false;
  return nonTitle.every(
    (sc) => (sc.audio_duration_seconds ?? 0) > 0 && (sc.word_timestamps?.length ?? 0) > 0,
  );
}

/** Scene ids whose missing voiceover timing is holding preparation back. */
export function blockingVisualModePrepSceneIds(content: ScriptContent): string[] {
  return content.segments
    .flatMap((seg) => seg.scenes)
    .filter(
      (sc) =>
        !sc.is_title_card &&
        ((sc.audio_duration_seconds ?? 0) <= 0 || (sc.word_timestamps?.length ?? 0) <= 0),
    )
    .map((sc) => sc.id);
}

/**
 * Every stage the YOLO pipeline can run, in execution order.
 *
 * `required` stages halt the run when they can't be completed: scene audio is
 * the timing source of truth for the whole render, so continuing without it
 * would burn an hour producing a broken video. Everything else is skippable —
 * the renderer backfills missing image-backed scenes (see
 * `remotion_render.ensure_renderable_scene_images`), and FX / Eli / SEO /
 * thumbnails degrade rather than break the output.
 */
export const YOLO_STAGES = [
  { key: "title-cards", label: "Title Cards", required: false },
  { key: "audio", label: "Generate Audio", required: true },
  { key: "visual-modes", label: "Prepare Visual Modes", required: false },
  { key: "images", label: "Generate Images", required: false },
  { key: "fx", label: "Generate FX", required: false },
  { key: "eli", label: "Add Eli", required: false },
  { key: "lf-thumbnail", label: "Long-Form Thumbnail", required: false },
  { key: "lf-seo", label: "Generate LF SEO", required: false },
  { key: "sf-thumbnails", label: "Generate SF Thumbnails", required: false },
  { key: "sf-seo", label: "Generate SF SEO", required: false },
  { key: "sf-renders", label: "Render SF Videos", required: false },
  { key: "export", label: "Export Bundle", required: false },
] as const;

export type YoloStageKey = (typeof YOLO_STAGES)[number]["key"];

export function clampProgress(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

export function compactProgressText(progress: number | null) {
  if (progress == null) return "";
  return `${Math.round(progress * 100)}%`;
}

/** Format a duration as `m:ss`, or `h:mm:ss` once it passes an hour. */
export function formatElapsed(seconds: number | null | undefined) {
  if (typeof seconds !== "number" || !Number.isFinite(seconds) || seconds < 0) return "—";
  const total = Math.floor(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}
