/**
 * Custom spring/easing configurations for Remotion animations.
 */
import { spring } from "remotion";

export interface SpringConfig {
  damping: number;
  mass: number;
  stiffness: number;
  overshootClamping?: boolean;
}

/** Gentle, cinematic spring — good for Ken Burns camera moves. */
export const CAMERA_SPRING: SpringConfig = {
  damping: 200,
  mass: 1,
  stiffness: 10,
  overshootClamping: true,
};

/** Snappy spring — good for UI elements popping in. */
export const SNAPPY_SPRING: SpringConfig = {
  damping: 15,
  mass: 0.5,
  stiffness: 200,
};

/** Bouncy spring — good for emphasis effects. */
export const BOUNCY_SPRING: SpringConfig = {
  damping: 10,
  mass: 0.8,
  stiffness: 150,
};

/** Smooth ease-out — good for fades and slides. */
export const SMOOTH_SPRING: SpringConfig = {
  damping: 30,
  mass: 1,
  stiffness: 80,
  overshootClamping: true,
};

/** Create a spring value that animates from 0 to 1. */
export function makeSpring(
  frame: number,
  fps: number,
  config: SpringConfig = CAMERA_SPRING,
  delay: number = 0,
): number {
  return spring({
    frame: frame - delay,
    fps,
    config: {
      damping: config.damping,
      mass: config.mass,
      stiffness: config.stiffness,
      overshootClamping: config.overshootClamping,
    },
  });
}
