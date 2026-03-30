/**
 * SceneTransition — dispatcher that wraps a scene with the appropriate
 * transition effect based on the scene's FX or legacy transition type.
 */
import React from "react";
import type { TransitionFX } from "../../types";
import { CrossDissolve } from "./CrossDissolve";
import { SlideWipe } from "./SlideWipe";
import { SmashCut } from "./SmashCut";
import { PushTransition } from "./PushTransition";

interface Props {
  children: React.ReactNode;
  transition?: TransitionFX | null;
  legacyTransition?: string;
  fps: number;
}

export const SceneTransition: React.FC<Props> = ({
  children,
  transition,
  legacyTransition,
  fps,
}) => {
  const type = transition?.type ?? mapLegacyTransition(legacyTransition);
  const duration = transition?.duration ?? 0.5;
  const durationInFrames = Math.round(duration * fps);
  const direction = transition?.direction ?? mapLegacyDirection(legacyTransition);

  if (!type || type === "cut") {
    return <>{children}</>;
  }

  switch (type) {
    case "crossfade":
      return (
        <CrossDissolve durationInFrames={durationInFrames} direction="in">
          {children}
        </CrossDissolve>
      );
    case "slide":
    case "wipe":
      return (
        <SlideWipe
          durationInFrames={durationInFrames}
          direction={(direction ?? "left") as "left" | "right" | "up" | "down"}
        >
          {children}
        </SlideWipe>
      );
    case "smash_cut":
      return <SmashCut>{children}</SmashCut>;
    case "push":
      return (
        <PushTransition
          durationInFrames={durationInFrames}
          direction={(direction ?? "up") as "left" | "right" | "up" | "down"}
        >
          {children}
        </PushTransition>
      );
    case "zoom_punch":
      // ZoomPunch as transition: just smash cut with 2 frames
      return <SmashCut flashFrames={2}>{children}</SmashCut>;
    default:
      return <>{children}</>;
  }
};

function mapLegacyTransition(legacy?: string): string | undefined {
  if (!legacy) return undefined;
  if (legacy === "crossfade") return "crossfade";
  if (legacy === "slide_left" || legacy === "slide_right") return "slide";
  if (legacy === "push_up") return "push";
  return undefined;
}

function mapLegacyDirection(legacy?: string): string | undefined {
  if (legacy === "slide_left") return "left";
  if (legacy === "slide_right") return "right";
  if (legacy === "push_up") return "up";
  return undefined;
}
