# Local Models Mode — end-to-end acceptance run

Companion to `docs/local-models-benchmarks.md`, which measures the models in
isolation. This file measures one real project going through the product's own
pipeline with Local Mode on.

**Hardware:** MacBook Pro 16", Apple M4 Max, 48 GB unified memory, macOS 27.0
**Date:** 2026-09-13
**Commit under test:** `34ebe5b4`
**Daemons:** started by `scripts/install-local-models.sh` — ollama `:11434`,
ComfyUI **`:8188`** (the product default; `LOCAL_COMFYUI_URL` must agree),
mlx-audio `:8770`. All three reported healthy from `GET /api/local-models`
before the run started.

**Configuration:** `LOCAL_MODELS_ENABLED=true`, all three modalities on `auto`,
so text/image/voice resolved to `local`. Models: `qwen3.8-27b`,
`flux2-klein-4b`, `higgs-tts-3-4b`. No cloud credentials exist on this machine
(`.env` is absent and `app_settings` holds no API keys), so nothing could have
silently fallen back to a cloud provider — a stage either ran locally or failed.

**Project:** `youtube-listicle`, "5 Everyday Objects That Were Invented By
Accident", `segmented=True` (the frontend default), Eli enabled. The listicle
format is fixed at 8 segments, so this is the smallest real listicle the product
can produce.

The run was driven through the backend's own HTTP API, stage by stage in the
order the app's YOLO button uses: script → title cards → voiceover → images →
SEO → render.

## Status: failed at segment 5 of 8, after 65 minutes

The script stage ran for **3 922 s (65.4 min)** and then aborted:

```
RuntimeError: Segmented script generation failed on segment 5/8
("The Annoying Burrs"): response could not be parsed (likely truncated or
malformed): Expecting value: line 1 column 1 (char 0)
```

No later stage ran. The failure is reported cleanly — the job goes to `failed`
with the segment named, nothing is half-written — but it is a failure, and a
65-minute one.

`Expecting value: line 1 column 1 (char 0)` means the parser was handed an
**empty string**. Ollama itself returned `200` after 13m33s with
`truncated = 0` and 21 900 tokens in the slot, so the model did answer. Two
candidates, not distinguished here:

* the response was entirely `<think>…</think>`, which `_strip_think_blocks`
  removes — i.e. this one call ignored `chat_template_kwargs.enable_thinking =
  false`; or
* `response_format: json_object` produced content the OpenAI-compatible shim
  returned as an empty `message.content`.

Either way the failure is **unhandled**: `_generate_segment_scenes` raises and
the whole 65-minute run is lost, with no retry and no partial save. Four
segments' work was thrown away. Worth fixing before local text is offered as a
supported path — a one-shot retry on an empty response would have cost ~11 more
minutes instead of everything.

## Stage 1 — script (measured, aborted)

Two-phase segmented generation: one outline call, then one call per segment.

| Call | Wall clock | Output tokens | Rate | |
|---|---|---|---|---|
| Outline | 480 s (8.0 min) | ~8 200 | 15.5 tok/s |
| Segment 1 — The Happy Accident | 651 s (10.9 min) | ~9 800 | 15.1 tok/s |
| Segment 2 — The Weak Glue | 880 s (14.7 min) | ~13 300 | 15.1 tok/s |
| Segment 3 — The Moldy Disaster | 441 s (7.4 min) | ~6 700 | 15.2 tok/s |
| Segment 4 — The Melting Chocolate | 660 s (11.0 min) | ~10 000 | 15.2 tok/s |
| Segment 5 — The Annoying Burrs | 813 s (13.6 min) | ~12 400 | 15.7 tok/s | **returned unparseable — run aborted** |
| Segments 6–8 | not reached | | |

Measured total before the abort: **3 922 s (65.4 min)** for the outline plus
five segment calls. Had segment 5 parsed, the projected total would have been
**~95 minutes** (8 min outline + 8 × ~11 min). The variance between calls is
output length, not speed.

An isolated control run through the same ollama endpoint — a 6-scene listicle
segment as JSON — produced 6 839 tokens in 388 s at **17.6 tok/s**, matching the
in-pipeline rate.

### What this changes about the numbers already on file

