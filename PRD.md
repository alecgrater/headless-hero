# YouTube AI Machine — Product Requirements Document

## 1. Executive Summary

YouTube AI Machine is a desktop application that provides an end-to-end pipeline for creating faceless educational/explainer YouTube content using AI. It replaces the current fragmented workflow of 5+ separate tools (ChatGPT for scripts, ElevenLabs for voice, InVideo for assembly, Midjourney for images, Canva for thumbnails) with a single integrated application.

The product targets a specific, proven content format: long-form explainer videos composed of named segments (e.g., "Every Drug Explained" with Caffeine, Nicotine, Alcohol as segments), where each segment can be independently exported as a TikTok/Reel/Short. The app handles idea generation, script writing, AI illustration, voiceover, video assembly, thumbnail creation, SEO optimization, and multi-platform publishing — all enforcing a consistent brand identity.

**MVP Goal:** A working desktop app where a single user can go from "I want to make a video about X" to exported YouTube video + TikTok clips, with AI assistance at every step and full editorial control via a storyboard editor.

## 2. Mission

**Mission Statement:** Reduce the end-to-end production time for high-quality faceless explainer content from hours across multiple tools to minutes in one application.

**Core Principles:**
1. **AI-first, human-edited** — AI generates the first draft of everything (script, visuals, voice, metadata), but the user has full control to tweak every detail
2. **Brand consistency by default** — Art style, voice, colors, and formatting are enforced per channel so every video looks like it belongs to the same creator
3. **One video, many platforms** — A single production yields both long-form YouTube content and platform-native short-form clips automatically
4. **Simple over powerful** — Storyboard cards, not timeline tracks. Presets, not infinite knobs. The tool should feel like a smart assistant, not a video editing suite
5. **Claude-native** — Use Claude for as much of the AI pipeline as possible; external APIs only where necessary (voice synthesis, image generation)

## 3. Target Users

**Primary Persona: Solo Content Operator (you)**
- Runs one or more faceless educational YouTube channels
- Technically comfortable (can work with APIs, desktop apps, basic config)
- Wants to produce 3-10 videos per week across YouTube + TikTok
- Pain points: too many tools, inconsistent output, manual segment splitting, repetitive SEO work, maintaining visual consistency across videos

**Future Persona: Content Agency Operator** (post-MVP)
- Manages multiple channels/brands for clients
- Needs team collaboration, approval workflows, white-labeling
- Deferred to SaaS phase

## 4. MVP Scope

### In Scope — Core Functionality
- ✅ Idea generation: AI suggests video topics based on niche + keyword analysis
- ✅ Script writing: AI generates full segmented scripts with hooks, cliffhangers, transitions
- ✅ Auto-segmentation: AI tags segment boundaries during script generation
- ✅ Storyboard editor: card-based scene editor with reorder, edit, preview
- ✅ AI image generation: per-scene illustrations in a consistent brand art style
- ✅ Simple animation: Ken Burns pan/zoom on stills, 2-3 frame animations, text overlay sync
- ✅ Voiceover: AI voice synthesis with prebuilt voice library
- ✅ Voice cloning: clone a custom brand voice
- ✅ Video assembly: FFmpeg-based rendering of final video
- ✅ Thumbnail generation: AI-generated thumbnails in brand style
- ✅ SEO & metadata: AI-suggested titles, descriptions, tags, keywords
- ✅ Brand profiles: store and enforce art style, voice, color palette, logo per channel
- ✅ Multi-format export: YouTube long-form (16:9) + TikTok/Reels/Shorts (9:16) per segment
- ✅ Publishing dashboard: manage one brand across YouTube, TikTok, Instagram

### In Scope — Technical
- ✅ Electron desktop app with web UI
- ✅ Python backend for AI orchestration
- ✅ FFmpeg for video rendering
- ✅ Claude API for script, SEO, idea gen, segmentation
- ✅ Image generation API (Flux/DALL-E) for illustrations
- ✅ ElevenLabs API for voice synthesis + cloning
- ✅ Local project storage (SQLite + filesystem)
- ✅ YouTube Data API for publishing
- ✅ TikTok/Instagram API for publishing

### Out of Scope (Future)
- ❌ Multi-user / team collaboration
- ❌ Multi-channel management from single dashboard
- ❌ SaaS deployment / cloud rendering
- ❌ Real-time collaboration / commenting
- ❌ Analytics dashboard (watch time, CTR, etc.)
- ❌ A/B testing for thumbnails/titles
- ❌ Automatic scheduling optimization (best time to post)
- ❌ Stock footage/image library integration
- ❌ Advanced animation (character rigs, complex motion graphics)
- ❌ Local AI model support
- ❌ Mobile companion app

