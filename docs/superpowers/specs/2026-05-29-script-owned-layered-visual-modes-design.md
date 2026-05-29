# Script-Owned Layered Visual Modes Design

## Goal

Move `popup_sequence` and `flipflop` selection into script generation so the writer can choose them from scene intent, while keeping the post-voiceover pass responsible for timing and layer completion.

Also align `flipflop` semantics across the codebase: it means compatible two-state micro-animation of one subject/action, not generic contrast between different ideas.

## Current Problem

`continuous`, `multi_frame`, and `captions` are selected during script generation because they shape narration, visual prompts, and frame directives. `popup_sequence` and `flipflop` are selected later by the visual treatment analyzer from narration heuristics.

That split creates two issues:

- The creative choice for `popup_sequence` and `flipflop` is made after the script is already written.
- `flipflop` has stale analyzer rules that route contrast markers such as `but`, `whereas`, `before`, and `after` into flip-flop, even though current rendering and image generation use it as micro-animation with full-bleed A/B state panels.

## Desired Behavior

Script generation may emit these final non-video visual modes:

- `full_frame`
- `continuous`
- `multi_frame`
- `captions`
- `popup_sequence`
- `flipflop`

`video` remains a post-voiceover media analyzer promotion because it depends on generated audio duration, segment spacing, caps, provider settings, and eligibility.

## Mode Semantics

### `popup_sequence`

Use when narration names a small set of concrete items, examples, ingredients, symptoms, tools, steps, or visible objects that should pop around the main subject.

The scriptwriter should set:

- `visual_mode: "popup_sequence"`
- compatibility `visual_beat: "popup_sequence"`
- empty or minimal `frame_directives`
- narration and visual prompt that preserve the intended anchor subject and popup item set

The post-voiceover analyzer should preserve explicit `popup_sequence` and create/fill `visual_layers` from word timings when missing.

### `flipflop`

Use for one subject/action that can read as simple animation by alternating compatible A/B states:

- a person gesturing while talking
- hands moving while typing, stirring, sorting, opening, closing, pointing, counting, or handling an object
- a character leaning in/out, looking up/down, pacing, nodding, or reacting
- a repeated physical action where both panels should share the same composition and subject

Do not use `flipflop` merely because a sentence contrasts two ideas, time periods, or emotional states. Broad contrast belongs in `multi_frame`, `continuous`, `captions`, or separate scenes unless there is a concrete same-subject action suitable for A/B alternation.

The scriptwriter should set:

- `visual_mode: "flipflop"`
- compatibility `visual_beat: "flipflop"`
- empty or minimal `frame_directives`
- a visual prompt describing one subject/action that can become two compatible states

The post-voiceover analyzer should preserve explicit `flipflop` and create/fill two compatible full-bleed state layers when missing.

## Analyzer Responsibility

The visual treatment analyzer remains post-voiceover because `popup_sequence` and `flipflop` layer timing can use `word_timestamps`.

It should:

- preserve explicit `popup_sequence` and `flipflop`
- fill missing `visual_layers` for explicit layered modes
- keep list-based fallback inference for `popup_sequence`
- limit fallback `flipflop` inference to clear same-subject physical motion cues
- stop routing generic contrast/two-state/repetition language to `flipflop`
- default to `full_frame` when no suitable layered pattern exists

## Prompt Responsibility

Script prompts should document `popup_sequence` and `flipflop` in the Visual Mode System, including the updated flipflop definition.

Distribution rules should treat `popup_sequence` and `flipflop` as variety modes, separated by at least one `full_frame` scene. Life-as-a can use them sparingly only if the format instructions allow it; otherwise existing format-specific restrictions win.

## Tests

Backend tests should cover:

- script prompt text includes `popup_sequence` and `flipflop`
- explicit `popup_sequence` is preserved and receives generated layers when missing
- explicit `flipflop` is preserved and receives two generated layers when missing
- generic contrast narration no longer becomes `flipflop`
- concrete micro-action narration can still fallback to `flipflop`
- repeated abstract words alone no longer trigger `flipflop`

Existing tests that assert contrast/two-state routing to `flipflop` should be rewritten to the new semantics.

## Documentation

Update `AGENTS.md` so the source-of-truth convention says:

- script generation may select `popup_sequence` and `flipflop`
- post-voiceover analysis fills timing/layer assets
- `flipflop` is micro-animation of one compatible subject/action, not generic contrast

## Out of Scope

- Changing Remotion flipflop rendering cadence
- Changing popup cutout generation
- Changing AI video promotion
- Removing legacy compatibility fields from old local data
