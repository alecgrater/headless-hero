# Portable Visual Identity — Design

**Date:** 2026-09-13
**Status:** Approved, ready for implementation planning

## Goal

Clone `headless-hero` on another machine and generate a video using the same
visual identity — style presets, preset-scoped main characters, Eli frame
library, asset vault, brand profile, and non-secret app settings — without
copying anything out of band.

## Background

Visual identity is split across SQLite and the filesystem, and `data/` is
entirely gitignored today, so a fresh clone starts with no identity at all.

| Piece | Location | Size |
|---|---|---|
| Style presets (4 rows) | `style_presets` + `data/style/presets/{id}.png` | 9 MB |
| Preset characters (5 rows) | `style_preset_characters` + `{preset}/characters/*.png` | in the 9 MB |
| Active selections | `app_settings`: `ACTIVE_STYLE_PRESET_ID`, `ACTIVE_STYLE_PRESET_CHARACTER_ID_*` | trivial |
| Brand profile (1 row) | `brand_profiles` | trivial |
| Model / voice / subtitle settings | `app_settings`, ~60 non-secret keys | trivial |
| API keys | `app_settings`, 14 plaintext credentials | must never be committed |
| Eli frame library | `data/character/frames/` (1095 PNGs) | 982 MB |
| Asset vault | `data/projects/asset-vault/` (198 files) | 60 MB |

### Why plain git, not Git LFS

`data/character/frames/` was committed once in `84fb6417` and removed in
`c26a54ee`, but the blobs remain in history — which is why `.git` is already
973 MB. 1075 of the 1095 frames currently on disk are byte-identical to blobs
already in that history, so re-adding them is nearly free:

```
Eli frames      ~20 MB   (20 new files; 1075 dedupe against existing blobs)
Style presets    ~9 MB
Asset vault     ~60 MB
Character refs   ~2 MB
──────────────────────
TOTAL           ~90 MB   on top of an already-973 MB .git
```

