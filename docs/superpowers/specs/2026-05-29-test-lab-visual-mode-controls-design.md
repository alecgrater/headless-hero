# Test Lab Visual Mode Controls Design

## Goal

Reshape the Test Lab settings column around the current visual-mode system so it is easier to test full-frame, video, multi-frame, continuous, popup sequence, flip-flop, comparison board, captions, and future modes.

The new layout should make visual mode the first decision, keep mode-specific scene text close to that decision, and move render-level miscellany out of the visual-mode area.

## Current Problems

- The current order starts with pipeline stages, then audio, character, visual/canvas, and scene text. This puts execution controls before the creative route being tested.
- Visual mode shares a section with canvas color, subtitle style, subtitle highlight, and segment timer, which makes the mode picker feel crowded and less scalable.
- Scene text is separate from visual mode even though each mode uses a different prompt shape.
- Audio fields allow per-run voice/model/settings overrides, but the desired behavior is to use Settings -> Voices as the source of truth.
- Pipeline stages still expose a Character stage even though Test Lab should not offer a separate "generate or refresh character reference before scene assets" path.
- The Eli stage is controllable as a normal stage even though whether it applies should be derived from the selected character mode.

## Proposed Layout

Every major settings area becomes an accordion panel that can expand or collapse to a title-only row. Collapse state is local UI state and does not need to persist across app restarts.

Panel order:

1. Visual Mode
2. Character
3. Audio
4. Pipeline Stages
5. Miscellaneous

The selected dummy scene header remains above the accordions.

## Visual Mode Panel

The Visual Mode panel contains:

- A scalable mode picker that handles the current eight modes without a long vertical list.
- Mode help text that explains what the selected mode generates.
- Scene text controls that adapt to the selected mode.
- A collapsed Advanced Mode Data drawer for inspecting or editing raw-ish mode payloads when structured controls are not enough.

The mode picker should use compact selectable tiles or a segmented-grid pattern with icons, short labels, and concise hover/help text. It should not contain canvas color, subtitle style, subtitle highlight, or segment timer controls.

### Structured Scene Text

Each mode gets friendly structured controls:

- `full_frame`: narration and one visual prompt.
- `video`: narration and one visual prompt, labeled as the anchor prompt used before video generation.
- `multi_frame`: narration, shared scene prompt, and editable frame prompts/directives.
- `continuous`: narration, shared scene prompt, and editable progression steps with continuity wording.
- `popup_sequence`: narration, scene prompt, and popup item list.
- `flipflop`: narration, shared scene prompt, state A prompt, and state B prompt.
- `comparison_board`: narration, board scene prompt, left/right/optional third subject prompts.
- `captions`: narration, optional background/scene prompt, caption text, and caption emphasis.

Switching visual modes must preserve user-entered narration and visual prompt text. Mode-specific structured fields may be initialized from existing `visual_layers`, `frame_directives`, or defaults, but switching modes must not rewrite narration or the main prompt.

Structured controls must write to fields the Test Lab runner actually consumes:

- Add top-level `frame_directives` to `TestLabSettings` and backend Test Lab settings handling. `multi_frame` and `continuous` controls write their generated directives there, and `build_content_from_preset` copies them onto the hidden `Scene.frame_directives`.
- Keep top-level `visual_layers` for `popup_sequence`, `flipflop`, and `comparison_board`; structured layer controls update that existing field.
- Keep `caption_text` and `caption_emphasis` top-level for `captions`.
- `advanced_script` remains an escape hatch for complete hidden-script overrides, not the normal structured-control path.

Integration tests must prove edited `frame_directives` for `multi_frame`/`continuous` and edited `visual_layers` for layered modes reach the generated hidden `Scene` and are used by asset stages.

### Advanced Mode Data Drawer

The Advanced Mode Data drawer is collapsed by default. It is for debugging and future flexibility, not the primary workflow.

It should expose the underlying mode payload in the narrowest useful form:

- `frame_directives` for `multi_frame` and `continuous`.
- `visual_layers` for `popup_sequence`, `flipflop`, and `comparison_board`.
- Relevant caption fields for `captions`.

The drawer may keep using JSON-style editing if that is the lowest-risk way to preserve advanced control, but the main controls should remain structured and understandable without knowing the backend model.

## Character Panel

The Character panel follows Visual Mode.

It keeps character mode selection focused on the two supported contexts:

- Style preset/current global character context.
- Eli.

When Eli is off, the run uses the active preset/global character context without regenerating a reference image. When Eli is on, the run uses Eli and can generate Eli animation timing in the pipeline.

The panel should keep a character preview/status area. If no active preset character is available, show a warning with the Settings location needed to resolve it.

## Audio Panel

The Audio panel becomes read-only.

It displays the active voice configuration from Settings -> Voices, including:

