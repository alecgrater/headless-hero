/**
 * Frame/second conversion helpers for Remotion compositions.
 */

/** Convert seconds to frames at the given FPS. */
export function secondsToFrames(seconds: number, fps: number): number {
  return Math.round(seconds * fps);
}

/** Convert frames to seconds at the given FPS. */
export function framesToSeconds(frames: number, fps: number): number {
  return frames / fps;
}

/** Get the progress (0-1) of the current frame within a range. */
export function getProgress(
  currentFrame: number,
  startFrame: number,
  endFrame: number,
): number {
  if (endFrame <= startFrame) return 1;
  return Math.max(0, Math.min(1, (currentFrame - startFrame) / (endFrame - startFrame)));
}
