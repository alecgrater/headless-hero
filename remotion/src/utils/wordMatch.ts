/**
 * Word boundary algorithm for aha_subtitle scenes.
 * Splits word_timestamps into lead-in words (narrated but not in subtitle)
 * and subtitle words (matching the subtitle text), using reverse suffix matching.
 */
import type { WordTimestamp } from "../types";

export interface WordBoundary {
  leadInWords: WordTimestamp[];
  subtitleWords: WordTimestamp[];
  leadInEndMs: number;
  subtitleStartMs: number;
}

/** Strip leading/trailing punctuation and lowercase for comparison. */
function normalize(word: string): string {
  return word.replace(/^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$/g, "").toLowerCase();
}

/**
 * Reverse suffix match: the subtitle text is a suffix of the narration.
 * Walk backwards from the end of both arrays matching normalized words.
 * Returns the split index in timestamps where subtitle words begin.
 */
function reverseSuffixMatch(
  timestamps: WordTimestamp[],
  subtitleWords: string[],
): number | null {
  let ti = timestamps.length - 1;
  let si = subtitleWords.length - 1;

  while (si >= 0 && ti >= 0) {
    if (normalize(timestamps[ti].word) === normalize(subtitleWords[si])) {
      si--;
      ti--;
    } else {
      // Mismatch — reverse suffix assumption broken
      return null;
    }
  }

  // If we matched all subtitle words, split point is ti + 1
  if (si < 0) {
    return ti + 1;
  }
  return null;
}

/**
 * Forward greedy scan fallback: find first occurrence of subtitle words
 * as a contiguous subsequence within timestamps.
 */
function forwardGreedyMatch(
  timestamps: WordTimestamp[],
  subtitleWords: string[],
): number | null {
  if (subtitleWords.length === 0) return timestamps.length;

  for (let start = 0; start <= timestamps.length - subtitleWords.length; start++) {
    let matched = true;
    for (let j = 0; j < subtitleWords.length; j++) {
      if (normalize(timestamps[start + j].word) !== normalize(subtitleWords[j])) {
        matched = false;
        break;
      }
    }
    if (matched) return start;
  }
  return null;
}

/**
 * Split word_timestamps into lead-in and subtitle portions.
 *
 * Strategy:
 * 1. Reverse suffix match (subtitle is a suffix of narration)
 * 2. Forward greedy scan (fallback)
 * 3. Treat all as subtitle words (final fallback)
 */
export function findWordBoundary(
  timestamps: WordTimestamp[],
  subtitleText: string,
): WordBoundary {
  if (!timestamps.length) {
    return {
      leadInWords: [],
      subtitleWords: [],
      leadInEndMs: 0,
      subtitleStartMs: 0,
    };
  }

  // Tokenize subtitle text into words
  const subWords = subtitleText.split(/\s+/).filter((w) => w.length > 0);

  if (subWords.length === 0) {
    // No subtitle text — all words are lead-in
    return {
      leadInWords: timestamps,
      subtitleWords: [],
      leadInEndMs: timestamps[timestamps.length - 1].end_ms,
      subtitleStartMs: timestamps[timestamps.length - 1].end_ms,
    };
  }

  // Try reverse suffix match first, then forward greedy, then fallback to all-subtitle
  let splitIndex =
    reverseSuffixMatch(timestamps, subWords) ??
    forwardGreedyMatch(timestamps, subWords) ??
    0;

  const leadInWords = timestamps.slice(0, splitIndex);
  const subtitleWords = timestamps.slice(splitIndex);

  return {
    leadInWords,
    subtitleWords,
    leadInEndMs:
      leadInWords.length > 0
        ? leadInWords[leadInWords.length - 1].end_ms
        : 0,
    subtitleStartMs:
      subtitleWords.length > 0 ? subtitleWords[0].start_ms : 0,
  };
}
