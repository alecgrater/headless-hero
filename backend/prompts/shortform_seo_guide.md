# Short-Form SEO Metadata Guide

Generate platform-specific SEO metadata for short-form video content. Each platform has different rules, tone, and character limits.

## YouTube Shorts
- **Title**: ≤100 characters. Must contain the primary keyword near the start. Emotionally charged — use curiosity gaps, numbers, or bold claims. Must include "#Shorts" at the end.
- **Description**: 2–3 sentences summarizing the video. Include 3–5 relevant hashtags. Add a CTA ("Subscribe for more").
- **Tags**: 15 tags. Mix broad keywords (e.g., "science facts") with niche long-tail (e.g., "caffeine effects on brain"). Include "#Shorts".

## TikTok
- **Caption**: ≤150 characters. Hook-style opening that mirrors the video's first line. End with a question or CTA to drive comments. Use casual, conversational tone.
- **Hashtags**: 5–7 hashtags. Mix 2 trending/broad tags with 3–5 niche tags. No "#Shorts" — use TikTok-native tags like "#LearnOnTikTok", "#fyp".

## Instagram Reels
- **Caption**: 150–300 characters. Storytelling tone — slightly more polished than TikTok. Include a hook, a key takeaway, and a CTA.
- **Hashtags**: 10–15 hashtags formatted for first-comment placement. Mix: 3 broad, 5 mid-range, 5 niche. Include "#Reels".

## Additional Fields
- **thumbnail_text**: 5 words max, ALL CAPS, bold statement for thumbnail overlay
- **hook_preview_text**: The exact first sentence of narration (for on-screen display)

## Output Format
Return JSON:
```json
{
  "youtube_shorts": {"title": "...", "description": "...", "tags": [...]},
  "tiktok": {"caption": "...", "hashtags": [...]},
  "instagram_reels": {"caption": "...", "hashtags": [...]},
  "thumbnail_text": "...",
  "hook_preview_text": "..."
}
```

Only include platforms that the user has selected.
