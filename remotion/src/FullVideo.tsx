/**
 * FullVideo composition — sequences all scenes with chapter transitions
 * and a global progress bar overlay.
 */
import React from "react";
import { Audio, Sequence } from "remotion";
import type { FullVideoProps, SceneInput, ChapterMarker } from "./types";
import { SceneRenderer } from "./scenes/SceneRenderer";
import { AnimatedChapterMap } from "./effects/structural/AnimatedChapterMap";
import { ChapterIndicator } from "./effects/overlays/ChapterIndicator";
import { SegmentTimer } from "./effects/overlays/SegmentTimer";
import { SegmentCounter } from "./effects/overlays/SegmentCounter";
import { secondsToFrames, CHAPTER_TRANSITION_SECONDS } from "./utils/timing";

const CHAPTER_TRANSITION_FRAMES = CHAPTER_TRANSITION_SECONDS * 30;

export const FullVideo: React.FC<FullVideoProps> = ({
  segments,
  fps,
  video_fx,
  chapter_map,
  segment_timer,
  subtitle_highlight,
  visual_canvas,
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

  // Track segment content frame ranges for timer overlay
  const segmentRanges: { start_frame: number; end_frame: number }[] = [];
  let segmentContentStart = 0;

  for (let i = 0; i < allScenes.length; i++) {
    const { scene, segmentIndex, segmentName } = allScenes[i];
    const durationFrames = Math.max(fps, secondsToFrames(scene.duration_seconds, fps));

    // Insert chapter transition before first scene of each segment
    if (segmentIndex !== prevSegmentIndex && chapter_map) {
      // Close previous segment range
      if (prevSegmentIndex >= 0) {
        segmentRanges.push({ start_frame: segmentContentStart, end_frame: currentFrame });
      }

      // Record marker if computing dynamically
      if (markers.length === 0) {
        computedMarkers.push({
          segment_index: segmentIndex,
          label: segmentName,
          frame_offset: currentFrame,
        });
      }

      // Check if this scene is a title card we'll absorb into the chapter transition
      const absorbTitleCard = !!(scene.is_title_card && scene.title_card_zoom_target);
      const transitionDuration = absorbTitleCard
        ? Math.max(CHAPTER_TRANSITION_FRAMES, durationFrames)
        : CHAPTER_TRANSITION_FRAMES;

      sceneSequences.push(
        <Sequence
          key={`chapter-${segmentIndex}`}
          from={currentFrame}
          durationInFrames={transitionDuration}
          name={`Chapter: ${segmentName}`}
        >
          <AnimatedChapterMap
            chapterMap={chapter_map}
            currentChapterIndex={segmentIndex}
          />
          {absorbTitleCard && scene.audio_path && (
            <Audio src={scene.audio_path} volume={1} />
          )}
        </Sequence>,
      );
      currentFrame += transitionDuration;

      // New segment content starts after transition
      segmentContentStart = currentFrame;

      // If the current scene IS the title card, skip it — the chapter transition already shows it
      if (absorbTitleCard) {
        prevSegmentIndex = segmentIndex;
        continue;
      }
    }

    // Record first segment marker (no chapter map case)
    if (segmentIndex !== prevSegmentIndex && segmentIndex === 0 && !chapter_map && markers.length === 0) {
      computedMarkers.push({
        segment_index: 0,
        label: segmentName,
        frame_offset: currentFrame,
      });
      segmentContentStart = currentFrame;
    } else if (segmentIndex !== prevSegmentIndex && prevSegmentIndex >= 0 && !chapter_map) {
      // Close previous segment range (no chapter map case)
      segmentRanges.push({ start_frame: segmentContentStart, end_frame: currentFrame });
      segmentContentStart = currentFrame;
    }

    prevSegmentIndex = segmentIndex;

    sceneSequences.push(
      <Sequence
        key={scene.id}
        from={currentFrame}
        durationInFrames={durationFrames}
        name={`Scene ${i + 1}: ${scene.id}`}
      >
        <SceneRenderer
          scene={{
            ...scene,
            transition_out: (() => {
              const next = allScenes[i + 1];
              if (!next || next.segmentIndex !== segmentIndex) return "cut";
              return next.scene.transition_in ?? "cut";
            })(),
          }}
          highlightEnabled={subtitle_highlight?.enabled ?? false}
          visualCanvas={visual_canvas}
        />
      </Sequence>,
    );

    currentFrame += durationFrames;
  }

  // Close the final segment range
  if (prevSegmentIndex >= 0) {
    segmentRanges.push({ start_frame: segmentContentStart, end_frame: currentFrame });
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

      {/* Segment countdown timer */}
      {segment_timer?.enabled && segmentRanges.length > 0 && (
        <Sequence from={0} durationInFrames={totalFrames}>
          <SegmentTimer segmentRanges={segmentRanges} />
        </Sequence>
      )}

      {/* Segment progress counter */}
      {segment_timer?.enabled && segmentRanges.length > 0 && (
        <Sequence from={0} durationInFrames={totalFrames}>
          <SegmentCounter segmentRanges={segmentRanges} />
        </Sequence>
      )}
    </div>
  );
};
