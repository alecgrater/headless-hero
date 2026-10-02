# YOLO Mode Reliability

Decision history for why YOLO mode retries, what it refuses to skip, and why
every run writes a log. Read this before changing retry counts, the
required/skippable split, or the run-history storage.

## The problem it solves

YOLO mode drives the whole pipeline — title cards through export bundle — from
the browser, and a full project takes well over an hour. In practice it stopped
2–4 times per project. Pressing YOLO again resumed correctly and usually got
further, so the work itself was fine; the run was giving up on it.

Three causes, all in `TimelinePage`'s pipeline:

1. **Hard aborts on partial completion.** Each stage ended with a completion
   check that threw — `"Image generation did not complete for every visual
   scene"` and its siblings. But batch image generation deliberately tolerates
   per-scene failures (it marks them failed and continues), so one flaky
   provider call out of sixty reached that check and ended the run.
2. **One try/catch around all twelve stages.** Any throw skipped every
   remaining stage.
3. **No retry anywhere.** Clicking YOLO again *was* the retry.

Going away from the machine made it worse: the renderer's `setTimeout` polling
loops were subject to Chromium background throttling on an occluded window, and
the machine could suspend the app outright.

And because the operator was always away when it happened, the error toast had
disappeared by the time they looked. There was no record of which stage failed.

## What it does now

**Retry, then continue.** `YoloRunController.stage()` runs each stage up to
`YOLO_STAGE_ATTEMPTS` times with `YOLO_RETRY_BACKOFF_MS` backoff. A stage's
`run` regenerates only what is missing, so a retry is cheap and idempotent, and
its `verify` re-reads the backend rather than trusting a resolved promise.

Status reads inside a stage go through the strict `requireShortForm*Status`
helpers, not the swallowing `refreshShortForm*Status` ones: an unreachable
status endpoint returning `{}` is indistinguishable from "nothing has been
generated", which would re-render every short — once per retry.

**Audio is the only required stage.** Scene audio durations are the render's
timing source of truth, so producing a video without them wastes an hour on
something broken — that one halts. Every other stage records the failure and
the pipeline carries on:

- missing images are backfilled at render time by
  `remotion_render.ensure_renderable_scene_images`;
- FX, Eli, SEO, and thumbnails degrade the output rather than break it.

The run then finishes as `completed_with_failures` and names the unresolved
stages, which is strictly more useful than stopping at the first one.

### Rejected alternatives

- **Retry forever.** A genuinely broken provider key turns into an infinite
  loop that looks identical to a slow run.
- **Halt on any failure (just with retries in front).** That is the old
  behaviour with a longer fuse; the operator still comes back to an unfinished
  project when the only problem was two cosmetic FX assignments.
- **Skip the completion checks entirely.** They are the only thing that
  notices a batch reporting per-item failures. Verify stays; the reaction to it
  changed.

## Why runs are persisted

An hour-long unattended run needs a durable record, not a toast. The controller
PUTs a full run snapshot to `/api/yolo/runs/{script_id}` at every transition and
`pipeline.yolo_runs` keeps the last `MAX_RUNS` under
`data/projects/{script_id}/yolo/runs.json`.

Whole snapshots rather than per-stage deltas: a retried PUT cannot corrupt the
record. That only covers corruption, though, not staleness — the controller
fires writes without awaiting, so `saveYoloRun` chains them per project and
`save_run` holds a lock around its read-modify-write. Without both, the last
stage's "running" snapshot could land after the terminal one and the run would
stay recorded as in-progress forever. Each PUT also emits one dev-dashboard
line, so the run is greppable alongside backend logs.

`TimelinePage` loads the newest run on mount and renders `YoloRunSummary`, so
the answer to "what happened while I was away" survives a reload and an app
restart. A stored run still marked `running` was interrupted — the app was
quit, crashed, or killed before the controller could close the run — so it is
shown as "Interrupted" rather than filtered out. Those are the cases where
"which stage was it on when it died" matters most.

## Stopping a run

Stop cancels work; it does not tear down the stack. The button calls
`POST /dev/api/kill-all`, which sets the cancel event on every background job
(image batches and render phases check it, and tracked Remotion subprocesses
are terminated), while the frontend sets its cancel refs. Every job poller
throws on a `cancelled` status, the controller sees `isCancelled()`, and the run
closes itself as `cancelled` and releases keep-awake in its own `finally`.

It used to be different: from May 2026 Stop went through a
`stopYoloProcesses` IPC that killed the backend and Vite listeners and then
called `app.quit()`. That closed the app on every Stop, and because the quit
landed ~100 ms later the controller never wrote its terminal snapshot, so every
deliberate Stop was later shown as "Interrupted". Cooperative cancellation
already covered the expensive work, so the teardown bought nothing.

What Stop does not interrupt: LLM jobs that never check the cancel event (FX,
Eli, visual-mode analysis) finish their in-flight calls in the background and
save the result, which costs cents. An image batch checks between rounds, but a
Google Batch poll already in progress runs to completion (that round is billed
either way). Pressing YOLO again immediately can overlap those last writes;
cached outputs mean the new run reuses rather than duplicates them. Any new
backend loop that generates paid assets must check `is_cancelled(job_id)` per
item, as the title-card chapter loop does.

## Timing display

`YoloProgressStrip` ticks once a second (never `requestAnimationFrame` — see the
Local Models notes on the 340k-re-render progress bar) and shows current-stage
elapsed, total elapsed, and a click-to-expand per-stage breakdown.
`YoloRunSummary` shows the same breakdown for a finished run. This is separate
from `recordDuration()`, which still feeds the cross-run ETA system.

## Keeping the run alive

`electron/main.js` sets `backgroundThrottling: false` on the window and holds a
`powerSaveBlocker("prevent-app-suspension")` for the duration of a run, started
and stopped through the `set-keep-awake` IPC. Both are needed: throttling slows
the polling loops on an occluded window, and suspension stops them outright.

## Open gaps

- Background jobs live in an in-memory dict on the backend, so a backend
  restart mid-run makes the in-flight job 404. The stage retry recovers by
  starting the work again, but the elapsed time is lost.
- The export stage has no `verify`; it relies on `render.yoloRender` throwing.
  Re-running it is cheap (it checks for an existing long-form render first),
  but a silent partial export would not be retried.
