/**
 * VerticalSceneLayout — three-band layout for 9:16 narration scenes.
 *
 * - Top band (y=0..656): blurred-dim copy of the focal image (Eli sits inside).
 * - Middle band (y=656..1264): clean focal image, full-width.
 * - Bottom band (y=1264..1920): blurred-dim copy of the focal image (subtitles overlay).
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

// Layout constants — derived from spec (656 + 608 + 656 = 1920)
const TOP_BAND_HEIGHT = 656;
const MIDDLE_BAND_HEIGHT = 608;
const BOTTOM_BAND_HEIGHT = 656;

const BLUR_FILTER = "blur(40px) brightness(0.4) saturate(0.6)";

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
        {children}
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
