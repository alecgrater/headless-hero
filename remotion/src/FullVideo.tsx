/**
 * FullVideo composition — sequences all scenes with chapter transitions
 * and a global progress bar overlay.
 */
import React from "react";
import { Sequence } from "remotion";
import type { FullVideoProps, SceneInput, ChapterMarker } from "./types";
import { SceneRenderer } from "./scenes/SceneRenderer";
import { AnimatedChapterMap } from "./effects/structural/AnimatedChapterMap";
import { ChapterIndicator } from "./effects/overlays/ChapterIndicator";
import { secondsToFrames } from "./utils/timing";

const CHAPTER_TRANSITION_FRAMES = 60; // 2 seconds at 30fps

export const FullVideo: React.FC<FullVideoProps> = ({
  segments,
  fps,
  video_fx,
  chapter_map,
}) => {
  // Flatten all scenes with segment info
  const allScenes: { scene: SceneInput; segmentIndex: number; segmentName: string }[] = [];
  for (let si = 0; si < segments.length; si++) {
    for (const scene of segments[si].scenes) {
      allScenes.push({ scene, segmentIndex: si, segmentName: segments[si].name });
    }
  }

  // Compute chapter markers from segment boundaries if not provided
  const markers: ChapterMarker[] = video_fx?.chapter_markers ?? [];

  // Build sequences: scenes + chapter transitions between segments
  const sceneSequences: React.ReactNode[] = [];
  let currentFrame = 0;
  let prevSegmentIndex = -1;

  // Track computed markers if none provided
  const computedMarkers: ChapterMarker[] = markers.length > 0 ? markers : [];

  for (let i = 0; i < allScenes.length; i++) {
    const { scene, segmentIndex, segmentName } = allScenes[i];
    const durationFrames = Math.max(fps, secondsToFrames(scene.duration_seconds, fps));

    // Insert chapter transition before first scene of each segment (except first)
    if (segmentIndex !== prevSegmentIndex && segmentIndex > 0 && chapter_map) {
      // Record marker if computing dynamically
      if (markers.length === 0) {
        computedMarkers.push({
          segment_index: segmentIndex,
          label: segmentName,
          frame_offset: currentFrame,
        });
      }

      sceneSequences.push(
        <Sequence
          key={`chapter-${segmentIndex}`}
          from={currentFrame}
          durationInFrames={CHAPTER_TRANSITION_FRAMES}
          name={`Chapter: ${segmentName}`}
        >
          <AnimatedChapterMap
            chapterMap={chapter_map}
            currentChapterIndex={segmentIndex}
          />
        </Sequence>,
      );
      currentFrame += CHAPTER_TRANSITION_FRAMES;

      // If the current scene IS the title card, skip it — the chapter transition already shows it
      if (scene.is_title_card && scene.title_card_zoom_target) {
        prevSegmentIndex = segmentIndex;
        continue;
      }
    }

    // Record first segment marker
    if (segmentIndex !== prevSegmentIndex && segmentIndex === 0 && markers.length === 0) {
      computedMarkers.push({
        segment_index: 0,
        label: segmentName,
        frame_offset: currentFrame,
      });
    }

    prevSegmentIndex = segmentIndex;

    sceneSequences.push(
      <Sequence
        key={scene.id}
        from={currentFrame}
        durationInFrames={durationFrames}
        name={`Scene ${i + 1}: ${scene.id}`}
      >
        <SceneRenderer scene={scene} />
      </Sequence>,
    );

    currentFrame += durationFrames;
  }

  const totalFrames = currentFrame;
  const activeMarkers = markers.length > 0 ? markers : computedMarkers;

  return (
    <div style={{ width: "100%", height: "100%", backgroundColor: "#000" }}>
      {sceneSequences}

      {/* Global progress bar */}
      {activeMarkers.length > 0 && (
        <Sequence from={0} durationInFrames={totalFrames}>
          <ChapterIndicator markers={activeMarkers} totalFrames={totalFrames} />
        </Sequence>
      )}
    </div>
  );
};
