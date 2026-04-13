import type React from "react";
import { spring, interpolate } from "remotion";

export const ACCENT_COLOR = "#a78bfa"; // violet-400

export interface StyleResult {
  style: React.CSSProperties;
  displayText?: string;
}

// Intensity multiplier: 1 = subtle, 2 = standard, 3 = max impact
function intensityScale(intensity: number, low: number, mid: number, high: number): number {
  if (intensity <= 1) return low;
  if (intensity >= 3) return high;
  return mid;
}

export function renderStyle(
  style: string,
  localFrame: number,
  fps: number,
  fullText: string,
  intensity: number,
): StyleResult {
  switch (style) {
    case "scale_pop": {
      const overshoot = intensityScale(intensity, 0.1, 0.2, 0.35);
      const s = spring({
        frame: localFrame,
        fps,
        config: {
          damping: intensityScale(intensity, 18, 12, 6),
          mass: 0.5,
          stiffness: 200,
        },
      });
      return {
        style: {
          transform: `scale(${0.8 + s * overshoot + (1 - overshoot)})`,
          display: "inline-block",
        },
      };
    }
    case "color_flash": {
      const flashDuration = intensityScale(intensity, 1, 2, 5);
      const isFlash = localFrame < flashDuration;
      const glowSize = intensityScale(intensity, 10, 20, 40);
      return {
        style: {
          color: isFlash ? ACCENT_COLOR : "#fff",
          textShadow: isFlash
            ? `0 0 ${glowSize}px ${ACCENT_COLOR}, 0 4px 16px rgba(0,0,0,0.9)`
            : "0 4px 16px rgba(0,0,0,0.9), 0 2px 4px rgba(0,0,0,0.5)",
        },
      };
    }
    case "size_burst": {
      const burstFrames = intensityScale(intensity, 10, 15, 20);
      const startScale = intensityScale(intensity, 2, 3, 5);
      const scale = localFrame < burstFrames
        ? interpolate(localFrame, [0, burstFrames], [startScale, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          })
        : 1;
      return {
        style: {
          transform: `scale(${scale})`,
          display: "inline-block",
        },
      };
    }
    case "shake": {
      const shakeFrames = intensityScale(intensity, 6, 10, 16);
      const magnitude = intensityScale(intensity, 1, 2, 4);
      if (localFrame < shakeFrames) {
        const offsetX = Math.sin(localFrame * 7) * magnitude;
        const offsetY = Math.cos(localFrame * 5) * magnitude;
        return {
          style: {
            transform: `translate(${offsetX}px, ${offsetY}px)`,
            display: "inline-block",
          },
        };
      }
      return { style: {} };
    }
    case "underline_draw": {
      const drawDuration = intensityScale(intensity, 20, 15, 8);
      const progress = Math.min(1, localFrame / drawDuration);
      const thickness = intensityScale(intensity, 3, 4, 6);
      return {
        style: {
          borderBottom: `${thickness}px solid #fff`,
          paddingBottom: "4px",
          backgroundImage: "linear-gradient(#fff, #fff)",
          backgroundSize: `${progress * 100}% ${thickness}px`,
          backgroundPosition: "left bottom",
          backgroundRepeat: "no-repeat",
          borderBottomColor: "transparent",
        },
      };
    }
    case "glow_pulse": {
      const pulseSpeed = intensityScale(intensity, 0.3, 0.6, 1.0);
      const maxBlur = intensityScale(intensity, 12, 24, 40);
      const maxSpread = intensityScale(intensity, 4, 12, 20);
      const pulsePhase = Math.sin(localFrame * pulseSpeed) * 0.5 + 0.5;
      const blurRadius = 8 + pulsePhase * maxBlur;
      const spreadRadius = 4 + pulsePhase * maxSpread;
      return {
        style: {
          color: ACCENT_COLOR,
          textShadow: `0 0 ${blurRadius}px ${ACCENT_COLOR}, 0 0 ${spreadRadius}px ${ACCENT_COLOR}, 0 4px 16px rgba(0,0,0,0.9)`,
        },
      };
    }
    case "typewriter": {
      const revealFrames = intensityScale(intensity, 18, 12, 6);
      const charsPerFrame = fullText.length / revealFrames;
      const visibleChars = Math.min(fullText.length, Math.floor(localFrame * charsPerFrame) + 1);
      return {
        style: {
          fontFamily: "'Courier New', monospace",
        },
        displayText: fullText.slice(0, visibleChars),
      };
    }
    case "slide_up": {
      const distance = intensityScale(intensity, 30, 60, 100);
      const s = spring({
        frame: localFrame,
        fps,
        config: {
          damping: intensityScale(intensity, 18, 14, 8),
          mass: 0.8,
          stiffness: 180,
        },
      });
      const translateY = interpolate(s, [0, 1], [distance, 0]);
      return {
        style: {
          transform: `translateY(${translateY}px)`,
          display: "inline-block",
        },
      };
    }
    case "bounce_in": {
      const distance = intensityScale(intensity, -40, -80, -140);
      const s = spring({
        frame: localFrame,
        fps,
        config: {
          damping: intensityScale(intensity, 10, 6, 3),
          mass: 0.6,
          stiffness: 200,
        },
      });
      const translateY = interpolate(s, [0, 1], [distance, 0]);
      return {
        style: {
          transform: `translateY(${translateY}px)`,
          display: "inline-block",
        },
      };
    }
    case "rotate_in": {
      const rotation = intensityScale(intensity, -8, -15, -25);
      const startScale = intensityScale(intensity, 0.85, 0.7, 0.5);
      const s = spring({
        frame: localFrame,
        fps,
        config: {
          damping: intensityScale(intensity, 16, 12, 6),
          mass: 0.5,
          stiffness: 180,
        },
      });
      const rot = interpolate(s, [0, 1], [rotation, 0]);
      const scale = interpolate(s, [0, 1], [startScale, 1]);
      return {
        style: {
          transform: `rotate(${rot}deg) scale(${scale})`,
          display: "inline-block",
          transformOrigin: "center center",
        },
      };
    }
    case "glitch": {
      const glitchFrames = intensityScale(intensity, 5, 8, 14);
      const magnitude = intensityScale(intensity, 1.5, 3, 6);
      const rgbMagnitude = intensityScale(intensity, 1, 2, 4);
      if (localFrame < glitchFrames) {
        const offsetX = Math.sin(localFrame * 13) * magnitude;
        const offsetY = Math.cos(localFrame * 9) * (magnitude * 0.66);
        const rgbShift = Math.floor(localFrame * rgbMagnitude) + 2;
        return {
          style: {
            transform: `translate(${offsetX}px, ${offsetY}px)`,
            display: "inline-block",
            textShadow: `${rgbShift}px 0 #ff0040, ${-rgbShift}px 0 #00ff88, 0 4px 16px rgba(0,0,0,0.9)`,
          },
        };
      }
      return { style: {} };
    }
    case "gradient_sweep": {
      const sweepFrames = intensityScale(intensity, 30, 20, 12);
      const sweepProgress = Math.min(1, localFrame / sweepFrames);
      const gradientPos = sweepProgress * 200 - 50;
      return {
        style: {
          background: `linear-gradient(90deg, #fff ${gradientPos - 30}%, ${ACCENT_COLOR} ${gradientPos}%, #38bdf8 ${gradientPos + 30}%, #fff ${gradientPos + 60}%)`,
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          backgroundClip: "text",
          display: "inline-block",
          textShadow: "none",
        },
      };
    }
    default:
      return { style: {} };
  }
}
