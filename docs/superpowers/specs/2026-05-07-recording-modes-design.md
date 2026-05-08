# Recording Modes & UX Improvements Design

## Summary

Implement the three recording modes (Single, Continuous, Free) that currently exist as UI-only toggles, plus three UX improvements: tooltips on mode buttons, auto-stop on silence for free mode, pre-roll beep, and clearer recording state indicators.

## Recording Modes

### Single (default, current behavior)
- Record one scene at a time. Press Space to start 3-2-1 countdown → record. Press Space to stop.
- Stay on the same scene after recording. Manual navigation to next scene.
- Tooltip: "Record one scene at a time with manual navigation."

### Continuous
- After stopping a recording (take uploaded), auto-advance to the next unrecorded narrated scene.
- Show a brief ~1.5s transition indicator, then auto-start the 3-2-1 countdown.
- Press Escape during countdown or transition to abort auto-advance and drop back to single mode.
- If no unrecorded scenes remain, show a toast "All scenes recorded!" and stop.
- Tooltip: "Auto-advance and record the next scene after each take."

### Free
- No countdown — Space starts recording immediately.
- Teleprompter text stays visible but fully static: no needle, no word highlighting, no WPM counter.
- Auto-stops recording after ~3 seconds of silence (once speech has been detected).
- Tooltip: "Record without teleprompter tracking. Auto-stops on silence."

### Rehearse (existing, unchanged)
- Tooltip: "Practice without recording. Teleprompter tracks normally."

## Auto-Stop on Silence (Free Mode)

- Monitor `recorder.audioLevel` during recording via `requestAnimationFrame` or interval.
- Track `hasSpoken` flag: set to true once audio level exceeds threshold (~0.05).
- Once `hasSpoken` is true, track consecutive low-level duration.
- If audio level stays below threshold for ~3 seconds, call `handleStopRecording()`.
- Reset `hasSpoken` when a new recording starts.
- Implemented in VoiceoverRecordingPage.tsx (not in the useRecorder hook, since it needs mode context).

## Pre-Roll Beep

- At the moment recording starts (countdown transitions to null), play a short ~120ms sine wave at 880Hz.
- Use Web Audio API: create OscillatorNode + GainNode, connect to destination, start/stop.
- Only plays in Single and Continuous modes (Free has no countdown).
- No external audio file needed.

## Recording State UI

- When not recording and no countdown: show a calm "Press Space to record" prompt in the teleprompter/bottom area.
- When countdown is active: existing countdown overlay (3-2-1) remains.
- When recording: prominent red pulsing indicator visible in the teleprompter area — more obvious than the current small corner pill.
- Bottom record button already changes to red when recording — keep this behavior.
- In Free mode, the prompt says "Press Space to record (no countdown)" to indicate the difference.

## Tooltips

- Add `title` attribute to each mode button (Single, Continuous, Free) and the Rehearse toggle.
- One-line descriptions as specified above.

## Files to Modify

- `frontend/src/components/recording/VoiceoverRecordingPage.tsx` — mode logic, auto-stop, beep, auto-advance, tooltips, state indicators
- `frontend/src/components/recording/TeleprompterPanel.tsx` — accept `isFreeMode` prop to disable needle/word tracking; accept recording state for indicator
- `frontend/src/components/recording/useRecorder.ts` — no changes needed (silence detection lives in the page component)
