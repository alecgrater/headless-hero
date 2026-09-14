export type ProductionTask = "lf-seo" | "sf-thumbnails" | "sf-seo" | "sf-renders" | "thumbnails-combined" | "seo-combined" | "export-combined";

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

export const YOLO_PROGRESS_STEPS = YOLO_STAGES.map((stage) => stage.label);

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
