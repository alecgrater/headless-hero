# Visual Mode Design Guardrails

Use this document before adding, renaming, or changing any scene `visual_mode`.

The goal is to keep Headless Hero's visual system expressive without letting modes overlap, contradict each other, weaken render determinism, or flatten the animation rhythm across a full video.

## Required Process

Before implementation, write down the proposed mode's answers to the checklist below. A new visual mode should only move forward when it has:

- A distinct visual purpose not already covered by an existing mode.
- Clear routing rules for when script generation or post-voiceover analysis should choose it.
- Clear avoidance rules for when another mode is a better fit.
- A deterministic scene JSON shape that can be rendered without hidden frontend state.
- Remotion behavior, cache invalidation, Test Lab support, export behavior, and fallback behavior.
- No contradiction with AGENTS.md visual-mode conventions.

If adding the mode establishes a new convention, update `AGENTS.md` in the same change.

## Existing Mode Responsibilities

Use the existing modes first when they already cover the visual job.

### `full_frame`

Use for one stable, full-bleed generated scene image. This is the default for simple visual beats, locations, objects, character moments, and concept illustrations.

Do not use a new mode when the scene only needs one full-screen image with normal subtitles, transitions, and FX.

### `multi_frame`

Use for multiple distinct generated frames inside one scene, especially quick examples, contrasts, escalation beats, or montage-like visual variety.

Do not create a new mode for separate quick-cut examples unless it needs a meaningfully different asset model or renderer.

### `continuous`

Use for same-scene progression where each generated frame advances one coherent event, object, environment, or character state.

Do not use `continuous` for unrelated montage frames, and do not create a new mode for progression unless it needs behavior beyond prior-frame reference chaining.

### `video`

Use for AI-video scenes generated from an anchor image after voiceover timing exists. This is for meaningful motion that improves the scene.

Do not use `video` before every scene has real voiceover timing. Do not create a new motion mode if anchor-image AI video already covers the need.

### `popup_sequence`

Use for a central anchor cutout with separate transparent item cutouts that pop in at voiceover timings and orbit clockwise.

Do not use normal scene images for popup sequence. Do not create another item-pop mode unless it needs a different staging model than anchor plus orbiting cutouts.

### `flipflop`

Use for same-subject cropped A/B micro-animation where compatible transparent character/body-language cutouts alternate from frame zero over the static canvas.

Do not use it for generic contrast between different ideas, time periods, unrelated emotional states, different locations, outcomes, or full-environment changes. Prefer character/human body language; object-only flip-flops require explicit object-action narration.

### `comparison_board`

Use for renderer-controlled side-by-side comparisons of two or three subjects, concepts, states, levels, choices, or outcomes.

This mode stages transparent cutouts over the static canvas. The renderer owns the split-screen board, dividers, labels, VS marker, arrows, badges, and stat chips. Do not bake readable text, labels, split panels, borders, or full backgrounds into generated images.

Do not use it for a single environment or event, same-subject micro-animation, ordinary item lists, or process progression. Use `flipflop` for compatible A/B motion of one subject, `popup_sequence` for item callouts around an anchor, `continuous` for progression, and `multi_frame` for independent example cuts.

### `captions`

Use for renderer-owned editorial text beats with large in-scene `caption_text` and optional `caption_emphasis`.

Do not bake readable text into generated images. Do not use `captions` as standard subtitle rendering, and do not create a new text-punch mode unless it has a distinct renderer behavior.

### `stat_card`

Use for a single dominant statistic — one decisive percentage, financial figure, population count, duration, distance, ranking, odds, risk factor, or scientific measurement — rendered as a giant headline `stat_value` plus a short supporting `stat_label` over the static canvas. The renderer owns all readable typography. The only generated asset is an optional transparent supporting icon cutout, declared as a single `visual_layers` entry; layers may be omitted entirely for a text-only beat.

Do not use `stat_card` when atmosphere or environment matters more than the metric, when narration covers multiple numbers or comparisons, or when the scene needs character/action staging. Do not bake the number, label, progress bars, gauges, trend arrows, or comparison badges into generated images. Distribution is capped at MAX 1-2 per video and never back-to-back; standard subtitles and Eli overlays are suppressed for the beat.

## New Mode Checklist

Answer these questions before implementation:

