/**
 * ShortFormVideo composition — sequences a single segment's scenes for 9:16
 * short-form export. The first scene (is_title_card=true) renders via
 * ShortTitleCardScene with the new vertical title-card layout. Remaining
 * scenes render via SceneRenderer with orientation="vertical".
 *
 * No chapter map, no global indicator bar, no segment timer/counter
 * (those are long-form-only).
 */
import React from "react";
import { Audio, Sequence } from "remotion";
import type { ShortFormVideoProps } from "./types";
import { SceneRenderer } from "./scenes/SceneRenderer";
import { ShortTitleCardScene } from "./scenes/ShortTitleCardScene";
import { secondsToFrames } from "./utils/timing";

export const ShortFormVideo: React.FC<ShortFormVideoProps> = ({
  scenes,
  stripped_title,
  segment_name,
  part_indicator,
  fps,
  subtitle_highlight,
  visual_canvas,
}) => {
  const sequences: React.ReactNode[] = [];
  let currentFrame = 0;

  for (let i = 0; i < scenes.length; i++) {
    const scene = scenes[i];
    const durationFrames = Math.max(fps, secondsToFrames(scene.duration_seconds, fps));

    if (i === 0 && scene.is_title_card) {
      sequences.push(
        <Sequence
          key={scene.id}
          from={currentFrame}
          durationInFrames={durationFrames}
          name={`Title card: ${scene.id}`}
        >
          <ShortTitleCardScene
            stripped_title={stripped_title}
            segment_name={segment_name}
            part_indicator={part_indicator ?? ""}
            backdrop_image_path={scene.image_path ?? ""}
          />
          {scene.audio_path && <Audio src={scene.audio_path} volume={1} />}
        </Sequence>,
      );
      currentFrame += durationFrames;
      continue;
    }

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
          visualCanvas={visual_canvas}
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
