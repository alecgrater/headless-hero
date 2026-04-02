/**
 * StaticImageScene — renders a single image with camera motion effects.
 * The default scene type for ai_generated images.
 */
import React from "react";
import { Img } from "remotion";
import { SpringKenBurns } from "../effects/camera/SpringKenBurns";
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

  // Camera motion from legacy ken_burns fields
  const kbEffect = scene.ken_burns_effect ?? "zoom_in";
  const kbIntensity = (scene.ken_burns_intensity ?? "moderate") as "subtle" | "moderate" | "dramatic";

  const image = (
    <Img
      src={scene.image_path}
      style={{ width: "100%", height: "100%", objectFit: "cover" }}
    />
  );

  let wrappedImage: React.ReactNode;

  if (kbEffect === "none" || kbEffect === "static") {
    wrappedImage = image;
  } else {
    wrappedImage = (
      <SpringKenBurns
        effect={kbEffect}
        intensity={kbIntensity}
      >
        {image}
      </SpringKenBurns>
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
      {wrappedImage}
    </div>
  );
};
