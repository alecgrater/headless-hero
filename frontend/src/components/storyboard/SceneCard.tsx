import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useState } from "react";
import { assetUrl } from "../../api";
import type { KenBurnsConfig, Scene } from "../../types/script";

const SEGMENT_COLORS_TOP = [
  "bg-violet-500",
  "bg-sky-500",
  "bg-emerald-500",
  "bg-amber-500",
  "bg-rose-500",
  "bg-cyan-500",
  "bg-fuchsia-500",
  "bg-lime-500",
];

const MOTION_ICONS: Record<NonNullable<KenBurnsConfig["effect"]>, string> = {
  none: "",
  zoom_in: "\u2197",
  zoom_out: "\u2199",
  pan_left: "\u2190",
  pan_right: "\u2192",
  pan_up: "\u2191",
  pan_down: "\u2193",
};

type BatchStatus = "idle" | "pending" | "generating" | "done" | "failed";

interface Props {
  scene: Scene;
  segmentIdx: number;
  sceneNumber: number;
  isSelected: boolean;
  onClick: () => void;
  onNarrationChange: (narration: string) => void;
  onGenerateImage?: () => void;
  isGenerating?: boolean;
  onGenerateAudio?: () => void;
  isGeneratingAudio?: boolean;
  batchImageStatus?: BatchStatus;
  onRetryImage?: () => void;
}

