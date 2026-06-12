import type { VisualMode } from "../../../types/script";

export type { VisualMode };

export type CompatibilityState = "supported" | "suppressed";
export type DurationProfile = "normal" | "medium" | "extended" | "planned";

export interface VisualModeCompatibility {
  standardSubtitles: CompatibilityState;
  eliOverlay: CompatibilityState;
  sceneFx: CompatibilityState;
  titleCardEligible: boolean;
}

export interface VisualModeEntry {
  id: VisualMode;
  label: string;
  shortDescription: string;
  longDescription: string;
  previewSrc: string;
  durationProfile: DurationProfile;
  durationLabel: string;
  durationDescription: string;
  requiredFields: string[];
  optionalFields: string[];
  compatibility: VisualModeCompatibility;
  distribution: string;
  routing: string;
  notCompatibleWith: string[];
  rendererPath: string;
}

export const VISUAL_MODE_CATALOG: VisualModeEntry[] = [
  {
    id: "full_frame",
    label: "Full Frame",
    shortDescription: "One stable, full-bleed generated scene image.",
    longDescription:
      "The default mode for simple visual beats: locations, objects, character moments, and concept illustrations. One generated image fills the canvas, supports normal subtitles, transitions, scene FX, and Eli overlays.",
    previewSrc: "/visual-modes/full_frame.mp4",
    durationProfile: "normal",
    durationLabel: "Normal target · 5-9s",
    durationDescription: "Planned as one concise visual beat before voiceover.",
    requiredFields: ["visual_prompt"],
    optionalFields: ["transition_in", "fx", "eli_overlay", "visual_in_seconds", "visual_out_seconds"],
    compatibility: {
      standardSubtitles: "supported",
      eliOverlay: "supported",
      sceneFx: "supported",
      titleCardEligible: true,
    },
    distribution: "Unlimited",
    routing:
      "Default mode for any scene that only needs one full-screen image. Script generation falls back to full_frame whenever no other mode applies.",
    notCompatibleWith: [],
    rendererPath: "remotion/src/scenes/StaticImageScene.tsx",
  },
  {
    id: "multi_frame",
    label: "Multi Frame",
    shortDescription: "Multiple distinct generated frames inside one scene.",
    longDescription:
      "Use for quick examples, contrasts, escalation beats, or montage-like visual variety. Each frame is independently generated and crossfades on its own schedule. Frames advance loosely without strict continuity between them.",
    previewSrc: "/visual-modes/multi_frame.mp4",
    durationProfile: "normal",
    durationLabel: "Normal target · 5-9s",
    durationDescription: "Planned as a short scene unless several concrete examples need a little more room.",
    requiredFields: ["visual_prompt", "frame_urls"],
    optionalFields: ["frame_timings", "fx", "eli_overlay"],
    compatibility: {
      standardSubtitles: "supported",
      eliOverlay: "supported",
      sceneFx: "supported",
      titleCardEligible: false,
    },
    distribution: "Unlimited",
    routing:
      "Script generation emits multi_frame for scenes with quick examples, list-style beats, or visual variety. Legacy 'quick_cuts' and 'montage' visual beats normalize to multi_frame.",
    notCompatibleWith: [],
    rendererPath: "remotion/src/scenes/MultiFrameScene.tsx",
  },
  {
    id: "continuous",
    label: "Continuous",
    shortDescription: "Same-scene progression — each frame advances one event.",
    longDescription:
      "Use for coherent progression where each generated frame moves one event, object, environment, or character state forward. Frame 1 establishes house style; later frames use the prior generated frame as their only image reference so the action advances visually.",
    previewSrc: "/visual-modes/continuous.mp4",
    durationProfile: "normal",
    durationLabel: "Normal target · 5-9s",
    durationDescription: "Planned as a short progression where one action or transformation unfolds.",
    requiredFields: ["visual_prompt", "frame_urls"],
    optionalFields: ["frame_timings", "fx", "eli_overlay"],
    compatibility: {
      standardSubtitles: "supported",
      eliOverlay: "supported",
      sceneFx: "supported",
      titleCardEligible: false,
    },
    distribution: "Unlimited",
    routing:
      "Script generation emits continuous for same-scene progression beats. Continuation prompts include the shared scene brief plus middle/final progression instructions.",
    notCompatibleWith: [],
    rendererPath: "remotion/src/scenes/MultiFrameScene.tsx",
  },
  {
    id: "video",
    label: "AI Video",
    shortDescription: "AI-generated motion clip from an anchor image.",
    longDescription:
      "After voiceover timing exists, an eligible scene's anchor image is sent to Runway Gen-4 Turbo or Fal Wan 2.2 (configurable) to produce a short motion clip. Clips can slow down up to 25% to match narration; larger gaps fall back to the static anchor.",
    previewSrc: "/visual-modes/video.mp4",
    durationProfile: "planned",
    durationLabel: "Planned video · validated after voiceover",
    durationDescription: "Planned before voiceover when motion helps, then validated after real timing exists.",
    requiredFields: ["visual_prompt", "video_url"],
    optionalFields: ["image_url", "fx", "eli_overlay"],
    compatibility: {
      standardSubtitles: "supported",
      eliOverlay: "supported",
      sceneFx: "supported",
      titleCardEligible: false,
    },
    distribution:
      "Up to AI_VIDEO_SCENES_PER_SEGMENT per segment (default 2). Never back-to-back. Requires AI_VIDEO_ENABLED.",
    routing:
      "Script generation can plan video before voiceover when motion clearly improves the scene. Post-voiceover validation may downgrade unsafe choices based on real timing, adjacency, duration, or assets.",
    notCompatibleWith: [],
    rendererPath: "remotion/src/scenes/VideoScene.tsx",
  },
  {
    id: "popup_sequence",
    label: "Popup Sequence",
    shortDescription: "Anchor cutout with item cutouts orbiting clockwise.",
    longDescription:
      "A central anchor character/subject cutout stays fixed; transparent item cutouts pop in at voiceover timings and join a shared clockwise orbit. Items are cropped from one contact-sheet image; the anchor uses the active style preset's character. No scene image, no panels, no readable text.",
    previewSrc: "/visual-modes/popup_sequence.mp4",
    durationProfile: "extended",
    durationLabel: "Extended target · 14-20s",
    durationDescription: "Planned longer before voiceover so each popup item has time to appear and register.",
    requiredFields: ["visual_prompt", "visual_layers"],
    optionalFields: ["eli_overlay"],
    compatibility: {
      standardSubtitles: "supported",
      eliOverlay: "supported",
      sceneFx: "suppressed",
      titleCardEligible: false,
    },
    distribution: "Unlimited",
    routing:
      "Script generation can choose popup_sequence; post-voiceover validation fills timing/layers. Test Lab fallback derives three left/center/right popup item cutout layers when validator output is unavailable.",
    notCompatibleWith: [],
    rendererPath: "remotion/src/scenes/TreatmentRenderer.tsx",
  },
  {
    id: "flipflop",
    label: "Flip Flop",
    shortDescription: "Experimental human cutouts alternating between A/B states.",
    longDescription:
      "Two transparent human/character state cutouts keyed from a shared A/B sheet onto one registered output canvas alternate over a renderer-owned context stage. This mode is currently Test Lab-only while shared-sheet generation is being hardened; production scriptwriting and visual analysis choose another visual mode. Test Lab can stress-test flipflop_action values, and cutouts that cannot be registered fail generation with a visible error.",
    previewSrc: "/visual-modes/flipflop.mp4",
    durationProfile: "normal",
    durationLabel: "Normal target · 5-9s",
    durationDescription: "Planned as a short A/B motion beat for one subject.",
    requiredFields: ["visual_prompt", "visual_layers", "renderer_context"],
    optionalFields: ["eli_overlay"],
    compatibility: {
      standardSubtitles: "supported",
      eliOverlay: "supported",
      sceneFx: "suppressed",
      titleCardEligible: false,
    },
    distribution: "Unlimited",
    routing:
      "Production script generation and visual analysis do not choose flipflop while shared A/B state-sheet generation is being hardened. Test Lab can still stress-test flipflop_action values, renderer_context staging, shared state-sheet prompts, and uniform-scale alpha-mask registration.",
    notCompatibleWith: [
      "Different-subject contrast — use comparison_board instead.",
      "Production same-subject A/B animation — use another mode until flipflop is re-enabled.",
      "Body repositioning, nods, hand gestures, shrugs, or object motion — use another mode instead.",
    ],
    rendererPath: "remotion/src/scenes/TreatmentRenderer.tsx",
  },
  {
    id: "comparison_board",
    label: "Comparison Board",
    shortDescription: "Side-by-side contrast with renderer-owned columns.",
    longDescription:
      "Renderer-controlled side-by-side comparison of two or three subjects, concepts, states, or outcomes (Before/After, Myth/Reality, Rich/Poor, Good/Bad Choice). Generates only transparent cutouts of the compared subjects; Remotion owns columns, dividers, VS markers, arrows, badges, and stat chips.",
    previewSrc: "/visual-modes/comparison_board.mp4",
    durationProfile: "extended",
    durationLabel: "Extended target · 16-24s",
    durationDescription: "Planned longer before voiceover so viewers can compare the board columns.",
    requiredFields: ["visual_prompt", "visual_layers"],
    optionalFields: ["eli_overlay"],
    compatibility: {
      standardSubtitles: "supported",
      eliOverlay: "supported",
      sceneFx: "suppressed",
      titleCardEligible: false,
    },
    distribution: "Unlimited",
    routing:
      "Script generation chooses comparison_board when narration explicitly contrasts two or three things. Avoid for single environments, item lists, same-subject animation, or progression.",
    notCompatibleWith: [
      "Cropped same-subject character/body-language A/B animation — use another mode until flipflop is re-enabled.",
      "Item callouts around an anchor — use popup_sequence.",
      "Process progression — use continuous.",
    ],
    rendererPath: "remotion/src/scenes/TreatmentRenderer.tsx",
  },
  {
    id: "stat_card",
    label: "Stat Card",
    shortDescription: "One giant headline statistic with optional icon.",
    longDescription:
      "A single dominant statistic — percentage, financial figure, population, duration, distance, ranking, odds, risk factor, or scientific measurement — rendered as a giant headline stat_value plus an optional short stat_label, over the static canvas. The renderer owns all readable typography. The only generated asset is one optional transparent supporting icon cutout.",
    previewSrc: "/visual-modes/stat_card.mp4",
    durationProfile: "medium",
    durationLabel: "Medium target · 10-14s",
    durationDescription: "Planned with enough time for one decisive statistic to land.",
    requiredFields: ["stat_value"],
    optionalFields: ["stat_label", "visual_layers"],
    compatibility: {
      standardSubtitles: "suppressed",
      eliOverlay: "suppressed",
      sceneFx: "suppressed",
      titleCardEligible: false,
    },
    distribution: "Max 1-2 per video. Never back-to-back.",
    routing:
      "Script generation emits stat_card only when narration genuinely revolves around one decisive number. Use sparingly; do not use when atmosphere matters more than the metric or when narration covers multiple numbers.",
    notCompatibleWith: [
      "Atmosphere-heavy or environmental beats — use full_frame.",
      "Multiple numbers in one scene — break apart or use captions.",
    ],
    rendererPath: "remotion/src/scenes/StatCard.tsx",
  },
  {
    id: "captions",
    label: "Captions",
    shortDescription: "Renderer-owned editorial text punch.",
    longDescription:
      "Static-canvas punch mode with optional side imagery plus large in-scene caption_text and red caption_emphasis. Not standard subtitle rendering: standard bottom subtitles are suppressed during the caption beat. Legacy aha_subtitle visual beats normalize into captions.",
    previewSrc: "/visual-modes/captions.mp4",
    durationProfile: "normal",
    durationLabel: "Normal target · 5-9s",
    durationDescription: "Planned as a short editorial punch beat.",
    requiredFields: ["caption_text"],
    optionalFields: ["caption_emphasis", "image_url"],
    compatibility: {
      standardSubtitles: "suppressed",
      eliOverlay: "suppressed",
      sceneFx: "suppressed",
      titleCardEligible: false,
    },
    distribution: "Use sparingly to preserve impact.",
    routing:
      "Fresh script generation emits caption fields directly in the existing script call. Generated images must not bake readable caption text inside.",
    notCompatibleWith: [
      "Standard subtitle rendering — captions owns its own typography.",
    ],
    rendererPath: "remotion/src/scenes/CaptionScene.tsx",
  },
];

export function visualModeEntry(mode: VisualMode): VisualModeEntry {
  return VISUAL_MODE_CATALOG.find((entry) => entry.id === mode) ?? VISUAL_MODE_CATALOG[0];
}

export function durationLabelForMode(mode: VisualMode): string {
  return visualModeEntry(mode).durationLabel;
}

export function durationDescriptionForMode(mode: VisualMode): string {
  return visualModeEntry(mode).durationDescription;
}
