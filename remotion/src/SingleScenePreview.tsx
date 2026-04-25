/**
 * SingleScenePreview — thin wrapper for rendering one scene in the Player.
 * No Composition registration, no global overlays (chapter indicators, etc.).
 * Used exclusively by the @remotion/player in the frontend PreviewPanel.
 */
import React from "react";
import type { SceneInput } from "./types";
import { SceneRenderer } from "./scenes/SceneRenderer";

interface Props {
  scene: SceneInput;
  fps: number;
  highlightEnabled?: boolean;
}

export const SingleScenePreview: React.FC<Props> = ({ scene, highlightEnabled }) => {
  return (
    <div style={{ width: "100%", height: "100%", backgroundColor: "#000" }}>
      <SceneRenderer scene={scene} highlightEnabled={highlightEnabled} />
    </div>
  );
};