## 5. User Stories

**US-1: Generate Video Ideas**
> As a content creator, I want AI to suggest video topics for my niche with keyword data, so that I can pick topics with high search potential and low competition.

Example: I type "psychology" as my niche. The system returns: "10 Cognitive Biases That Control Your Life" (search vol: 12K, competition: low), "Every Personality Disorder Explained" (search vol: 8K, competition: medium), etc.

**US-2: Write a Segmented Script**
> As a content creator, I want AI to write a full script broken into named segments with hooks and transitions, so that I have a production-ready script and auto-detected TikTok split points.

Example: I select "Every Drug Explained" as my topic. The system generates a script with segments: Caffeine (90s), Nicotine (80s), Alcohol (95s)... each with title card text, narration, and segment boundary markers.

**US-3: Edit Script in Storyboard**
> As a content creator, I want to see my script as a series of scene cards I can reorder, edit, split, or merge, so that I have full editorial control without needing a timeline editor.

Example: I see 45 cards. I drag the "Cannabis" card to appear before "Alcohol." I click into the "Caffeine" card and rewrite the closing line. I split one card into two because the scene is too long.

**US-4: Generate Consistent Visuals**
> As a content creator, I want AI to generate illustrations for each scene that match my channel's art style, so that every video has a visually cohesive look.

Example: My brand profile specifies "flat illustration, muted earth tones, thick outlines, dark background." Every generated image — whether it's a brain, a coffee cup, or a molecule — follows that style consistently.

**US-5: Add Voiceover**
> As a content creator, I want to generate AI voiceover for my entire script using my brand voice, so that narration is consistent across all my videos.

Example: I cloned a voice during onboarding. Now every script is narrated in that voice. I can regenerate individual scene narrations if the pacing feels off.

**US-6: Preview and Adjust**
> As a content creator, I want to preview the assembled video scene-by-scene and make adjustments to timing, visuals, or text overlays before final render, so that I catch issues before export.

Example: I preview the "Cocaine" segment. The text overlay appears too early. I adjust the timing by 0.5s. The Ken Burns zoom on the illustration feels too fast — I slow it down. I swap the generated image for a regenerated one.

**US-7: Export Multi-Platform**
> As a content creator, I want one-click export that produces both a full YouTube video and individual TikTok clips per segment, so that I get maximum content from one production session.

Example: I hit "Export All." The system renders: 1x 16:9 YouTube video (15 min), 12x 9:16 TikTok clips (60-90s each, with auto-generated hooks/intros), and 1x YouTube thumbnail.

**US-8: Publish Across Platforms**
> As a content creator, I want to upload and schedule content to YouTube, TikTok, and Instagram from one dashboard, so that I don't have to manually upload to each platform.

Example: I select the YouTube video and 3 TikTok clips. I set YouTube to publish tomorrow at 9am, and stagger the TikToks across the next 3 days. I review AI-generated titles/descriptions/tags for each, tweak one title, and hit "Schedule All."

## 6. Core Architecture & Patterns

### High-Level Architecture

```
┌─────────────────────────────────────────────┐
│              Electron Shell                  │
│  ┌───────────────────────────────────────┐  │
│  │         React Frontend (UI)           │  │
│  │  Storyboard Editor | Dashboard | etc  │  │
│  └──────────────┬────────────────────────┘  │
│                 │ IPC                        │
│  ┌──────────────▼────────────────────────┐  │
│  │       Node.js Main Process            │  │
│  │  File I/O | FFmpeg | API routing      │  │
│  └──────────────┬────────────────────────┘  │
│                 │ HTTP/subprocess            │
│  ┌──────────────▼────────────────────────┐  │
│  │     Python Backend (FastAPI)          │  │
│  │  AI Orchestration | Pipeline Engine   │  │
│  └──────────────┬────────────────────────┘  │
│                 │                            │
│     ┌───────────┼───────────┐               │
│     ▼           ▼           ▼               │
│  Claude API  Image Gen  ElevenLabs          │
│              (Flux/     (Voice)             │
│              DALL-E)                        │
└─────────────────────────────────────────────┘
```

### Directory Structure

