import React from "react";
import { Img, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { SceneInput, VisualLayer } from "../types";

interface Props {
  scene: SceneInput;
}

const validIconLayer = (scene: SceneInput): VisualLayer | undefined => {
  const layers = scene.visual_layers ?? [];
  return layers.find((layer) => layer.type === "image" && layer.image_path);
};

export const StatCard: React.FC<Props> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const iconLayer = validIconLayer(scene);
  const statValue = (scene.stat_value ?? "").trim();
  const statLabel = (scene.stat_label ?? "").trim();

  const valuePop = spring({
    frame,
    fps,
    config: { damping: 18, stiffness: 220, mass: 0.6 },
    durationInFrames: Math.round(fps * 0.6),
  });
  const labelOpacity = interpolate(frame, [Math.round(fps * 0.18), Math.round(fps * 0.5)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const iconPop = spring({
    frame: Math.max(0, frame - Math.round(fps * 0.08)),
    fps,
    config: { damping: 16, stiffness: 200, mass: 0.6 },
    durationInFrames: Math.round(fps * 0.6),
  });

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "8% 6%",
        gap: 28,
      }}
    >
      {iconLayer?.image_path && (
        <div
          style={{
            width: "26%",
            maxWidth: 360,
            aspectRatio: "1 / 1",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transform: `scale(${0.6 + 0.4 * iconPop})`,
            opacity: iconPop,
          }}
        >
          <Img
            src={iconLayer.image_path}
            style={{ width: "100%", height: "100%", objectFit: "contain" }}
          />
        </div>
      )}
      <div
        style={{
          fontFamily: "Arial Black, Impact, sans-serif",
          fontSize: "min(24vw, 360px)",
          fontWeight: 900,
          lineHeight: 0.95,
          color: "#FFFFFF",
          textAlign: "center",
          letterSpacing: -2,
          textShadow: "0 6px 0 rgba(0, 0, 0, 0.85), 0 14px 28px rgba(0, 0, 0, 0.45)",
          transform: `scale(${0.7 + 0.3 * valuePop})`,
          opacity: valuePop,
        }}
      >
        {statValue || "—"}
      </div>
      {statLabel && (
        <div
          style={{
            fontFamily: "Arial Black, Impact, sans-serif",
            fontSize: "min(5.2vw, 76px)",
            fontWeight: 800,
            lineHeight: 1.15,
            color: "#0F172A",
            textAlign: "center",
            maxWidth: "84%",
            background: "#F6C54A",
            padding: "12px 28px",
            borderRadius: 18,
            boxShadow: "0 6px 0 rgba(0, 0, 0, 0.85)",
            opacity: labelOpacity,
            transform: `translateY(${(1 - labelOpacity) * 12}px)`,
          }}
        >
          {statLabel}
        </div>
      )}
    </div>
  );
};

export default StatCard;