export default function SceneCard({
  scene,
  segmentIdx,
  sceneNumber,
  isSelected,
  onClick,
  onNarrationChange,
  onGenerateImage,
  isGenerating = false,
  onGenerateAudio: _onGenerateAudio,
  isGeneratingAudio = false,
  batchImageStatus = "idle",
  onRetryImage,
}: Props) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: scene.id });

  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(scene.narration);

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  const handleDoubleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditValue(scene.narration);
    setIsEditing(true);
  };

  const handleBlur = () => {
    setIsEditing(false);
    if (editValue !== scene.narration) {
      onNarrationChange(editValue);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      setIsEditing(false);
      setEditValue(scene.narration);
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleBlur();
    }
  };

  const topStripeColor = SEGMENT_COLORS_TOP[segmentIdx % SEGMENT_COLORS_TOP.length];

  return (
    <div
      ref={setNodeRef}
      style={style}
      onClick={onClick}
      className={`group rounded-xl border border-neutral-800/80 bg-neutral-900 overflow-hidden cursor-pointer transition-all duration-200 select-none card-enter ${
        isSelected
          ? "ring-2 ring-violet-500/70 ring-offset-1 ring-offset-neutral-950"
          : "hover:border-neutral-700 hover:shadow-lg hover:shadow-black/20"
      }`}
    >
      {/* Top accent stripe */}
      <div className={`h-0.5 ${topStripeColor}`} />

      {/* Drag handle + header */}
      <div className="flex items-center gap-2 px-3 pt-2.5 pb-1.5">
        <span
          {...attributes}
          {...listeners}
          className="cursor-grab active:cursor-grabbing text-neutral-700 hover:text-neutral-400"
        >
          ⠿
        </span>
        <span className="text-[11px] font-mono text-neutral-500 bg-neutral-800 px-1.5 py-0.5 rounded">#{sceneNumber}</span>
        {scene.is_title_card && (
          <span className="text-[10px] bg-violet-500/20 text-violet-300 px-1.5 py-0.5 rounded-full">
            title
          </span>
        )}
        {scene.is_animated && (
          <span className="text-[10px] bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded-full" title="Animated A/B flip between two images">
            A/B
          </span>
        )}
        {scene.media_type === "gameplay_clip" && (
          <span className="text-[10px] bg-red-500/20 text-red-300 px-1.5 py-0.5 rounded-full" title="Real gameplay clip from YouTube">
            clip
          </span>
        )}
        {scene.media_type === "hardware_image" && (
          <span className="text-[10px] bg-blue-500/20 text-blue-300 px-1.5 py-0.5 rounded-full" title="Real hardware image from YouTube">
            hw
          </span>
        )}
        <span className="text-[10px] text-neutral-500 ml-auto tabular-nums" title="Estimated scene duration">
          {scene.duration_estimate_seconds}s
        </span>
        {scene.ken_burns && scene.ken_burns.effect !== "none" && (
          <span
            className="text-[10px] bg-cyan-500/20 text-cyan-300 px-1.5 py-0.5 rounded-full"
            title={`${scene.ken_burns.effect.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())} (${scene.ken_burns.intensity})`}
          >
            {MOTION_ICONS[scene.ken_burns.effect]}
          </span>
        )}
        {scene.audio_url ? (
          <span className="text-[10px] text-emerald-400" title="Audio generated">
            &#9835;
          </span>
        ) : isGeneratingAudio ? (
          <span className="w-3 h-3 border border-sky-400 border-t-transparent rounded-full animate-spin" />
        ) : null}
      </div>

      {/* Thumbnail / Image */}
      <div className="relative bg-neutral-800 mx-3 rounded-lg h-[140px] mb-2 overflow-hidden">
        {scene.video_clip_url ? (
          <video
            src={assetUrl(scene.video_clip_url)}
            muted
            className="w-full h-full object-cover fade-in-image transition-transform duration-300 group-hover:scale-[1.02]"
          />
        ) : scene.image_url ? (
          <img
            src={assetUrl(scene.image_url)}
            alt="Scene visual"
            className="w-full h-full object-cover fade-in-image transition-transform duration-300 group-hover:scale-[1.02]"
          />
        ) : isGenerating || batchImageStatus === "generating" ? (
          <div className="shimmer-skeleton w-full h-full" />
        ) : batchImageStatus === "failed" ? (
          <div className="flex flex-col items-center justify-center h-full bg-red-500/10">
            <span className="text-red-400 text-xs mb-1">Failed</span>
            {onRetryImage && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onRetryImage();
                }}
                className="text-[10px] px-2 py-0.5 bg-red-600/30 hover:bg-red-600/50 rounded text-red-300 transition-colors"
              >
                Retry
              </button>
            )}
          </div>
        ) : batchImageStatus === "done" ? (
          <div className="flex items-center justify-center h-full">
            <span className="text-emerald-400 text-sm">&#10003;</span>
          </div>
        ) : batchImageStatus === "pending" ? (
          <div className="shimmer-skeleton w-full h-full flex items-center justify-center">
            <span className="text-neutral-500 text-[10px]">Queued</span>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full p-2">
            {scene.visual_prompt ? (
              <p className="text-[10px] text-neutral-600 leading-snug line-clamp-4 text-center">
                {scene.visual_prompt}
              </p>
            ) : onGenerateImage ? (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onGenerateImage();
                }}
                disabled={isGenerating}
                className="text-[10px] px-2 py-1 bg-neutral-700 hover:bg-neutral-600 rounded text-neutral-400 transition-colors disabled:opacity-40"
              >
                Generate
              </button>
            ) : (
              <span className="text-neutral-600 text-xs">Visual Preview</span>
            )}
          </div>
        )}
      </div>

      {/* Narration */}
      {isEditing ? (
        <div className="px-3 pb-3">
          <textarea
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onBlur={handleBlur}
            onKeyDown={handleKeyDown}
            autoFocus
            className="w-full text-[13px] text-neutral-300 bg-neutral-800 rounded p-1.5 border border-neutral-700 resize-none focus:outline-none focus:ring-1 focus:ring-violet-500"
            rows={3}
          />
        </div>
      ) : (
        <p
          onDoubleClick={handleDoubleClick}
          className="text-[13px] text-neutral-400 leading-relaxed line-clamp-3 px-3 pb-3"
          title="Double-click to edit"
        >
          {scene.narration || <span className="italic text-neutral-600">Double-click to write narration...</span>}
        </p>
      )}

      {/* Overlay indicator */}
      {scene.text_overlay && (
        <p className="text-[10px] text-amber-400/70 px-3 pb-2 truncate">
          {scene.text_overlay}
        </p>
      )}
    </div>
  );
}