```
youtube-ai-machine/
├── electron/                  # Electron main process
│   ├── main.ts               # App entry, window management
│   ├── ipc/                  # IPC handlers
│   ├── ffmpeg/               # FFmpeg wrapper & rendering
│   └── storage/              # Local file/DB management
├── frontend/                  # React UI
│   ├── src/
│   │   ├── components/
│   │   │   ├── storyboard/   # Scene cards, drag-drop, editor
│   │   │   ├── dashboard/    # Publishing, scheduling
│   │   │   ├── brand/        # Brand profile management
│   │   │   ├── ideation/     # Topic/idea generation UI
│   │   │   └── common/       # Shared components
│   │   ├── stores/           # State management (Zustand)
│   │   ├── hooks/            # Custom React hooks
│   │   └── types/            # TypeScript interfaces
│   └── public/
├── backend/                   # Python backend
│   ├── api/                  # FastAPI routes
│   ├── pipeline/             # Production pipeline stages
│   │   ├── ideation.py       # Topic/idea generation
│   │   ├── scriptwriter.py   # Script generation + segmentation
│   │   ├── visual_gen.py     # Image generation orchestration
│   │   ├── voiceover.py      # Voice synthesis orchestration
│   │   ├── assembly.py       # Video assembly logic
│   │   ├── thumbnail.py      # Thumbnail generation
│   │   └── seo.py            # SEO/metadata generation
│   ├── brand/                # Brand profile & style enforcement
│   ├── export/               # Multi-platform export logic
│   ├── integrations/         # External API clients
│   │   ├── claude_client.py
│   │   ├── image_gen_client.py
│   │   └── elevenlabs_client.py
│   └── models/               # Data models (Pydantic)
├── data/                      # Local storage
│   ├── projects/             # Per-project folders
│   ├── brands/               # Brand profiles
│   ├── voices/               # Cloned voice data
│   └── db.sqlite             # Project metadata
└── scripts/                   # Build & dev scripts
```

### Key Design Patterns

- **Pipeline pattern** — Each production stage (script → visuals → voice → assembly) is an independent pipeline step. Steps can be re-run individually without restarting the whole pipeline.
- **Brand context injection** — Every AI call (Claude, image gen, voice) receives the active brand profile as context so outputs stay consistent.
- **Scene as atomic unit** — A scene (storyboard card) is the fundamental data unit. It contains: script text, visual prompt, generated image(s), audio clip, timing metadata, text overlays. Everything operates on scenes.
- **Non-destructive editing** — All generated assets are versioned. Swapping an image doesn't delete the old one. Undo is always possible.
- **Segment tagging** — Segments (TikTok boundaries) are metadata on scenes, not separate entities. A segment is a contiguous range of scenes with a shared title.

## 7. Features — Detailed Specifications

### 7.1 Idea Generator

**Purpose:** Generate video topic ideas with keyword/search data for a given niche.

**How it works:**
1. User enters their niche or broad topic area
2. Claude generates 10-20 video ideas, each with:
   - Title (optimized for YouTube search)
   - Estimated segment count (how many sub-topics)
   - Brief description of angle/hook
   - Suggested keywords
3. User selects an idea to move into script writing

**Key features:**
- Niche memory: remembers previously generated ideas to avoid repeats
- "More like this" — regenerate variations of a selected idea
- Manual idea entry — user can skip AI and type their own topic

### 7.2 Script Writer

**Purpose:** Generate a full, segmented script with production metadata.

**How it works:**
1. User selects a topic (from idea generator or manual entry)
2. Claude generates a complete script with:
   - Segment boundaries (auto-detected, each segment named)
   - Per-scene visual direction notes (what the illustration should depict)
   - Text overlay cues (key phrases to display on screen)
   - Intro hook and outro CTA
   - Segment transition lines
3. Script appears in the storyboard editor as scene cards

**Script data model:**
```json
{
  "title": "Every Drug Explained",
  "segments": [
    {
      "name": "Caffeine",
      "scenes": [
        {
          "id": "scene_001",
          "narration": "Caffeine is a stimulant, a chemical that speeds up your brain...",
          "visual_prompt": "Flat illustration of a glowing coffee cup with neural pathways emanating from it, dark background, muted earth tones",
          "text_overlay": "CAFFEINE",
          "duration_estimate_seconds": 8,
          "is_title_card": true
        },
        {
          "id": "scene_002",
          "narration": "Once you drink it, caffeine enters your bloodstream and quickly travels to your brain...",
          "visual_prompt": "Cross-section illustration of a human brain with caffeine molecules (shown as small glowing dots) traveling through blood vessels toward brain receptors",
          "text_overlay": "Blocks adenosine → hides exhaustion",
          "duration_estimate_seconds": 12,
          "is_title_card": false
        }
      ]
    }
  ],
  "intro_hook": "You consume it every day. But do you know what it actually does to your brain?",
  "outro_cta": "Which of these surprised you the most? Let us know in the comments."
}
```

