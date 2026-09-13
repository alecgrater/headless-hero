# Local Models Mode — Design

Date: 2026-09-12
Status: Approved design, pending implementation plan

## 1. Purpose

Add a Settings-configurable **Local Mode** that replaces the cloud models used
across the generation workflow with local models running on this machine
(MacBook Pro 16", M4 Max, 48 GB unified memory). Local Mode is an override
layer over the existing provider routing — it removes nothing and changes no
cloud default.

Goals:

- One switch that moves text, image, and voice generation onto local models.
- Per-modality escape hatches, so any single modality can stay on the cloud.
- A provisioning script that installs and configures the runtimes and weights.
- No silent quality traps: caches invalidate, costs report as zero, and the
  dev dashboard says which engine produced each asset.

## 2. Decisions

These were settled with the user before this spec was written.

| Question | Decision |
|---|---|
| AI video in Local Mode | **Stays on the cloud** (Runway / fal). No local video provider. |
| Setting granularity | **Master switch plus per-modality overrides** (`auto` / `local` / `cloud`). |
| Local voice engine | **Higgs TTS 3 (4B)**, chosen for expressiveness over speed. |
| Higgs attribution requirement | **Auto-append the credit** to generated SEO descriptions. |
| Memory contention | **Run one heavy model at a time**, favouring quality over wall-clock. |
| Install autonomy | **Full auto**, including ACC domain-allowlist edits, with every change reported. |

## 3. Model selection

All four selections were verified on Hugging Face on 2026-09-12.

| Modality | Model | License | On-disk | Notes |
|---|---|---|---|---|
| Text — narrative | `Qwen3.8-27B` GGUF Q4_K_M | Apache 2.0 | ~17 GB | Dense, 262k context. Thinking mode on by default; `llm_client._strip_think_blocks` already handles the `<think>` blocks. |
| Text — structured | same 27B model by default | Apache 2.0 | shared | Serves the tasks whose `openai_reasoning_effort` is `minimal`. See 3.3. |
| Image | `FLUX.2-klein-4B` **or** `Qwen-Image-Edit-2511` Q4_K_M | Apache 2.0 (both) | 13 GB / 13.2 GB | Both support multi-reference editing, which the character/style reference pipeline requires. |
| Voice | `Higgs TTS 3 4B`, MLX build | Boson research/non-commercial **+ Creator Use Grant** | ~4 GB | Zero-shot cloning, 21 emotion tags, 24 kHz. Kokoro-82M (Apache 2.0) and Chatterbox (MIT) ship as selectable alternatives. |
| Video | unchanged | — | — | Runway Gen-4 Turbo / fal Wan 2.2, exactly as today. |

### 3.1 Image default is chosen by measurement, not by preference

`FLUX.2-klein-4B` is 4-step distilled and therefore much faster;
`Qwen-Image-Edit-2511` explicitly targets character consistency, which the
Eli / style-preset-character pipeline depends on. Implementation installs both,
benchmarks them on real scene prompts with a character reference, and sets the
default from measured seconds-per-image plus character-consistency spot checks.
The measured numbers are reported to the user and recorded in this repo.

### 3.2 The fast text tier defaults to the same model

`LOCAL_TEXT_FAST_MODEL` exists so the cheap structured-JSON tasks can run on a
smaller model, but it **defaults to the same 27B id as the narrative tier**.
Under a one-model-at-a-time arena, a second text model buys speed on individual
calls while adding an unload/reload cycle every time the pipeline alternates
between narrative and structured tasks, which is the common case. Pointing the
key at a smaller model is a measured optimisation to make later, not a default
to assume; it is exposed in Settings so it can be changed without code.

### 3.3 Higgs attribution is enforced by the code, not by the user

The Boson licence permits monetized video under a Creator Use Grant *provided
the work credits Boson AI's Higgs Audio in the audio or in visibly accompanying
text*. Attribution is therefore a property of the model, not a user preference:
the local model registry carries a `requires_attribution` field and an
attribution string, and SEO description generation appends that string whenever
the project's voiceover was produced by a model that requires it. There is no
setting to switch it off. Selecting Kokoro or Chatterbox removes the credit
because those licences do not ask for one.

## 4. Runtime topology

Three local daemons, started on demand and health-checked by a new
`backend/pipeline/local_runtime.py`:

| Daemon | Port | Serves |
|---|---|---|
| `ollama serve` | 11434 | Text. Already assumed by `scripts/mac-app-launcher.sh`. |
| ComfyUI | 8188 | Image, GGUF weights via ComfyUI-GGUF on PyTorch MPS. |
| `mlx_audio.server` | 8770 | Voice, OpenAI-compatible `/v1/audio/speech`. |

`local_runtime` owns: health probes, on-demand start, readiness waits, and
structured dev-dashboard events for every start, stall, and failure. It never
kills a daemon the user started by hand.

### 4.1 Memory arena

17 GB text + 13 GB image + 4 GB voice, plus Electron, Vite, and Remotion's
Chromium, exceeds 48 GB. Because the pipeline phases are already sequential
(script → images → voice → render), Local Mode enforces **at most one heavy
model resident at a time**:

- Ollama is called with a short `keep_alive` in Local Mode instead of `30m`.
- ComfyUI is sent `/free` after an image phase completes.
- All local models are unloaded before `remotion_render.render_full_video`
  starts, since the renderer is the largest memory consumer in the app.

The arena is a module-level lock in `local_runtime`, not a setting. Acquiring
the lock for a different modality unloads the previous occupant.

## 5. Settings surface

A new **Local Models** section under the *AI & Generation* group in
`SettingsPage.tsx`, following the framed-section-header convention.

It contains: the master switch, three modality selectors, the model pickers for
each modality, and a live status panel showing per-daemon health, which weights
are installed, resident memory, and total disk used. Non-obvious controls get
hint text, per the project's feature-UX convention.

New keys, added to `ALLOWED_KEYS`, `_PLAINTEXT_KEYS`, and `_DEFAULTS` in
`backend/api/settings.py`:

| Key | Values | Default |
|---|---|---|
| `LOCAL_MODELS_ENABLED` | `true` / `false` | `false` |
| `LOCAL_TEXT_MODE` | `auto` / `local` / `cloud` | `auto` |
| `LOCAL_IMAGE_MODE` | `auto` / `local` / `cloud` | `auto` |
| `LOCAL_VOICE_MODE` | `auto` / `local` / `cloud` | `auto` |
| `LOCAL_TEXT_MODEL` | registry id | narrative 27B id |
| `LOCAL_TEXT_FAST_MODEL` | registry id | same as `LOCAL_TEXT_MODEL` |
| `LOCAL_IMAGE_MODEL` | registry id | `qwen-image-edit-2511`, revised if the benchmark favours klein-4B |
| `LOCAL_VOICE_MODEL` | registry id | `higgs-tts-3-4b` |
| `LOCAL_COMFYUI_URL` | URL | `http://127.0.0.1:8188` |
| `LOCAL_TTS_URL` | URL | `http://127.0.0.1:8770` |

`auto` means "follow `LOCAL_MODELS_ENABLED`". `local` and `cloud` pin that
modality regardless of the master switch. There is no key for AI video, which
is cloud-only by decision.

### 5.1 Model registry

`backend/integrations/local_models.py` holds a declarative registry, in the
same spirit as `LLM_TASKS` and `VideoFormat`: one entry per local model with
its id, modality, serving backend, weight source, approximate resident memory,
licence, and `requires_attribution` / `attribution_text`. The registry is the
single source of truth for the Settings pickers, the installer script, and the
attribution logic — adding a model means adding one entry.

## 6. Code seams

The existing abstractions are close to right, so the changes are narrow.

**Text.** `llm_client._resolve_provider` and `_resolve_model` consult the Local
Mode override before per-task settings: when text resolves to local, the
provider is forced to `ollama` and the model to `LOCAL_TEXT_MODEL` for
narrative tasks or `LOCAL_TEXT_FAST_MODEL` for tasks whose
`openai_reasoning_effort` is `minimal`. Per-task keys keep working when Local
Mode is off. `ALLOWED_PROVIDERS` is unchanged.

**Image.** `image_client.generate_image` gains a `local` provider that
delegates to a new `integrations/local_image_client.py` speaking the ComfyUI
HTTP API. Two functions currently bypass the router and would silently stay on
Gemini, so they move behind it as well:

- `pipeline/thumbnail.py:181` and `:439` — `transform_with_references`
- `pipeline/main_character.py:19` — `generate_image`
- `pipeline/image_gen.py:15` — `generate_images_batch`

`image_client` therefore grows `transform_with_references` and
`generate_images_batch` alongside `generate_image`, and becomes the only
module that names an image provider. On the local backend, `generate_images_batch`
maps onto sequential ComfyUI calls, because batching exists to amortise cloud
round-trips and buys nothing locally.

**Voice.** A new `integrations/local_tts_client.py` implements
`generate_speech(...) -> tuple[bytes, list[dict]]` — byte-for-byte the same
contract as the ElevenLabs client, so `voiceover.py` and everything downstream
of it are untouched apart from selecting the client. The local path produces
WAV, transcodes to MP3 with the ffmpeg already in the stack, and derives word
timestamps from the existing `pipeline/audio_alignment.align_audio` faster-whisper
aligner rather than inventing a second timing source. Voice-settings mapping is
per-model and lives in the registry; Higgs emotion tags are **not** auto-injected,
consistent with the project's rule that expressiveness comes from settings
rather than narration rewrites.

**Attribution.** `pipeline/seo.py` appends the registry's attribution string to
the generated description when the project's voiceover came from a model that
requires it.

**Video.** `pipeline/video_gen.py` is unchanged. Note that in Local Mode the
AI-video *anchor image* is generated locally and then animated in the cloud,
which is intended. `video_gen._cache_marker` already fingerprints
`IMAGE_PROVIDER`, so switching modes invalidates stale video clips for free.

## 7. Cache invalidation

Local and cloud assets are not interchangeable, so every fingerprint that can
outlive a mode switch must include the local model identity:

- Image `.prompt` marker files gain the resolved image provider and model id.
- `remotion_render.subtitle_render_fingerprint` gains the voice model id.
- Audio caching keys on the voice model id, so flipping engines re-voices
  rather than mixing two narrators inside one video.

Per the project's forward-only bias, existing cloud-generated assets are simply
treated as stale under Local Mode. No migration shim.

## 8. Observability and cost

Local calls go through `record_usage` with `service="local_text"`,
`"local_image"`, or `"local_voice"` and `cost_estimate=0.0`, so the project
cost breakdown shows local runs as free rather than as missing data. Token and
character counts are still recorded where the backend reports them.

Dev-dashboard events cover daemon lifecycle, model load and unload, per-asset
engine attribution, and every fallback from local to cloud, matching the
project's rule that new generation behaviour is observable.

## 9. Provisioning

`scripts/install-local-models.sh`, idempotent and checked into the repo:

1. Add the required hosts to `~/.claude/apple/dangerous_allowed_domains.csv`,
   reporting each one. `huggingface.co` and its CDN hosts are already present;
   `ollama.com`, `registry.ollama.ai`, `pypi.org`, `files.pythonhosted.org`,
   and the Homebrew bottle hosts are not.
2. `brew install ollama`, then pull the two text models.
3. Install ComfyUI plus ComfyUI-GGUF, and fetch the image weights.
4. `uv tool install mlx-audio`, and fetch the Higgs MLX weights.
5. Verify each daemon answers a health probe, and print a summary.

Roughly 50–70 GB of weights against 690 GB free. `scripts/mac-app-launcher.sh`
gains health checks for the new daemons, following its existing rule of freeing
only stale listeners it owns.

## 10. Verification

- Backend pytest: Local Mode routing precedence, the local TTS contract shape,
  fingerprint invalidation across a mode switch, attribution injection, and
  registry integrity.
- Frontend Vitest for the new Settings section.
- Test Lab support for local image generation, per the project rule that new
  scene visual functionality gets equivalent Test Lab coverage.
- One complete short project generated end to end in Local Mode, with measured
  per-stage timings reported to the user. This is the acceptance gate; unit
  tests alone do not demonstrate that the mode works.

## 11. Documentation

`CLAUDE.md` gains a Local Models section covering the master switch, the
registry, the memory arena, and the attribution rule. The in-app docs
(`frontend/src/components/docs/`) gain a Local Mode section, since the
end-to-end workflow changes and the project requires workflow changes to reach
the in-app docs in the same change.

## 12. Risks

- **Quality regression.** Local output will be visibly weaker than Claude,
  Gemini, and ElevenLabs. Per-modality overrides exist precisely so individual
  stages can be moved back.
- **Image throughput.** The dominant cost in a local video. Mitigated by
  choosing between a 4-step distilled model and a quality model on measured
  evidence rather than assumption.
- **ComfyUI on MPS.** The least mature dependency in the stack. If it proves
  unworkable, the fallback is a direct diffusers-on-MPS worker behind the same
  `local_image_client` interface; the seam does not change.
- **Serialized stages.** Accepted by decision. A full local video takes longer
  end to end than a cloud one, beyond the per-call latency difference.

## 13. Out of scope

Local AI video, local YouTube publishing, replacing faster-whisper, removing
any cloud provider, and multi-machine or remote local-model serving.
