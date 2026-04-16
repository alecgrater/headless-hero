/**
 * StaticImageScene — renders a single image.
 * All camera motion is handled by the CameraDrift wrapper in SceneRenderer.
 */
import React from "react";
import { Img } from "remotion";
import type { SceneInput } from "../types";

interface Props {
  scene: SceneInput;
}

export const StaticImageScene: React.FC<Props> = ({ scene }) => {
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
      }}
    >
      <Img
        src={scene.image_path}
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
      />
    </div>
  );
};
