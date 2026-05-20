# Split-Progression Thumbnail for life-as-a Format

**Status:** Design  
**Date:** 2026-05-20  
**Scope:** life-as-a / cinematic-chapters format only

## Goal

Replace the current cinematic-chapters thumbnail (single iconic image with a Pillow title overlay) with a "split-progression" thumbnail that visually contrasts an early level against a later level, modeled on the reference example provided by the user. The thumbnail must:

1. Look visually consistent across projects (same structural layout, same label treatment).
2. Add no net new Gemini image-generation calls vs. the current pipeline.
3. Match the format: diagonal split, two contrasting illustrations, "LEVEL X" / "LEVEL Y" labels, minimal text.

## Reference

User produced an acceptable example by feeding the existing cinematic iconic image to Gemini with a long redesign prompt. The new pipeline operationalizes that workflow.

## Non-Goals

- No changes to the youtube-listicle / composite-grid format. Its existing `gemini_enhance_thumbnail` flow stays intact.
- No new prompt fields on `ScriptContent` or `LevelMeta`.
- No video-title text on the final thumbnail. The redesign prompt explicitly discourages it; only "LEVEL X" / "LEVEL Y" labels are required.

## Architecture

### Pipeline (life-as-a format only)

In `CinematicChaptersStrategy.prepare_thumbnail`:

1. **Generate the cinematic iconic image.** Gemini call with `content.cinematic_thumbnail_prompt` → `cinematic_thumbnail_clean.png`. Unchanged from today.
2. **Reuse it as level 1's chapter card.** Copy `cinematic_thumbnail_clean.png` → `chapter_1.png`. No Gemini call. The cinematic prompt is assumed to be acceptable as level 1's image without modification.
3. **Generate chapters 2..N.** Loop `content.levels[1:]`, generate each as `chapter_{number}.png`. (N-1 Gemini calls, where today there were N.)
4. **Choose level pair.** Random selection (see "Level pair selection" below). Cache the chosen pair to a sidecar.
5. **Split-progression enhancement.** Single Gemini call: pass `cinematic_thumbnail_clean.png` + `SPLIT_PROGRESSION_PROMPT` (with `{left_level}` / `{right_level}` substituted) → `cinematic_thumbnail.png` (final, frontend reads this).

### Gemini call accounting

| Step | Today | Proposed |
|---|---|---|
| Cinematic iconic image | 1 | 1 |
| Chapter images | N | N − 1 (chapter 1 is a copy) |
| Pillow title overlay | 0 | 0 (removed) |
| Split-progression enhancement | 0 | 1 |
| **Total** | **N + 1** | **N + 1** |

Net change: zero new LLM calls.

### File layout (`data/projects/{script_id}/images/`)

| File | Role |
|---|---|
| `cinematic_thumbnail_clean.png` | AI-generated iconic image. Source for both chapter 1 and the split-progression enhancement input. |
| `chapter_1.png` | Copy of `cinematic_thumbnail_clean.png`. Used by `prepare_title_card_scene` for level 1's in-video chapter card. |
| `chapter_2.png` … `chapter_N.png` | Per-level AI-generated chapter card images (unchanged). |
| `cinematic_thumbnail.png` | Final split-progression thumbnail. Read by `get_composite_thumbnail`. |
| `cinematic_thumbnail.levels.json` | Sidecar storing `{"left_level": int, "right_level": int}` for cache stability across re-renders. |

The path written by `_thumbnail_paths` shifts: `cinematic_thumbnail_clean.png` (clean) and `cinematic_thumbnail.png` (final) — same names, but the final is now Gemini-enhanced rather than Pillow-overlaid. The intermediate Pillow `with_title` file is removed.

### Level pair selection

```
N = len(content.levels)
left_level  ∈ {1, 2}   (clamped to ≤ N)
right_level ∈ {N-1, N} (clamped to ≥ 1)
constraint: left_level < right_level
```

Edge cases:
- `N < 2`: skip enhancement, fall back to writing `cinematic_thumbnail.png` as a copy of `cinematic_thumbnail_clean.png`. Log a warning.
- `N == 2`: deterministic `(1, 2)`.
- `N == 3`: random from `{(1, 2), (1, 3), (2, 3)}`.
- `N >= 4`: full random from `{1, 2} × {N-1, N}` with `left < right`.

Selection is computed once and persisted to `cinematic_thumbnail.levels.json`. Subsequent calls without `force=True` reuse the persisted pair, so the labels stay stable across re-renders of the same project.

### Caching

Each step uses mtime-based caching, matching existing patterns in this codebase:

