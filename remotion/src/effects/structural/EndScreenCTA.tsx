/**
 * EndScreenCTA — animated subscribe/next-video prompt.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, spring } from "remotion";

interface Props {
  channelName?: string;
}

export const EndScreenCTA: React.FC<Props> = ({ channelName }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Only show in the last 5 seconds
  const showAfter = durationInFrames - fps * 5;
  if (frame < showAfter) return null;

  const relativeFrame = frame - showAfter;

  const entry = spring({
    frame: relativeFrame,
    fps,
    config: { damping: 18, mass: 0.8, stiffness: 100 },
  });

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: `rgba(10,10,10,${0.9 * entry})`,
        zIndex: 20,
      }}
    >
      <div
        style={{
          transform: `scale(${0.8 + entry * 0.2})`,
          textAlign: "center",
        }}
      >
        <div
          style={{
            fontSize: "40px",
            fontWeight: 800,
            color: "#fff",
            marginBottom: "16px",
          }}
        >
          Thanks for watching!
        </div>
        {channelName && (
          <div
            style={{
              fontSize: "20px",
              color: "rgba(255,255,255,0.6)",
              marginBottom: "24px",
            }}
          >
            {channelName}
          </div>
        )}
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            backgroundColor: "#ef4444",
            color: "#fff",
            fontSize: "18px",
            fontWeight: 700,
            padding: "12px 32px",
            borderRadius: "8px",
          }}
        >
          SUBSCRIBE
        </div>
      </div>
    </div>
  );
};
