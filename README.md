# Headless Hero

AI-powered desktop app for creating faceless educational YouTube content. Full pipeline from idea to published video — in one tool.

Replace the fragmented workflow of ChatGPT + ElevenLabs + Midjourney + InVideo + Canva with a single integrated application that enforces brand consistency across every video.

![Architecture Diagram](architecture.png)

## What It Does

Headless Hero handles the entire content creation pipeline:

1. **Idea Generation** — AI suggests video topics for your niche with keyword analysis
2. **Script Writing** — Generates segmented scripts with hooks, transitions, and auto-detected TikTok split points
3. **Storyboard Editing** — Card-based scene editor with drag-and-drop reorder, split, merge, and full editorial control
4. **Image Generation** — Per-scene AI illustrations enforcing your brand's art style
5. **Voiceover** — AI voice synthesis with voice cloning support
6. **Video Assembly** — FFmpeg-based rendering with Ken Burns motion, text overlays, and effects
7. **Multi-Format Export** — YouTube 16:9 long-form + TikTok/Reels 9:16 per segment
8. **Thumbnail & SEO** — AI-generated thumbnails and optimized metadata for YouTube, TikTok, and Instagram
9. **YouTube Publishing** — Direct upload with scheduling via OAuth2

## Architecture

The app is structured as four layers:

| Layer | Tech | Role |
|-------|------|------|
| **Desktop Shell** | Electron 41 | Window management, IPC bridge, system integration |
| **Frontend** | React 19, Vite, TypeScript, Tailwind 4 | UI views: brands, ideation, script editor, storyboard, export/publish |
| **Backend** | FastAPI, Python 3.12, uv, SQLite (SQLModel) | REST API on `:8420`, database, static file serving |
| **Pipeline** | Claude API, Google Gemini, ElevenLabs, FFmpeg | AI orchestration: ideation, scriptwriting, image gen, TTS, rendering, SEO, publishing |

### API Routes

| Endpoint | Purpose |
|----------|---------|
| `/api/brands` | Brand profile CRUD |
| `/api/ideas` | AI topic generation |
| `/api/scripts` | Script generation and editing |
| `/api/visuals` | Image generation (single + batch) |
| `/api/voice` | TTS generation, batch audio, voice cloning, voice listing |
| `/api/render` | Video rendering (preview, full, segments, status, export audio) |
| `/api/thumbnail` | Thumbnail generation |
| `/api/seo` | SEO metadata generation |
| `/api/publish` | YouTube OAuth, upload, status, history |

### External Services

| Service | Purpose | Env Var |
|---------|---------|---------|
| [Anthropic Claude](https://console.anthropic.com/) | Ideas, scripts, SEO, thumbnail concepts | `ANTHROPIC_API_KEY` |
| [Google Gemini](https://ai.google.dev/) | Image generation (gemini-2.5-flash) | `GOOGLE_AI_KEY` |
| [ElevenLabs](https://elevenlabs.io/) | Text-to-speech + voice cloning | `ELEVENLABS_API_KEY` |
| [YouTube Data API v3](https://console.cloud.google.com/) | Video upload + scheduling | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` |
| FFmpeg 8.1 | Video rendering, Ken Burns, overlays, concat, 9:16 export | System install |

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
│       │   ├── brand/        # Brand profile management
│       │   ├── ideation/     # Idea generation UI
│       │   ├── script/       # Script editor
│       │   ├── storyboard/   # Storyboard editor (scene cards, properties,
│       │   │                 #   grid, render state, publish state)
│       │   ├── ErrorBoundary.tsx
│       │   └── ToastContainer.tsx
│       └── types/            # TypeScript interfaces (visual, audio, render, publish)
├── backend/
│   ├── api/
│   │   ├── __init__.py       # FastAPI app, router registration, static mount
│   │   ├── brands.py         # Brand CRUD endpoints
│   │   ├── ideas.py          # Idea generation endpoint
│   │   ├── scripts.py        # Script generation + CRUD
│   │   ├── visuals.py        # Image generation (single + batch)
│   │   ├── voiceover.py      # TTS generation + voice cloning
│   │   ├── render.py         # Video render endpoints + job status
│   │   ├── thumbnail.py      # Thumbnail generation
│   │   ├── seo.py            # SEO metadata generation
│   │   ├── publish.py        # YouTube OAuth + upload
│   │   └── database.py       # SQLite engine + session dependency
│   ├── pipeline/
│   │   ├── ideation.py       # Idea generation via Claude
│   │   ├── scriptwriter.py   # Script generation via Claude
│   │   ├── image_gen.py      # Image gen: prompt → Gemini → local file
│   │   ├── voiceover.py      # TTS: ElevenLabs → MP3 + duration
│   │   ├── video_render.py   # Render orchestration (scenes → full video)
│   │   ├── ffmpeg_builder.py # FFmpeg CLI arg construction
│   │   ├── render_jobs.py    # Background job tracking with threading
│   │   ├── thumbnail.py      # Claude concepts + Gemini + FFmpeg composite
│   │   ├── seo.py            # SEO metadata via Claude
│   │   └── publishing.py     # YouTube upload orchestration
│   ├── integrations/
│   │   ├── claude_client.py       # Anthropic SDK wrapper
│   │   ├── google_image_client.py # google-genai SDK wrapper
│   │   ├── elevenlabs_client.py   # ElevenLabs httpx wrapper
│   │   └── youtube_client.py      # YouTube Data API v3 wrapper
│   ├── models/
│   │   ├── brand.py          # BrandProfile table + schemas
│   │   ├── script.py         # Script table + Scene/Segment models
│   │   ├── credential.py     # OAuth token storage
│   │   └── publish.py        # Upload history tracking
│   └── pyproject.toml        # Python dependencies (uv)
├── data/
│   ├── db.sqlite             # SQLite database
│   └── projects/             # Generated assets per script
│       └── {script_id}/
│           ├── images/       # Scene images (.png)
│           ├── audio/        # Scene audio (.mp3)
│           ├── renders/      # Rendered videos
│           │   ├── scenes/   # Individual scene videos
│           │   ├── tiktok/   # 9:16 segment exports
│           │   └── thumbnails/
│           └── full_youtube.mp4
├── package.json              # Root package (Electron + concurrently)
├── PRD.md                    # Product Requirements Document
└── SETUP.md                  # API keys & service setup guide
```

### How It Works

1. **Brand Setup** — Create a brand profile with art style, voice preferences, and color palette
2. **Ideate** — Enter a niche/topic, Claude generates video ideas with keyword analysis
3. **Script** — Select an idea, Claude writes a segmented script with narration and scene descriptions
4. **Storyboard** — Edit scenes in the card-based editor. Generate images (Gemini) and audio (ElevenLabs) per scene
5. **Render** — FFmpeg assembles scenes into a full video with Ken Burns motion, text overlays, and transitions
6. **Export** — Download YouTube 16:9 video, TikTok 9:16 clips per segment, audio-only, and thumbnails
7. **Publish** — Upload directly to YouTube with scheduling, copy metadata for TikTok/Instagram

### Caching

- **Image generation** — Skips regeneration if the prompt hasn't changed (`.prompt` marker files)
- **Scene rendering** — Skips re-render if source image/audio haven't been modified (mtime comparison)

## API Key Setup

See [SETUP.md](SETUP.md) for detailed instructions on obtaining each API key and configuring Google OAuth2 for YouTube publishing.

## License

ISC
