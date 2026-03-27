# YouTube AI Machine — Setup Guide

## Required API Keys & Services

### 1. Anthropic Claude API (`ANTHROPIC_API_KEY`)

**Used for:** Script generation, idea generation, SEO metadata, thumbnail concepts

**How to get it:**
1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Navigate to **API Keys** in the dashboard
4. Click **Create Key**, copy the value

**Fallback:** If not set, the app falls back to a local proxy at `http://localhost:11211/api/anthropic`. You only need this key if you're not running a local proxy.

---

### 2. fal.ai (`FAL_KEY`)

**Used for:** AI image generation (scene images + thumbnails) via the Flux model

**How to get it:**
1. Go to https://fal.ai/
2. Sign up or log in
3. Navigate to **Keys** at https://fal.ai/dashboard/keys
4. Create a new key, copy the value

**Pricing:** Pay-per-use. Flux image generation is typically a few cents per image.

**Required:** Yes — image generation will fail without this key.

---

### 3. ElevenLabs (`ELEVENLABS_API_KEY`)

**Used for:** Text-to-speech voiceover and voice cloning

**How to get it:**
1. Go to https://elevenlabs.io/
2. Sign up or log in
3. Click your profile icon → **Profile + API key**
4. Copy your API key

**Pricing:** Free tier includes limited characters/month. Paid plans start at $5/month for more usage.

**Required:** Yes — audio generation will fail without this key.

---

### 4. Google OAuth2 (`GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET`)

**Used for:** YouTube video upload and scheduling

**How to get it:**
1. Go to https://console.cloud.google.com/
2. Create a new project (or select an existing one)
3. Enable the **YouTube Data API v3**:
   - Go to **APIs & Services → Library**
   - Search for "YouTube Data API v3" and click **Enable**
4. Configure the **OAuth consent screen**:
   - Go to **APIs & Services → OAuth consent screen**
   - Choose **External** user type
   - Fill in app name, support email, etc.
   - Add scope: `https://www.googleapis.com/auth/youtube.upload`
   - Add your Google account as a test user (while in "Testing" mode)
5. Create **OAuth 2.0 credentials**:
   - Go to **APIs & Services → Credentials**
   - Click **Create Credentials → OAuth client ID**
   - Application type: **Web application**
   - Add authorized redirect URI: `http://localhost:8420/api/publish/oauth/callback/youtube`
   - Copy the **Client ID** and **Client Secret**

**Required:** Only if you want to publish directly to YouTube from the app.

---

## System Dependencies

### 5. FFmpeg

**Used for:** Video rendering, scene assembly, TikTok export, thumbnail compositing

**How to install:**

```bash
# macOS (Homebrew)
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows (Chocolatey)
choco install ffmpeg
```

Verify it's installed: `ffmpeg -version`

**Required:** Yes — video rendering will fail without FFmpeg.

---

## Setting Environment Variables

Create a `.env` file in the project root or export the variables in your shell:

```bash
# Required for AI features
export ANTHROPIC_API_KEY="sk-ant-..."
export FAL_KEY="..."
export ELEVENLABS_API_KEY="..."

# Optional — only for YouTube publishing
export GOOGLE_CLIENT_ID="...apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="GOCSPX-..."
```

If running via Electron (`npm run dev`), the backend inherits environment variables from your shell. Make sure they're exported before launching.

---

## Quick Start

```bash
# 1. Set your API keys (add to ~/.zshrc or ~/.bashrc for persistence)
export ANTHROPIC_API_KEY="your-key"
export FAL_KEY="your-key"
export ELEVENLABS_API_KEY="your-key"

# 2. Install dependencies
npm install
cd backend && uv sync && cd ..
cd frontend && npm install && cd ..

# 3. Run the app
npm run dev
```

---

## Troubleshooting

| Problem | Likely Cause |
|---------|-------------|
| Images fail to generate | `FAL_KEY` not set or invalid |
| Audio fails to generate | `ELEVENLABS_API_KEY` not set or invalid |
| Script/idea generation fails | `ANTHROPIC_API_KEY` not set and no local proxy running |
| YouTube publish fails | `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` not set, or OAuth redirect URI misconfigured |
| Video render fails | FFmpeg not installed or not on PATH |
