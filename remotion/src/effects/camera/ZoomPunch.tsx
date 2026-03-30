/**
 * ZoomPunch camera effect — quick digital push-in for emphasis.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, spring } from "remotion";

interface Props {
  children: React.ReactNode;
  intensity?: "subtle" | "moderate" | "dramatic";
  triggerAt?: number; // seconds into scene
}

const PUNCH_SCALE: Record<string, number> = {
  subtle: 1.08,
  moderate: 1.15,
  dramatic: 1.25,
};

export const ZoomPunch: React.FC<Props> = ({
  children,
  intensity = "moderate",
  triggerAt = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const triggerFrame = Math.round(triggerAt * fps);
  const maxScale = PUNCH_SCALE[intensity] ?? 1.15;

  const progress = spring({
    frame: frame - triggerFrame,
    fps,
    config: {
      damping: 12,
      mass: 0.4,
      stiffness: 200,
    },
  });

  const scale = 1 + (maxScale - 1) * progress;

  return (
    <div style={{ width: "100%", height: "100%", overflow: "hidden" }}>
      <div
        style={{
          width: "100%",
          height: "100%",
          transform: `scale(${scale})`,
          willChange: "transform",
        }}
      >
        {children}
      </div>
    </div>
  );
};
