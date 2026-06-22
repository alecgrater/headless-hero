# Google Batch Image Generation Design

## Context

Headless Hero currently labels several workflows as "batch" because they process many scenes, but the timeline's Generate All Images button still loops through normal `/api/visuals/generate` calls from the frontend. Each scene or frame uses the standard Google Gemini image-generation path, so it does not receive Google Batch API's lower pricing.

Google's Batch API is asynchronous, generateContent-only, priced at 50% of standard interactive API cost, and has a target turnaround of up to 24 hours. That tradeoff fits whole-project Generate All Images, but not interactive single-scene regeneration.

## Goal

Add an opt-in Settings toggle that lets Generate All Images use true Google Batch API pricing for eligible Gemini 2.5 Flash Image requests while keeping the current standard path available and easy to restore.

## Non-Goals

- Do not migrate the default image model to `gemini-3.1-flash-image`.
- Do not batch single-scene regeneration, title cards, thumbnails, Test Lab, style preset generation, image review edits, AI video, or layered cutout generation.
- Do not silently downgrade from a failed Google Batch job to standard paid calls.

## Setting

Add `GOOGLE_IMAGE_BATCH_ENABLED` to app settings.

- Default: `false`.
- UI placement: Settings -> Visuals near the image provider controls.
- Label: "Google Batch for Generate All".
- Helper text: Explain that this can roughly halve eligible Google image-generation cost, but may take much longer before images appear.

## Eligible Work

Batch mode applies only to Generate All Images requests from the timeline.

For v1, Google Batch handles only independent Gemini image requests that do not depend on previous generated outputs:

- `full_frame` scenes with one normal image.
- `captions` scenes with a non-empty visual prompt, treated like one normal image.
- Frame directives that are `ai_generated` and do not use `reference_previous`.

The standard path still handles:

- AI video scenes.
- Text-only captions scenes.
- Layered renderer modes (`popup_sequence`, `comparison_board`, `stat_card`, legacy/test `blink`).
- Frame directives that require previous-frame references or style anchors.
- Any request whose local cache is already valid.

This keeps quality-sensitive or sequential visual workflows on the existing behavior.

## Backend Architecture

Add a Google image batch helper in `backend/integrations/google_image_client.py` that:

- Builds inline Batch API requests using `DEFAULT_IMAGE_MODEL`.
- Uses the same prompt, aspect ratio, character reference, style reference, and source metadata semantics as the standard image client where possible.
- Polls the Google batch job until it reaches a terminal state.
- Writes returned inline image bytes to temporary PNG files.
- Records usage as `operation="image_gen_batch"` with the existing Google image cost estimate adjusted to the current app's cost model.

Add batch planning helpers in `backend/pipeline/image_gen.py` that:

- Compose prompts and cache checks before submission.
- Return a mixed plan of batch-eligible items and standard-path items.
- Save successful batch outputs to the same project image paths and prompt marker files as standard generation.
- Return the same result shape currently used by timeline image generation.

Add a background visual batch job endpoint in `backend/api/visuals.py`:

- `POST /api/visuals/generate-batch-job` starts a job and returns `job_id`.
- `GET /api/visuals/generate-batch-status/{job_id}` returns render-job status.
- The job decides whether to use true Google Batch from `GOOGLE_IMAGE_BATCH_ENABLED`.
- If the setting is off, the job uses the existing standard `generate_batch` path.
- If the setting is on, eligible work goes to Google Batch and unsupported work stays on the existing standard path.
- Google Batch failures produce a clear failed job message instead of silently rerunning everything as standard calls.

Persist generated scene assets after the background job completes using the same script JSON updates as the existing `/generate-batch` endpoint.

## Frontend Architecture

Timeline Generate All Images should:

- Continue generating title cards first.
- Send the collected scene payload to `/api/visuals/generate-batch-job`.
- Poll `/api/visuals/generate-batch-status/{job_id}` for progress.
- Refresh the script when the job completes.
- Keep existing cancel behavior by marking the local loop cancelled; v1 cancellation does not cancel a submitted Google Batch job.

Single scene regeneration stays on `/api/visuals/generate`.

## Observability

Add dev logs around:

- Whether full-project image generation used standard mode or Google Batch mode.
- Batch job name and eligible item count.
- Unsupported item count routed through the standard path.
- Failed Google Batch state or per-item errors.

## Compatibility

The toggle defaults off, so existing behavior remains the default. Enabling the setting changes only future Generate All Images runs; existing projects and cached images do not need migration.

## Testing

Backend tests should cover:

- Settings exposes and saves `GOOGLE_IMAGE_BATCH_ENABLED`.
- Batch mode disabled uses existing standard generation.
- Batch mode enabled routes eligible scene images through the Google batch helper.
- Unsupported modes stay on the standard path.
- Batch failures fail the background job without silently generating paid standard replacements.

Frontend tests should cover:

- The Visuals settings toggle loads and autosaves.
- Generate All Images starts the background visual batch job and polls status.

