# Visual Mode Duration Policy Design

## Goal

Make scene length follow the intended visual mode automatically, before voiceover generation, so modes that need more viewer processing time get enough narration to breathe. The policy applies to every script type: listicle, life-as-a, and future formats all use the same visual-mode duration rules.

The app should also make the workflow clear in the Timeline and in Settings -> Reference, so users understand how visual modes are chosen, why some scenes are longer, and what post-voiceover validation still does.

## Current Problem

The default scene target is about 8 seconds, with prompts asking for 1-2 sentences and roughly 5-9 seconds of speech. That works for simple image beats, but it is too short for renderer-owned modes such as `comparison_board` and `captions`, where the viewer must read or compare on-screen structure while listening.

The current workflow also mixes two decisions:

1. Which visual mode a scene should use.
2. Which timing/layer metadata is needed after voiceover exists.

Because the post-voiceover analysis button can change or fill visual modes after audio is already generated, it is too late for that pass to make the narration longer without rewriting and revoicing scenes. The project already avoids post-voiceover script rewrites, so longer mode-specific narration should be planned before voiceover.

## Recommended Architecture

Add a shared backend visual-mode duration policy. It should be mode-driven, not format-driven.

The policy owns:

- Target duration range by `visual_mode`.
- Soft variety expectations by `visual_mode`.
- Spacing and cap guidance for modes that should stay rare.
- Labels/helper text used by prompts and UI.
- Validation hints for modes that may be downgraded after voiceover.

This should live in one small module that can be imported by script generation, format post-processing, API response shaping if needed, and tests. Avoid scattering checks such as `if mode == "comparison_board"` across prompt builders, splitters, and UI code.

## Duration Profiles

Use these first-pass profile targets:

| Visual mode | Profile | Target guidance |
| --- | --- | --- |
| `full_frame` | normal | About 5-9 seconds; 8 seconds remains the default. |
| `multi_frame` | normal | About 5-9 seconds unless the scene contains several concrete examples. |
| `continuous` | normal | About 5-9 seconds, with room for subtle progression. |
| `flipflop` | normal | About 5-9 seconds for simple A/B micro-motion. |
| `captions` | extended | About 14-18 seconds, enough for the editorial text to land in context. |
| `comparison_board` | extended | About 16-24 seconds, enough for two or three columns to be understood. |
| `popup_sequence` | extended | About 14-20 seconds, scaling with the number of items/layers. |
| `dossier` | extended | About 14-20 seconds, scaling with evidence/subject count. |
| `stat_card` | medium | About 10-14 seconds unless it is only a fast numerical punch. |
| `video` | planned | Planned before voiceover as an intended mode; later validation may downgrade if timing, adjacency, duration, or assets make it unsafe. |

The exact numbers can be constants, but the important behavior is that prompts and scene splitting agree on the same profile. If a mode is extended, generated narration should be allowed to contain the equivalent of about two to three normal scenes.

## Mode Variety Policy

Full frame remains the fallback and can repeat freely.

The script phase should intentionally plan a healthy visual rhythm across the whole project:

- `multi_frame`, `continuous`, `flipflop`, and `captions` should appear often when the scene content supports them.
- `popup_sequence`, `comparison_board`, and `stat_card` should appear at least once or twice per project when the topic provides natural opportunities, and more only when they clearly fit.
- `video` should be planned before voiceover and should generally appear at least three times per project, subject to later validation.
- `comparison_board`, `popup_sequence`, `stat_card`, `dossier`, and `video` should not be forced into scenes where they reduce clarity or conflict with the narration.
- Non-`full_frame` modes should still respect spacing rules so the video does not become visually noisy.

These are soft planning targets, not hard quotas. The policy should guide prompts and post-processing, while preserving the rule that each scene uses the single best visual mode for its content.

## Script-Type Behavior

All script types use the same visual-mode duration and variety policy.

Format-specific prompts still own narrative voice, structure, and craft rules:

- Listicles can sound explanatory and segmented.
- Life-as-a can stay literary, second-person, and progression-driven.
- Future formats can define their own voice and structural conventions.

Those format rules must not override the universal visual-mode policy. For example, a `comparison_board` scene gets comparison-board breathing room whether it appears in a listicle, life-as-a, or another format.

The existing life-as-a 5-9 second enforcement should become profile-aware so it does not split or compress intentionally extended visual-mode scenes back into normal-length beats.

