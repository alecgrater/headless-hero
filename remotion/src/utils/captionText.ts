import { formatSubtitleText } from "./subtitleText";

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
