/**
 * SmashCut transition — 2-4 frame black flash for dramatic cuts.
 */
import React from "react";
import { useCurrentFrame } from "remotion";

interface Props {
  children: React.ReactNode;
  flashFrames?: number;
}

export const SmashCut: React.FC<Props> = ({
  children,
  flashFrames = 3,
}) => {
  const frame = useCurrentFrame();

  if (frame < flashFrames) {
    return (
      <div style={{ width: "100%", height: "100%", backgroundColor: "#000" }} />
    );
  }

  return <>{children}</>;
};
