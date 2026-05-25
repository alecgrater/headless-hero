# Captions Visual Mode Design

## Purpose

Add a new `captions` visual mode for short, high-impact editorial text beats. A captions scene is designed for a single emotional or intellectual punch: one side may show a character, object, or simple panel, while the other side shows large stylized text. If the visual side is not useful, the text can occupy the center.

This is not standard subtitle rendering. The caption is editorial emphasis: short, graphic, readable at thumbnail scale, and timed to land with narration. Most words render in high-contrast dark or light styling, while the hardest-hitting word or phrase renders red and snaps or pulses when it lands.

## Decision

Build `captions` as a new canonical `visual_mode`, not as a repurposed `aha_subtitle` beat.

`aha_subtitle` remains the existing text-only visual beat for pure typography moments. `captions` becomes a richer static-canvas scene mode that can combine a generated visual with editorial text. It reuses the same timing concepts as `aha_subtitle`, especially word-level reveal from ElevenLabs timing, but keeps its product contract separate.

## User Experience

Captions scenes are for:

- shocking realizations
- emotional labels
- reversals
- key claims
- "this is the point" moments
- short quote-like lines where the visual punch matters more than bottom subtitles

The expected scene rhythm is:

1. The static canvas and side visual land first.
2. Caption words appear one by one in sync with voiceover word timing.
3. The red emphasis word or phrase snaps or pulses when spoken.
4. Normal bottom subtitles are suppressed while the caption text is active.

The renderer owns typography, animation, and layout. The scriptwriter only chooses the mode and supplies concise text fields, so project generation does not add any required LLM calls.

## Data Model

Extend `Scene` with optional caption fields:

- `caption_text: str = ""`
- `caption_emphasis: str = ""`

`caption_text` is the rendered editorial phrase, ideally 2-15 words. It may be a subset of narration, a quote-like compression of narration, or a short label for the scene.

`caption_emphasis` is the exact word or phrase to render red. It should be a substring of `caption_text` when possible. If it is missing or does not match, the renderer falls back to a deterministic emphasis choice.

Fallback behavior:

- If `caption_text` is empty, use `scene.narration`.
- If `caption_emphasis` is empty, use a deterministic emphasis heuristic such as the final content word, the final 1-3 word phrase, or the first strong all-caps candidate if present.
- If word timing is missing, render the full caption with a deterministic pop/fade animation instead of per-word sync.

## Visual Mode Semantics

Add `"captions"` to the canonical visual mode vocabulary across backend, frontend, and Remotion types.

Compatibility fields:

- `media_source` remains `"ai"`.
- `visual_treatment` remains `"full_frame"` because captions are not a popup or flip-flop layer treatment.
- `visual_beat` should be `"captions"` for compatibility with legacy beat-oriented prompt and render code.

Generated media behavior:

- Captions scenes may generate one normal scene image when `visual_prompt` is present.
- Captions scenes do not need popup/flip-flop `visual_layers`.
- Text-only captions scenes may skip normal image generation when `visual_prompt` is empty.
- They should not generate text inside the AI image; all readable caption text is rendered by Remotion.

## Rendering

Add a Remotion `CaptionScene` component.

Responsibilities:

- Render the global/static canvas underneath the scene.
- Place an optional scene image or panel on one side.
- Place caption text on the other side, or center it when no image is available.
- Reveal words one by one using `word_timestamps`.
- Color the `caption_emphasis` phrase red.
- Apply a snap or pulse when the emphasis phrase starts.
- Use hand-drawn/cartoon typography styling with thick weight, imperfect-feeling edges, strong outline/shadow, and thumbnail-scale readability.
- Support horizontal and vertical output.

`CaptionScene` should reuse or share utilities with `SubtitleScene` where useful:

- word normalization
- subtitle/caption word boundary matching
- fallback timing
- hyphen display cleanup

Normal `SubtitleOverlay` should be suppressed for `visual_mode="captions"` while caption words are active. The simplest first version may suppress subtitles for the entire captions scene. A later refinement can suppress only the active caption window if useful.

## Script Generation

Fresh script generation should not add any extra LLM calls. The existing scriptwriter prompt should be extended so when it chooses `visual_mode="captions"`, it also emits:

- `caption_text`
- `caption_emphasis`

Keep prompt instructions short:

