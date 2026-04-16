/**
 * SceneTransition — applies entrance/exit effects at scene boundaries.
 *
 * Each transition is split into paired exit + entrance animations within
 * the scene's existing time allocation (no overlapping Sequences).
 *
 * Durations at 30fps:
 *   fade_black:   10 frames exit (0.33s), 10 frames enter (0.33s)
 *   flash_white:   4 frames exit (0.13s),  8 frames enter (0.27s)
 *   wipe:         12 frames exit (0.40s), 12 frames enter (0.40s)
 *   cut:           0 frames (instant)
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";

type TransitionType = "cut" | "fade_black" | "flash_white" | "wipe";

interface Props {
  transitionIn?: TransitionType;
  transitionOut?: TransitionType;
  children: React.ReactNode;
}

/** Frame counts for enter/exit per transition type (at 30fps, scaled proportionally). */
function getEnterFrames(type: TransitionType, fps: number): number {
  const scale = fps / 30;
  switch (type) {
    case "fade_black": return Math.round(10 * scale);
    case "flash_white": return Math.round(8 * scale);
    case "wipe": return Math.round(12 * scale);
    default: return 0;
  }
}

function getExitFrames(type: TransitionType, fps: number): number {
  const scale = fps / 30;
  switch (type) {
    case "fade_black": return Math.round(10 * scale);
    case "flash_white": return Math.round(4 * scale);
    case "wipe": return Math.round(12 * scale);
    default: return 0;
  }
}

export const SceneTransition: React.FC<Props> = ({
  transitionIn = "cut",
  transitionOut = "cut",
  children,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const enterFrames = getEnterFrames(transitionIn, fps);
  const exitFrames = getExitFrames(transitionOut, fps);
  const exitStart = durationInFrames - exitFrames;

  // --- Entrance effects ---
  let enterOpacity = 1;
  let enterClipPath: string | undefined;
  let whiteOverlayOpacity = 0;

  if (enterFrames > 0 && frame < enterFrames) {
    switch (transitionIn) {
      case "fade_black":
        enterOpacity = interpolate(frame, [0, enterFrames], [0, 1], {
          extrapolateRight: "clamp",
        });
        break;
      case "flash_white":
        // White overlay fades out from full white
        whiteOverlayOpacity = interpolate(frame, [0, enterFrames], [1, 0], {
          extrapolateRight: "clamp",
        });
        break;
      case "wipe":
        // Reveal from right: clip-path inset slides left edge from 100% to 0%
        const enterProgress = interpolate(frame, [0, enterFrames], [100, 0], {
          extrapolateRight: "clamp",
        });
        enterClipPath = `inset(0 0 0 ${enterProgress}%)`;
        break;
    }
  }

  // --- Exit effects ---
  let exitOpacity = 1;
  let exitClipPath: string | undefined;

  if (exitFrames > 0 && frame >= exitStart) {
    switch (transitionOut) {
      case "fade_black":
        exitOpacity = interpolate(frame, [exitStart, durationInFrames], [1, 0], {
          extrapolateLeft: "clamp",
        });
        break;
      case "flash_white":
        // White overlay ramps up to full white
        whiteOverlayOpacity = Math.max(
          whiteOverlayOpacity,
          interpolate(frame, [exitStart, durationInFrames], [0, 1], {
            extrapolateLeft: "clamp",
          }),
        );
        break;
      case "wipe":
        // Conceal to left: clip-path inset slides right edge from 0% to 100%
        const exitProgress = interpolate(frame, [exitStart, durationInFrames], [0, 100], {
          extrapolateLeft: "clamp",
        });
        exitClipPath = `inset(0 ${exitProgress}% 0 0)`;
        break;
    }
  }

  // Combine opacity (both enter and exit can affect it)
  const combinedOpacity = enterOpacity * exitOpacity;

  // Combine clip paths (only one can be active at a time since enter/exit don't overlap)
  const clipPath = enterClipPath || exitClipPath;

  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      <div
        style={{
          width: "100%",
          height: "100%",
          opacity: combinedOpacity,
          clipPath,
        }}
      >
        {children}
      </div>
      {/* White flash overlay */}
      {whiteOverlayOpacity > 0 && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundColor: "white",
            opacity: whiteOverlayOpacity,
            pointerEvents: "none",
          }}
        />
      )}
    </div>
  );
};
