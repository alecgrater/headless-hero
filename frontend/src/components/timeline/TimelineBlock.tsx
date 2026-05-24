import { assetUrl } from "../../api";
import { SEGMENT_COLORS } from "./constants";
import type { Scene } from "../../types/script";

interface Props {
  scene: Scene;
  laneType: "images" | "voiceover" | "fx" | "eli" | "timer" | "subtitle";
  pixelsPerSecond: number;
  segmentIdx: number;
  isSelected: boolean;
  onClick: () => void;
  segmentTimerEnabled?: boolean;
  subtitleHighlightEnabled?: boolean;
}

export default function TimelineBlock({
  scene,
  laneType,
  pixelsPerSecond,
  segmentIdx,
  isSelected,
  onClick,
  segmentTimerEnabled,
  subtitleHighlightEnabled,
}: Props) {
  const duration = scene.audio_duration_seconds || scene.duration_estimate_seconds;
  const width = Math.max(40, duration * pixelsPerSecond);
  const borderColor = SEGMENT_COLORS[segmentIdx % SEGMENT_COLORS.length];

  return (
    <button
      onClick={onClick}
      className={`relative h-full rounded-md overflow-hidden flex items-center shrink-0 transition-all ${
        isSelected
          ? "ring-2 ring-violet-500 bg-violet-500/5 shadow-lg shadow-violet-500/10"
          : "hover:bg-neutral-750"
      } bg-neutral-800`}
      style={{ width: `${width}px` }}
    >
      {/* Color-coded left border */}
      <div className={`absolute left-0 top-0 bottom-0 w-1 ${borderColor}`} />

      {/* Media source badge */}
      {laneType === "images" && <MediaSourceBadge source={scene.media_source} />}

      <div className="pl-2.5 pr-1.5 w-full overflow-hidden">
        {laneType === "images" && <ImageContent scene={scene} />}
        {laneType === "voiceover" && <VoiceoverContent scene={scene} duration={duration} />}
        {laneType === "fx" && <FxContent scene={scene} />}
        {laneType === "eli" && <EliContent scene={scene} />}
        {laneType === "timer" && <TimerContent enabled={!!segmentTimerEnabled} />}
        {laneType === "subtitle" && <SubtitleHighlightContent enabled={subtitleHighlightEnabled !== false} />}
      </div>
    </button>
  );
}

function MediaSourceBadge({ source }: { source?: string }) {
  const color: Record<string, string> = {
    ai: "bg-violet-500/60",
    ai_video: "bg-fuchsia-500/60",
  };
  const c = color[source || "ai"];
  if (!c) return null;

  return (
    <div className={`absolute bottom-0 left-0 right-0 h-1 ${c} z-10`} />
  );
}

function ImageContent({ scene }: { scene: Scene }) {
  const hasImage = !!scene.image_url || (scene.frame_urls && scene.frame_urls.length > 0);

  if (scene.video_url) {
    return (
      <div className="flex gap-1.5 items-center">
        <span className="w-2 h-2 rounded-full shrink-0 bg-fuchsia-500" />
        <span className="text-[10px] font-medium text-fuchsia-200 uppercase">Video</span>
      </div>
    );
  }

  if (scene.frame_urls && scene.frame_urls.length > 0) {
    return (
      <div className="flex gap-1.5 items-center h-full">
        <span className={`w-2 h-2 rounded-full shrink-0 ${hasImage ? "bg-emerald-500" : "bg-neutral-600"}`} />
        {scene.frame_urls.slice(0, 3).map((url, i) => (
          <img
            key={i}
            src={assetUrl(url)}
            alt=""
            className="h-6 w-6 rounded-sm object-cover"
          />
        ))}
        {scene.frame_urls.length > 3 && (
          <span className="text-[9px] text-neutral-500 ml-0.5">
            +{scene.frame_urls.length - 3}
          </span>
        )}
      </div>
    );
  }

  if (scene.image_url) {
    return (
      <div className="flex gap-1.5 items-center">
        <span className="w-2 h-2 rounded-full shrink-0 bg-emerald-500" />
        <img
          src={assetUrl(scene.image_url)}
          alt=""
          className="h-7 w-10 rounded-sm object-cover"
        />
      </div>
    );
  }

  // Placeholder
  return (
    <div className="flex gap-1.5 items-center">
      <span className="w-2 h-2 rounded-full shrink-0 bg-neutral-600" />
      <svg className="w-4 h-4 text-neutral-600" viewBox="0 0 20 20" fill="currentColor">
        <path
          fillRule="evenodd"
          d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm12 12H4l4-8 3 6 2-4 3 6z"
          clipRule="evenodd"
        />
      </svg>
    </div>
  );
}

function VoiceoverContent({ scene, duration }: { scene: Scene; duration: number }) {
  const hasAudio = !!scene.audio_url;
  return (
    <div className="flex items-center gap-1.5">
      <span
        className={`w-2 h-2 rounded-full shrink-0 ${
          hasAudio ? "bg-emerald-500" : "bg-neutral-600"
        }`}
      />
      <span className="text-[10px] text-neutral-400 tabular-nums truncate">
        {duration.toFixed(1)}s
      </span>
    </div>
  );
}

function FxContent({ scene }: { scene: Scene }) {
  const fx = scene.fx;
  const badges: string[] = [];
  if (fx?.drift) {
    badges.push(fx.drift.motion.replace("_", " "));
  }
  if (fx?.zoom_punch) {
    badges.push("zoom");
  }
  const hasFx = badges.length > 0;

  return (
    <div className="flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full shrink-0 ${hasFx ? "bg-emerald-500" : "bg-neutral-600"}`} />
      {hasFx ? (
        badges.map((badge, i) => (
          <span
            key={i}
            className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-medium"
          >
            {badge}
          </span>
        ))
      ) : (
        <span className="text-[10px] text-neutral-600">--</span>
      )}
    </div>
  );
}

function EliContent({ scene }: { scene: Scene }) {
  const hasEli = !!scene.eli_overlay?.enabled;

  return (
    <div className="flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full shrink-0 ${hasEli ? "bg-emerald-500" : "bg-neutral-600"}`} />
      {hasEli ? (
        <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-teal-500/20 text-teal-300 font-medium">
          eli
        </span>
      ) : (
        <span className="text-[10px] text-neutral-600">--</span>
      )}
    </div>
  );
}

function TimerContent({ enabled }: { enabled: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full shrink-0 ${enabled ? "bg-emerald-500" : "bg-neutral-600"}`} />
      {enabled ? (
        <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-sky-500/20 text-sky-300 font-medium">
          timer
        </span>
      ) : (
        <span className="text-[10px] text-neutral-600">--</span>
      )}
    </div>
  );
}

function SubtitleHighlightContent({ enabled }: { enabled: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full shrink-0 ${enabled ? "bg-emerald-500" : "bg-neutral-600"}`} />
      {enabled ? (
        <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-violet-500/20 text-violet-300 font-medium">
          highlight
        </span>
      ) : (
        <span className="text-[10px] text-neutral-600">--</span>
      )}
    </div>
  );
}
