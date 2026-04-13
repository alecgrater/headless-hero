# Headless Hero

AI-powered desktop app for creating faceless educational YouTube content. Full pipeline from idea to published video — in one tool.

Replace the fragmented workflow of ChatGPT + ElevenLabs + Midjourney + InVideo + Canva with a single integrated application that enforces brand consistency across every video.

![Architecture Diagram](media/architecture.png)

## What It Does

Headless Hero handles the entire content creation pipeline:

1. **Idea Generation** — AI suggests video topics for your niche with keyword analysis
2. **Script Writing** — Generates segmented scripts with visual storytelling arc, hooks, and transitions
3. **Timeline Editing** — Lane-based timeline editor with scene editing, split, merge, and full editorial control
4. **Image Generation** — Per-scene AI illustrations via Google Gemini or Replicate Flux
5. **Voiceover** — AI voice synthesis with voice cloning support via ElevenLabs
6. **Video Rendering** — Remotion-based frame-by-frame rendering with kinetic captions, zoom punch, and Eli character overlay
7. **Thumbnail & SEO** — AI-generated thumbnails and optimized metadata for YouTube
8. **YouTube Publishing** — Direct upload via OAuth2

## Architecture

The app is structured as four layers:

| Layer | Tech | Role |
|-------|------|------|
| **Desktop Shell** | Electron 41 | Window management, IPC bridge, system integration |
| **Frontend** | React 19, Vite, TypeScript, Tailwind 4 | UI views: dashboard, ideation, script editor, timeline, settings |
| **Backend** | FastAPI, Python 3.12, uv, SQLite (SQLModel) | REST API on `:8420`, database, static file serving |
| **Pipeline** | Claude API, Google Gemini, ElevenLabs, Remotion, FFmpeg | AI orchestration: ideation, scriptwriting, image gen, TTS, video rendering, SEO, publishing |

### API Routes

| Endpoint | Purpose |
|----------|---------|
| `/api/brands` | Brand profile CRUD |
| `/api/ideas` | AI topic generation |
| `/api/scripts` | Script generation and editing |
| `/api/visuals` | Image generation (single + batch + multi-frame) |
| `/api/voice` | TTS generation, batch audio, voice cloning, voice listing |
| `/api/render` | Video rendering (full, export test, status, export audio) |
| `/api/fx` | AI-powered FX generation (kinetic captions, zoom punch) |
| `/api/eli` | Eli character animation keyframe generation |
| `/api/character` | Character frame library management |
| `/api/thumbnail` | Thumbnail generation |
| `/api/seo` | SEO metadata generation |
| `/api/publish` | YouTube OAuth, upload, status, history |
| `/api/settings` | API key management |
| `/dev/` | Dev dashboard (log viewer, job monitor, API tester, DB inspector, usage tracker) |

### External Services

