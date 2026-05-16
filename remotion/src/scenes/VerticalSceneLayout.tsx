/**
 * VerticalSceneLayout — three-band layout for 9:16 narration scenes.
 *
 * - Top band (y=0..500): dimmed blurred copy of the focal image (Eli sits inside).
 * - Middle band (y=500..1420): focal image, enlarged vertically (cover-cropped + subtle stretch).
 * - Bottom band (y=1420..1920): dimmed blurred copy (subtitles overlay).
 *
 * Eli is positioned top-center inside the top band by EliOverlay (handled separately).
 * Subtitles are positioned by SubtitleOverlay using its `orientation` prop.
 */
import React from "react";
import { Img } from "remotion";

interface Props {
  imagePath: string | null | undefined;
  children: React.ReactNode; // the focal-image element rendered by StaticImageScene/MultiFrameScene/etc.
}

// Layout constants — 500 + 920 + 500 = 1920
const TOP_BAND_HEIGHT = 500;
const MIDDLE_BAND_HEIGHT = 920;
const BOTTOM_BAND_HEIGHT = 500;

// Children are wrapped with a small non-uniform scale to push the image a bit
// taller without an obvious stretch. Cover-cropping handles the horizontal
// overflow that results.
const FOCAL_STRETCH = "scale(1.0, 1.04)";

// Tuned for visibility: image is still readable through the blur, but dim
// enough that white text overlays remain high-contrast.
const BLUR_FILTER = "blur(28px) brightness(0.6) saturate(0.85)";

export const VerticalSceneLayout: React.FC<Props> = ({ imagePath, children }) => {
  return (
    <div style={{ width: "100%", height: "100%", position: "relative", backgroundColor: "#000" }}>
      {/* Top blurred-dim band */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: TOP_BAND_HEIGHT,
          overflow: "hidden",
        }}
      >
        {imagePath && (
          <Img
            src={imagePath}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              filter: BLUR_FILTER,
              transform: "scale(1.1)", // prevents blur edge artifacts
            }}
          />
        )}
      </div>

      {/* Middle focal image band */}
      <div
        style={{
          position: "absolute",
          top: TOP_BAND_HEIGHT,
          left: 0,
          width: "100%",
          height: MIDDLE_BAND_HEIGHT,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: "100%",
            height: "100%",
            transform: FOCAL_STRETCH,
            transformOrigin: "center center",
          }}
        >
          {children}
        </div>
      </div>

      {/* Bottom blurred-dim band */}
      <div
        style={{
          position: "absolute",
          top: TOP_BAND_HEIGHT + MIDDLE_BAND_HEIGHT,
          left: 0,
          width: "100%",
          height: BOTTOM_BAND_HEIGHT,
          overflow: "hidden",
        }}
      >
        {imagePath && (
          <Img
            src={imagePath}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              filter: BLUR_FILTER,
              transform: "scale(1.1)",
            }}
          />
        )}
      </div>
    </div>
  );
};

// Exported for use by SubtitleOverlay positioning logic
export const VERTICAL_LAYOUT = {
  TOP_BAND_HEIGHT,
  MIDDLE_BAND_HEIGHT,
  BOTTOM_BAND_HEIGHT,
} as const;