### 7.3 Storyboard Editor

**Purpose:** Visual editor for reviewing and tweaking every aspect of the video.

**Layout:**
- Left panel: segment list (collapsible)
- Center: scene card grid/list (main workspace)
- Right panel: properties panel for selected scene (script text, visual, timing, overlays)
- Bottom: preview player (plays current scene or full segment)

**Scene card shows:**
- Thumbnail of generated image
- First line of narration text
- Duration
- Segment tag (color-coded)
- Status indicators (image generated, voice generated, etc.)

**Operations:**
- Drag-drop reorder scenes within/across segments
- Click to edit narration text inline
- Regenerate image (with or without modified prompt)
- Adjust timing (duration per scene)
- Edit text overlay content and position
- Split scene into two / merge adjacent scenes
- Add/remove segment boundaries
- Preview individual scene, segment, or full video

### 7.4 Visual Generation Engine

**Purpose:** Generate consistent-style illustrations for every scene.

**How it works:**
1. Brand profile defines the base style prompt (e.g., "flat illustration, thick outlines, muted earth tones, dark background, educational style")
2. Each scene has a visual prompt from the script writer
3. The system combines: `{brand_style_prompt} + {scene_visual_prompt}` and sends to image generation API
4. Generated image is stored and displayed on the scene card

**Key features:**
- **Style lock:** Brand style prefix is prepended to every image prompt automatically
- **Regeneration:** Click to regenerate with same prompt, modified prompt, or completely new prompt
- **Batch generation:** Generate all scene images at once (parallelized)
- **2-3 frame animation:** For select scenes, generate 2-3 slight variations of the same image to create simple animation (e.g., a brain "lighting up" in stages)
- **Aspect ratio variants:** Generate both 16:9 (YouTube) and 9:16 (TikTok) crops

### 7.5 Animation & Motion Engine

**Purpose:** Apply motion effects to still images and sync text overlays with voiceover.

**Effects available:**
- **Ken Burns:** slow pan, zoom in, zoom out on still images (configurable direction and speed)
- **Frame animation:** cycle through 2-3 image variants to create simple motion
- **Text overlay:** animated text that appears/disappears in sync with narration
- **Title cards:** segment title with animated entrance (fade, slide)
- **Transitions:** crossfade, cut, or fade-to-black between scenes

**All timing is driven by voiceover duration** — the image/animation fills the time the narration takes.

### 7.6 Voiceover Engine

**Purpose:** Generate narration audio for every scene.

**How it works:**
1. Brand profile specifies the voice (prebuilt or cloned)
2. Each scene's narration text is sent to voice synthesis API
3. Audio clip is returned and attached to the scene
4. Duration of audio clip sets the scene's actual duration

**Key features:**
- **Prebuilt voice library:** select from available voices (ElevenLabs catalog)
- **Voice cloning:** upload audio sample(s) to create a custom brand voice
- **Per-scene regeneration:** re-record one scene without affecting others
- **Speed/pitch adjustment:** fine-tune voice pacing
- **Batch generation:** generate all scene audio at once

### 7.7 Video Assembly (FFmpeg)

**Purpose:** Render the final video from all assets.

**Inputs per scene:**
- Image(s) (still or 2-3 frame animation)
- Audio clip (voiceover)
- Motion config (Ken Burns params)
- Text overlay (content, position, timing)
- Transition type to next scene

**Outputs:**
- Full video: 16:9 MP4 for YouTube (all segments concatenated)
- Per-segment clips: 9:16 MP4 for TikTok/Reels (each segment individually, with auto-generated hook intro)
- Audio-only: MP3 of full narration (for podcast repurposing)

**The TikTok hook:** Each segment clip gets a 2-3 second hook prepended. Claude generates these based on the segment content. Example: for the Caffeine segment, the hook might be "You drink this every morning and have no idea what it does to your brain" over the title card, before the main narration begins.

### 7.8 Thumbnail Generator

