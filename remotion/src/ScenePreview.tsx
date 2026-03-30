/**
 * ScenePreview composition — renders a single scene for preview.
 */
import React from "react";
import type { ScenePreviewProps } from "./types";
import { SceneRenderer } from "./scenes/SceneRenderer";

export const ScenePreview: React.FC<ScenePreviewProps> = ({ scene }) => {
  return (
    <div style={{ width: "100%", height: "100%", backgroundColor: "#000" }}>
      <SceneRenderer scene={scene} />
    </div>
  );
};
