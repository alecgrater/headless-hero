/**
 * FullVideo composition — sequences all scenes with transitions.
 * This is the top-level composition that renders the entire video.
 */
import React from "react";
import { Sequence, Audio } from "remotion";
import type { FullVideoProps, SceneInput } from "./types";
import { SceneRenderer } from "./scenes/SceneRenderer";
import { SceneTransition } from "./effects/transitions/SceneTransition";
import { secondsToFrames } from "./utils/timing";

export const FullVideo: React.FC<FullVideoProps> = ({ segments, fps }) => {
  // Flatten all scenes with their metadata
  const allScenes: SceneInput[] = segments.flatMap((seg) => seg.scenes);

  let currentFrame = 0;
  const sceneSequences: React.ReactNode[] = [];

  for (let i = 0; i < allScenes.length; i++) {
    const scene = allScenes[i];
    const durationFrames = secondsToFrames(scene.duration_seconds, fps);

    // Determine transition overlap with next scene
    const transition = scene.fx?.transition;
    const legacyTransition = scene.scene_transition;
    const transitionDuration = transition?.duration ?? 0.5;
    const hasTransition =
      (transition && transition.type !== "cut") ||
      (legacyTransition && legacyTransition !== "");
    const overlapFrames = hasTransition
      ? secondsToFrames(transitionDuration, fps)
      : 0;

    sceneSequences.push(
      <Sequence
        key={scene.id}
        from={currentFrame}
        durationInFrames={durationFrames}
        name={`Scene ${i + 1}: ${scene.id}`}
      >
        <SceneTransition
          transition={transition}
          legacyTransition={legacyTransition}
          fps={fps}
        >
          <SceneRenderer scene={scene} />
        </SceneTransition>
      </Sequence>,
    );

    // Advance timeline, accounting for transition overlap
    currentFrame += durationFrames - overlapFrames;
  }

  return (
    <div style={{ width: "100%", height: "100%", backgroundColor: "#000" }}>
      {sceneSequences}
    </div>
  );
};
