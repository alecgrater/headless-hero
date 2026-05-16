/**
 * ShortFormVideo composition — sequences a single segment's intro + scenes
 * for 9:16 short-form export. No chapter map, no global indicator bar, no
 * segment timer/counter (those are long-form-only).
 */
import React from "react";
import { Audio, Sequence } from "remotion";
import type { ShortFormVideoProps } from "./types";
import { SceneRenderer } from "./scenes/SceneRenderer";
import { ShortTitleCardScene } from "./scenes/ShortTitleCardScene";
import { secondsToFrames } from "./utils/timing";

export const ShortFormVideo: React.FC<ShortFormVideoProps> = ({
  intro,
  scenes,
  fps,
  subtitle_highlight,
}) => {
  const introDurationFrames = Math.max(fps, secondsToFrames(intro.duration_seconds, fps));

  const sequences: React.ReactNode[] = [];
  let currentFrame = 0;

  // Intro scene
  sequences.push(
    <Sequence
      key="intro"
      from={currentFrame}
      durationInFrames={introDurationFrames}
      name={`Intro: segment ${intro.segment_idx}`}
    >
      <ShortTitleCardScene intro={intro} />
      <Audio src={intro.audio_path} volume={1} />
    </Sequence>,
  );
  currentFrame += introDurationFrames;

  // Segment scenes
  for (let i = 0; i < scenes.length; i++) {
    const scene = scenes[i];
    const durationFrames = Math.max(fps, secondsToFrames(scene.duration_seconds, fps));

    sequences.push(
      <Sequence
        key={scene.id}
        from={currentFrame}
        durationInFrames={durationFrames}
        name={`Scene ${i + 1}: ${scene.id}`}
      >
        <SceneRenderer
          scene={{
            ...scene,
            transition_out: scenes[i + 1]?.transition_in ?? "cut",
          }}
          highlightEnabled={subtitle_highlight?.enabled ?? false}
          orientation="vertical"
        />
      </Sequence>,
    );

    currentFrame += durationFrames;
  }

  return (
    <div style={{ width: "100%", height: "100%", backgroundColor: "#000" }}>
      {sequences}
    </div>
  );
};