1. What unique visual job does this mode perform that is not already covered by `full_frame`, `multi_frame`, `continuous`, `video`, `popup_sequence`, `flipflop`, `comparison_board`, `stat_card`, or `captions`?
2. When should script generation choose this mode?
3. When should post-voiceover visual analysis choose or preserve this mode?
4. When should this mode be avoided in favor of an existing mode?
5. How does this mode improve variety across the full video without becoming repetitive or visually noisy?
6. Should the mode have spacing or frequency rules, such as no back-to-back use or a per-segment cap?
7. Does the mode depend on narration text, ElevenLabs audio duration, word timestamps, phrase timestamps, scene duration, or segment boundaries?
8. Does it interact with standard subtitles, `captions`, title cards, transitions, scene FX, Eli overlays, short-form exports, or thumbnails?
9. What scene JSON fields are required, and which fields are optional?
10. What Remotion props and renderer components must understand this mode?
11. Does it need normal scene images, generated frame sequences, AI video clips, transparent cutouts, layered assets, renderer-owned text, or a new asset type?
12. Does the mode preserve the full-bleed/no-border rule for normal generated images and panels?
13. Does it avoid readable text inside generated images unless the renderer owns that text?
14. How should manual visual regeneration, batch generation, Test Lab runs, long-form renders, short-form renders, thumbnails, and exports handle this mode?
15. What files or metadata should be included in render sidecars or export sidecars?
16. What cache fingerprint inputs make assets stale, including prompts, renderer behavior, labels, timing, model settings, provider settings, and generated asset paths?
17. What fallback should be used if asset generation fails?
18. What fallback should be used if timing data is missing or malformed?
19. What fallback should be used if provider API keys or required settings are unavailable?
20. What dev dashboard logs, warnings, status messages, editor hints, or disabled states are needed?
21. What backend tests, frontend tests, Remotion tests, and Test Lab coverage prove the mode works?
22. What docs, prompts, API schemas, frontend labels, and AGENTS.md rules must be updated?

## Routing Requirements

Each mode needs routing language for both creation paths:

- Script generation: how the scriptwriter can emit the mode in fresh scenes.
- Post-voiceover analysis: how timing-aware analysis can promote, preserve, reject, or fill this mode after audio exists.

Avoid routing rules that are only vibes. Prefer observable scene features: narration shape, visual prompt intent, audio duration, word timing, segment position, title-card status, protagonist presence, or action suitability.

## Asset And Cache Requirements

New modes must define their asset ownership precisely.

- Media-backed modes should say whether they create `image_url`, `frame_urls`, `video_url`, or another persisted asset field.
- Layered modes should say whether they use `visual_layers`, cutout assets, panel images, renderer-owned text, or other layer metadata.
- Modes that skip normal scene images must explicitly clear or ignore stale `image_url` and `frame_urls` where appropriate.
- Cache fingerprints must include every input that changes visible output.
- Stale-cache behavior must be explicit for old renders that lack new sidecar metadata.

## Renderer Requirements

Remotion should be able to render the mode from persisted props alone.

Define:

- Which component renders the mode.
- How the mode enters and exits the scene.
- Whether it covers the canvas or stages assets over `visual_canvas.background_color`.
- How it handles scene duration, audio duration, clip duration, frame timings, and word timings.
- Whether standard subtitles appear, move, or suppress.
- Whether scene FX and transitions apply normally or need mode-specific handling.
- What the mode does on missing, invalid, or partial assets.

## Test Lab Requirements

Every new visual mode must be testable in Test Lab in the same change that adds it.

Test Lab support should include:

- A selectable visual mode option with clear labeling.
- Preset or manual fields for any required mode-specific inputs.
- Production-equivalent generation paths where feasible.
- A fallback demo path only when production analyzer output is not available.
- No automatic rewrite of narration or visual prompt when switching modes.
- Run manifests that preserve enough mode metadata to debug output.

## Flow And Variety Requirements

Visual modes should improve the rhythm of the whole video, not just make one scene interesting.

Check for:

- Repetitive motion patterns across adjacent scenes.
- Too many layered scenes in a row.
- Too many text-punch scenes in a row.
- Confusing transitions between modes.
- Mode choices that reduce clarity of narration.
- Modes that compete with subtitles or title-card text.
- Shorts where the mode depends on context removed by segment export.

When a mode can become visually dominant, define spacing rules or analyzer penalties.

## Failure And Fallback Requirements

Every new mode needs graceful failure behavior. Prefer falling back to a stable existing mode over producing a broken render.

Common fallback targets:

- `full_frame` when a normal anchor image exists or can be generated.
- `multi_frame` when a sequence can still communicate the idea without custom renderer behavior.
- Static anchor image when AI-video output is too short, missing, or invalid.
- Suppressed optional layers when nonessential layered assets fail.

Failures that affect generation, rendering, export, integrations, caching, or background jobs should produce dev dashboard logs.

## Final Acceptance Rule

A new visual mode is ready only when it has a distinct purpose, deterministic data shape, renderer support, Test Lab coverage, cache invalidation rules, graceful fallbacks, dev observability, tests, docs, and no semantic conflict with existing visual-mode responsibilities.