`docs/local-models-benchmarks.md` says "effective throughput is a few tokens per
second". **That is no longer true and should be read as pre-`enable_thinking:
false` data.** With reasoning disabled the model sustains **15–17.6 tok/s**, a
roughly 10× correction. Every figure in this file was taken after that fix.

So the problem is not that the model is slow. It is that **each segment call
emits 7 000–13 000 tokens**, and there are nine calls.

### The timeout does not need raising

The longest single call observed was 14.7 minutes. `LOCAL_TEXT_TIMEOUT_SECONDS`
already floors every local text call at 1800 s (30 min), which is roughly double
the worst case — the largest legal response, 32 768 tokens at 15 tok/s, would be
36 minutes, but nothing came close. **The earlier "script generation kept
exceeding timeouts" symptom was the pre-fix reasoning overhead, and it is gone.**
Raising the timeout further would fix nothing; the cost is the sum of nine
legitimate calls, each of which completes.

## Stages 2–6 — not reached

The run aborted in stage 1. The per-model figures in
`docs/local-models-benchmarks.md` still apply and imply, for a ~40-scene video:
images ~33 min with a character reference on every scene, voiceover ~2.5 min,
render unchanged from cloud mode. Nothing in this run contradicts them; they
simply were not re-measured end to end.

## Verdict on local text, and the smaller-model trade-off

**Local text is both too slow and, on this evidence, not reliable enough to be a
default.** ~95 minutes of scripting before the first image is generated is
already outside what this product should ask for — the cloud path returns a
script in a couple of minutes — and the run did not even get there, losing 65
minutes to a single unparseable segment with no retry.

Three things follow, and the first is not about model choice at all:

**0. A segment that comes back empty must not cost the whole script.** Nine
sequential calls at ~11 minutes each means a per-call failure probability that
would be negligible against a 3-second cloud call is close to fatal here. One
retry on an empty/unparseable response, and persisting completed segments so a
resume is possible, are worth more than any speedup below.

Two levers, in the order they should be tried:

### 1. Output volume is the real cost, and it is not a model-size problem

At a fixed 15 tok/s, a 9 000-token segment costs 10 minutes no matter which
model writes it. Qwen3.8-27B is verbose here: `_SEGMENT_SCENES_INSTRUCTIONS`
is written for Claude and is given `max_tokens=32768`, which invites a long
answer. Halving the output halves the stage, on any model. This is worth
measuring before swapping models, and it costs nothing at inference time.

### 2. A smaller model — recommended as a *selectable option*, not a default

Adding a smaller text model to `local_models.REGISTRY` so `LOCAL_TEXT_MODEL` can
select it is the right shape: the registry already supports it, the setting
already exists, and nothing else changes.

**These are projections from the measured 15 tok/s, not measurements** — no
smaller model was benchmarked in this session, and that is the obvious next step:

| Model | Resident | Projected rate | Projected script stage | Trade-off |
|---|---|---|---|---|
| `qwen3.8-27b` (current) | 16.5 GB | 15–17.6 tok/s (measured) | ~95 min | Best narrative quality; unusable as a default |
| Qwen3 14B Q4 | ~9 GB | ~30 tok/s | ~50 min | Roughly 2× faster. Weaker long-form structure; the listicle's per-segment JSON schema is the risk — a schema miss costs a retry, which erases the gain |
| Qwen3 8B Q4 | ~5 GB | ~45 tok/s | ~33 min | Roughly 3× faster and the only option approaching tolerable. Expect visibly thinner narration; `SCRIPT_LLM_PROVIDER` per-task overrides let it serve the cheap structured tasks while the 27B keeps `script` |

The memory arena also gets cheaper: an 8 B text model plus the 7.2 GB image
model is 12 GB rather than 24 GB, which is the first configuration on this
machine where the single-resident constraint could plausibly be relaxed.

**Recommendation: keep `qwen3.8-27b` as the default for quality, register a
smaller sibling as a selectable option, and tell the user in Settings what the
script stage costs on each.** The honest framing for the UI is that fully local
text trades about an hour and a half of wall clock for zero API spend — which is
a real trade some users will take, and not one to make silently.

## Reproducing

The daemons are started and verified by:

```bash
scripts/install-local-models.sh          # start + verify
scripts/install-local-models.sh --check  # verify only; no installs, no allowlist writes
```

Then enable Local Mode in Settings → AI & Generation → **Local Models** (or set
`LOCAL_MODELS_ENABLED=true`), and generate a `youtube-listicle` project. Per-call
timings are visible in the ollama log (`/tmp/ollama.log`) and in the backend's
`Ollama call complete in %.1fs` lines.
