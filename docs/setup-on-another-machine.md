# Setting Up on Another Machine

The visual identity — style presets, preset-scoped main characters, the Eli
frame library, the asset vault, the brand profile, and non-secret settings —
travels with the repository. Cloning is enough to start generating video in the
house style; only credentials and storage paths need re-entering.

## What travels, and how

| Piece | How it travels |
|---|---|
| Style preset images | Tracked files under `data/style/presets/` |
| Preset character references + cutouts | Tracked files under `data/style/presets/{id}/characters/` |
| Eli frame library | Tracked files under `data/character/frames/` |
| Asset vault cutouts | Tracked files under `data/projects/asset-vault/` |
| Style preset + character DB rows | `data/identity.json` |
| Brand profile | `data/identity.json` |
| Model routes, subtitle styles, voice params, feature flags | `data/identity.json` |
| **API keys** | **Does not travel — re-enter them** |
| **Exports / downloads paths** | **Does not travel — re-set them** |
| Projects, scripts, renders | Does not travel (ignored) |

## First run on a new machine

```bash
git clone https://github.com/alecgrater/headless-hero.git
cd headless-hero
npm install
uv sync --project backend
npm run dev
```

The backend applies `data/identity.json` on startup, so presets and characters
are present the first time the app opens. Then:

1. **Settings → API Keys** — enter `ANTHROPIC_API_KEY`, `GOOGLE_AI_KEY`, and
   `ELEVENLABS_API_KEY` at minimum. Optional: `GOOGLE_CLIENT_ID` /
   `GOOGLE_CLIENT_SECRET` for YouTube upload, `FAL_API_KEY` or
   `RUNWAYML_API_SECRET` for AI video.
2. **Settings → General → Storage** — set the Exports folder. It defaults to
   `~/Headless Hero Videos`; the previous machine's path is deliberately not
   synced, since it may point at an external volume.
3. **Settings → Style Presets** — confirm the expected preset and character are
   active.

## How the snapshot stays current

`data/identity.json` is rewritten automatically whenever identity changes —
creating or deleting a preset, adding or selecting a character, saving settings,
or updating the brand. There is no export command to remember: after making a
preset, both the new PNG and the updated JSON show up in `git status`. Commit
and push them, then pull on the other machine.

On startup the snapshot **wins** over local rows, so a pulled change takes
effect on the next launch. Seeding is **non-destructive**: a preset deleted on
one machine is not deleted on the other, so delete it in both places.

## What `.gitignore` allows

`data/` is deny-all with explicit re-includes, so anything new under `data/` is
ignored until someone opts it in. This is deliberate — `data/db.sqlite` holds
API keys in plaintext and `data/projects/` holds every render, and the
repository is public.

`backend/tests/test_gitignore_identity.py` asserts both directions. If you add a
new kind of identity asset, add the negation **and** a case to that test.