| Service | Purpose | Env Var |
|---------|---------|---------|
| [Anthropic Claude](https://console.anthropic.com/) | Ideas, scripts, SEO, thumbnail concepts | `ANTHROPIC_API_KEY` |
| [Google Gemini](https://ai.google.dev/) | Image generation (gemini-2.5-flash) | `GOOGLE_AI_KEY` |
| [Replicate](https://replicate.com/) | Alternative image generation (Flux) | `REPLICATE_API_TOKEN` (optional) |
| [ElevenLabs](https://elevenlabs.io/) | Text-to-speech + voice cloning | `ELEVENLABS_API_KEY` |
| [YouTube Data API v3](https://console.cloud.google.com/) | Video upload | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` |
| FFmpeg 8.1 | Audio concatenation | System install |

## Prerequisites

- **Node.js** 18+
- **Python** 3.12+
- **[uv](https://docs.astral.sh/uv/)** (Python package manager)
- **FFmpeg** 8+

```bash
# macOS
brew install node python uv ffmpeg

# Ubuntu/Debian
sudo apt install nodejs python3 ffmpeg
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/your-username/headless-hero.git
cd headless-hero

# 2. Set API keys (add to ~/.zshrc for persistence)
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_AI_KEY="..."
export ELEVENLABS_API_KEY="..."

# Optional — only for YouTube publishing
export GOOGLE_CLIENT_ID="...apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="GOCSPX-..."

# 3. Install dependencies
npm install
cd backend && uv sync && cd ..
cd frontend && npm install && cd ..

# 4. Run the app (starts backend + frontend + Electron)
npm run dev
```

The app opens an Electron window. The backend runs on `http://127.0.0.1:8420` and the frontend dev server on `http://localhost:5173`.

## Development

### Available Scripts

| Command | What It Does |
|---------|-------------|
| `npm run dev` | Start backend + frontend + Electron concurrently |
| `npm run dev:frontend` | Frontend only (Vite on `:5173`) |
| `npm run dev:backend` | Backend only (uvicorn on `:8420` with hot reload) |
| `cd frontend && npm run build` | Build frontend for production |

### Project Structure

```
headless-hero/
├── electron/
│   ├── main.js              # Electron main process, spawns backend
│   └── preload.js           # IPC bridge → window.api
├── frontend/
│   └── src/
│       ├── api.ts            # API client, assetUrl(), error interceptor
│       ├── App.tsx           # Root component with view routing
│       ├── components/
│       │   ├── brand/        # Voice setup modal + voice cloning
│       │   ├── dashboard/    # Project list and management
│       │   ├── ideation/     # Idea generation UI
│       │   ├── script/       # Script generation + editing
│       │   ├── settings/     # API keys, voice, character, general settings
│       │   ├── shared/       # Shared components (EliPositionPicker)
│       │   ├── timeline/     # Timeline editor (lanes, blocks, properties,
│       │   │                 #   export, render/publish state hooks)
│       │   ├── ErrorBoundary.tsx
│       │   ├── GenerationProgressBar.tsx
│       │   └── ToastContainer.tsx
│       └── types/            # TypeScript interfaces (script, audio, render, publish, etc.)
├── backend/
│   ├── config.py            # Shared constants (DATA_DIR, FPS, dimensions, utilities)
│   ├── database.py          # SQLite engine + session dependency
│   ├── api/
│   │   ├── __init__.py       # FastAPI app, router registration, static mount
│   │   ├── brands.py         # Brand CRUD endpoints
│   │   ├── ideas.py          # Idea generation endpoint
│   │   ├── scripts.py        # Script generation + CRUD
│   │   ├── visuals.py        # Image generation (single + batch)
│   │   ├── voiceover.py      # TTS generation + voice cloning
│   │   ├── render.py         # Video render endpoints + job status
│   │   ├── fx.py             # FX generation (kinetic captions, zoom punch)
│   │   ├── eli.py            # Eli animation keyframe generation
│   │   ├── character.py      # Character frame library management
│   │   ├── thumbnail.py      # Thumbnail generation
│   │   ├── seo.py            # SEO metadata generation
│   │   ├── publish.py        # YouTube OAuth + upload
│   │   ├── settings.py       # API key management
│   │   └── generation.py     # Generation time estimates
│   ├── pipeline/
│   │   ├── ideation.py       # Idea generation via Claude
│   │   ├── scriptwriter.py   # Script generation via Claude
│   │   ├── image_gen.py      # Image gen: prompt → Gemini → local file
│   │   ├── voiceover.py      # TTS: ElevenLabs → MP3 + duration
│   │   ├── remotion_render.py # Remotion CLI orchestration → full video
│   │   ├── video_render.py   # Audio concatenation via FFmpeg
│   │   ├── ffmpeg_builder.py # FFmpeg CLI arg construction
│   │   ├── render_jobs.py    # Background job tracking with threading
│   │   ├── fx_generator.py   # Claude-powered FX assignment
│   │   ├── eli_animator.py   # Claude-powered Eli animation
│   │   ├── character_frames.py # Eli frame library generation
│   │   ├── thumbnail.py      # Claude concepts + Gemini + FFmpeg composite
│   │   ├── seo.py            # SEO metadata via Claude
│   │   ├── publishing.py     # YouTube upload orchestration
│   │   ├── title_card.py     # Per-segment title card generation
│   │   ├── title_card_composer.py # Composite title card grid assembly
│   │   ├── refine.py         # Scene refinement
│   │   └── modifiers/        # Content modifier plugin system
│   ├── integrations/
│   │   ├── claude_client.py       # Anthropic SDK wrapper
│   │   ├── google_image_client.py # google-genai SDK wrapper
│   │   ├── elevenlabs_client.py   # ElevenLabs httpx wrapper
│   │   ├── youtube_client.py      # YouTube Data API v3 wrapper
│   │   ├── replicate_client.py    # Replicate API wrapper (optional)
│   │   ├── image_client.py        # Image provider router (Google/Replicate)
│   │   ├── google_image_scraper.py # Google Image scraping for real photos
│   │   └── usage_tracker.py       # API usage recording + pricing constants
│   ├── models/
│   │   ├── brand.py          # BrandProfile table + schemas
│   │   ├── script.py         # Script table + Scene/Segment/FX models
│   │   ├── credential.py     # OAuth token storage
│   │   ├── publish.py        # Upload history tracking
│   │   ├── settings.py       # Key-value app settings
│   │   ├── generation_duration.py  # Render time estimation data
│   │   └── api_usage.py      # API call tracking (tokens, cost, etc.)
│   ├── dev/
│   │   ├── log_handler.py    # SQLite logging handler + DevLog model
│   │   ├── routes.py         # Dashboard API routes + WebSocket
│   │   └── dashboard.html    # Self-contained dashboard UI
│   ├── prompts/              # LLM system prompt guides (.md files)
│   └── pyproject.toml        # Python dependencies (uv)
├── remotion/
│   └── src/
│       ├── Root.tsx           # Remotion composition definitions
│       ├── FullVideo.tsx      # Main video composition (all scenes sequenced)
│       ├── scenes/            # Scene components (StaticImage, MultiFrame,
│       │                      #   TitleCard, Subtitle, SceneRenderer)
│       ├── effects/
│       │   ├── camera/        # ZoomPunch effect
│       │   ├── typography/    # KineticCaption overlay
│       │   ├── overlays/      # EliOverlay, ChapterIndicator
│       │   └── structural/    # AnimatedChapterMap
│       ├── utils/             # Frame/second conversion helpers
│       └── types.ts           # Input props types mirroring Python models
├── data/                      # Runtime data (gitignored)
│   ├── db.sqlite             # SQLite database
│   ├── character/            # Eli frame library
│   └── projects/             # Generated assets per script
│       └── {script_id}/
│           ├── images/       # Scene images (.png)
│           ├── audio/        # Scene audio (.mp3)
│           └── renders/      # Rendered videos + thumbnails
├── docs/
│   ├── PRD.md                # Product Requirements Document
│   └── SETUP.md              # API keys & service setup guide
├── package.json              # Root package (Electron + concurrently)
└── CLAUDE.md                 # Development conventions & AI instructions
```

### Dev Dashboard

A browser-based developer dashboard is available at **http://localhost:8420/dev/** whenever the backend is running. It provides real-time visibility into backend activity without needing to watch the terminal.

#### Accessing the Dashboard

Start the backend (`npm run dev` or `npm run dev:backend`), then open [http://localhost:8420/dev/](http://localhost:8420/dev/) in any browser.

#### Logs Tab

The Logs tab streams backend log entries in real time over WebSocket:

- **Filters** — Filter by log level (DEBUG through CRITICAL), module name, or free-text search
- **Live streaming** — New log entries appear instantly via WebSocket. Auto-scrolls to the latest entry, but pauses when you scroll up to inspect older logs
- **Expandable rows** — Click any log entry to see the full message, source file/function/line number, and exception traceback (if present)
- **Pause/Resume** — Temporarily pause the live stream without disconnecting
- **Analytics sidebar** — Shows log distribution by level, top recurring messages (last 24h), per-module log counts, and messages that appeared for the first time in the last hour

#### Jobs Tab

The Jobs tab monitors active and completed render jobs:

- **Active jobs** — Each running job shows a progress bar, current step description, and elapsed time
- **Completed/failed jobs** — Lists finished jobs with duration and status. Failed jobs show an expandable error traceback
- **Auto-refresh** — The Jobs tab polls every 2 seconds while visible

#### API Tester Tab

The API tab provides an interactive explorer for all backend endpoints:

- **Endpoint discovery** — Fetches the OpenAPI schema automatically and lists all endpoints grouped by tag (brands, scripts, render, etc.)
- **Search/filter** — Filter endpoints by path or tag name
- **Request builder** — Click an endpoint to populate path parameters, query parameters, and a pre-filled JSON body generated from the schema
- **Response viewer** — Displays status code, response time, and syntax-highlighted JSON response

#### Database Tab

The Database tab provides a browser for the SQLite database:

- **Table list** — All tables with row counts. Click to browse rows
- **Row browser** — Paginated data table (50 rows/page) with clickable rows for detailed view. JSON blobs are pretty-printed in the detail modal
- **Sensitive field redaction** — `access_token`, `refresh_token`, and `value` fields in credential/settings tables are automatically masked
- **SQL query runner** — Collapsible textarea for running custom `SELECT`/`PRAGMA` queries. Write operations are rejected

#### Usage Tab

The Usage tab tracks API costs across all external services:

- **Service cards** — Per-service cost breakdown for Anthropic, Google AI Studio, Replicate, and ElevenLabs with call counts and relevant metrics (tokens, characters, images)
- **Daily cost chart** — Stacked bar chart showing cost per day per service
- **Operation breakdown** — Table of costs grouped by service, operation type, and model
- **Recent calls log** — Detailed table of recent API calls with timestamps, token counts, and per-call cost
- **Time range** — Configurable window (7, 30, 90, or 365 days)

Cost estimates are approximate and based on standard published pricing. Usage is recorded automatically whenever any integration client makes an API call.

#### Log Persistence

Logs are stored in SQLite (`data/db.sqlite` in the `dev_logs` table) and persist across backend restarts. Logs older than 7 days are automatically pruned on startup.

#### API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /dev/` | Dashboard HTML |
| `GET /dev/api/logs` | Query logs (params: `level`, `logger_name`, `search`, `since`, `limit`, `offset`) |
| `GET /dev/api/logs/stats` | Log analytics (top messages, by level/module, new messages) |
| `GET /dev/api/logs/modules` | List distinct logger names for filtering |
| `GET /dev/api/jobs` | Current render job statuses |
| `WebSocket /dev/ws/logs` | Live log stream |
| `GET /dev/api/db/tables` | List all tables with row counts and columns |
| `GET /dev/api/db/tables/{name}` | Paginated row browser (params: `limit`, `offset`) |
| `POST /dev/api/db/query` | Execute read-only SQL (body: `{sql, limit}`) |
| `GET /dev/api/usage/summary` | Aggregated usage stats per service (param: `days`) |
| `GET /dev/api/usage/recent` | Recent API call log (param: `limit`) |

### How It Works

1. **Brand Setup** — Configure voice preferences and Eli character overlay in Settings
2. **Ideate** — Enter a niche/topic, Claude generates video ideas with keyword analysis
3. **Script** — Select an idea, Claude writes a segmented script with narration, scene descriptions, and title cards
4. **Timeline** — Edit scenes in the lane-based timeline editor. Generate images (Gemini) and audio (ElevenLabs) per scene
5. **Effects** — AI generates kinetic captions and zoom punch effects; Eli character animation keyframes
6. **Render** — Remotion renders the full video with all effects, overlays, and transitions
7. **Export** — Download YouTube 16:9 video, audio-only, and thumbnails
8. **Publish** — Upload directly to YouTube with metadata

### Caching

- **Image generation** — Skips regeneration if the prompt hasn't changed (`.prompt` marker files)
- **Scene rendering** — Skips re-render if source image/audio haven't been modified (mtime comparison)

## API Key Setup

See [docs/SETUP.md](docs/SETUP.md) for detailed instructions on obtaining each API key and configuring Google OAuth2 for YouTube publishing.

## License

ISC
