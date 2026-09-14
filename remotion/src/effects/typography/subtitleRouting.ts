import type { Orientation, RoutedSubtitleStyle, SceneInput, SubtitleSettingsConfig, SubtitleStyle, WordTimestamp } from "../../types";

export const SUBTITLE_ROUTER_VERSION = "standard-subtitle-router-v2";

export type ResolvedSubtitleStyle = Exclude<SubtitleStyle, "auto">;
export type SubtitleRoutingSettings = Pick<SubtitleSettingsConfig, "enabled_styles"> & {
  kinetic_max_words?: number;
  kinetic_max_span_seconds?: number;
} | {
  enabledStyles?: RoutedSubtitleStyle[];
  kineticMaxWords?: number;
  kineticMaxSpanSeconds?: number;
};

export interface SubtitlePhrase {
  words: WordTimestamp[];
  startFrame: number;
  endFrame: number;
}

const MAX_WORDS_PER_LINE = 8;
const PAUSE_THRESHOLD_MS = 300;

/**
 * Kinetic routing defaults. The backend owns these and ships them in `subtitle_settings`
 * (see remotion_render.KINETIC_MAX_WORDS / KINETIC_MAX_SPAN_SECONDS); these are the
 * fallback for props written before the thresholds were transported.
 *
 * Pace is deliberately NOT a term. Measured narration runs 318ms/word at p10 and short
 * scenes are systematically *slower* per word, so any per-word pace gate either never
 * fires or fires on everything.
 */
export const DEFAULT_KINETIC_MAX_WORDS = 6;
export const DEFAULT_KINETIC_MAX_SPAN_SECONDS = 3.0;

export function groupIntoSubtitlePhrases(timestamps: WordTimestamp[], fps: number): SubtitlePhrase[] {
  if (timestamps.length === 0) return [];

  const phrases: SubtitlePhrase[] = [];
  let currentWords: WordTimestamp[] = [];

  for (let i = 0; i < timestamps.length; i++) {
    const w = timestamps[i];
    currentWords.push(w);

    const isLast = i === timestamps.length - 1;
    const hitMax = currentWords.length >= MAX_WORDS_PER_LINE;
    const endsWithPunctuation = /[.!?]$/.test(w.word.trim());
    const longPauseAfter = !isLast && timestamps[i + 1].start_ms - w.end_ms > PAUSE_THRESHOLD_MS;

    if (isLast || hitMax || endsWithPunctuation || longPauseAfter) {
      const startMs = currentWords[0].start_ms;
      const endMs = currentWords[currentWords.length - 1].end_ms;
      phrases.push({
        words: [...currentWords],
        startFrame: Math.round((startMs / 1000) * fps),
        endFrame: Math.round((endMs / 1000) * fps),
      });
      currentWords = [];
    }
  }

  return phrases;
}

export function isWordActive(word: WordTimestamp, frame: number, fps: number): boolean {
  const wordStartFrame = Math.round((word.start_ms / 1000) * fps);
  const wordEndFrame = Math.round((word.end_ms / 1000) * fps);
  return frame >= wordStartFrame && frame <= wordEndFrame;
}

export function wordProgress(word: WordTimestamp, frame: number, fps: number): number {
  const start = Math.round((word.start_ms / 1000) * fps);
  const end = Math.max(start + 1, Math.round((word.end_ms / 1000) * fps));
  return Math.min(1, Math.max(0, (frame - start) / (end - start)));
}

function enabledStylesFromSettings(settings?: SubtitleRoutingSettings | null): RoutedSubtitleStyle[] {
  if (!settings) return ["clean", "kinetic"];
  if ("enabled_styles" in settings) return settings.enabled_styles;
  return settings.enabledStyles ?? ["clean", "kinetic"];
}

function kineticThresholds(settings?: SubtitleRoutingSettings | null): { maxWords: number; maxSpanSeconds: number } {
  const maxWords = settings && "enabled_styles" in settings
    ? settings.kinetic_max_words
    : settings?.kineticMaxWords;
  const maxSpanSeconds = settings && "enabled_styles" in settings
    ? settings.kinetic_max_span_seconds
    : settings?.kineticMaxSpanSeconds;
  return {
    maxWords: typeof maxWords === "number" ? maxWords : DEFAULT_KINETIC_MAX_WORDS,
    maxSpanSeconds: typeof maxSpanSeconds === "number" ? maxSpanSeconds : DEFAULT_KINETIC_MAX_SPAN_SECONDS,
  };
}

/** "clean" is the floor of the catalogue — anything unavailable falls back to it. */
function resolveDisabledFallback(
  desired: RoutedSubtitleStyle,
  enabledStyles: RoutedSubtitleStyle[],
): ResolvedSubtitleStyle {
  if (enabledStyles.length === 0) return "none";
  if (enabledStyles.includes(desired)) return desired;
  if (enabledStyles.includes("clean")) return "clean";
  return enabledStyles[0];
}

export function spokenSpanSeconds(timestamps: WordTimestamp[]): number {
  if (timestamps.length === 0) return 0;
  return Math.max(0, (timestamps[timestamps.length - 1].end_ms - timestamps[0].start_ms) / 1000);
}

export function resolveSubtitleStyle(
  scene: SceneInput,
  _orientation: Orientation,
  settings?: SubtitleRoutingSettings | null,
): ResolvedSubtitleStyle {
  if (scene.is_title_card || scene.visual_mode === "captions" || scene.visual_mode === "stat_card" || scene.visual_beat === "aha_subtitle") {
    return "none";
  }
  const enabledStyles = enabledStylesFromSettings(settings);
  if (scene.subtitle_style && scene.subtitle_style !== "auto") {
    if (scene.subtitle_style === "none") return "none";
    return resolveDisabledFallback(scene.subtitle_style, enabledStyles);
  }

  const timestamps = scene.word_timestamps ?? [];
  if (timestamps.length === 0) return resolveDisabledFallback("clean", enabledStyles);

  // Kinetic is the short-punch-beat exception: few words, delivered in a short span.
  // Everything else is clean. Orientation is not a term — a punch beat is a punch beat
  // in either aspect ratio.
  const { maxWords, maxSpanSeconds } = kineticThresholds(settings);
  const isPunchBeat = timestamps.length <= maxWords && spokenSpanSeconds(timestamps) <= maxSpanSeconds;
  return resolveDisabledFallback(isPunchBeat ? "kinetic" : "clean", enabledStyles);
}