| Output | Re-runs when |
|---|---|
| `cinematic_thumbnail_clean.png` | `force=True` or `.prompt` marker mismatch (existing `generate_scene_image` behavior). |
| `chapter_1.png` | Source `cinematic_thumbnail_clean.png` mtime is newer, or file missing. |
| `chapter_{2..N}.png` | Existing `generate_scene_image` caching. |
| `cinematic_thumbnail.png` | Source `cinematic_thumbnail_clean.png` mtime is newer than output, or `force=True`, or sidecar missing. |
| `cinematic_thumbnail.levels.json` | Written once when first generating; not regenerated unless `force=True`. |

### Prompt

Stored as `SPLIT_PROGRESSION_PROMPT` in `backend/prompts.py` (matches `IMAGE_CTR_EXPRESSION_GUIDANCE` precedent). Uses Python `.format()` placeholders `{left_level}` and `{right_level}`.

Derived from the user's validated prompt with two substantive edits:

1. **Minimal-text section replaces the title-bar section.** The original "FULL TITLE should be placed at the TOP" instruction is removed. In its place:

   > IMPORTANT: Do NOT include the full video title in the thumbnail unless absolutely necessary. Prefer minimal text. The thumbnail should rely primarily on visual storytelling, emotional contrast, progression, and curiosity. Use only: "LEVEL {left_level}", "LEVEL {right_level}", and optionally ONE very short supporting phrase if it significantly improves clarity. Prioritize larger visuals and cleaner composition over extra text.

2. **Level numbers are templated.** "LEVEL 1" / "LEVEL 4" become `LEVEL {left_level}` / `LEVEL {right_level}`, substituted at call time with the chosen pair.

All other sections (layout rules for the diagonal divider, left-side rules, right-side rules, visual contrast rules, CTR optimization rules, style rules, "do not simply split the original image" guidance) are preserved verbatim.

### Code touch points

| File | Change |
|---|---|
| `backend/prompts.py` | Add `SPLIT_PROGRESSION_PROMPT` constant. |
| `backend/pipeline/thumbnail.py` | Add `enhance_split_progression(clean_image_path, left_level, right_level, script_id, force) -> Path`. Remove `composite_title_overlay` (no remaining callers after this change — verify and delete). |
| `backend/pipeline/formats/title_cards/cinematic_chapters.py` | Rewrite `prepare_thumbnail`: drop title-overlay step; copy clean → `chapter_1.png`; skip generating `chapter_1.png` from `levels[0].image_prompt`; pick level pair (with sidecar caching); call `enhance_split_progression`. Update `_thumbnail_paths` to return `(clean, final)` only. |
| `backend/pipeline/scriptwriter.py` & `backend/prompts.py` (life-as-a outline schema) | Update the life-as-a outline JSON schema and instructions so Claude does NOT emit `image_prompt` for `levels[0]`. The cinematic thumbnail prompt covers level 1's image. Validation in `enforce_life_as_a_constraints` (or equivalent) accepts a missing/empty `levels[0].image_prompt`. |
| `backend/integrations/google_image_client.py` | Reuse existing `transform_with_references()` — accepts a single image + prompt + script_id. No changes. |

### Frontend

No changes. `get_composite_thumbnail` keeps reading `cinematic_thumbnail.png` and the API surface is unchanged.

## Error Handling

- If `enhance_split_progression` fails (Gemini error, API down): copy `cinematic_thumbnail_clean.png` → `cinematic_thumbnail.png` as a fallback so the project still has a thumbnail. Log a warning. Do not raise — thumbnails are non-critical to render success.
- If `len(content.levels) < 2`: same fallback. Logged once.
- The sidecar `cinematic_thumbnail.levels.json` is best-effort. If it's missing or unreadable, re-pick a pair and overwrite it. Never raise on sidecar I/O.

## Testing

- Unit test for level pair selection across `N ∈ {1, 2, 3, 4, 5}` — verify constraints (`left < right`, both in valid ranges, edge cases handled).
- Unit test for sidecar persistence: pair is stable across two non-force calls; re-rolled on `force=True`.
- Unit test for fallback when `len(levels) < 2`: `cinematic_thumbnail.png` exists and equals the clean image bytes.
- Integration touch (manual): run a life-as-a project end-to-end, verify thumbnail file structure and visual output.
- Existing `test_formats_registry.py` test that asserts `levels[0].image_prompt` is forwarded — update to reflect the new outline schema (level 1 has no `image_prompt` requirement).

## Migration

- Existing projects on disk will have a `cinematic_thumbnail.png` that is the old Pillow-overlaid file. On next render with `force=True`, it gets overwritten with the split-progression version.
- No DB migration needed — `ScriptContent.cinematic_thumbnail_prompt` and `LevelMeta` schemas are unchanged in storage. Only the scriptwriter prompt changes (Claude stops emitting `levels[0].image_prompt`).
- Old scripts with a populated `levels[0].image_prompt` continue to deserialize fine; the new pipeline simply ignores that field at runtime.

## Open Questions

None remaining as of design freeze.
