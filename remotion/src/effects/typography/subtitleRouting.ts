import type { Orientation, RoutedSubtitleStyle, SceneInput, SubtitleSettingsConfig, SubtitleStyle, WordTimestamp } from "../../types";

export const SUBTITLE_ROUTER_VERSION = "standard-subtitle-router-v1";

export type ResolvedSubtitleStyle = Exclude<SubtitleStyle, "auto">;
export type SubtitleRoutingSettings = Pick<SubtitleSettingsConfig, "enabled_styles"> | {
  enabledStyles?: RoutedSubtitleStyle[];
};

export interface SubtitlePhrase {
  words: WordTimestamp[];
  startFrame: number;
  endFrame: number;
}

const MAX_WORDS_PER_LINE = 8;
const PAUSE_THRESHOLD_MS = 300;
const FAST_WORD_MS = 190;
const DENSE_WORD_COUNT = 6;

const BURST_CUES = [
  "but",
  "then",
  "suddenly",
  "the catch",
  "the real reason",
  "finally",
  "snaps",
  "reveals",
  "turns out",
];

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
  if (!settings) return ["clean", "kinetic", "burst"];
  if ("enabled_styles" in settings) return settings.enabled_styles;
  return settings.enabledStyles ?? ["clean", "kinetic", "burst"];
}

function resolveDisabledFallback(
  desired: RoutedSubtitleStyle,
  enabledStyles: RoutedSubtitleStyle[],
): ResolvedSubtitleStyle {
  if (enabledStyles.length === 0) return "none";
  if (enabledStyles.length === 1) return enabledStyles[0];
  if (enabledStyles.includes(desired)) return desired;

  if (desired === "burst") {
    if (enabledStyles.includes("kinetic")) return "kinetic";
    if (enabledStyles.includes("clean")) return "clean";
  }

  if (desired === "kinetic") {
    if (enabledStyles.includes("clean")) return "clean";
    if (enabledStyles.includes("burst")) return "burst";
  }

  return enabledStyles[0];
}

export function resolveSubtitleStyle(
  scene: SceneInput,
  orientation: Orientation,
  settings?: SubtitleRoutingSettings | null,
): ResolvedSubtitleStyle {
  if (scene.is_title_card || scene.visual_mode === "captions" || scene.visual_beat === "aha_subtitle") {
    return "none";
  }
  const enabledStyles = enabledStylesFromSettings(settings);
  if (scene.subtitle_style && scene.subtitle_style !== "auto") {
    if (scene.subtitle_style === "none") return "none";
    return resolveDisabledFallback(scene.subtitle_style, enabledStyles);
  }

  const timestamps = scene.word_timestamps ?? [];
  const narration = scene.narration.toLowerCase();
  const wordCount = timestamps.length || narration.split(/\s+/).filter(Boolean).length;
  const durationMs = Math.max(1, scene.duration_seconds * 1000);
  const averageWordMs = timestamps.length >= 2
    ? (timestamps[timestamps.length - 1].end_ms - timestamps[0].start_ms) / timestamps.length
    : durationMs / Math.max(1, wordCount);
  const hasBurstCue = BURST_CUES.some((cue) => narration.includes(cue));
  let desired: RoutedSubtitleStyle = "clean";
  if (wordCount >= DENSE_WORD_COUNT && averageWordMs <= FAST_WORD_MS) {
    desired = "kinetic";
    return resolveDisabledFallback(desired, enabledStyles);
  }

  const isShortPayoff = wordCount <= 4 && /[!?]$/.test(scene.narration.trim());

  if (hasBurstCue || isShortPayoff) {
    desired = "burst";
    return resolveDisabledFallback(desired, enabledStyles);
  }

  if (orientation === "vertical" && wordCount <= 5 && averageWordMs <= 230) {
    desired = "kinetic";
    return resolveDisabledFallback(desired, enabledStyles);
  }

  return resolveDisabledFallback(desired, enabledStyles);
}
