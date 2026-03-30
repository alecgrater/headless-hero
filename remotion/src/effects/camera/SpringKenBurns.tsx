/**
 * Spring-based Ken Burns camera motion effect.
 * Replaces FFmpeg's zoompan filter with smooth spring animations.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";
import { makeSpring, CAMERA_SPRING, type SpringConfig } from "../../utils/easing";

interface Props {
  children: React.ReactNode;
  effect: string;
  intensity?: "subtle" | "moderate" | "dramatic";
  easing?: "spring" | "linear" | "ease_in_out";
}

const INTENSITY_SCALE: Record<string, number> = {
  subtle: 0.05,
  moderate: 0.12,
  dramatic: 0.22,
};

export const SpringKenBurns: React.FC<Props> = ({
  children,
  effect,
  intensity = "moderate",
  easing = "spring",
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const scale = INTENSITY_SCALE[intensity] ?? 0.12;

  if (effect === "none" || effect === "static") {
    return <div style={{ width: "100%", height: "100%" }}>{children}</div>;
  }

  let progress: number;
  if (easing === "spring") {
    // Use spring for smooth organic motion
    const springConfig: SpringConfig = {
      ...CAMERA_SPRING,
      stiffness: 5 + scale * 40,
    };
    progress = makeSpring(frame, fps, springConfig);
    // For long durations, blend with linear to keep moving
    const linearProgress = Math.min(1, frame / durationInFrames);
    progress = progress * 0.3 + linearProgress * 0.7;
  } else if (easing === "linear") {
    progress = Math.min(1, frame / durationInFrames);
  } else {
    progress = interpolate(frame, [0, durationInFrames], [0, 1], {
      easing: Easing.inOut(Easing.ease),
      extrapolateRight: "clamp",
    });
  }

  let transformScale = 1;
  let translateX = 0;
  let translateY = 0;

  switch (effect) {
    case "zoom_in":
      transformScale = 1 + progress * scale;
      break;
    case "zoom_out":
      transformScale = 1 + scale - progress * scale;
      break;
    case "pan_left":
      translateX = -progress * scale * 100;
      transformScale = 1 + scale * 0.3;
      break;
    case "pan_right":
      translateX = progress * scale * 100;
      transformScale = 1 + scale * 0.3;
      break;
    case "pan_up":
      translateY = -progress * scale * 100;
      transformScale = 1 + scale * 0.3;
      break;
    case "pan_down":
      translateY = progress * scale * 100;
      transformScale = 1 + scale * 0.3;
      break;
  }

  return (
    <div style={{ width: "100%", height: "100%", overflow: "hidden" }}>
      <div
        style={{
          width: "100%",
          height: "100%",
          transform: `scale(${transformScale}) translate(${translateX}%, ${translateY}%)`,
          willChange: "transform",
        }}
      >
        {children}
      </div>
    </div>
  );
};
