# Flip-flop Test Lab Tab

## Goal

Add a Test Lab tab for flip-flop visual diagnostics that can create a stable reusable fixture once, then rerun anchor detection, overlay placement, and Remotion previews against existing generated cutout PNGs without repeat Gemini or ElevenLabs calls.

## Plan

1. Add a backend helper that lists cached Test Lab flip-flop base cutouts and analyzes one selected PNG using the current deterministic anchor detector.
2. Save a debug overlay image beside the selected asset so the frontend can display detector points and rerun the same asset repeatedly with cache busting.
3. Add Test Lab API endpoints for listing and analyzing flip-flop debug assets.
4. Add frontend API/types and a new `Flip-flop` tab next to `Scene Pipeline` and `Popup Crop`.
5. Cover the no-provider-call workflow with backend and frontend tests.
6. Add persistent fixture controls so a saved base cutout can be generated once, selected later, and rerendered locally as renderer logic changes.
