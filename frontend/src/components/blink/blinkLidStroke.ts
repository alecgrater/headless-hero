// Mirrors the renderer (remotion BlinkOverlay.tsx / TreatmentRenderer.tsx):
// the character's own line color when the anchor carries a valid one,
// otherwise the original brown.
export const BLINK_DEFAULT_LID_STROKE = "#2A1712";

export const blinkLidStroke = (anchor?: { lid_stroke?: unknown } | null): string =>
  typeof anchor?.lid_stroke === "string" && /^#[0-9a-f]{6}$/i.test(anchor.lid_stroke)
    ? anchor.lid_stroke
    : BLINK_DEFAULT_LID_STROKE;
