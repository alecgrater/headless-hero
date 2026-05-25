import { formatSubtitleText } from "./subtitleText";
import type { WordTimestamp } from "../types";

export interface CaptionWord {
  text: string;
  emphasized: boolean;
}

const STOPWORDS = new Set([
  "a",
  "an",
  "and",
  "are",
  "as",
  "at",
  "but",
  "by",
  "for",
  "from",
  "in",
  "into",
  "is",
  "it",
  "of",
  "on",
  "or",
  "that",
  "the",
  "this",
  "to",
  "was",
  "were",
  "while",
  "with",
  "you",
  "your",
]);

export function normalizeCaptionToken(value: string): string {
  return formatSubtitleText(value)
    .replace(/\s+/g, "")
    .replace(/^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$/g, "");
}

export function captionWordsForDisplay({
  captionText,
  narration,
}: {
  captionText?: string | null;
  narration?: string | null;
}): string[] {
  const text = captionText?.trim() ? captionText : narration;
  return (text ?? "")
    .split(/\s+/)
    .map(normalizeCaptionToken)
    .filter((word) => word.length > 0);
}

function tokensForMatch(value: string): string[] {
  return captionWordsForDisplay({ captionText: value }).map((word) => word.toLowerCase());
}

function includesTokenRange(words: string[], phrase: string[]): boolean {
  if (phrase.length === 0 || phrase.length > words.length) return false;

  for (let i = 0; i <= words.length - phrase.length; i++) {
    const matches = phrase.every((word, offset) => words[i + offset] === word);
    if (matches) return true;
  }

  return false;
}

export function chooseCaptionEmphasis(
  captionText: string,
  captionEmphasis?: string | null,
): string {
  const displayWords = captionWordsForDisplay({ captionText });
  const captionTokens = displayWords.map((word) => word.toLowerCase());
  const explicitTokens = tokensForMatch(captionEmphasis ?? "");

  if (includesTokenRange(captionTokens, explicitTokens)) {
    return explicitTokens.join(" ");
  }

  const contentWords = displayWords.filter((word) => !STOPWORDS.has(word.toLowerCase()));
  return contentWords.slice(-2).join(" ");
}

export function splitCaptionWords(
  captionText: string,
  captionEmphasis?: string | null,
): CaptionWord[] {
  const words = captionWordsForDisplay({ captionText });
  const emphasis = chooseCaptionEmphasis(captionText, captionEmphasis);
  const emphasisTokens = tokensForMatch(emphasis);
  const wordTokens = words.map((word) => word.toLowerCase());
  let emphasisStart = -1;

  if (emphasisTokens.length > 0) {
    for (let i = 0; i <= wordTokens.length - emphasisTokens.length; i++) {
      const matches = emphasisTokens.every((word, offset) => wordTokens[i + offset] === word);
      if (matches) {
        emphasisStart = i;
        break;
      }
    }
  }

  return words.map((word, index) => ({
    text: word,
    emphasized:
      emphasisStart >= 0 &&
      index >= emphasisStart &&
      index < emphasisStart + emphasisTokens.length,
  }));
}

function timestampToken(word: WordTimestamp): string {
  return normalizeCaptionToken(word.word).toLowerCase();
}

function matchCaptionFromIndex(
  timestamps: WordTimestamp[],
  captionTokens: string[],
  startIndex: number,
): WordTimestamp[] | null {
  const matched: WordTimestamp[] = [];
  let timestampIndex = startIndex;

  for (const captionToken of captionTokens) {
    let spokenToken = "";
    let firstTimestamp: WordTimestamp | null = null;

    while (timestampIndex < timestamps.length && spokenToken.length < captionToken.length) {
      const timestamp = timestamps[timestampIndex];
      const token = timestampToken(timestamp);
      timestampIndex++;
      if (!token) continue;

      firstTimestamp ??= timestamp;
      spokenToken += token;
    }

    if (!firstTimestamp || spokenToken !== captionToken) {
      return null;
    }

    matched.push(firstTimestamp);
  }

  return matched;
}

export function findCaptionWordTimestamps(
  timestamps: WordTimestamp[],
  captionText: string,
  displayWordCount: number,
): WordTimestamp[] {
  if (timestamps.length === 0 || displayWordCount === 0) return [];

  const captionTokens = captionWordsForDisplay({ captionText })
    .slice(0, displayWordCount)
    .map((word) => word.toLowerCase());
  if (captionTokens.length === 0) return [];

  for (let i = timestamps.length - 1; i >= 0; i--) {
    const matched = matchCaptionFromIndex(timestamps, captionTokens, i);
    if (matched) return matched;
  }

  return timestamps.slice(-displayWordCount);
}
