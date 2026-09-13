# Local Model Benchmarks

Measured on the machine this project targets. Numbers here are the basis for
the Local Mode defaults in `backend/integrations/local_models.py` — they are
not estimates.

**Hardware:** MacBook Pro 16", Apple M4 Max, 48 GB unified memory, macOS 27.0
**Date:** 2026-09-12
**Stack:** ComfyUI on PyTorch 2.14 MPS, ollama 0.33.3, mlx-audio (uv tool)

## Images

All runs at 1920×1080, the project's render resolution, through
`integrations.image_client.generate_image` — the same path production uses, not
a bespoke harness.

| Model | Precision | Steps | Cold | Warm | Verdict |
|---|---|---|---|---|---|
| `Qwen-Image-Edit-2511` | GGUF Q4_K_M (12 GB) | 20 | 791 s | 800 s, 801 s | Rejected |
| `FLUX.2-klein-4B` | safetensors (7.2 GB) | 4 | 45 s | 33 s | **Default** |

Qwen-Image-Edit's 800 s is a steady-state rate, not a cold-start artifact —
three consecutive images landed within 10 s of each other. At that rate a
40-scene video needs about **9 hours of image generation alone**, so it fails
the "more than three times slower" clause in the selection rule by a factor of
eight. It stays in the registry as a selectable option because its output
quality is good and a user may prefer it for a small batch, but it is not a
sane default.

Two effects compound in the gap: klein-4B is a 4 B model against a 20 B one,
and it is step-distilled to 4 sampling steps against 20. GGUF dequantisation
overhead on MPS likely contributes as well, since klein runs from plain
safetensors.

### Character consistency

The deciding capability, since the Eli / style-preset-character pipeline
depends on it. A character reference was generated, then a scene was generated
conditioned on it through `reference_image_path`:

| Step | Time | Result |
|---|---|---|
| Character reference, 1024×1024 | 14 s | Clean flat-2D character sheet |
| Scene conditioned on that reference, 1920×1080 | 50 s | Identity preserved |

The scene retained the round glasses, curly dark hair, teal shirt, grey hoodie,
and facial structure of the reference. FLUX.2 conditions through chained
`ReferenceLatent` nodes rather than encoder image slots, which is why
`local_image_client` carries a per-workflow `reference_mode`.

Practical throughput for a 40-scene video: roughly **22 minutes** unreferenced,
or **33 minutes** with a character reference on every scene.

## Text

`Qwen3.8-27B` GGUF UD-Q4_K_M (16 GB) via ollama, called through
`integrations.llm_client.chat`.

| Call | Time |
|---|---|
| Short completion, cold (includes model load) | 16 s |

The registry originally recorded this model as `Q4_K_M`; Unsloth publishes it
as `UD-Q4_K_M` (Unsloth Dynamic). The pull fails silently against the wrong tag,
which is why the installer validates it.

## Voice

`Higgs TTS 3 4B`, MLX 6-bit (3.7 GB) via mlx-audio, called through
`integrations.local_tts_client.generate_speech`.

| Call | Time | Output |
|---|---|---|
| 10-word sentence, cold (model + whisper load) | 43 s | MP3 + 10 aligned words |
| 18-word sentence, warm | 3.7 s | MP3 + 18 aligned words |
| 18-word sentence, warm | 3.1 s | MP3 + 18 aligned words |

Word timestamps come from the existing faster-whisper aligner and matched the
ElevenLabs `{word, start_ms, end_ms}` shape exactly, so nothing downstream of
`voiceover.py` changes.

Practical throughput for a 40-scene video: roughly **2.5 minutes** of narration
generation.

## What this means for a full local video

Adding the stages, and remembering that the memory arena runs them one at a
time rather than overlapping:

| Stage | Estimate |
|---|---|
| Script and metadata (text) | a few minutes |
| Images, 40 scenes with references | ~33 min |
| Voiceover, 40 scenes | ~2.5 min |
| Remotion render | unchanged from cloud mode |

Local Mode is therefore viable end to end, with images dominating the cost — as
expected, and now with a real number attached rather than an assumption.

## Corrections this benchmarking forced

Three registry entries were wrong as originally specified, and were only caught
by installing them:

- Text model tag is `UD-Q4_K_M`, not `Q4_K_M`.
- Kokoro needs `mlx-community/Kokoro-82M-bf16`; the upstream `hexgrad/Kokoro-82M`
  ships `.pth` weights that mlx-audio cannot load.
- Chatterbox likewise needs `mlx-community/Chatterbox-TTS-8bit`.

Separately, `ffmpeg` was not installed on this machine at all, which would have
broken the existing audio-export and render paths independently of Local Mode.
