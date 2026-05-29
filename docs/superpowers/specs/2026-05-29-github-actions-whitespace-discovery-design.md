# GitHub Actions Whitespace Discovery Design

## Goal

Add a scheduled/dispatched discovery pipeline that uses the creator's local content profile as a sanitized search seed, runs YouTube whitespace analysis in GitHub Actions, and publishes a cached JSON feed that the Discover page can show in a new tab.

The feature should surface channels, niches, and topics with unusually high audience demand relative to visible supply, especially channels with very few videos and strong total or per-video view counts.

## User Experience

Settings -> API Keys adds one new Discovery credential:

- `GITHUB_CONTENTS_TOKEN`
- Label: GitHub Contents Token
- Description: Fine-grained GitHub token with Contents write access for uploading the sanitized discovery seed.

The repository and branch are hard-coded:

- Repository: `alecgrater/headless-hero`
- Branch: `main`

No repo or branch picker is exposed in Settings.

When the user clicks Refresh profile in Discover -> For You:

1. The app refreshes the local content profile exactly as it does today.
2. If `GITHUB_CONTENTS_TOKEN` is configured, the backend builds a sanitized discovery seed from the refreshed profile.
3. The backend uploads that seed to `discovery/content-profile-seed.json` in `alecgrater/headless-hero` on `main` using the GitHub contents API.
4. The UI shows success/warning feedback for the profile refresh and seed upload separately.

If the token is missing or the upload fails, profile refresh still succeeds locally. The user sees a warning that the remote whitespace refresh was not triggered.

Discover adds a third tab next to For You and Trending:

- Label: Whitespace
- Purpose: Show the latest GitHub Actions-produced opportunities.
- Data source: `frontend/public/discovery/youtube-whitespace.json`

The Whitespace tab displays the feed read-only in V1. Manual local regeneration is out of scope for this first pass.

## Sanitized Seed

The seed contains no local database dump, script bodies, API keys, OAuth data, generated asset paths, or project records.

Shape:

```json
{
  "version": 1,
  "generated_at": "2026-05-29T16:30:00Z",
  "source": "headless-hero-content-profile",
  "profile": {
    "script_count": 12,
    "common_topics": ["science myths", "hidden history"],
    "typical_keywords": ["evolution", "ancient", "psychology"],
    "audience_profile": "Curious adults interested in educational explainers.",
    "narration_style": "Fast, vivid, second-person educational narration.",
    "visual_approach": "High-contrast visual metaphors and clean comparisons.",
    "avg_segment_count": 8.0
  },
  "search_queries": [
    "science myths explained",
    "hidden history documentary",
    "psychology facts explained"
  ]
}
```

Search queries are derived deterministically from `common_topics`, `typical_keywords`, and short safe combinations. The app should cap the list to avoid wasting YouTube API quota. V1 target: 20-40 queries.

## GitHub Upload

Add a small backend integration for updating one file through GitHub's contents API.

Inputs:

- token from AppSettings/env key `GITHUB_CONTENTS_TOKEN`
- hard-coded owner/repo `alecgrater/headless-hero`
- hard-coded branch `main`
- path `discovery/content-profile-seed.json`
- JSON content

Behavior:

- Fetch the current file first to get its SHA when it exists.
- Create the file if missing.
- Update the file if present.
- Commit message: `Update discovery content profile seed`
- Log success and failure to the backend/dev dashboard.
- Raise a normal Python exception on upload failure so the API layer can return a warning payload without rolling back local profile refresh.

This integration should not shell out to `git`.

## GitHub Actions Workflow

Add `.github/workflows/youtube-whitespace.yml`.

Triggers:

- `push` paths: `discovery/content-profile-seed.json`
- `workflow_dispatch`
- Optional schedule: once per day, using the latest checked-in seed

Secrets:

- `YOUTUBE_API_KEY`

Permissions:

- `contents: write`

Workflow steps:

1. Check out the repo.
2. Set up Python.
3. Install minimal dependencies with `uv` or plain pip inside the workflow. The project rule says local Python operations use `uv`; using `uv` here keeps the workflow consistent.
4. Run a repository script that reads `discovery/content-profile-seed.json`.
5. Write results to `frontend/public/discovery/youtube-whitespace.json`.
6. Commit the results back to `main` only when the output changed.

The workflow should skip cleanly if `YOUTUBE_API_KEY` is missing or the seed file is absent.

## YouTube Whitespace Analyzer

Add a repo script, for example `scripts/youtube_whitespace.py`, adapted from the provided analyzer.

The analyzer uses the seed's `search_queries` as inputs. For each query it:

1. Searches YouTube for candidate channels and/or recent/high-view videos.
2. Resolves channel IDs.
3. Fetches channel statistics and uploads playlists.
4. Filters for low supply:
   - `total_videos <= 10`