- Use captions for punch moments, reversals, emotional labels, key claims, and "this is the point" beats.
- Keep `caption_text` short: ideally 2-15 words.
- Choose one most intense word or phrase as `caption_emphasis`.
- Do not describe typography, animation, color, or layout in detail; the renderer handles those.
- Do not put readable caption text into `visual_prompt`.

Distribution guidance:

- Captions are a variety mode like `multi_frame`, `continuous`, and `aha_subtitle`.
- Avoid consecutive captions scenes.
- Use captions sparingly enough that they feel like impact moments rather than a default scene type.
- In `life-as-a`, captions remain disabled in the first pass to preserve the format's current tone and because `aha_subtitle` is already disabled there.

## Visual Analysis and Existing Projects

The first implementation should support explicit/manual captions mode and fresh script generation.

Visual treatment analysis may preserve an existing `visual_mode="captions"` scene and should not overwrite caption fields. Auto-converting existing scenes into captions can be added later, but is not required for the first implementation because that could require another LLM or a brittle heuristic.

If analysis does infer captions later, it should do so without a required extra LLM call unless a user explicitly requests caption rewriting.

## Frontend UI

Timeline properties:

- Add Captions to the visual mode picker.
- Use an icon that suggests editorial text, such as a quote/text icon from `lucide-react`.
- When selected, show two compact fields:
  - Caption text
  - Red emphasis
- Include concise helper text only where needed, for example: "Short editorial text rendered in-scene; normal subtitles are suppressed during the caption."

Test Lab:

- Add Captions to visual mode options.
- Add a captions preset/default text example.
- Ensure the selected mode can run through audio, optional visual generation, render, and preview.
- Treatment asset generation should stay disabled for captions because it does not use popup/flip-flop layers.

Media review and labels:

- Captions should not be labeled as AI video.
- If image/frame counts are displayed, captions should be treated as a static-canvas caption scene with optional image media, not as a popup/flip-flop layer mode.

## Backend Pipeline

Model normalization:

- Add `captions` to `VISUAL_MODES` and `VisualMode`.
- Preserve captions through assignment and save/load paths.
- Keep `visual_treatment="full_frame"` and `media_source="ai"`.

Image generation:

- If `visual_mode="captions"` and `visual_prompt` is non-empty, generate one base image through the normal scene-image path.
- If `visual_prompt` is empty, skip image generation and render text-centered over the canvas.
- Do not clear `image_url` solely because the mode is captions.
- Do not generate popup/flip-flop visual layers.

FX:

- Avoid camera drift and zoom punch on captions unless explicitly proven useful. The text animation is the main motion.
- Transitions should default to `cut` or other simple transitions.

Logging:

- Add concise dev-dashboard/test-lab logs when captions render with missing word timing and fall back to non-synced animation.
- Log when a captions scene skips image generation because it is text-only.

## Tests

Backend tests:

- `Scene(visual_mode="captions")` normalizes to `media_source="ai"` and `visual_treatment="full_frame"`.
- Assigning legacy fields does not accidentally erase captions mode.
- Captions mode does not clear `frame_urls` or `image_url` like video/popup/flip-flop modes.
- Test Lab accepts captions mode and disables treatment assets.
- Batch image generation skips image calls only when captions has no `visual_prompt`.

Remotion/frontend tests:

- `CaptionScene` reveals words according to `word_timestamps`.
- The emphasis phrase renders red.
- Missing timing falls back to static pop/fade.
- `SceneRenderer` suppresses `SubtitleOverlay` for captions scenes.
- Captions appears in Timeline and Test Lab visual mode selectors.

Prompt tests:

- Script prompt documents `captions` in the visual mode vocabulary.
- Output schema examples include `caption_text` and `caption_emphasis`.
- Prompt wording keeps renderer styling out of the scriptwriter's responsibility.

## Rollout

Implement in small steps:

1. Add model/types/schema support and tests.
2. Add Remotion renderer and subtitle suppression tests.
3. Add frontend controls and Test Lab support.
4. Update script prompts and prompt tests.
5. Verify with Test Lab using an audio-timed captions scene.

## Open Non-Goals

Do not add a new project-generation LLM call.

Do not generate caption text as pixels inside AI images.

Do not make captions a popup/flip-flop `visual_treatment`; it is a canonical visual mode.

Do not auto-convert old projects into captions mode in the first pass.
