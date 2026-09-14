# Two-Style Subtitles — Design

**Date:** 2026-09-14
**Status:** Approved (user delegated final decisions; see *Decisions made on the user's behalf*)

## Problem

The standard subtitle system ships three styles — `clean`, `kinetic`, `burst` — routed
per scene by deterministic heuristics in `remotion/src/effects/typography/subtitleRouting.ts`.
Measured against the only real project in the database (58 subtitled scenes with word
timings), the catalogue does not work:

| Style | Share | Why |
|---|---|---|
| `clean` | 76% | the default fall-through |
| `burst` | 24% | fires on a **substring** match of `but` / `then` / `finally` / `turns out` in the narration |
| `kinetic` | **0%** | requires ≤190 ms/word; the corpus runs 318 ms/word at p10, 395 ms median |

Three separate defects:

1. **`burst` is mis-designed.** Its hero word is `activeIndex` — whichever word is
   *currently being spoken* — so it is a travelling karaoke highlight, not the "one payoff
   word" its Settings copy promises. The hero word jumps 32px→40px and weight 850→900,
   which **reflows the line on every word**. It stacks `WebkitTextStroke: 1.5px` with
   `textShadow: 0 4px 0` plus a 24px blur, which at 40px erodes the glyph counters and
   reads as a gritty, aliased edge. Its trigger is uncorrelated with anything a viewer
   cares about.
2. **`kinetic` is unreachable.** Its gate cannot fire on human-paced narration.
3. **The substrate is unfinished.** `Subtitles.tsx` never calls `loadFont`; `clean` and
   `kinetic` set no `fontFamily` at all, and `burst` hardcodes the *string*
   `"Inter, Arial, sans-serif"` rather than the handle returned by `loadFont`. Inter is
   registered only as a side effect of `SubtitleScene`/`CaptionScene` being in the bundle.
   Base size is 32px on a 1920×1080 frame — 3.0% of frame height, against a 4–5% norm for
   burned-in captions.

## Measurement that drives the new rule

Pace is not a usable signal in this corpus. Across 58 scenes: p10 = 318 ms/word,
median = 395, p75 = 472, fastest scene = 280 (214 wpm). Any pace gate either never fires
or fires on everything.

Worse, short scenes are systematically **slower** per word, because they are dramatic
beats with pauses baked in:

```
scene_028   2w   510 ms/w   "Trophy."
scene_043   3w   533 ms/w   "Her finding?"
scene_038   3w   580 ms/w   "It's not wrong."
scene_027   4w   790 ms/w   "Diploma. Promotion letter."
```

So "few words **and** fast" is self-contradictory here — it selects for nothing. **Word
count alone is a strong signal.** Gating on `words ≤ 6` selects:

> "Trophy." · "And honestly?" · "Her finding?" · "It's not wrong." · "That's not a
> coincidence." · "Marriages can end." · "Diploma. Promotion letter." · "Happiness isn't
> something you win." · "Now, the metaphor isn't perfect." · "Happiness doesn't exactly
> file for divorce."

One outlier shows what the second term must be: `scene_059` — "But the maintenance logic
holds anyway." — is 4 words spread over **7.2 seconds**. Short, but not a punch beat. The
right companion is **total spoken span**, not per-word pace.

| Rule | Fires on |
|---|---|
| `words ≤ 6` | 11/58 (19%) — includes the 7.2 s outlier |
| `words ≤ 6 AND span ≤ 3.0 s` | **10/58 (17%)** — excludes it, keeps every real punch beat |

## Design

### 1. Catalogue: two styles

`clean` is the default. `kinetic` is the exception. **`burst` is deleted outright** — the
`BurstSubtitleOverlay` component, the `SUBTITLE_STYLE_BURST_ENABLED` setting, its routing
branch, the burst-cue term in `_subtitle_punch_score`, its Settings toggle, and the
`"burst"` member of `SubtitleStyle` in all three type definitions (Python, Remotion,
frontend).

Stored scenes carrying `subtitle_style: "burst"` normalize to **`"auto"`**, not `"clean"` —
`Scene.normalize_subtitle_style` already falls back to `"auto"` for unrecognized values, so
removing `"burst"` from `SUBTITLE_STYLES` gets this for free. `"auto"` means the scene is
re-routed by the new rule, so a short punchy scene that used to be `burst` becomes
`kinetic` rather than being pinned to `clean`. This matches the repo's forward-only bias.

### 2. Routing rule

```
kinetic  iff  word_count <= KINETIC_MAX_WORDS (6)
         and  spoken_span <= KINETIC_MAX_SPAN_SECONDS (3.0)
else     clean
```

`spoken_span` is `last.end_ms - first.start_ms` over the scene's `word_timestamps`.
Suppression is unchanged: title cards, `captions`, `stat_card`, and legacy `aha_subtitle`
still return `"none"`, and an explicit non-`auto` `scene.subtitle_style` still wins.

The cue-substring matching and the ≤190 ms/word pace gate are both deleted, from the
router *and* from `_subtitle_punch_score` (which governs `coverage="punchy"` — which scenes
get subtitles at all — and is a separate concern from which style they get).

**The coverage scorer must stay orthogonal to the style router.** The first implementation
replaced the deleted cue term with the kinetic rule itself at the same weight. Because no
other term could outrank it, every punch beat was selected before any other scene, and
punchy mode — the shipped configuration in `data/identity.json` — rendered **83%** kinetic
against the 17% this design targets. The exception became the rule. `_subtitle_punch_score`
therefore carries **no word-count or span term at all**; it ranks on figures in the
narration (+3), a terminal `?`/`!` (+2), and motion-heavy visual modes (+1). A test pins
that two scenes differing only in length score identically.

**The budget must also be spread across the script.** Those terms are sparse — on the
corpus, 38 of 59 scenes score 0.0 and exactly one contains a digit — so ranking the whole
script and taking the top N left 9 of 12 slots as score ties broken by array position.
Every subtitle landed in the first half and the back 45% of the video got none.
`_select_punchy_scene_ids` instead divides the script into one contiguous window per slot
and takes the best scorer in each; score decides which scene wins a window, position only
decides which window a scene is in. Windows are provably non-empty (`slots = ceil(0.2n) ≤ n`
for all `n ≥ 1`). Selections on the real script then span indices 1–55 of 58, six per half.

This also fixed an unnoticed short-form bug: `short_form_render` computes coverage over the
whole script and slices per segment, so under the old top-N, segments 4–7 of the real
script rendered with **zero** subtitles. Every segment now gets at least one.

**Residual correlation is two scenes, and that is acceptable.** Kinetic measures 17% under
`coverage="all"` and 33% under `punchy` (4 of 12) on the real script. Only two of those four
come from the `[!?]$` term — short punch beats often end in a question mark; the other two
win their windows on `visual_mode`, which is fully orthogonal. Removing `[!?]$` would bring
punchy to 16.7% against 17.0%, but would leave 38 of 59 scenes tied at 0.0 and make
windowing the only discriminator, trading a two-scene correlation for the ranking signal.
The term stays. Note that with a 12-slot budget one scene moves the share by ~8 points, so
the tests assert counts and an absolute ceiling rather than a ratio of a ratio.

**The thresholds live in Python and ship to the renderer in props.** `subtitle_settings`
already flows from `remotion_render.subtitle_settings_from_env()` into `FullVideo` and
`ShortFormVideo`, so it gains `kinetic_max_words` and `kinetic_max_span_seconds`. The TS
router reads them from settings with the same values as a fallback default. One source of
truth, and because `subtitle_settings` is already inside `subtitle_render_fingerprint`,
changing a threshold invalidates prior renders automatically.

### 3. Kinetic's new look ("K2")

The current kinetic — white cards, black text, red active word, hard offset shadow — is
deleted. It is a different visual language from `clean`, and alternating them mid-video
reads as a channel change rather than an emphasis.

The replacement shares `clean`'s spine exactly — same typeface, same weight family, same
accent colour — and differs only in *behaviour*:

- 1.25× `clean`'s font size
- no plate
- words stagger in with a y-offset as they are spoken, rather than appearing as a block
- the active word pops harder than `clean`'s (1.14 vs 1.07) and is tracked tighter

Prototyped and chosen against the two alternatives (today's cards scaled up; an
accent-plate-behind-the-active-word variant) in an animated harness built over real scene
images and real ElevenLabs timings.

### 4. Substrate

- `Subtitles.tsx` loads Inter via `@remotion/google-fonts/Inter` and uses the **returned
  handle**, shared by both styles. No hardcoded family strings.
- Base horizontal size 32px → **52px** (4.8% of frame height). Vertical scales
  proportionally from the same base rather than carrying independent literals.
- Every per-word emphasis is expressed as `transform` only, never as a font-size or
  weight change, so **the line can never reflow mid-phrase**. This is the specific defect
  that made `burst` look broken, and the invariant that stops it recurring.

### 5. Settings

Three style toggles is the wrong shape for two styles, and `clean` is the floor — it
cannot be disabled. Settings → Subtitles becomes:

- **Coverage** — `all` | `punchy` (unchanged)
- **Kinetic accents** — on/off, backed by the existing `SUBTITLE_STYLE_KINETIC_ENABLED` key

`SUBTITLE_STYLE_BURST_ENABLED` and `SUBTITLE_STYLE_CLEAN_ENABLED` are removed from the
settings API, the defaults map, and the `pipeline.identity` export allowlist. Stale rows
left in `AppSettings` are inert (nothing reads them) and drop out of `data/identity.json`
on the next `write_snapshot`, so no migration is needed.

`enabled_styles` keeps its array shape in the render props — `["clean"]` or
`["clean", "kinetic"]` — so the renderer's fallback logic and the fingerprint stay
meaningful. `resolveDisabledFallback` collapses to: kinetic disabled → clean.

### 6. Observability

`render_full_video` emits one `logger.info` line per render reporting the resolved
clean/kinetic/suppressed split. The 17% rate is measured from a **single** video; if a
future script has a different rhythm the rate will move, and this makes the drift visible
on the dev dashboard instead of discoverable only in a finished render.

### 7. Cache

`SUBTITLE_ROUTER_VERSION` bumps to `standard-subtitle-router-v2`. It is already inside
`subtitle_render_fingerprint`, so every prior render invalidates. `enabled_styles` also
changes shape, which would invalidate independently.

## Decisions made on the user's behalf

| Decision | Choice | Why |
|---|---|---|
| Kinetic's look | K2 (shared spine) over today's cards or an accent-plate variant | alternating two visual languages mid-video reads as a channel change; K2 keeps one identity and expresses emphasis through motion |
| Clean's plate | kept | legibility insurance on bright/busy frames, and it is what ships today — the user asked to keep clean |
| Base size | 52px | 4.8% of frame height, inside the 4–5% norm; 32px is what the heavy shadows were compensating for |
| Legacy `burst` scenes | → `"auto"` (re-route) not `"clean"` (pin) | forward-only bias; a short punchy ex-burst scene should become kinetic |
| Threshold ownership | Python, shipped in props | avoids a second copy of the rule in TS drifting from the one the punch-score logger uses |
| `SUBTITLE_STYLE_CLEAN_ENABLED` | deleted, not kept-and-ignored | with two styles, clean is the floor; a toggle that must never be off is a trap |

## Out of scope

- **Phrase grouping is unchanged** (8 words / sentence punctuation / >300 ms pause). If it
  is also wrong that deserves its own measurement pass, and changing it here would confound
  the evaluation of the style change.
- `CaptionScene`, `StatCard`, title cards, and the legacy `SubtitleScene` (`aha_subtitle`)
  are separate text systems and are not touched.
- Coverage scoring keeps its `punchy` mode and its 20% ceiling; the burst-cue and dead
  pace terms are removed, and it gains the hard constraint above that it may not encode
  the routing rule.

## Testing

- **Router unit tests** (`SubtitleRouting.test.ts`): the boundary cases on both terms —
  6 words/3.0 s in, 7 words out, 6 words/3.1 s out; suppression paths; explicit-style
  override; kinetic-disabled fallback to clean.
- **Overlay tests** (`SubtitleOverlay.test.tsx`): burst treatment gone; both styles resolve
  one font handle; the no-reflow invariant — assert no rendered word span carries a
  per-word `fontSize` or `fontWeight` difference within a phrase.
- **Backend** (`test_remotion_render.py`): `subtitle_settings_from_env` shape including the
  two thresholds; `_subtitle_punch_score` no longer rewards cue substrings;
  `_subtitle_styles_for_render` unchanged under `coverage="all"`.
- **Settings** (`SubtitlesSection.test.tsx`, backend settings tests): the two-control shape;
  removed keys rejected/absent; identity allowlist no longer exports them.
- **Regression**: a scene with `subtitle_style: "burst"` loads as `"auto"`.
