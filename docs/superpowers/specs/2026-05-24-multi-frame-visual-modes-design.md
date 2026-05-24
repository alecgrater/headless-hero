# Multi-Frame Visual Modes Design

## Summary

Promote the legacy `quick_cuts`, `montage`, and `continuous` visual beat behavior into canonical `visual_mode` values.

The target canonical visual modes are:

```text
video
full_frame
multi_frame
continuous
popup_sequence
flipflop
```

`quick_cuts` and `montage` collapse into one mode: `multi_frame`. `continuous` becomes its own canonical mode because it has different generation semantics: frames should preserve continuity and evolve the same scene over time.

The future `captions` visual mode is intentionally out of scope for this design.

## Current Problem

Headless Hero currently has two overlapping scene classification systems:

- `visual_beat`: legacy scriptwriter vocabulary such as `static`, `continuous`, `quick_cuts`, `montage`, and `aha_subtitle`.
- `visual_mode`: canonical rendering/routing vocabulary such as `video`, `full_frame`, `popup_sequence`, and `flipflop`.

`quick_cuts` and `montage` are too similar to justify separate concepts. Both mean a single narration scene uses multiple independent AI-generated frames. The difference is editorial tone, not a different data or render model.

`continuous` should remain distinct because it means a single visual action progresses over multiple frames using reference continuity.

## Goals

- Add `multi_frame` as the canonical mode for former `quick_cuts` and `montage` scenes.
- Add `continuous` as a canonical visual mode.
- Make both modes available to listicle and `life-as-a` scripts.
- Keep existing scripts and generated assets loading safely.
- Preserve current multi-frame rendering behavior while moving routing and prompts toward `visual_mode`.
- Keep `aha_subtitle` unchanged for now.

## Non-Goals

- Do not implement the future `captions` mode in this change.
- Do not remove the `visual_beat` field yet.
- Do not migrate files on disk or regenerate existing scene assets.
- Do not redesign the Remotion `MultiFrameScene` renderer unless required by the type change.
- Do not add mode subtypes such as `rapid`, `montage`, or `atmospheric`.

## Canonical Mode Semantics

### `full_frame`

One normal scene image or single-frame visual fills the scene.

Legacy compatibility:

- `visual_beat="static"` maps to `visual_mode="full_frame"` when no explicit mode exists.

### `multi_frame`

One narration scene renders multiple independent AI-generated frames.

Generation behavior:

- `frame_directives` contain 3-8 `ai_generated` directives.
- `reference_previous=false`.
- Transitions are mostly `cut`, with occasional `crossfade` allowed when already present in old data.
- Each frame may use a different subject, angle, composition, or example.

Legacy compatibility:

- `visual_beat="quick_cuts"` maps to `visual_mode="multi_frame"` when no explicit mode exists.
- `visual_beat="montage"` maps to `visual_mode="multi_frame"` when no explicit mode exists.

### `continuous`

One narration scene renders multiple frames that depict the same scene evolving over time.

Generation behavior:

- `frame_directives` contain 2-4 `ai_generated` directives.
- `reference_previous=true` after the first frame.
- Transitions are primarily `crossfade`.
- Frame prompts describe progression, not unrelated examples.

Legacy compatibility:

- `visual_beat="continuous"` maps to `visual_mode="continuous"` when no explicit mode exists.

### Existing Modes

`video`, `popup_sequence`, and `flipflop` keep their current behavior.

`aha_subtitle` remains a special visual beat and Remotion scene path for now. It should not become `multi_frame` or `continuous`.

## Data Model

Update Python and TypeScript visual-mode unions:

```python
VisualMode = Literal[
    "video",
    "full_frame",
    "multi_frame",
    "continuous",
    "popup_sequence",
    "flipflop",
]
```

```ts
export type VisualMode =
  | "video"
  | "full_frame"
  | "multi_frame"
  | "continuous"
  | "popup_sequence"
  | "flipflop";
```

The legacy `visual_treatment` field should remain limited to static-canvas layer treatments:

```text
full_frame | popup_sequence | flipflop
```

For `multi_frame` and `continuous`, legacy mirrors should be:

```text
media_source = "ai"
visual_treatment = "full_frame"
```

This keeps Remotion and older code compatible while `visual_mode` carries the actual meaning.

## Normalization

Scene model normalization should resolve modes in this priority order:

1. Valid explicit `visual_mode`.
2. `media_source="ai_video"` maps to `video`.
3. Layered legacy `visual_treatment` maps to `popup_sequence` or `flipflop`.
4. Legacy `visual_beat` maps to a canonical mode:
   - `quick_cuts` -> `multi_frame`
   - `montage` -> `multi_frame`
   - `continuous` -> `continuous`
   - `static` -> `full_frame`
5. Default to `full_frame`.

When normalizing `video`, `popup_sequence`, or `flipflop`, keep the current frame-clearing behavior.

For `multi_frame` and `continuous`, do not clear `frame_urls` or `frame_directives`. Those modes depend on frame data.

## Script Generation

The scriptwriter prompt should stop asking for `quick_cuts` and `montage` as future beat labels.

The new prompt vocabulary should describe visual mode directly:

- `full_frame`: one strong image.
- `multi_frame`: multiple independent frames for examples, comparisons, or rapid visual variety.
- `continuous`: multiple related frames showing a single physical process unfolding.
- `aha_subtitle`: unchanged special text-only beat for now.

