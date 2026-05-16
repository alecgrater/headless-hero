import React from "react";
import { Composition } from "remotion";
import { FullVideo } from "./FullVideo";
import { ShortFormVideo } from "./ShortFormVideo";
import type { FullVideoProps, ShortFormVideoProps } from "./types";
import { CHAPTER_TRANSITION_SECONDS } from "./utils/timing";
import "./styles.css";

// Remotion 4 expects LooseComponentType<Record<string, unknown>>.
// We cast our typed components to satisfy the generic constraint.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const FullVideoComp = FullVideo as any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ShortFormVideoComp = ShortFormVideo as any;

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="FullVideo"
        component={FullVideoComp}
        fps={30}
        width={1920}
        height={1080}
        durationInFrames={300}
        defaultProps={{
          segments: [],
          title: "",
          fps: 30,
          width: 1920,
          height: 1080,
        }}
        calculateMetadata={({ props }) => {
          const p = props as unknown as FullVideoProps;
          const totalSceneSeconds = p.segments.reduce(
            (sum, seg) =>
              sum +
              seg.scenes.reduce((s, sc) => s + sc.duration_seconds, 0),
            0,
          );
          // Add chapter transitions between segments (except before the first)
          const chapterTransitions = Math.max(0, p.segments.length - 1);
          const hasChapterMap = !!(p as unknown as Record<string, unknown>).chapter_map;
          const transitionSeconds = hasChapterMap ? chapterTransitions * CHAPTER_TRANSITION_SECONDS : 0;
          return {
            durationInFrames: Math.max(1, Math.ceil((totalSceneSeconds + transitionSeconds) * p.fps)),
            fps: p.fps,
            width: p.width,
            height: p.height,
          };
        }}
      />
      <Composition
        id="ShortFormVideo"
        component={ShortFormVideoComp}
        fps={30}
        width={1080}
        height={1920}
        durationInFrames={300}
        defaultProps={{
          intro: {
            segment_idx: 0,
            display_text: "",
            audio_path: "",
            duration_seconds: 3,
            word_timestamps: [],
            backdrop_image_path: "",
          },
          scenes: [],
          fps: 30,
          width: 1080,
          height: 1920,
        }}
        calculateMetadata={({ props }) => {
          const p = props as unknown as ShortFormVideoProps;
          const sceneSeconds = p.scenes.reduce((s, sc) => s + sc.duration_seconds, 0);
          const totalSeconds = p.intro.duration_seconds + sceneSeconds;
          return {
            durationInFrames: Math.max(1, Math.ceil(totalSeconds * p.fps)),
            fps: p.fps,
            width: p.width,
            height: p.height,
          };
        }}
      />
    </>
  );
};
