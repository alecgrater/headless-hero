# AI Video Scene Duration — Decision History

This doc records *why* AI-video scene-length handling works the way it does, what
we tried, what we deliberately rejected, and what is still unsolved. Read it
before changing fal video generation, the renderer's video/image fallback, the
AI-video routing ceiling, or the life-as-a scene splitter — the current behavior
is the result of several connected fixes, and the obvious "simpler" changes were
considered and rejected for reasons captured below.

Last updated: 2026-06-24.

## The symptom that started this

Exporting "Your Life At Every Level Of Working At Burger King" (a `life-as-a`
project), scenes that were `visual_mode="video"` showed up in the final render as
**still images**, not motion. Three scenes were affected (006, 024, 034). All
three fal clips existed on disk and were real generations — they were just
dropped from the render.

## Root cause #1 — the clip was shorter than the narration

- The narration is the timing source of truth. scene_006 = 8.0s, 034 = 8.7s,
  024 = 15.4s of audio.
- The fal clips were all **~5.03s** (≈ 81 frames ÷ 16 fps — Wan's default).
- `pipeline/remotion_render.py:_scene_video_render_plan` will slow a short clip
  to fill narration **only up to `MAX_AI_VIDEO_SLOWDOWN_RATIO = 1.25`**. Beyond
  that, heavy slow-motion looks broken, so it falls back to the anchor still for
  the whole scene. A 5s clip therefore covers at most ~6.3s of narration.
- The deeper cause: `integrations/fal_video_client.py` was on the
  `fal-ai/wan/v2.2-a14b/image-to-video/**turbo**` model, which emits a **fixed**
  ~5s clip and exposes **no duration parameter** (confirmed against the fal
  schema). It also recorded `duration_seconds` in `.source.json` as the
  *requested* scene length (8.0s), masking that the clip was only 5s.
- Mismatch that let it through: the `life-as-a` analyzer ceiling allowed video
  scenes up to `single_visual_max` (8s), but turbo + the 1.25x cap could only
  deliver ~6.3s. So the router green-lit scenes the provider couldn't fill.

### Fix #1 (commit e151fdfb)

- Switched the default fal model to the **non-turbo**
  `fal-ai/wan/v2.2-a14b/image-to-video`, which accepts `num_frames` (17–161) and
  `frames_per_second`.
- Size each clip to the narration: `num_frames = ceil(duration * 16) + 1`,
  clamped to `[17, 161]` (≈10s max), `frames_per_second = 16`,
  `interpolator_model="none"` for predictable duration. Gated behind
  `_model_supports_frame_count` so a `/turbo` override never gets `num_frames`.
- Record the **actual** clip duration in metadata (fal's reported value → else
  `num_frames/fps` → else scene duration). The renderer still re-probes with
  ffprobe; metadata is only a fallback.
- Separate non-turbo pricing (`FAL_WAN_22_PER_VIDEO_BY_RESOLUTION`).
- Capped AI-video routing at `media_analyzer.AI_VIDEO_MAX_CLIP_SECONDS = 10.0`
  (`min()` with the per-format setting) so scenes no single clip can fill are
  never routed to video and don't silently fall back to a still.

### Alternatives rejected for #1

- **Stay on turbo + lower the routing ceiling to ~6.2s.** Cheaper/faster and
  needs no provider change, but it makes every >6.3s scene a still — the
  opposite of the goal (we *want* these as video). Kept only as the fallback if
  someone overrides `FAL_VIDEO_MODEL` back to turbo.
- **Raise `MAX_AI_VIDEO_SLOWDOWN_RATIO`.** Stretching a 5s clip to 15s is 3x
  slow-motion — looks broken. The 1.25x cap exists for a reason; left untouched.
- **Loop/hold the clip to fill the gap.** Explicitly disallowed elsewhere ("no
  silent looping or held final frame while camera FX continue").

## Root cause #2 — overlong single-sentence beats were never split

scene_024 had 15.4s of narration as **one beat**. `life-as-a` targets 5–9s
beats and has a pre-voiceover splitter (`formats/life_as_a._split_life_as_a_scenes`),
but it kept scene_024 whole:

- Its estimate (16s) exceeded the effective max (14s) — the duration check
  *wanted* to split it.
- But its narration is a **single grammatical sentence** (a comma/em-dash list
  with one terminal period), and the splitter's only cut points were sentence
  boundaries (`_SENTENCE_SPLIT_RE` on `.!?`). The `or len(sentences) <= 1` guard
  then kept it whole regardless of length.
- This affected 6 scenes in that one project (004, 024, 027, 039, 040, 047).

### Fix #2 (commit 31dad39b)

Added a **clause-delimiter fallback** (`_CLAUSE_SPLIT_RE = (?<=[—–;:,])\s+`),
used **only** when a scene is over the max **and** has ≤1 sentence. Delimiters
stay attached to each clause so the chunked narration reproduces the original
text exactly. A sentence with no clause delimiters still stays whole.

### Alternatives rejected for #2

- **Scriptwriter-prompt-only** (tell the LLM not to emit run-on list beats).
  Prevents future cases but doesn't fix existing ones and isn't a deterministic
  guarantee. We chose the deterministic splitter as the safety net; tightening
  the prompt remains a reasonable *additional* future step.

## Related fix — characters appeared to talk (commit 04941caa)

On-screen characters (who are NOT the narrator) were moving their mouths,
reading as a second speaker. The animation prompt
(`video_gen._build_animation_prompt`) now states any character is a silent
subject and forbids talking/lip-sync in both the positive directive and the
negative list. The prompt is part of the video cache marker, so changing it
regenerates clips.

**This fix is UNVERIFIED.** The clips were never regenerated after the prompt
change (fal is unreachable from the dev sandbox — egress proxy 403s `fal.run`),
so we don't yet know whether the prompt alone stops the talking. Because the
observed clips still show talking mouths, AI video was turned **off by default**:
`AI_VIDEO_ENABLED` defaults to `false` and was flipped off in the local DB. When
re-enabling, first regenerate the affected clips and confirm mouths stay closed;
if the prompt isn't enough, the lever is the provider's dedicated
negative-prompt parameter / a motion-mask, not another tweak to the prompt text
(the in-prompt `_NEGATIVE_MOTION_GUIDANCE` list already covers talking). The Settings → Visuals → "AI Video"
toggle carries a short note flagging this.

## Current constraints (the system as it stands)

| Constraint | Value | Where |
| --- | --- | --- |
| Max fal clip | 161 frames ÷ 16 fps ≈ **10.06s** | `fal_video_client.FAL_MAX_FRAMES` |
| Renderer slowdown tolerance | **1.25x** | `remotion_render.MAX_AI_VIDEO_SLOWDOWN_RATIO` |
| AI-video routing ceiling | `min(format_setting, **10.0s**)` | `media_analyzer.AI_VIDEO_MAX_CLIP_SECONDS` |
| life-as-a beat target / max | 8s / 12s (settings) | `LIFE_AS_A_*_SECONDS` |
| Runway (alt provider) | requests 10s clips for scenes >6.5s | `runway_video_client.duration_for_scene` |

## Known remaining gaps / where to look next

1. **Hard ~10s ceiling.** No current provider path fills a scene longer than
   ~10s with one clip. scene_024 (15.4s) still becomes a still even after Fix #1.
   To make very long beats video you'd need multi-clip stitching, a longer-clip
   model, or to ensure the splitter produces ≤10s beats *before* video routing.
2. **Fixes are forward-only.** Fix #2 runs during *script generation* (before
   voiceover); it does not retroactively re-split existing saved projects. The
   Burger King project's scene_024 stays long unless the script is regenerated.
3. **Multi-sentence scenes can still exceed the max.** The splitter decides on
   the LLM's pre-voiceover `duration_estimate_seconds`; when that underpredicts,
   actual TTS can overshoot (e.g. 13–15s) and there is **no post-voiceover
   re-split by design** (post-audio LLM rewrite is forbidden). These are usually
   `full_frame` stills, so far less harmful than a dropped video. If this
   becomes a problem, the lever is a better pre-voiceover duration estimate, not
   a post-audio splitter.
4. **Clause fragments can sound clipped.** Each chunk is voiced separately, so a
   mid-sentence fragment (ending in a dangling comma/dash) gets its own TTS beat.
   Accepted as a tradeoff for list-style sentences. If quality suffers, consider
   grouping clauses more conservatively or smoothing fragment intonation.
5. **Cost/quality of non-turbo.** Non-turbo costs more and is slower than turbo
   (rough estimate ~2x; verify against live fal pricing). It was chosen because
   it is the only fal path that can size clips to narration.

## Key files / symbols

- `backend/integrations/fal_video_client.py` — model default, `_frames_for_duration`,
  `_model_supports_frame_count`, `_per_video_cost`, `_extract_video_duration`.
- `backend/integrations/runway_video_client.py` — alt provider, `duration_for_scene`.
- `backend/pipeline/remotion_render.py` — `_scene_video_render_plan`,
  `_video_clip_duration`, `MAX_AI_VIDEO_SLOWDOWN_RATIO`.
- `backend/pipeline/media_analyzer.py` — `AI_VIDEO_MAX_CLIP_SECONDS`,
  `AI_VIDEO_MAX_ROUTED_DURATION_SECONDS`, routing ceiling clamp.
- `backend/pipeline/formats/life_as_a.py` — `_split_life_as_a_scenes`,
  `_split_sentences`, `_split_clauses`, `_CLAUSE_SPLIT_RE`, `_chunk_sentences`.
- `backend/pipeline/video_gen.py` — `_build_animation_prompt` (silent-subject rules).

## Commit trail

- `04941caa` — stop AI-video characters talking/lip-syncing.
- `e151fdfb` — non-turbo fal model + per-scene `num_frames` + 10s routing cap.
- `1b12f9fc` — unit tests for the fal clip-sizing helpers/payload.
- `31dad39b` — clause-split fallback for overlong single-sentence life-as-a beats.
