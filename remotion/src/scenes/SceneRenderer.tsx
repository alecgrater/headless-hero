/**
 * SceneRenderer — dispatches to the appropriate scene component
 * based on scene type, media_type, and flags.
 * Also layers FX overlays, typography, and structural effects.
 */
import React from "react";
import { Audio } from "remotion";
import type { SceneInput } from "../types";
import { StaticImageScene } from "./StaticImageScene";
import { MultiFrameScene } from "./MultiFrameScene";
import { TitleCardScene } from "./TitleCardScene";
import { VideoClipScene } from "./VideoClipScene";

// Typography effects
import { KineticCaption } from "../effects/typography/KineticCaption";
import { WordReveal } from "../effects/typography/WordReveal";
import { LowerThird } from "../effects/typography/LowerThird";
import { TitleInsert } from "../effects/typography/TitleInsert";
import { SourceCitation } from "../effects/typography/SourceCitation";

// Overlay effects
import { ChapterIndicator } from "../effects/overlays/ChapterIndicator";
import { FilmGrain } from "../effects/overlays/FilmGrain";
import { Letterbox } from "../effects/overlays/Letterbox";
import { Vignette } from "../effects/overlays/Vignette";

// Structural effects
import { ColdOpenCard } from "../effects/structural/ColdOpenCard";
import { ChapterTransition } from "../effects/structural/ChapterTransition";
import { RecapCard } from "../effects/structural/RecapCard";
import { EndScreenCTA } from "../effects/structural/EndScreenCTA";

// Counters
import { DynamicCounter } from "../effects/counters/DynamicCounter";

interface Props {
  scene: SceneInput;
}

export const SceneRenderer: React.FC<Props> = ({ scene }) => {
  const hasMultipleFrames = scene.frame_paths && scene.frame_paths.length > 1;
  const isVideoClip = scene.media_type === "gameplay_clip" && scene.video_clip_path;
  const isTitleCard = scene.is_title_card && scene.title_card_zoom_target;
  const fx = scene.fx;

  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      {/* Visual layer */}
      {isVideoClip ? (
        <VideoClipScene scene={scene} />
      ) : isTitleCard ? (
        <TitleCardScene scene={scene} />
      ) : hasMultipleFrames ? (
        <MultiFrameScene scene={scene} />
      ) : (
        <StaticImageScene scene={scene} />
      )}

      {/* Typography effects */}
      {fx?.text_effects?.map((te, i) => {
        switch (te.type) {
          case "kinetic_caption":
            return (
              <KineticCaption
                key={i}
                text={te.text ?? scene.text_overlay}
                emphasisWords={te.words ?? []}
                enterAt={te.enter_at}
                duration={te.duration}
              />
            );
          case "word_reveal":
            return (
              <WordReveal
                key={i}
                text={te.text ?? scene.text_overlay}
                enterAt={te.enter_at}
              />
            );
          case "lower_third":
            return (
              <LowerThird
                key={i}
                text={te.text ?? scene.text_overlay}
                enterAt={te.enter_at}
                duration={te.duration}
              />
            );
          case "title_insert":
            return (
              <TitleInsert
                key={i}
                text={te.text ?? scene.text_overlay}
                enterAt={te.enter_at}
                duration={te.duration}
              />
            );
          case "source_citation":
            return (
              <SourceCitation
                key={i}
                text={te.text ?? scene.text_overlay}
                enterAt={te.enter_at}
                duration={te.duration}
              />
            );
          default:
            return null;
        }
      })}

      {/* Overlay effects */}
      {fx?.overlays?.map((ov, i) => {
        switch (ov.type) {
          case "chapter_indicator":
            return <ChapterIndicator key={i} />;
          case "film_grain":
            return <FilmGrain key={i} opacity={ov.config?.opacity as number} />;
          case "letterbox":
            return <Letterbox key={i} />;
          case "vignette":
            return <Vignette key={i} />;
          default:
            return null;
        }
      })}

      {/* Structural effects */}
      {fx?.structural && (() => {
        const cfg = fx.structural!.config ?? {};
        switch (fx.structural!.type) {
          case "cold_open":
            return <ColdOpenCard text={cfg.text as string} />;
          case "chapter_transition":
            return (
              <ChapterTransition
                title={cfg.title as string}
                subtitle={cfg.subtitle as string}
              />
            );
          case "recap":
            return <RecapCard text={cfg.text as string} />;
          case "end_screen":
            return <EndScreenCTA channelName={cfg.channel_name as string} />;
          default:
            return null;
        }
      })()}

      {/* Dynamic counter (stored in structural config) */}
      {fx?.structural?.type === "cold_open" &&
        fx.structural.config?.counter_target != null && (
          <DynamicCounter
            targetNumber={fx.structural.config.counter_target as number}
            suffix={fx.structural.config.counter_suffix as string}
            prefix={fx.structural.config.counter_prefix as string}
          />
        )}

      {/* Audio layer — narration voiceover */}
      {scene.audio_path && (
        <Audio src={scene.audio_path} volume={1} />
      )}
    </div>
  );
};
