/** Shared constants — keep in sync with backend/config.py where noted. */

// Backend server port — keep in sync with backend/config.py BACKEND_PORT
export const BACKEND_PORT = 8420;

// Default Claude model — keep in sync with backend/config.py DEFAULT_CLAUDE_MODEL
export const DEFAULT_MODEL = "anthropic.claude-opus-4-6-v1";

// Default Eli overlay position (bottom-right with padding)
export const DEFAULT_ELI_POSITION = { x: 1400, y: 835 } as const;

// Eli overlay dimensions — keep in sync with remotion/src/effects/overlays/EliOverlay.tsx
export const ELI_OVERLAY_WIDTH = 380;
export const ELI_OVERLAY_HEIGHT = 215;
