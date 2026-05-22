export type ProductionTask = "lf-seo" | "sf-thumbnails" | "sf-seo" | "sf-renders" | "thumbnails-combined" | "seo-combined" | "export-combined";

export const YOLO_PROGRESS_STEPS = [
  "Title Cards",
  "Generate Audio",
  "Generate Images",
  "Generate FX",
  "Add Eli",
  "Generate LF SEO",
  "Generate SF Thumbnails",
  "Generate SF SEO",
  "Render SF Videos",
  "Export Bundle",
] as const;

export function clampProgress(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

export function compactProgressText(progress: number | null) {
  if (progress == null) return "";
  return `${Math.round(progress * 100)}%`;
}
