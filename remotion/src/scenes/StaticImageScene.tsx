/**
 * StaticImageScene — renders a single image with camera motion effects.
 * The default scene type for ai_generated images.
 */
import React from "react";
import { Img, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { SpringKenBurns } from "../effects/camera/SpringKenBurns";
import { ZoomPunch } from "../effects/camera/ZoomPunch";
import { ParallaxDepth } from "../effects/camera/ParallaxDepth";
import type { SceneInput } from "../types";

interface Props {
  scene: SceneInput;
}

export const StaticImageScene: React.FC<Props> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

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

  // Fade out at the very end (last 0.3s equivalent)
  const fadeOutFrames = 9; // ~0.3s at 30fps
  const opacity = interpolate(
    frame,
    [durationInFrames - fadeOutFrames, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // Determine camera effect from FX or legacy fields
  const fx = scene.fx;
  const cameraType = fx?.camera?.type ?? scene.ken_burns_effect ?? "ken_burns";
  const cameraDirection = fx?.camera?.direction ?? mapLegacyEffect(scene.ken_burns_effect);
  const cameraIntensity = fx?.camera?.intensity ?? scene.ken_burns_intensity ?? "moderate";
  const cameraEasing = fx?.camera?.easing ?? "spring";

  const image = (
    <Img
      src={scene.image_path}
      style={{ width: "100%", height: "100%", objectFit: "cover" }}
    />
  );

  let wrappedImage: React.ReactNode;

  if (cameraType === "zoom_punch") {
    wrappedImage = (
      <ZoomPunch intensity={cameraIntensity as "subtle" | "moderate" | "dramatic"}>
        {image}
      </ZoomPunch>
    );
  } else if (cameraType === "parallax") {
    wrappedImage = (
      <ParallaxDepth
        direction={cameraDirection as "left" | "right" | "up" | "down"}
        intensity={cameraIntensity as "subtle" | "moderate" | "dramatic"}
      >
        {image}
      </ParallaxDepth>
    );
  } else if (cameraType === "static") {
    wrappedImage = image;
  } else {
    // Default: Ken Burns
    const kbEffect = cameraDirection
      ? `${cameraDirection === "in" ? "zoom_in" : cameraDirection === "out" ? "zoom_out" : `pan_${cameraDirection}`}`
      : scene.ken_burns_effect ?? "zoom_in";

    wrappedImage = (
      <SpringKenBurns
        effect={kbEffect}
        intensity={cameraIntensity as "subtle" | "moderate" | "dramatic"}
        easing={cameraEasing as "spring" | "linear" | "ease_in_out"}
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
        opacity,
      }}
    >
      {wrappedImage}
    </div>
  );
};

/** Map legacy ken_burns_effect string to a direction for the new FX system. */
function mapLegacyEffect(effect?: string): string | undefined {
  if (!effect || effect === "none") return undefined;
  if (effect === "zoom_in") return "in";
  if (effect === "zoom_out") return "out";
  if (effect.startsWith("pan_")) return effect.replace("pan_", "");
  return undefined;
}