**Purpose:** Generate a YouTube thumbnail that matches the brand style.

**How it works:**
1. Claude analyzes the video topic and suggests 3 thumbnail concepts
2. Image generation API creates the thumbnail illustration in brand style
3. System composites: illustration + title text + branding elements (logo, color bar)
4. User can regenerate or manually adjust text/layout

**Output:** 1280x720 PNG/JPG

### 7.9 SEO & Metadata Engine

**Purpose:** Generate optimized titles, descriptions, tags, and keywords.

**Per-platform generation:**
- **YouTube:** Title (≤70 chars), description (with timestamps for each segment), tags (30+), category
- **TikTok:** Caption (≤150 chars), hashtags (5-10), sounds tag
- **Instagram:** Caption, hashtags (20-30)

All generated by Claude with the video content as context. User can edit all fields before publishing.

### 7.10 Brand Profile Manager

**Purpose:** Store and enforce consistent branding across all content.

**Brand profile contains:**
- Channel name
- Art style description (used as image generation prefix)
- Color palette (hex codes for overlays, text, backgrounds)
- Logo file
- Font selection (for text overlays and thumbnails)
- Voice selection (prebuilt ID or cloned voice ID)
- Intro/outro templates (optional recurring elements)
- Platform accounts (YouTube, TikTok, Instagram API keys)

### 7.11 Publishing Dashboard

**Purpose:** Upload and schedule content across platforms.

**Features:**
- View all ready-to-publish content (videos + clips)
- Per-platform metadata editing
- Schedule publishing date/time per piece
- Upload progress tracking
- Status indicators (draft, scheduled, published, failed)
- Quick-publish: upload immediately to selected platforms

## 8. Technology Stack

### Frontend
| Tech | Purpose |
|------|---------|
| Electron 33+ | Desktop shell, IPC, native file access |
| React 19 | UI framework |
| TypeScript 5.x | Type safety |
| Zustand | State management |
| Tailwind CSS 4 | Styling |
| DND Kit | Drag-and-drop for storyboard |
| Wavesurfer.js | Audio waveform display in editor |

### Backend
| Tech | Purpose |
|------|---------|
| Python 3.12+ | AI orchestration runtime |
| FastAPI | HTTP API between Electron and Python |
| UV | Python package/env management |
| Pydantic v2 | Data models and validation |
| SQLite (via SQLModel) | Local project/metadata storage |
| FFmpeg 7+ | Video rendering |
| python-ffmpeg | FFmpeg Python bindings |

### External APIs
| Service | Purpose | Fallback |
|---------|---------|----------|
| Claude API (Anthropic) | Scripts, SEO, ideas, segmentation, thumbnail concepts, TikTok hooks | — |
| Flux / DALL-E 3 | Image generation per scene | Swap between providers |
| ElevenLabs | Voice synthesis + cloning | — |
| YouTube Data API v3 | Upload & schedule YouTube videos | Manual upload |
| TikTok Content Posting API | Upload TikTok clips | Manual upload |
| Instagram Graph API | Upload Reels | Manual upload |

### Dev Tools
| Tool | Purpose |
|------|---------|
| Vite | Frontend bundler |
| Electron Forge | Electron packaging/distribution |
| uv | Python dependency management |
| ESLint + Prettier | JS/TS linting |
| Ruff | Python linting |

## 9. Security & Configuration

### API Key Management
- All API keys stored in OS keychain (via `keytar` in Electron) — never in plaintext config files
- Keys: `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `IMAGE_GEN_API_KEY`
- OAuth tokens for YouTube/TikTok/Instagram stored similarly

### Configuration
- `config.json` in app data directory for non-sensitive settings:
  - Default export paths
  - Preferred image generation provider
  - FFmpeg binary path
  - Backend port
  - UI preferences
- Brand profiles stored in SQLite database
- Generated assets stored in per-project directories on local filesystem

### Security Scope
**In scope:**
- Secure API key storage
- No plaintext secrets in config or logs
- Input sanitization for FFmpeg commands (prevent injection)

**Out of scope (personal use):**
- User authentication (single user)
- Network encryption beyond HTTPS to APIs
- Audit logging

## 10. API Specification (Internal Backend)

The Python backend exposes a REST API consumed by the Electron frontend over localhost.

### Endpoints

#### Ideas
```
POST /api/ideas/generate
Body: { "niche": "psychology", "count": 10 }
Response: { "ideas": [{ "title": "...", "segments_est": 8, "description": "...", "keywords": [...] }] }
```

#### Scripts
```
POST /api/scripts/generate
Body: { "topic": "Every Drug Explained", "brand_id": "brand_001", "segment_count": 12 }
Response: { "script": { "title": "...", "segments": [...], "intro_hook": "...", "outro_cta": "..." } }

