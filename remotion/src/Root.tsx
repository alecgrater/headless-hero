import React from "react";
import { Composition } from "remotion";
import { FullVideo } from "./FullVideo";
import { ScenePreview } from "./ScenePreview";
import type { FullVideoProps, ScenePreviewProps } from "./types";
import "./styles.css";

// Remotion 4 expects LooseComponentType<Record<string, unknown>>.
// We cast our typed components to satisfy the generic constraint.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const FullVideoComp = FullVideo as any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ScenePreviewComp = ScenePreview as any;

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
          const CHAPTER_TRANSITION_SECONDS = 2; // 60 frames at 30fps
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
        id="ScenePreview"
        component={ScenePreviewComp}
        fps={30}
        width={1920}
        height={1080}
        durationInFrames={300}
        defaultProps={{
          scene: {
            id: "preview",
            narration: "",
            visual_prompt: "",
            text_overlay: "",
            duration_seconds: 10,
            is_title_card: false,
            media_type: "ai_generated",
          },
          fps: 30,
          width: 1920,
          height: 1080,
        }}
        calculateMetadata={({ props }) => {
          const p = props as unknown as ScenePreviewProps;
          return {
            durationInFrames: Math.max(
              1,
              Math.ceil(p.scene.duration_seconds * p.fps),
            ),
            fps: p.fps,
            width: p.width,
            height: p.height,
          };
        }}
      />
    </>
  );
};
