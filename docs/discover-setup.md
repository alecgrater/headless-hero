# Getting the Discover Dashboard Working

## 1. Install Python dependencies

The new dependencies (`pytrends`, `feedparser`, `newsapi-python`, `thefuzz`) were added to `backend/pyproject.toml`. If you haven't synced since the commit:

```bash
cd backend
uv sync
```

## 2. Configure API keys

Open the app and go to **Settings → API Keys**. Two new keys are available:

| Key | Required? | What it unlocks |
|-----|-----------|-----------------|
| `YOUTUBE_API_KEY` | Optional | YouTube trending + competitor velocity + saturation checks |
| `NEWS_API_KEY` | Optional | NewsAPI article fetching (supplements RSS) |

### Getting a YouTube API key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use your existing one)
3. Enable **YouTube Data API v3** under APIs & Services → Library
4. Create an API key under APIs & Services → Credentials
5. Paste it into Settings as `YOUTUBE_API_KEY`

**Note:** This is a separate key from your existing `GOOGLE_AI_KEY` (which is for Gemini image generation). The YouTube Data API uses a plain API key, not an OAuth client.

### Getting a NewsAPI key

1. Go to [newsapi.org](https://newsapi.org/register)
2. Sign up for a free developer account
3. Copy your API key
4. Paste it into Settings as `NEWS_API_KEY`

**Free tier limits:** 100 requests/day, articles up to 1 month old. More than enough for this use case.

## 3. What works without any API keys

Even with zero keys configured, two sources work out of the box:

- **Reddit** — uses the public JSON API (no auth needed, just rate-limited)
- **RSS feeds** — parses Scientific American, Psychology Today, Ars Technica, Quanta Magazine, Smithsonian, New Scientist

So you can hit Refresh immediately and get results. The YouTube and NewsAPI sources will log warnings and return empty results until their keys are added.

## 4. Using the Discover dashboard

1. Click the **globe icon** in the top header bar (between Save controls and the Settings gear)
2. Click **Refresh** to start fetching from all sources
3. Watch the per-source progress indicators (checkmarks appear as each source completes)
4. Browse the ranked topic cards — each shows:
   - **Score** (0–100) with color coding (green 80+, amber 60–79, gray below)
   - **Score breakdown bar** showing the 4 signal components
   - **Source chips** (YouTube, Reddit, Trends, News)
   - **Format fit rationale** from Claude
   - **Evidence snippet** summarizing the trend signals
5. Use filters: source chips, sort dropdown, breakout-only toggle
6. Click **Generate Ideas →** on any topic to generate ideas seeded with that topic's context
7. You'll be taken to the Ideation page with pre-loaded results — continue normally from there

## 5. How scoring works

Each topic gets a weighted composite score:

| Signal | Weight | Source |
|--------|--------|--------|
| Search velocity | 35% | Google Trends rise percentage |
| Competitor view rate | 30% | YouTube competitor channel video velocity |
| Reddit engagement | 20% | Upvotes × comment ratio from target subreddits |
| Format fit | 15% | Claude evaluation of suitability for educational listicle format |

Modifiers:
- **Saturation penalty (−15):** If >20 YouTube videos cover this topic in the last 3 weeks
- **First mover bonus (+10):** Trending on Reddit/Trends but NOT saturated on YouTube

## 6. Troubleshooting

**"Some sources failed" warning after refresh**
This is normal if a source times out or rate-limits you. Results from successful sources still appear. Try again later.

**Google Trends returns nothing**
`pytrends` scrapes Google Trends and can get rate-limited. Wait a few minutes and retry. This is the most unreliable source.

**YouTube returns nothing but key is configured**
Check that YouTube Data API v3 is enabled in your Google Cloud project. The key needs the YouTube Data API specifically, not just a generic Google API key.

**Reddit returns very few topics**
Reddit's public API only returns posts from the last 24 hours in rising/hot. If the target subreddits are quiet, fewer topics come back. This is expected.