GET /api/scripts/{id}
Response: { "id": "...", "brand_id": "...", "topic_title": "...", "topic_description": "...", "script": {...}, "created_at": "..." }

PUT /api/scripts/{id}
Body: { "script": { "title": "...", "segments": [...], "intro_hook": "...", "outro_cta": "..." } }
Response: { "id": "...", "brand_id": "...", "topic_title": "...", "topic_description": "...", "script": {...}, "created_at": "..." }
```

#### Visuals
```
POST /api/visuals/generate
Body: { "scene_id": "scene_001", "prompt": "...", "brand_style": "...", "aspect_ratio": "16:9" }
Response: { "image_url": "file:///path/to/image.png", "prompt_used": "..." }

POST /api/visuals/generate-batch
Body: { "scenes": [{ "scene_id": "...", "prompt": "..." }], "brand_style": "..." }
Response: { "results": [{ "scene_id": "...", "image_url": "..." }] }
```

#### Voiceover
```
POST /api/voice/generate
Body: { "scene_id": "scene_001", "text": "Caffeine is a stimulant...", "voice_id": "brand_voice_001" }
Response: { "audio_url": "file:///path/to/audio.mp3", "duration_seconds": 8.3 }

POST /api/voice/clone
Body: { "name": "My Brand Voice", "audio_samples": ["file:///path/to/sample1.mp3"] }
Response: { "voice_id": "cloned_voice_xyz" }
```

#### Assembly
```
POST /api/render/preview-scene
Body: { "scene_id": "scene_001" }
Response: { "preview_url": "file:///path/to/preview.mp4" }

POST /api/render/full
Body: { "project_id": "proj_001", "format": "youtube" }
Response: { "status": "rendering", "job_id": "render_001" }

POST /api/render/segments
Body: { "project_id": "proj_001", "format": "tiktok" }
Response: { "status": "rendering", "job_id": "render_002" }

