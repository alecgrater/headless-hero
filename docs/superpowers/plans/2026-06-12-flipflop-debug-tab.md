# Flip-flop Debug Tab

## Goal

Add a Test Lab tab for flip-flop visual diagnostics that can rerun anchor detection and overlay placement against existing generated cutout PNGs without making Gemini, ElevenLabs, or render-provider calls.

## Plan

1. Add a backend helper that lists cached Test Lab flip-flop base cutouts and analyzes one selected PNG using the current deterministic anchor detector.
2. Save a debug overlay image beside the selected asset so the frontend can display detector points and rerun the same asset repeatedly with cache busting.
3. Add Test Lab API endpoints for listing and analyzing flip-flop debug assets.
4. Add frontend API/types and a new `Flip-flop Debug` tab next to `Scene Pipeline` and `Popup Crop`.
5. Cover the no-provider-call workflow with backend and frontend tests.
