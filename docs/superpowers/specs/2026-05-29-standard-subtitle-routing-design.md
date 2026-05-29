# Standard Subtitle Routing Design

## Summary

Standard subtitles should feel more like modern short-form creator subtitles without turning every scene into the same visual effect. The app will support scene-level subtitle treatments that can vary across a video:

- `clean`: readable phrase subtitles with polished active-word emphasis.
- `kinetic`: chunky per-word/card-like motion for fast or list-like narration.
- `burst`: one larger payoff phrase moment for reveal or impact beats.
- `none`: no standard subtitle overlay.
- `auto`: deterministic renderer-side routing to one of the display treatments.

The first implementation should avoid an additional LLM call. Routing can be derived from scene data, narration shape, word timings, and existing visual-mode exclusions.

## Goals

- Make standard subtitles feel more contemporary and retention-oriented.
- Vary subtitle presentation by scene so the video has rhythm instead of one global style.
- Preserve readability, especially for vertical shorts where subtitles must stay above app chrome.
- Keep `visual_mode="captions"` separate: caption scenes own their in-scene text and continue suppressing standard subtitles.
- Allow future manual per-scene overrides without requiring them for v1.

## Non-Goals

- Do not add a new post-processing LLM call solely for subtitle style routing.
- Do not merge standard subtitles with `captions` visual mode.
- Do not make generated scene images contain readable subtitle text.
- Do not add broad script-generation prompt changes for v1 unless needed to persist an optional field safely.

## Data Model

Add an optional scene-level field:

```ts
subtitle_style?: "auto" | "clean" | "kinetic" | "burst" | "none";
```

Equivalent backend typing should accept the same values. Missing values are treated as `auto` for backward compatibility.

`none` is an explicit override for suppressing standard subtitles on a normal scene. Existing renderer-owned suppressions still win for title cards, legacy `aha_subtitle`, and `visual_mode="captions"`.

## Routing Behavior

When `subtitle_style` is missing or `auto`, the Remotion renderer chooses a display treatment deterministically:

- Use `clean` for longer explanatory narration, slower cadence, and ordinary phrases.
- Use `kinetic` for dense word timing, fast speech, short words, lists, or quick contrast beats.
- Use `burst` for short payoff scenes, strong punctuation, or cue words such as "but", "then", "suddenly", "the catch", "the real reason", "finally", or similar reveal language.
- Use `none` only through explicit override or existing scene suppressions.

The router should favor `clean` when uncertain. Subtitle novelty should support comprehension, not fight it.

The router must receive enough scene metadata to make that decision. It can accept the full `SceneInput`, or an explicit derived input object containing at least `narration`, `duration_seconds`, `visual_mode`, `visual_beat`, `is_title_card`, `word_timestamps`, `subtitle_style`, and `orientation`. Do not leave `SubtitleOverlay` limited to only `wordTimestamps`, `highlightEnabled`, and `orientation` if the auto router depends on narration or scene shape.

## Renderer Design

Keep the existing phrase grouping and `formatSubtitleText` path as shared infrastructure. Refactor the current `SubtitleOverlay` into a small router plus treatment renderers:

- `SubtitleOverlay`: validates timing, applies suppression rules, resolves `auto`, and delegates.
- `CleanSubtitleOverlay`: current behavior upgraded with stronger active-word scale/glow and cleaner spacing.
- `KineticSubtitleOverlay`: per-word/card-like styling with staggered entrance and active word pop.
- `BurstSubtitleOverlay`: phrase display that enlarges the most important active phrase or final words while keeping surrounding text readable.

All treatments must continue to hide hyphens through `formatSubtitleText`.

## UI And Overrides

V1 should include automatic routing, the scene-level data field, and Test Lab subtitle-style selection so every treatment can be manually exercised before a full script render. The timeline editor may defer its compact per-scene control, but the renderer and API shape should be ready for timeline overrides.

The later timeline UI should expose a compact per-scene subtitle style control near the visual mode controls:

- Auto
- Clean
- Kinetic
- Burst
- None

Because this changes scene visual behavior, Test Lab support is part of V1 rather than a follow-up. Test Lab should expose the same style choices and pass the selected value through the same render path production uses.

## Captions Visual Mode

`visual_mode="captions"` remains a separate visual mode. It renders its own `caption_text` and `caption_emphasis`, and standard bottom subtitles stay suppressed for that scene. The standard subtitle router must not override or decorate caption scenes.

## Cache Validity

Subtitle style changes affect visual output, so render cache fingerprints must include the explicit `subtitle_style` value for each rendered scene. Auto-routed scenes must also include a subtitle router version or heuristic fingerprint so changes to routing behavior cannot reuse stale long-form renders, short-form renders, thumbnails/previews that include subtitles, or exported assets with the wrong subtitle treatment.

## Testing

Add focused tests around:

- Auto routing chooses `clean`, `kinetic`, or `burst` from representative timing inputs.
- Explicit `subtitle_style` overrides win over auto routing.
- `visual_mode="captions"` and title cards still suppress standard subtitles.
- Test Lab can force `auto`, `clean`, `kinetic`, `burst`, and `none` through the production render input path.
- Render cache validity changes when explicit subtitle style or the auto-router fingerprint changes.
- Hyphen formatting remains applied in every standard subtitle treatment.
- Vertical subtitle placement still stays in the bottom blurred band above app chrome.

Frontend tests can cover any future subtitle-style selector. Renderer utility tests should cover routing without needing a full Remotion render where possible.
