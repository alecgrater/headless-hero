import type { WordTimestamp } from "../../../types/script";
export type { WordTimestamp };

/** Props common to all lane sub-components. */
export interface LaneProps {
  /** Total scene duration in seconds. */
  durationSeconds: number;
  /** Current playhead position in seconds. */
  playheadSeconds: number;
  /** Container width in pixels (for time↔px conversion). */
  widthPx: number;
  /** Whether this lane is the currently selected lane. */
  isSelected: boolean;
  /** Called when the lane background is clicked (to select it). */
  onSelect: () => void;
}

/** State for an in-progress drag operation. */
export interface MarkerDragState {
  markerId: string;
  startX: number;
  startSeconds: number;
}

/** Convert seconds to pixel offset within the lane. */
export function secondsToPx(seconds: number, durationSeconds: number, widthPx: number): number {
  if (durationSeconds <= 0) return 0;
  return (seconds / durationSeconds) * widthPx;
}

/** Convert pixel offset to seconds within the lane. */
export function pxToSeconds(px: number, durationSeconds: number, widthPx: number): number {
  if (widthPx <= 0) return 0;
  return (px / widthPx) * durationSeconds;
}

/** Clamp value between min and max. */
export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/**
 * Snap a time (seconds) to the nearest word boundary if within threshold.
 * Returns the snapped time, or the original if no word boundary is close enough.
 */
export function snapToWordBoundary(
  seconds: number,
  wordTimestamps: WordTimestamp[] | undefined | null,
  thresholdSeconds: number = 0.1,
): number {
  if (!wordTimestamps || wordTimestamps.length === 0) return seconds;

  let closest = seconds;
  let closestDist = Infinity;

  for (const wt of wordTimestamps) {
    // Snap to word start
    const startSec = wt.start_ms / 1000;
    const dStart = Math.abs(seconds - startSec);
    if (dStart < closestDist) {
      closestDist = dStart;
      closest = startSec;
    }
    // Snap to word end
    const endSec = wt.end_ms / 1000;
    const dEnd = Math.abs(seconds - endSec);
    if (dEnd < closestDist) {
      closestDist = dEnd;
      closest = endSec;
    }
  }

  return closestDist <= thresholdSeconds ? closest : seconds;
}

/** FPS constant (matches Remotion and backend). */
export const FPS = 30;

/** Nudge amount in seconds for 1 frame. */
export const FRAME_SECONDS = 1 / FPS;

/**
 * Look up a word's start time in word_timestamps.
 * Returns seconds, or null if not found.
 */
export function wordToSeconds(
  word: string,
  wordTimestamps: WordTimestamp[] | undefined | null,
): number | null {
  if (!wordTimestamps || wordTimestamps.length === 0 || !word) return null;
  const lower = word.toLowerCase();
  const match = wordTimestamps.find(
    (wt) => wt.word.toLowerCase().replace(/[^a-z0-9]/g, "") === lower.replace(/[^a-z0-9]/g, ""),
  );
  return match ? match.start_ms / 1000 : null;
}

/**
 * Find the nearest word to a given time in seconds.
 * Returns the word text, or null if no timestamps.
 */
export function secondsToWord(
  seconds: number,
  wordTimestamps: WordTimestamp[] | undefined | null,
): string | null {
  if (!wordTimestamps || wordTimestamps.length === 0) return null;
  let closest: WordTimestamp | null = null;
  let closestDist = Infinity;
  for (const wt of wordTimestamps) {
    const d = Math.abs(wt.start_ms / 1000 - seconds);
    if (d < closestDist) {
      closestDist = d;
      closest = wt;
    }
  }
  return closest ? closest.word : null;
}

/**
 * Estimate word position when no word_timestamps are available.
 * Linearly estimates based on word index in narration text.
 */
export function estimateWordPosition(
  word: string,
  narration: string,
  durationSeconds: number,
): number {
  const words = narration.split(/\s+/);
  const lower = word.toLowerCase().replace(/[^a-z0-9]/g, "");
  const idx = words.findIndex(
    (w) => w.toLowerCase().replace(/[^a-z0-9]/g, "") === lower,
  );
  if (idx < 0 || words.length <= 1) return durationSeconds / 2;
  return (idx / (words.length - 1)) * durationSeconds;
}
