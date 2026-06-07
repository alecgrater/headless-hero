# YouTube Whitespace Discovery

Whitespace discovery finds YouTube channels that look under-supplied relative to demand: few uploads, but unusually strong view counts. It is designed to surface topic areas where a Headless Hero-style channel may have room to compete.

## What It Produces

The Discover -> Whitespace tab reads a static feed:

```text
frontend/public/discovery/youtube-whitespace.json
```

Each result includes the source query, channel name, channel URL, video count, view metrics, a whitespace score, and the top videos that made the channel qualify.

The tab is read-only. It shows the latest feed committed by GitHub Actions, not live data from YouTube.

## End-To-End Flow

1. The local app refreshes the creator content profile from existing scripts.
2. The backend sanitizes that profile into `discovery/content-profile-seed.json`.
3. If `GITHUB_CONTENTS_TOKEN` is configured, the backend uploads the seed to `alecgrater/headless-hero` on `main`.
4. The seed commit triggers `.github/workflows/youtube-whitespace.yml`.
5. GitHub Actions reads the seed and runs `scripts/youtube_whitespace.py` with the repo secret `YOUTUBE_API_KEY`.
6. The analyzer writes `frontend/public/discovery/youtube-whitespace.json`.
7. If the feed changed, GitHub Actions commits it back to `main`.
8. The local app sees new results after the repo is pulled or the packaged/static feed is refreshed.

## Required Keys

Two different keys are involved:

| Key | Where it lives | Purpose |
| --- | --- | --- |
| `GITHUB_CONTENTS_TOKEN` | Headless Hero -> Settings -> API Keys -> Discovery | Lets the local app upload the sanitized seed JSON to GitHub. |
| `YOUTUBE_API_KEY` | GitHub repo -> Settings -> Secrets and variables -> Actions | Lets GitHub Actions call the YouTube Data API when refreshing the feed. |

`YOUTUBE_API_KEY` may also exist locally for Discover's other YouTube features, but the remote whitespace workflow cannot see local app settings. It needs the same key added as a GitHub Actions secret.

## GitHub Token Permissions

Create a fine-grained personal access token:

- Resource owner: `alecgrater`
- Repository access: only `headless-hero`
- Repository permissions: `Contents` -> `Read and write`
- No other permissions are required

Save that token as `GITHUB_CONTENTS_TOKEN` in the app.

## Seed Privacy

The seed is intended to be safe to commit. It contains only sanitized profile summaries and deterministic search queries, such as common topics, typical keywords, audience profile, narration style, visual approach, script count, and average segment count.

It must never include:

- local SQLite data
- script bodies
- API keys or OAuth data
- generated asset paths
- project records
- prompts or full generated text

## Analyzer Rules

The V1 analyzer is intentionally conservative. A channel qualifies only when it roughly matches all of these:

- `total_videos <= 10`
- total demand of at least `200,000` views
- at least one video with `100,000` views
- discovered through one of the profile-derived search queries

The score is:

```text
log10(total_views + 1) * 100 / max(total_videos, 1)
```

This rewards channels with high view totals and very low supply. It is normal for early runs to return a small number of results.

## Why The App May Show Old Results

The app reads a local static JSON file. GitHub Actions may have generated a newer feed on `origin/main`, but the running app will not automatically fetch it from GitHub.

If GitHub Actions produced a new feed but the app still shows old results:

1. Pull `main` locally.
2. Restart the app.
3. If running from a built Electron/static frontend, rebuild the frontend or refresh `frontend/dist/discovery/youtube-whitespace.json` from `frontend/public/discovery/youtube-whitespace.json`.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| GitHub Actions succeeds but feed stays old | `YOUTUBE_API_KEY` secret is missing | Add `YOUTUBE_API_KEY` under repo Actions secrets. |
| Refresh profile says seed upload skipped | `GITHUB_CONTENTS_TOKEN` is missing locally | Add it in Settings -> API Keys -> Discovery. |
| Refresh profile says seed upload failed | Token lacks Contents write access or repo access | Recreate the fine-grained token with `Contents: Read and write` for `headless-hero`. |
| Whitespace tab shows zero results after a successful run | Analyzer found no channels under the strict V1 thresholds | Try later, refresh the profile after more scripts, or tune thresholds/query generation. |
| Logs show `playlistNotFound` warnings | YouTube returned a bad or inaccessible uploads playlist for a candidate channel | Non-fatal in current runs, but analyzer error handling can be improved to skip only that channel. |

## Current Limitations

- Results update through GitHub commits, not live in-app API calls.
- The UI does not yet distinguish "no matches" from "local feed is stale."
- Query generation is deterministic and profile-based, so weak or narrow profiles produce fewer candidates.
- The analyzer searches channels first; video-first discovery would likely find more opportunities.
- A bad candidate channel can still reduce coverage for a query. Future analyzer work should skip bad channels more locally.
