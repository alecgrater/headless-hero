# Headless Hero — Setup Guide

## Required API Keys & Services

### 1. Anthropic Claude API (`ANTHROPIC_API_KEY`)

**Used for:** Script generation, idea generation, FX generation, Eli animation, SEO metadata, thumbnail concepts

**How to get it:**
1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Navigate to **API Keys** in the dashboard
4. Click **Create Key**, copy the value

**Fallback:** If not set, the app falls back to a local proxy at `http://localhost:11211/api/anthropic`. You only need this key if you're not running a local proxy.

---

### 2. Google AI Studio (`GOOGLE_AI_KEY`)

**Used for:** AI image generation (scene images, thumbnails, Eli character frames) via Gemini 2.5 Flash

**How to get it:**
1. Go to https://ai.google.dev/
2. Sign up or log in with your Google account
3. Click **Get API key** → **Create API key**
4. Copy the generated key

**Pricing:** Free tier available with rate limits. Pay-as-you-go for higher volume.

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

### 5. Replicate (`REPLICATE_API_TOKEN`) — Optional

**Used for:** Alternative image generation via Flux 1.1 Pro (can be used instead of Google Gemini)

**How to get it:**
1. Go to https://replicate.com and sign up
2. Add a payment method at [replicate.com/account/billing](https://replicate.com/account/billing) (Flux costs ~$0.04/image)
3. Create a token at [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens) — it starts with `r8_`

**How to enable:**
1. In Headless Hero, go to **Settings → API Keys** and paste your token
2. Go to **Settings → General** and change the **Image Provider** dropdown to **Replicate (Flux)**

To switch back, change the Image Provider dropdown back to **Google Gemini**.

**Required:** No — Google Gemini is the default image provider.

---

## System Dependencies

### 6. FFmpeg

**Used for:** Audio concatenation and thumbnail compositing

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

**Required:** Yes — audio export will fail without FFmpeg.

---

## Setting Environment Variables

Create a `.env` file in the project root or export the variables in your shell:

```bash
# Required for AI features
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_AI_KEY="..."
export ELEVENLABS_API_KEY="..."

# Optional — only for YouTube publishing
export GOOGLE_CLIENT_ID="...apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="GOCSPX-..."

# Optional — only if using Replicate instead of Gemini
export REPLICATE_API_TOKEN="r8_..."
```

If running via Electron (`npm run dev`), the backend inherits environment variables from your shell. Make sure they're exported before launching.

---

## Quick Start

```bash
# 1. Set your API keys (add to ~/.zshrc or ~/.bashrc for persistence)
export ANTHROPIC_API_KEY="your-key"
export GOOGLE_AI_KEY="your-key"
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
| Images fail to generate | `GOOGLE_AI_KEY` not set or invalid (or `REPLICATE_API_TOKEN` if using Replicate) |
| Audio fails to generate | `ELEVENLABS_API_KEY` not set or invalid |
| Script/idea generation fails | `ANTHROPIC_API_KEY` not set and no local proxy running |
| YouTube publish fails | `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` not set, or OAuth redirect URI misconfigured |
| Audio export fails | FFmpeg not installed or not on PATH |
