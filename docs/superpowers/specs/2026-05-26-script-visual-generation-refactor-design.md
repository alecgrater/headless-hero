# Script And Visual Generation Refactor Design

## Goal

Rebuild project generation around one clean pipeline that works for both `youtube-listicle` and `life-as-a`, removes legacy visual mode vocabulary, and makes visual mode selection a single intelligent post-voiceover planning step.

The finished system should make every script type follow the same production shape:

1. Generate short, single-beat scenes.
2. Run shared and format-specific script cleanup.
3. Rate the script.
4. Generate per-scene voiceover timing.
5. Run one high-quality visual planner call for the whole project.
6. Generate visuals by canonical `visual_mode`.
7. Apply simple compatible FX.
8. Render/export.

## Scope

This effort includes:

- Shared short-scene pacing for listicle and life-as-a scripts.
- Removal of script hook scoring.
- Canonical visual modes only: `video`, `full_frame`, `multi_frame`, `continuous`, `popup_sequence`, `flipflop`, `captions`.
- Removal of new-code dependence on `aha_subtitle`, `static`, `quick_cuts`, `montage`, and `ai_video` as selection names.
- One post-voiceover visual planner that selects every scene's canonical mode.
- One high-quality LLM task route for visual planning, matching the quality expectations of script and cold-open generation.
- Unified protagonist/character rules across both script types.
- Generic FX limited to `full_frame` scenes.
- Updated Test Lab and dev observability where generation behavior changes.

This effort does not include:

- Parallelized ElevenLabs voiceover generation.
- A full TTS service refactor.
- ElevenLabs concurrency settings UI.
- A complete removal of every temporary compatibility mirror from persisted/API/render shapes if a small transitional mirror is needed to keep the app working.
- Advanced visual plan scoring beyond deterministic validation and repair.
- Mode-specific FX design for non-full-frame modes.
- A prompt/model evaluation harness.
- Old script/data migration.

## Canonical Pipeline

### 1. Project Setup

The script generation request resolves:

- format (`youtube-listicle`, `life-as-a`, or future formats)
- brand
- Eli enabled state
- style preset enabled state
- active style preset and character requirements
- model override for script generation

If Eli is disabled, the existing style preset character gate remains: image and video generation must not proceed unless an active style preset and active preset-scoped character reference exist.

### 2. Script Generation

The script LLM writes script structure and visual intent, not final visual modes.

Generated scenes should contain:

- `id`
- `narration`
- shot-labeled `visual_prompt`
- `duration_estimate_seconds`
- `is_title_card`
- `contains_person`
- optional `caption_text` / `caption_emphasis` hints when the line is naturally caption-like

The script prompt should not ask for:

- `visual_beat`
- `media_source`
- `visual_treatment`
- `frame_directives`
- `aha_subtitle`
- `static`
- `quick_cuts`
- `montage`
- `ai_video`

The prompt may ask for lightweight visual intent if it helps planning later, but final mode assignment belongs to the visual planner.

### 3. Shared And Format Cleanup

Every format goes through the same named cleanup phases.

Shared cleanup:

- normalize segment and scene IDs
- enforce short, single-beat scenes
- split scenes that contain multiple visual/narrative beats or exceed the shared max duration
- keep unchanged narration stable when possible so existing audio caches can be reused
- reset visual planning fields after any split

Shared pacing target:

- ideal non-title scene: 5-9 seconds of speech
- soft maximum: 12 seconds
- longer scenes are allowed only when the narration is clearly one visual beat and splitting would make it worse

Format-specific cleanup:

- listicle keeps its high-retention educational voice and segment structure
- life-as-a keeps second-person, literary voice, chapter cards, descriptor-only chapter-card narration, and long-arc continuity rules

Life-as-a scene chunking becomes an instance of the shared single-beat scene cleanup instead of an isolated one-off rule.

### 4. Script Rating

Script rating runs after cleanup and before voiceover.

It evaluates writing quality only:

- retention
- narrative quality
- craft
- audience fit
- SEO alignment

It does not depend on final visual modes. Visual planning quality is a separate concern.

### 5. Voiceover Timing

Voiceover remains the timing source of truth.

The contract for visual planning is:

- every non-title scene has `audio_duration_seconds > 0`
- every non-title scene has non-empty `word_timestamps`
- scene audio remains one file per scene

Do not concatenate multiple scenes into one ElevenLabs request in this effort. Future concurrency may still keep one request per scene while running several requests in parallel.

### 6. Unified Visual Planning

Add `backend/pipeline/visual_mode_planner.py` as the single owner of post-voiceover visual mode selection.

The planner runs one high-quality LLM call per project. It receives compact scene summaries:

- format ID
- format visual rules
- project title
- Eli/style/character mode
- scene ID and segment
- narration
- visual prompt
- duration
- timing summary
- protagonist/main-subject hints
- optional caption hints

The planner returns one assignment per scene:

- `scene_id`
- `visual_mode`
- `reasoning`
- `frame_directives` when applicable
- `caption_text` / `caption_emphasis` when applicable
- `visual_layers` plan when applicable

Allowed modes:

- `full_frame`: one full-bleed image
- `multi_frame`: independent full-bleed images
- `continuous`: reference-chained progression
- `video`: anchor image plus generated AI video
- `popup_sequence`: central anchor cutout plus popup cutouts
- `flipflop`: rapid full-bleed A/B visual alternation
- `captions`: renderer-owned large caption typography with optional side visual