For compatibility with the existing output parser, there are two acceptable implementation paths:

1. Short-term: keep `visual_beat` in the generated JSON, but restrict it to `static`, `continuous`, `multi_frame`, and `aha_subtitle`, then map it into `visual_mode`.
2. Preferred: ask for `visual_mode` directly and let `visual_beat` become compatibility metadata derived from mode.

The preferred implementation is path 2 if the parser changes stay small. If parser changes become large, path 1 is acceptable as a temporary bridge, but `quick_cuts` and `montage` should still disappear from new prompt instructions.

## Frame Directive Synthesis

Frame directive synthesis should key off `visual_mode` first.

`multi_frame` synthesis:

- Generate 3-4 fallback directives when missing.
- Use independent prompts.
- Set `reference_previous=false`.
- Use `transition="cut"`.

`continuous` synthesis:

- Generate 2-4 fallback directives when missing.
- The first frame establishes the base visual.
- Later frames describe deltas or progression.
- Set `reference_previous=true` for progression frames.
- Use `transition="crossfade"`.

Legacy beat values should still synthesize the same directives through normalization:

- `quick_cuts` and `montage` call the `multi_frame` path.
- `continuous` calls the `continuous` path.

## Rendering

No new Remotion scene component is required for the first implementation.

`SceneRenderer` can keep using `MultiFrameScene` whenever `frame_paths.length > 1`. The new modes only need to be represented in props so future components, logs, and UI can reason about the scene.

Expected render behavior:

- `multi_frame`: existing multi-frame cut/crossfade behavior.
- `continuous`: existing multi-frame behavior, with continuity produced by frame directive generation.

## UI and Test Lab

Test Lab should expose both modes:

- `Multi-frame`: multiple independent frames inside one scene.
- `Continuous`: one evolving scene across multiple frames.

The visual mode option descriptions should explain the distinction in plain language:

- Multi-frame: examples, comparisons, rapid visual variety.
- Continuous: physical process or transformation over time.

When either mode is selected, Test Lab should allow frame/image generation and render stages. It should not require layered treatment assets.

## Analyzer and Routing

Visual-mode analysis should emit canonical modes only.

Routing rules:

- Lists, multiple examples, rapid comparisons, or varied context -> `multi_frame`.
- Physical processes, growth, construction, transformation, or a single action unfolding -> `continuous`.
- Two-state contrast -> `flipflop`.
- Object callouts or named list items suitable for staged cutouts -> `popup_sequence`.
- Motion with generated video eligibility -> `video`.
- Otherwise -> `full_frame`.

The analyzer should never emit `quick_cuts` or `montage`.

## Format Behavior

Listicle scripts may use both `multi_frame` and `continuous`.

`life-as-a` scripts may use both modes too, with existing format constraints still applied:

- Scenes should remain short render beats.
- Protagonist-visibility rules still apply.
- The post-processor may split overlong scenes before voiceover.
- `aha_subtitle` remains disabled for `life-as-a`.

The key behavior change is that `life-as-a` no longer needs to reject all former quick-cut or montage behavior. It can use `multi_frame` when a scene benefits from several independent images.

## Dev Observability

Add concise dev dashboard or backend logs when visual-mode normalization changes legacy data:

```text
[VISUAL_MODE] scene=scene_003 legacy visual_beat=montage normalized to multi_frame
```

Add similar logs when analyzer output applies `multi_frame` or `continuous`.

## Testing

Model tests:

- Explicit `visual_mode="multi_frame"` survives normalization.
- Explicit `visual_mode="continuous"` survives normalization.
- `visual_beat="quick_cuts"` derives `multi_frame` if `visual_mode` is missing.
- `visual_beat="montage"` derives `multi_frame` if `visual_mode` is missing.
- `visual_beat="continuous"` derives `continuous` if `visual_mode` is missing.
- `multi_frame` and `continuous` do not clear `frame_urls`.

Scriptwriter tests:

- New prompt text does not ask for `quick_cuts` or `montage`.
- Generated or synthesized multi-frame scenes use `visual_mode="multi_frame"`.
- Generated or synthesized continuous scenes use `visual_mode="continuous"`.

Renderer/serialization tests:

- Remotion props include `visual_mode="multi_frame"` and frame paths.
- Remotion props include `visual_mode="continuous"` and frame paths.
- Both modes render through the existing multi-frame path without falling back to a single image.

Test Lab tests:

- Visual mode controls include `multi_frame` and `continuous`.
- Selecting either mode keeps treatment assets disabled or irrelevant.
- Test Lab run settings preserve the selected mode.

Analyzer tests:

- Example/list narration maps to `multi_frame`.
- Physical progression narration maps to `continuous`.
- Analyzer output never contains `quick_cuts` or `montage`.

## Rollout

1. Update model constants, literals, and normalization.
2. Add legacy beat-to-mode compatibility.
3. Update TypeScript types and Test Lab controls.
4. Update scriptwriter prompts and directive synthesis.
5. Update analyzer/routing logic to emit canonical modes.
6. Update Remotion props tests and backend tests.
7. Run backend and frontend test suites.

## Open Decisions

No open product decisions remain for this scope. `captions` is deferred to a separate design and implementation session.