GET /api/render/status/{job_id}
Response: { "status": "complete", "progress": 100, "output_files": [...] }
```

#### Thumbnail
```
POST /api/thumbnail/generate
Body: { "project_id": "proj_001", "brand_id": "brand_001" }
Response: { "concepts": [{ "description": "...", "image_url": "..." }] }
```

#### SEO
```
POST /api/seo/generate
Body: { "project_id": "proj_001", "platform": "youtube" }
Response: { "title": "...", "description": "...", "tags": [...], "keywords": [...] }
```

#### Publishing
```
POST /api/publish/upload
Body: { "project_id": "proj_001", "platform": "youtube", "file_path": "...", "metadata": {...}, "schedule_at": "2026-03-28T09:00:00Z" }
Response: { "status": "scheduled", "platform_id": "yt_abc123" }
```

## 11. Success Criteria

### MVP Definition of Done
The MVP is complete when a user can perform this end-to-end workflow:
1. Open the app and enter a video topic
2. Get an AI-generated segmented script
3. Review and edit the script in the storyboard editor
4. Generate consistent-style illustrations for all scenes
5. Generate voiceover for all scenes
6. Preview the assembled video
7. Export a YouTube video (16:9) and TikTok clips (9:16 per segment)
8. Upload to at least YouTube from the app

### Functional Requirements
- ✅ AI generates coherent, segmented scripts given a topic
- ✅ Generated images maintain consistent art style within a project
- ✅ Voiceover audio syncs correctly with scene timing
- ✅ Storyboard editor supports reorder, edit, split, merge of scenes
- ✅ FFmpeg renders watchable, correctly-timed video output
- ✅ TikTok clips have auto-generated hooks prepended
- ✅ Brand profile persists and applies across multiple projects
- ✅ SEO metadata is generated per platform

### Quality Indicators
- Video output looks comparable to "Everything Professor" quality
- Script quality requires minimal manual editing (<20% of text changed by user)
- Image style consistency: a viewer cannot tell which images came from different generation calls
- Full pipeline (idea → export) completes in under 30 minutes for a 10-segment video

## 12. Implementation Phases

### Phase 1: Foundation (Weeks 1-3)
**Goal:** App shell with working script generation and storyboard editor.

- ✅ ~~Electron + React + Python project scaffolding~~ **DONE** — Electron 41 + React 19 + Vite + Tailwind 4 + FastAPI + uv. `npm run dev` starts all three layers. Backend health check verified. FFmpeg 8.1 available.
- ✅ ~~Brand profile creation and storage~~ **DONE** — SQLModel/SQLite persistence, FastAPI CRUD endpoints (POST/GET/PUT/DELETE /api/brands), React UI with create form + brand list/selection + edit + delete. Pydantic models: BrandProfileCreate, BrandProfileUpdate, BrandProfileRead.
- ✅ ~~Claude integration for idea generation~~ **DONE** — Pipeline generates 10-20 VideoIdea objects via Claude. POST /api/ideas/generate endpoint. React UI with niche input, idea cards, "more like this".
- ✅ ~~Claude integration for script generation with auto-segmentation~~ **DONE** — Pipeline generates full segmented scripts (ScriptContent with segments, scenes, intro_hook, outro_cta) via Claude. POST /api/scripts/generate + GET /api/scripts/{id} + PUT /api/scripts/{id}. SQLite persistence. React UI with loading state, read-only script preview, "Continue to Storyboard" button.
- ✅ ~~Storyboard editor UI (scene cards, reorder, edit text)~~ **DONE** — Three-panel layout: SegmentList (left, 220px), SceneGrid (center, responsive grid), PropertiesPanel (right, 320px). Drag-drop via @dnd-kit (SortableContext per segment, cross-segment moves). Inline narration editing (double-click), full scene form in properties panel. Split scene (at sentence midpoint), merge with next. useStoryboardState hook: state management, undo stack (Ctrl+Z), debounced auto-save (5s), explicit save (Ctrl+S), beforeunload guard, save status indicator. Segment color coding (8-color palette). Persists via PUT /api/scripts/{id}.
- ✅ ~~Local project persistence (SQLite)~~ **DONE** — Brands, scripts, and storyboard edits all persisted to SQLite via SQLModel.

**Validation:** Can generate a script from a topic and view/edit it in the storyboard.

### Phase 2: Media Generation (Weeks 4-6)
**Goal:** Generate all visual and audio assets.

- ✅ ~~Image generation integration with brand style enforcement~~ **DONE** — fal.ai Flux via fal-client SDK. Brand `art_style` prepended to every scene `visual_prompt`. POST /api/visuals/generate for single scenes. Images stored at `data/projects/{script_id}/images/{scene_id}.png`, served via FastAPI StaticFiles at `/static/projects/...`. Scene model has `image_url` field persisted inside script_json.
- ✅ ~~Batch image generation across all scenes~~ **DONE** — POST /api/visuals/generate-batch endpoint, sequential loop (no rate-limit issues). "Generate All Images" button in storyboard header. Spinner overlay per scene during generation.
- ✅ ~~ElevenLabs integration for voiceover~~ **DONE** — `httpx`-based ElevenLabs API client in `backend/integrations/elevenlabs_client.py`. `generate_speech()` calls ElevenLabs TTS v1, `list_voices()` fetches available voices. Uses `ELEVENLABS_API_KEY` env var. Model: `eleven_multilingual_v2`.
- ◻️ Voice cloning setup flow
- ✅ ~~Per-scene audio generation~~ **DONE** — Pipeline in `backend/pipeline/voiceover.py` with `generate_scene_audio()` and `generate_batch_audio()`. Audio stored at `data/projects/{script_id}/audio/{scene_id}.mp3`, served via existing StaticFiles mount. Scene model has `audio_url` and `audio_duration_seconds` fields persisted inside script_json. API router at `backend/api/voiceover.py`: POST /api/voice/generate (single), POST /api/voice/generate-batch (batch), GET /api/voice/voices (list). Frontend: voice selector dropdown + "Generate All Audio" button in storyboard header, per-scene generate/regenerate in PropertiesPanel, audio note indicator in SceneCard, `<audio>` playback in PropertiesPanel.
- ✅ ~~Scene preview (image + audio playback)~~ **DONE** — PropertiesPanel shows image preview + `<audio>` player with HTML5 controls when both are generated. Duration from TTS displayed alongside.
- ◻️ Ken Burns motion and text overlay configuration

**Validation:** Can generate images and audio for all scenes and preview individual scenes.

### Phase 3: Video Assembly & Export (Weeks 7-9)
**Goal:** Render and export final videos in both formats.

- ✅ FFmpeg rendering pipeline (scene → segment → full video)
- ✅ 16:9 YouTube export with all motion/overlay effects
- ✅ 9:16 TikTok export per segment with hook generation
- ✅ Thumbnail generation
- ✅ SEO metadata generation
- ✅ Full video preview in app
- ✅ Audio-only export

**Validation:** Can render and export a complete YouTube video + TikTok clips that look and sound professional.

### Phase 4: Publishing & Polish (Weeks 10-12)
**Goal:** Multi-platform publishing and workflow polish.

- ✅ YouTube upload integration
- ✅ TikTok upload integration
- ✅ Instagram Reels upload integration
- ✅ Scheduling UI
- ✅ Publishing status tracking
- ✅ End-to-end workflow polish and bug fixing
- ✅ Performance optimization (parallel generation, caching)

**Validation:** Can go from topic idea to published content on YouTube + TikTok in one session without leaving the app.

## 13. Future Considerations

### Post-MVP Enhancements
- **Multi-channel management:** Switch between brand profiles / channels from one dashboard
- **Analytics integration:** Pull YouTube/TikTok analytics to inform future topic selection
- **Template library:** Save successful video structures as reusable templates
- **A/B thumbnail testing:** Generate multiple thumbnails, run split tests
- **Batch production:** Queue up multiple videos to generate overnight
- **Script from URL/article:** Paste a source article, generate a video script from it
- **Music/sound effects:** AI-selected background music per segment mood

### SaaS Migration Path
- Move Python backend to cloud (AWS/GCP)
- Replace local SQLite with PostgreSQL
- Add user authentication (Clerk/Auth0)
- Replace local FFmpeg with cloud rendering (e.g., Remotion on Lambda)
- Add Stripe billing
- Web UI already exists (React) — just needs to be served from a CDN instead of Electron

### Advanced Features (Long-term)
- Team collaboration with role-based access
- Custom animation editor (beyond Ken Burns + frame animation)
- AI-generated B-roll video clips (not just stills)
- Live performance dashboard
- Content calendar with AI-optimized scheduling
- Multi-language video generation (same video, different voice/language)

## 14. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Image style inconsistency** — AI image gen produces visually inconsistent results across scenes | High — breaks the "brand look" that makes these channels work | Strong style prompts with brand prefix; seed locking where API supports it; allow easy regeneration; consider fine-tuning a LoRA model per brand style |
| **API cost at scale** — generating 12+ images, 45+ audio clips, and multiple Claude calls per video adds up | Medium — could make per-video cost prohibitive | Cache aggressively; batch API calls; track cost per video in UI; allow selective regeneration instead of full re-runs |
| **Platform API instability** — YouTube/TikTok/Instagram APIs change frequently and have strict rate limits | Medium — publishing feature could break | Abstract platform APIs behind an adapter layer; support manual export as fallback; monitor API changelogs |
| **FFmpeg complexity** — video rendering with motion, overlays, and format conversion is finicky | Medium — rendering bugs are hard to debug | Comprehensive FFmpeg command templates; scene-level preview before full render; extensive test fixtures |
| **Voice cloning quality** — cloned voices may sound robotic or inconsistent | Low-Medium — voice is 50% of brand identity | Offer both cloned and prebuilt voices; allow per-scene voice regeneration; ElevenLabs quality is generally high with good samples |

## 15. Appendix

### Key Dependencies
- [Anthropic Claude API](https://docs.anthropic.com/en/docs) — scripting, ideation, SEO
- [ElevenLabs API](https://elevenlabs.io/docs) — voice synthesis and cloning
- [FFmpeg](https://ffmpeg.org/documentation.html) — video rendering
- [YouTube Data API v3](https://developers.google.com/youtube/v3) — video upload
- [TikTok Content Posting API](https://developers.tiktok.com/doc/content-posting-api-get-started) — clip upload
- [Electron](https://www.electronjs.org/docs/latest/) — desktop app shell
- [FastAPI](https://fastapi.tiangolo.com/) — Python backend framework

### Reference Channels
- [Everything Professor](https://www.youtube.com/@EverythingProfessor) — primary format/style reference
- [@smartscrolls_hub (TikTok)](https://www.tiktok.com/@smartscrolls_hub) — TikTok short-form reference
- [@GamingExpIaned](https://www.youtube.com/@GamingExpIaned) — gaming niche variant of the same format
