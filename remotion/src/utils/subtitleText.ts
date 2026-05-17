const SUBTITLE_HYPHEN_PATTERN = /[\u002D\u2010-\u2015\u2212]+/g;

/**
 * Format text for on-screen subtitles only.
 * Script narration keeps hyphens so voice generation can interpret pacing.
 */
export function formatSubtitleText(text: string): string {
  return text.replace(SUBTITLE_HYPHEN_PATTERN, " ").replace(/\s+/g, " ").trim();
}
