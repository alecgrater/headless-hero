/**
 * SubtitleScene — white text on pure black background.
 * Used for "aha_subtitle" visual beats: dramatic reveals, shocking stats.
 * Spring pop-in animation: scale 0.85 → 1.0.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, spring } from "remotion";
import type { SceneInput } from "../types";

interface Props {
  scene: SceneInput;
}

export const SubtitleScene: React.FC<Props> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Text from first frame directive, or fallback to narration
  const text =
    scene.frame_directives?.[0]?.prompt || scene.narration || "";

  // Adaptive font size based on text length
  const charCount = text.length;
  const fontSize = charCount < 60 ? 96 : charCount < 120 ? 72 : 56;

  // Spring pop-in: scale from 0.85 to 1.0
  const scale = spring({
    frame,
    fps,
    config: { damping: 15, mass: 0.8 },
    from: 0.85,
    to: 1,
  });

  // Fade in opacity
  const opacity = spring({
    frame,
    fps,
    config: { damping: 20, mass: 0.5 },
    from: 0,
    to: 1,
  });

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        backgroundColor: "#000",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 120,
      }}
    >
      <div
        style={{
          color: "#fff",
          fontSize,
          fontWeight: 700,
          textAlign: "center",
          lineHeight: 1.3,
          transform: `scale(${scale})`,
          opacity,
          maxWidth: "85%",
        }}
      >
        {text}
      </div>
    </div>
  );
};