## Generation Flow

1. Script generation chooses the intended visual mode for each scene, including planned `video` scenes.
2. A shared duration policy is included in script prompts so the model writes longer narration for extended modes.
3. Post-processing validates mode variety and scene granularity before voiceover. It should preserve extended-mode scenes as longer single scenes when the mode profile calls for that.
4. Voiceover generation runs after the intended visual rhythm is already planned.
5. Post-voiceover validation fills timing-dependent metadata and may downgrade invalid modes. It should not be the main place where major mode choices are discovered.

Post-voiceover validation may still be needed for:

- AI-video eligibility and duration caps.
- Layer enter times from word timestamps.
- Missing or malformed mode metadata.
- Downgrading planned modes that cannot be safely rendered.

## UI And Workflow

The Timeline should make automatic mode duration behavior obvious.

Recommended UI changes:

- Scene cards, the micro-timeline, or the properties panel should show each scene's duration profile, for example `Normal`, `Medium`, or `Extended`.
- Extended scenes should show concise helper text such as `Comparison board scenes are planned longer so viewers can compare the columns.`
- The visual mode picker should make profile behavior visible in each option label or description, for example `Comparison board · extended`.
- The Visual Modes tab should explain that script generation now plans the intended visual rhythm before voiceover.
- The current post-voiceover button should be renamed or reframed away from "Re-analyze Visual Modes" if it no longer owns major mode discovery. Better labels include `Validate Visual Modes`, `Prepare Visual Assets`, or `Validate and Prepare Modes`.
- When validation downgrades a planned mode, the UI should show the reason instead of silently hiding the change.
- Manual mode changes in the editor should immediately update visible profile hints so users understand that choosing a different mode changes the intended scene weight.

Do not add per-scene duration sliders in the first implementation. The first pass should be automatic policy plus clear explanation.

## Settings Reference Documentation

Add documentation under Settings -> Reference that explains:

- Visual modes are selected during script generation as part of the intended visual rhythm.
- Duration targets are tied to visual mode, not script type.
- Full-frame scenes are normal-length defaults.
- Captions, comparison boards, popup sequences, dossiers, and similar renderer-owned modes are planned longer.
- Video is planned before voiceover but validated afterward because timing and asset eligibility matter.
- The post-voiceover validation step fills timing/layer metadata and downgrades invalid modes; it should not usually rewrite the visual rhythm.
- Manual mode edits update the scene's duration profile expectations.

This can live on the existing Visual Modes reference page, with links from Script Types if useful.

## Data Flow

The shared duration policy should feed:

- Backend prompt text for script generation.
- Backend post-processing and scene splitting.
- Frontend visual mode metadata for Settings -> Reference.
- Timeline helper text and mode labels.
- Tests that assert all formats share the same policy.

Avoid duplicating duration ranges separately in Python and TypeScript without a clear synchronization strategy. If the existing frontend reference catalog remains static, mirror only stable profile labels and helper copy there, and keep numeric enforcement in the backend policy.

## Error Handling And Validation

If post-voiceover validation downgrades a planned mode, it should emit a reason suitable for UI display and dev-dashboard logs.

Validation should be conservative:

- Downgrade `video` if the real audio duration, adjacency, or scene content makes it ineligible.
- Downgrade layered modes only when required metadata or assets are missing and cannot be generated.
- Preserve script-owned modes whenever they are valid.

Validation must not call an LLM to rewrite narration or automatically revoice scenes after voiceover.

## Tests

Add focused coverage for:

- The shared policy returns expected profiles for all canonical visual modes.
- Generic scene splitting preserves extended-mode scenes that exceed the normal max but fit their mode profile.
- Life-as-a chunking respects the same extended-mode policy.
- Prompt builders include mode-specific duration guidance.
- Script type metadata or reference surfaces show the shared policy for every format.
- Timeline or settings UI renders duration profile helper text for selected modes.
- Post-voiceover validation preserves valid planned modes and reports reasons for downgrades.

## Documentation And Conventions

Update `AGENTS.md` with the new convention:

Visual-mode duration policy is universal across script types. Script generation plans visual rhythm and mode-specific scene length before voiceover; post-voiceover validation fills timing/assets and only downgrades invalid planned modes.

Also update any existing format docs that describe life-as-a or listicle scene duration so they refer to the shared visual-mode policy instead of implying that all non-title scenes must remain 5-9 seconds.
