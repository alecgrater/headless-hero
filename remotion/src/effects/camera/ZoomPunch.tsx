/**
 * ZoomPunch camera effect — quick asymmetric scale hit on key moments.
 * Fast in (~6 frames), slow out (~18 frames via spring with high damping).
 * Scale range: 1.04-1.07.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, spring } from "remotion";

interface Props {
  children: React.ReactNode;
  triggerFrame: number;
  scale: number; // 1.04-1.07
}

export const ZoomPunch: React.FC<Props> = ({
  children,
  triggerFrame,
  scale: maxScale,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const localFrame = frame - triggerFrame;

  let currentScale = 1;

  if (localFrame >= 0) {
    const PUNCH_IN_FRAMES = 6;
    const punchIn = interpolate(localFrame, [0, PUNCH_IN_FRAMES], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });

    const punchOut = localFrame >= PUNCH_IN_FRAMES
      ? spring({
          frame: localFrame - PUNCH_IN_FRAMES,
          fps,
          config: {
            damping: 30,
            mass: 0.8,
            stiffness: 40,
          },
        })
      : 0;

    const amount = maxScale - 1;
    if (localFrame < PUNCH_IN_FRAMES) {
      currentScale = 1 + amount * punchIn;
    } else {
      currentScale = 1 + amount * (1 - punchOut);
    }
  }

  return (
    <div style={{ width: "100%", height: "100%", overflow: "hidden" }}>
      <div
        style={{
          width: "100%",
          height: "100%",
          transform: `scale(${currentScale})`,
          willChange: "transform",
        }}
      >
        {children}
      </div>
    </div>
  );
};