The planner LLM is advisory plus structured. Deterministic validation and repair enforce hard rules.

### 7. Visual Plan Validation And Repair

Validation must ensure:

- every non-title scene has one canonical `visual_mode`
- no two adjacent non-title scenes use the same `visual_mode`
- title cards remain `full_frame`
- mode-specific fields are present and coherent
- captions mode never asks image generation to render readable text
- generated normal images/frames/panels remain full-bleed with no text, labels, borders, cards, or margins
- popup/flipflop plans use active style and cutout/panel rules
- protagonist/main-subject scenes follow the shared character rule

The shared character rule:

- if Eli is enabled, protagonist/main-subject scenes depict Eli as the visually dominant subject
- if Eli is disabled, protagonist/main-subject scenes depict the active style-preset character as the visually dominant subject
- AI video scenes follow the same rule
- secondary people may appear only when visually distinct and not competing with the protagonist
- object-only and environment-only scenes may omit the protagonist

There is no extra special spacing rule for video. The universal adjacency rule applies to every mode: no adjacent non-title scenes may share the same `visual_mode`.

### 8. Visual Generation

Visual generation dispatches by `visual_mode`.

- `full_frame`: generate one normal scene image
- `multi_frame`: generate independent frame sequence from frame directives
- `continuous`: generate reference-chained progression frames
- `video`: generate a full-frame anchor image, then generate AI video from that anchor
- `popup_sequence`: generate one anchor cutout and a contact sheet of item cutouts
- `flipflop`: generate full-bleed state panels
- `captions`: generate no normal image when `visual_prompt` is empty; generate only optional side imagery when provided

`media_source="ai_video"` may remain as a temporary compatibility mirror for `visual_mode="video"` where existing response/render shapes still require it. New selection logic must set `visual_mode`, not `media_source`.

### 9. FX And Transitions

Generic FX should apply only to `full_frame` scenes for this refactor.

Other modes own their motion or structure:

- `video`: clip motion
- `multi_frame`: cuts
- `continuous`: progression
- `popup_sequence`: layer motion
- `flipflop`: alternation
- `captions`: typography emphasis

Transitions can still be assigned between scenes, but the FX generator should not add normal camera FX to non-full-frame scenes.

### 10. Render And Export

Remotion should render primarily by `visual_mode`.

Transitional compatibility is acceptable:

```python
if scene.visual_mode == "video":
    render_video_scene()
```

Old-style fallback checks such as `scene.media_source == "ai_video"` should move toward load/apply normalization only. They should not be part of new planner, generation, or UI decision-making.

## API And UI Shape

### Backend

Add one visual planning API path that runs after voiceover:

- `POST /api/visual-modes/analyze/{script_id}` or equivalent
- `GET /api/visual-modes/analyze/status/{job_id}`
- optional apply/update endpoint if analysis remains reviewable before persistence

During migration, existing `/api/media/analyze` and `/api/visual-treatments/.../analyze` may delegate to the new planner or be removed when callers are updated.

### Settings

Add a first-class LLM task route:

- task ID: `visual_planner`
- label: `Visual planner`
- purpose: choosing scene visual modes and mode-specific generation plans after voiceover timing exists
- default provider/model quality should match script/cold-open quality rather than old media-routing defaults
- OpenAI reasoning default should be `low`, not `minimal`

### Frontend

Timeline, media review, visual treatment review, and Test Lab should present one visual mode concept rather than separate media source and treatment concepts.

Test Lab must support every canonical mode and must preserve scene text when users switch visual modes.

## Hook Scoring Removal

Remove hook scoring as part of this effort.

Remove:

- automatic post-script hook scoring from script generation
- manual script hook score endpoint
- script `hook_score` persistence/display
- project dashboard hook score badges
- hook-scoring settings route if it only supports removed hook scoring
- hook score tests tied to generated scripts

Cold-open generation may remain, but any hook score/refinement UI or backend behavior should be removed if it depends on the hook scoring feature.

## AGENTS.md Updates

Update project instructions after implementation so future work treats this design as source of truth:

- script generation emits short single-beat scenes and visual intent, not final visual modes
- visual planning runs after voiceover timing
- `visual_mode` is the canonical selector
- legacy visual names are not valid in new code
- hook scoring is removed
- generic FX applies only to `full_frame`
- one scene remains one voiceover audio/timing unit

## Risks

- This refactor touches many surfaces and needs focused tests before production code changes.
- Removing hook scoring can affect idea/cold-open UI if the feature is more entangled than expected.
- Compatibility mirrors may be needed longer than ideal to avoid breaking Remotion or frontend type assumptions mid-refactor.
- One project-level planner call can fail or return invalid assignments, so deterministic repair is mandatory.

## Success Criteria

- Script prompts contain no legacy visual mode names.
- New scripts default to short, single-beat scenes across both formats.
- Script generation no longer runs AI video/media analysis before voiceover.
- Script hook scoring is gone from generated-project flow and UI.
- Visual planning runs only after voiceover timing exists.
- The planner produces only canonical modes.
- No adjacent non-title scenes share the same mode after validation.
- Visual generation dispatches by `visual_mode`.
- Generic FX is skipped for non-full-frame scenes.
- Tests cover listicle and life-as-a visual planning with the same shared planner.
