/**
 * StaticImageScene — renders a single image.
 * All camera motion is handled by the CameraDrift wrapper in SceneRenderer.
 */
import React from "react";
import { Img, useCurrentFrame, useVideoConfig } from "remotion";
import type { SceneInput } from "../types";
import {
  BlinkMicroExpressionOverlay,
  blinkMicroOverlay,
  blinkOverlayVisible,
  resolveBlinkOverlayAnchor,
} from "./BlinkOverlay";

interface Props {
  scene: SceneInput;
}

export const StaticImageScene: React.FC<Props> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const blink = scene.full_frame_blink?.enabled ? scene.full_frame_blink : null;
  const blinkOverlay = blinkMicroOverlay(blink?.action);
  const blinkAnchor = blink ? resolveBlinkOverlayAnchor(blink.anchor) : null;
  const blinkVisible = blinkOverlay ? blinkOverlayVisible(frame, fps) : false;

  if (!scene.image_path) {
    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          backgroundColor: "#0a0a0a",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#666",
          fontSize: 24,
        }}
      >
        No image
      </div>
    );
  }

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        backgroundColor: "#000",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <Img
        src={scene.image_path}
        style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
      />
      {blinkOverlay && blinkAnchor ? (
        <BlinkMicroExpressionOverlay
          anchor={blinkAnchor}
          overlay={blinkOverlay}
          visible={blinkVisible}
        />
      ) : null}
    </div>
  );
};