- Selected voice name or ID.
- ElevenLabs model.
- Visible model-specific controls only: v2 preset/custom values when v2 is active, and v3 stability when v3 is active.

The panel should clearly state that voice settings are changed in Settings -> Voices. It should not expose Test Lab-specific voice ID, model ID, or voice settings JSON overrides.

Backend behavior must match the read-only UI: remove Test Lab support for per-run `voice_id`, `voice_model_id`, and `voice_settings` overrides. Audio always resolves voice, model, and model-specific settings from the same Settings -> Voices source of truth used by normal project voiceover.

Add a friendly voice summary to `/api/test-lab/scenes` so Test Lab does not duplicate Settings interpretation in the UI:

```json
{
  "voice_summary": {
    "voice_id": "string",
    "voice_name": "string",
    "model_id": "eleven_multilingual_v2 | eleven_v3 | string",
    "model_label": "string",
    "delivery_preset": "Steady | More Human | Dramatic | Custom | null",
    "visible_settings": [
      { "label": "Stability", "value": "0.50" }
    ]
  }
}
```

For v2, `visible_settings` includes the active preset label and the visible custom values only when Custom is active. For v3, it includes stability only. Remove tests that assert per-run override forwarding and replace them with assertions that Test Lab resolves Settings -> Voices values and that the summary matches v2/v3 visible-settings behavior.

## Pipeline Stages Panel

The Pipeline Stages panel follows Audio.

Remove the Character stage button from the UI. Test Lab no longer offers generating or refreshing a character reference before scene assets.

Remaining user-controllable stages:

- Audio.
- Visual.
- Animation assets, enabled only for layered/cutout modes that use `visual_layers`.
- FX.
- Render.

Eli appears as a read-only derived stage/status:

- Off when `eli_enabled` is false.
- On when `eli_enabled` is true.
- Disabled as a direct toggle.
- Explanation: off means preset/current global character context; on means Eli is used and Eli animation timing will be generated.

Backend stage defaults must align with the UI:

- Remove `stages.character` from Test Lab frontend types, defaults, API request normalization, runner defaults, run manifests, and tests. `_stage_character_reference` should no longer be reachable from the Test Lab runner.
- Remove direct `stages.eli` control from Test Lab frontend types, defaults, API request normalization, runner defaults, run manifests, and tests. Runner stage selection derives Eli solely from `eli_enabled`.
- Add backend tests proving the runner stage list has no Character stage and that `eli_enabled=true` schedules/runs Eli without reading a `stages.eli` flag.

## Miscellaneous Panel

The Miscellaneous panel contains render-level options that are not visual-mode selection:

- Canvas color.
- Subtitle style.
- Subtitle highlight.
- Segment timer.

These controls remain available because they affect render previews, but moving them out of Visual Mode keeps the mode picker focused.

## Data Flow

The existing `TestLabSettings` shape can remain mostly intact:

- Keep `visual_mode`, `narration`, `visual_prompt`, top-level `frame_directives`, `visual_layers`, captions fields, character flags, current stage flags, subtitle settings, and canvas settings.
- Remove obsolete Test Lab-only settings fields for per-run voice overrides, `stages.character`, and `stages.eli` in the same implementation pass. This is a one-time cleanup; no compatibility layer is required for old Test Lab payloads.
- Add frontend helpers that map structured mode controls to the existing `frame_directives` and `visual_layers` payloads.
- Avoid introducing a second visual-mode schema unless a future mode requires it.

When a mode changes:

1. Update `visual_mode`.
2. Preserve narration and main visual prompt.
3. Clear or reinitialize incompatible generated layer/directive payloads only when needed.
4. Set `treatment_assets` true for `popup_sequence`, `flipflop`, and `comparison_board`; false or disabled for modes that do not use those assets.

## Testing

Frontend tests should cover:

- Accordion sections render in the requested order and can collapse/expand.
- Visual Mode panel does not render canvas color, subtitle style, subtitle highlight, or segment timer controls.
- Scene text controls change by selected visual mode.
- Switching modes preserves narration and visual prompt.
- Audio panel is read-only and points to Settings -> Voices.
- Pipeline stages do not expose a Character toggle.
- Eli stage is derived and not directly controllable.
- Miscellaneous panel contains canvas color, subtitle style, subtitle highlight, and segment timer.

Backend or integration tests should cover:

- Test Lab no longer exposes or schedules a Character stage.
- Eli stage selection remains derived from `eli_enabled`.
- Voice settings summary, if added, matches Settings -> Voices behavior for v2 and v3.

## Out Of Scope

- Adding a new visual mode.
- Changing Remotion rendering behavior for any mode.
- Reworking Settings -> Voices itself.
- Replacing the hidden Test Lab script/project creation model.
- Persisting accordion collapse state across app restarts.