Git LFS was rejected: it would cost $5/mo (GitHub's free tier is 1 GB storage),
requires installing `git-lfs` on every machine, and buys nothing against blobs
already sitting in plain history. Clone transfer grows 973 MB → ~1.06 GB.

### Public-repo constraint

`alecgrater/headless-hero` is **public**. History was audited: `data/db.sqlite`,
`.env`, and the asset vault have never been committed, so no credential has
leaked. Two consequences, both accepted by the user:

1. The settings snapshot must be a strict allowlist. Keys pushed to a public
   repo are scraped within minutes, and `app_settings` mixes 14 live
   credentials with ~60 harmless keys in one table.
2. Committing the asset vault publishes 198 generated images permanently.
   The user chose to proceed; the Eli frames are already public in history, so
   they disclose nothing new.

## Approach

Un-ignore the identity directories so assets are live-tracked in `data/`, and
carry the DB rows in a committed `data/identity.json` that is written through on
every mutation and seeded back on startup.

The rejected alternative was a curated `identity/` directory with explicit
`identity:export` / `identity:import` commands. It is safer against accidental
commits but adds a step to remember; the user chose live-tracking. The
deny-all gitignore (§1) plus the guard test (§2) exist specifically to recover
the safety that the rejected approach would have provided structurally.

## 1. `.gitignore` — deny-all, then re-include

Invert the current `data/` block into an allowlist so unlisted files are ignored
by default. This is what prevents `db.sqlite` and project renders from ever
being committed by accident.

```gitignore
# --- Runtime data ---
# Deny everything, then re-include only curated visual identity. New files are
# ignored by default, so db.sqlite (plaintext API keys) and project renders can
# never be committed by accident. Each level needs its own negation — git will
# not descend into an excluded directory.
/data/**
!/data/identity.json
!/data/style/
!/data/style/**
!/data/character/
!/data/character/frames/
!/data/character/frames/**
!/data/character/references/
!/data/character/references/**
!/data/character/thumbnail_references/
!/data/character/thumbnail_references/**
!/data/character/manifest.json
!/data/character/reference_selection.json
!/data/projects/
!/data/projects/asset-vault/
!/data/projects/asset-vault/**
backend/data/
```

Placement matters: this block must sit **above** the existing `.DS_Store` rule.
Gitignore is last-match-wins, and `!/data/style/**` would otherwise re-include
`data/character/.DS_Store`.

## 2. Guard test

`backend/tests/test_gitignore_identity.py` shells out to `git check-ignore` and
asserts both directions. This is the regression guard for the accidental-commit
risk; without it a single `.gitignore` edit re-opens the credential hole.

| Must be IGNORED | Must be TRACKED |
|---|---|
| `data/db.sqlite` | `data/identity.json` |
| `data/projects/<uuid>/renders/full_youtube.mp4` | `data/style/presets/<id>.png` |
| `data/projects/<uuid>/images/s1.png` | `data/style/presets/<id>/characters/<c>.cutout.png` |
| `data/test-lab/runs/x.json` | `data/character/frames/<f>.png` |
| `data/character/.DS_Store` | `data/projects/asset-vault/characters/<c>.png` |

## 3. `data/identity.json`

SQLite cannot be committed, so four tables' worth of identity travels as JSON:

```json
{
  "version": 1,
  "style_presets": [
    { "id": "…", "name": "…", "prompt": "…", "created_at": "…" }
  ],
  "style_preset_characters": [
    { "id": "…", "style_preset_id": "…", "name": "…", "appearance": "…",
      "vibe": "…", "reference_image_url": "…", "cutout_image_url": "…",
      "created_at": "…" }
  ],
  "brand_profile": {
    "name": "…", "art_style": "…", "color_palette": "…", "font": "…",
    "voice_id": "…", "content_modifiers": "…", "style_string": "…",
    "eli_position_json": "…"
  },
  "settings": { "ACTIVE_STYLE_PRESET_ID": "…" }
}
```

`platform_credentials` (YouTube OAuth tokens) never travels. Neither do
`scripts`, `project_config`, or any other per-project table — this is identity
only, not project data.

Datetimes serialize as timezone-aware ISO-8601 strings and parse back as
aware `datetime` objects, matching the `_utcnow()` convention in
`models/style_preset.py`.

## 4. Settings allowlist — `backend/pipeline/identity.py`

An explicit allowlist of exact keys and prefixes. Anything unlisted is excluded,
so a credential added later is safe by default.

**Exported:**

- `ACTIVE_STYLE_PRESET_ID`, `ACTIVE_STYLE_PRESET_CHARACTER_ID_*` (prefix)
- `SUBTITLE_COVERAGE_MODE`, `SUBTITLE_STYLE_*_ENABLED`
- `ELEVENLABS_TTS_MODEL`, `ELEVENLABS_STABILITY`, `ELEVENLABS_STYLE`, `ELEVENLABS_SPEED`
- `*_LLM_PROVIDER`, `*_MODEL`, `OPENAI_REASONING_EFFORT_*`
- `VISUAL_CANVAS_COLOR_PALETTE`, `IMAGE_PROVIDER`, `IMAGE_RATE_LIMIT_MS`
- Feature flags: `AI_VIDEO_*`, `LIFE_AS_A_*`, `ELI_ENABLED_DEFAULT`,
  `STYLE_PRESET_ENABLED_DEFAULT`, `HOOK_REFINEMENT_ENABLED`,
  `GOOGLE_IMAGE_BATCH_ENABLED`, `IMAGE_SCRAPER_FALLBACK_ENABLED`,
  `SHOW_SPEED_RENDER_BUTTON`
- `REPLICATE_MODEL`, `REPLICATE_OUTPUT_FORMAT`, `REPLICATE_PROMPT_UPSAMPLING`,
  `REPLICATE_SAFETY_TOLERANCE`, `QWEN_MODEL`

**Never exported:**

- All 14 credentials: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_AI_KEY`,
  `ELEVENLABS_API_KEY`, `FAL_API_KEY`, `REPLICATE_API_TOKEN`,
  `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `TWITCH_CLIENT_ID`,
  `TWITCH_CLIENT_SECRET`, `NEWS_API_KEY`, `PEXELS_API_KEY`, `YOUTUBE_API_KEY`,
  `GITHUB_CONTENTS_TOKEN`
- Machine-specific paths: `DOWNLOADS_DIR` (`/Volumes/256GB/…`) and
  `EXPORT_FOLDER` (an iCloud Drive path). These point at volumes that will not
  exist on the other machine.
- `_yt_channel_id:*`, a lookup cache that rebuilds itself.

Note `GOOGLE_CLIENT_ID` is sensitive while `ACTIVE_STYLE_PRESET_ID` is not, and
both end in `_ID` — this is why the allowlist is exact-match rather than
pattern-based.

## 5. Write-through

`identity.write_snapshot()` rewrites `data/identity.json` from the DB after every
identity mutation, so there is no command to remember. Call sites:

- `pipeline/style_presets.generate_preset`
- `api/style.delete_preset`, `set_active`, `create_preset_character`,
  `select_preset_character`
- `api/settings.save_keys`
- `api/brands.update_brand` (`backend/api/brands.py:61`)

The file is a few KB, so rewriting it wholesale is cheap. After creating a
preset, `git status` shows the new PNG and the updated JSON together.

`seed_identity()` must **not** trigger `write_snapshot()`, or a partially-seeded
DB could overwrite a good snapshot mid-startup.

## 6. Seeding on startup

New `seed_identity()` in `database.py`, called from `lifespan` in
`api/__init__.py` after `ensure_default_brand()` (which guarantees the brand row
exists to update) and **before** `load_keys_into_env(session)` at line 75, so
seeded model and provider settings reach the environment on first boot.

Behavior when `data/identity.json` exists:

- **JSON wins.** Presets, characters, brand fields, and allowlisted settings are
  upserted by id/key, overwriting local values. Combined with write-through the
  local JSON is always current, so this only ever propagates what was pulled.
- **Non-destructive.** Rows present in the DB but absent from the JSON are left
  alone. Deleting a preset is a per-machine UI action. Rationale: a destructive
  code path running on every backend start is a bad trade for four presets, and
  a truncated or malformed JSON would otherwise wipe the identity.
- Missing or unparseable JSON logs a warning and seeds nothing. Startup must not
  fail because of it.

A preset row whose PNG did not arrive needs no new handling: per CLAUDE.md a
preset is valid only when both the row and `data/style/presets/{id}.png` exist,
and the read-only preset API already hides fileless rows.

## 7. Fresh-machine flow

```
git clone … && npm install && uv sync && npm run dev
```

Identity seeds automatically on backend start. Two manual steps remain, both
unavoidable:

1. Enter API keys in Settings → API Keys.
2. Set the two storage paths (Exports folder, downloads folder).

Then generate a video. Documented as a new page under `docs/` and referenced
from CLAUDE.md, per the self-maintenance rule.

## 8. One-time commit

Roughly 1315 files added across `data/style/`, `data/character/`, and
`data/projects/asset-vault/`. `git add` reads ~1 GB to hash it; 1075 frames
dedupe, so net-new storage is ≈90 MB.

## Testing

- **gitignore guard** — `git check-ignore` assertions in both directions (§2).
- **Allowlist safety** — every known credential key is rejected; a synthetic key
  matching `_KEY|_SECRET|_TOKEN` is rejected; `DOWNLOADS_DIR` and
  `EXPORT_FOLDER` are rejected.
- **Snapshot round-trip** — write → read → identical rows, including
  timezone-aware datetimes.
- **Seeding idempotency** — run `seed_identity()` twice, no duplicate rows.
- **JSON-wins** — a differing local value is overwritten by the snapshot.
- **Non-destructive** — a local row absent from the snapshot survives seeding.
- **Degraded input** — missing and malformed `identity.json` both leave startup
  healthy.

Preset-touching tests use an isolated test engine, never the dev
`data/db.sqlite`, per the existing convention in CLAUDE.md.

## Non-goals

- Syncing project data (scripts, renders, exports) — identity only.
- Syncing OAuth tokens or API keys.
- Deleting rows across machines (§6).
- Any migration or compatibility shim for older snapshots; `version` exists to
  fail loudly, not to support v0.