5. Filters for demand:
   - channel or summed video views above `200000`
   - at least one video above a configurable minimum view count
6. Computes a whitespace score that rewards high views with low video count.

Initial score:

```text
score = log10(total_views + 1) * 100 / max(total_videos, 1)
```

The analyzer should then sort descending by score and keep the top 20.

The result record includes:

- rank
- score
- query
- channel name
- channel URL
- subscriber count when visible
- total videos
- channel total views
- summed analyzed video views
- max video views
- average video views
- top videos with title, URL, views, likes, published date
- reason string explaining the demand/supply mismatch
- fetched timestamp

The analyzer should dedupe channels across queries and retain the highest-scoring query match.

## Published Feed

Output path:

- `frontend/public/discovery/youtube-whitespace.json`

Shape:

```json
{
  "version": 1,
  "generated_at": "2026-05-29T17:00:00Z",
  "seed_generated_at": "2026-05-29T16:30:00Z",
  "source_queries": ["science myths explained"],
  "results": [
    {
      "rank": 1,
      "score": 582.1,
      "query": "science myths explained",
      "channel_id": "UC...",
      "channel_name": "Example Channel",
      "channel_url": "https://www.youtube.com/channel/UC...",
      "subscriber_count": 12000,
      "total_videos": 4,
      "channel_total_views": 850000,
      "video_views_total": 830000,
      "max_views": 600000,
      "avg_views": 207500,
      "reason": "4 videos with 850K total views from a profile-matched query.",
      "videos": [
        {
          "video_id": "abc123",
          "title": "Example video",
          "url": "https://www.youtube.com/watch?v=abc123",
          "views": 600000,
          "likes": 12000,
          "published_at": "2026-05-01"
        }
      ]
    }
  ]
}
```

The file lives under `frontend/public` so Vite serves it as a static asset and the packaged frontend can load a cached copy.

## Whitespace Tab UI

The Whitespace tab fetches `/discovery/youtube-whitespace.json` from the frontend public root.

UI elements:

- Header with generated timestamp and number of results.
- Refresh hint explaining that results update after Refresh profile uploads a seed and the GitHub Action completes.
- Empty state when the JSON file is absent or has no results.
- Error state for invalid JSON.
- Cards or table rows for each channel.

Each result shows:

- rank
- channel name linked to YouTube
- score
- source query
- videos count
- total views
- max views
- average views
- subscriber count if visible
- reason
- top video links

The tab should fit the current dark Discover styling and use hover states and `transition-colors` for interactive links/buttons.

## Error Handling

Profile refresh:

- Missing GitHub token: local profile refresh succeeds; remote seed upload is skipped with a warning.
- GitHub 401/403: show a warning that the token needs Contents write access.
- GitHub conflict or branch update race: refetch the file SHA once and retry one time.
- Network failure: show warning and log details.

Action:

- Missing YouTube key: workflow exits successfully with a clear log message and does not overwrite the last good feed.
- Quota/API error: write logs, fail the workflow, and keep the previous feed committed.
- No matches: commit a valid feed with an empty results array and metadata.

Frontend:

- Missing feed: show "No whitespace feed has been generated yet."
- Stale feed: show generated timestamp; do not block usage.

## Security And Privacy

- Never commit the local SQLite database.
- Never include script bodies, local file paths, generated assets, OAuth tokens, or API keys in the seed.
- Store only the GitHub token in AppSettings/env, masked through the existing API key UI.
- The checked-in seed is assumed public enough for the repository. Its contents should be profile summaries and search terms only.
- The workflow reads `YOUTUBE_API_KEY` from GitHub Secrets only.

## Tests

Backend tests:

- Seed builder includes only sanitized fields and deterministic search queries.
- Profile refresh still returns success when GitHub token is missing.
- GitHub upload integration uses create/update payloads correctly with mocked HTTP responses.
- Upload failure is surfaced as a warning without losing the refreshed local profile.

Analyzer tests:

- Filters out channels above the max video count.
- Filters out low-demand channels.
- Sorts by whitespace score descending.
- Dedupes the same channel across multiple queries.
- Writes the expected feed shape.

Frontend tests:

- API Keys section shows GitHub Contents Token under Discovery.
- Discover page includes the Whitespace tab.
- Whitespace tab renders results, empty state, and invalid/missing feed states.

Workflow validation:

- Use a small checked-in fixture seed and mocked analyzer tests locally.
- The live workflow requires `YOUTUBE_API_KEY` in GitHub Secrets and should be verified manually after merge.

## Out Of Scope

- Uploading the local SQLite database.
- Running the YouTube analyzer inside the desktop backend.
- User-editable repo/branch settings.
- Manual in-app triggering of GitHub Actions through the workflow dispatch API.
- Multi-user or private hosted discovery feeds.
- Full competitive saturation analysis beyond the first demand/supply score.
