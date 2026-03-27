import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useState } from "react";
import { assetUrl } from "../../api";
import type { Scene } from "../../types/script";

const SEGMENT_COLORS_BORDER = [
  "border-l-violet-500",
  "border-l-sky-500",
  "border-l-emerald-500",
  "border-l-amber-500",
  "border-l-rose-500",
  "border-l-cyan-500",
  "border-l-fuchsia-500",
  "border-l-lime-500",
];

interface Props {
  scene: Scene;
  segmentIdx: number;
  isSelected: boolean;
  onClick: () => void;
  onNarrationChange: (narration: string) => void;
  onGenerateImage?: () => void;
  isGenerating?: boolean;
  onGenerateAudio?: () => void;
  isGeneratingAudio?: boolean;
}

export default function SceneCard({
  scene,
  segmentIdx,
  isSelected,
  onClick,
  onNarrationChange,
  onGenerateImage,
  isGenerating = false,
  onGenerateAudio: _onGenerateAudio,
  isGeneratingAudio = false,
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

  const colorClass = SEGMENT_COLORS_BORDER[segmentIdx % SEGMENT_COLORS_BORDER.length];

  return (
    <div
      ref={setNodeRef}
      style={style}
      onClick={onClick}
      className={`rounded-lg border-l-4 ${colorClass} border border-neutral-800 bg-neutral-900 px-3 py-2.5 cursor-pointer transition-colors select-none ${
        isSelected
          ? "ring-2 ring-violet-500 border-neutral-700"
          : "hover:border-neutral-700"
      }`}
    >
      {/* Drag handle + header */}
      <div className="flex items-center gap-2 mb-1.5">
        <span
          {...attributes}
          {...listeners}
          className="cursor-grab active:cursor-grabbing text-neutral-600 hover:text-neutral-400"
        >
          ⠿
        </span>
        <span className="text-[10px] font-mono text-neutral-600">{scene.id}</span>
        {scene.is_title_card && (
          <span className="text-[10px] bg-violet-500/20 text-violet-300 px-1.5 py-0.5 rounded-full">
            title
          </span>
        )}
        <span className="text-[10px] text-neutral-500 ml-auto">
          {scene.duration_estimate_seconds}s
        </span>
        {scene.audio_url ? (
          <span className="text-[10px] text-emerald-400" title="Audio generated">
            &#9835;
          </span>
        ) : isGeneratingAudio ? (
          <span className="w-3 h-3 border border-sky-400 border-t-transparent rounded-full animate-spin" />
        ) : null}
      </div>

      {/* Thumbnail / Image */}
      <div className="relative bg-neutral-800 rounded h-20 mb-2 overflow-hidden">
        {scene.image_url ? (
          <img
            src={assetUrl(scene.image_url)}
            alt="Scene visual"
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="flex items-center justify-center h-full">
            {onGenerateImage ? (
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
        {isGenerating && (
          <div className="absolute inset-0 bg-neutral-900/70 flex items-center justify-center">
            <div className="w-5 h-5 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}
      </div>

      {/* Narration */}
      {isEditing ? (
        <textarea
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
          autoFocus
          className="w-full text-xs text-neutral-300 bg-neutral-800 rounded p-1.5 border border-neutral-700 resize-none focus:outline-none focus:ring-1 focus:ring-violet-500"
          rows={3}
        />
      ) : (
        <p
          onDoubleClick={handleDoubleClick}
          className="text-xs text-neutral-400 leading-relaxed line-clamp-3"
          title="Double-click to edit"
        >
          {scene.narration || <span className="italic text-neutral-600">No narration</span>}
        </p>
      )}

      {/* Overlay indicator */}
      {scene.text_overlay && (
        <p className="text-[10px] text-amber-400/70 mt-1 truncate">
          📝 {scene.text_overlay}
        </p>
      )}
    </div>
  );
}

export { SEGMENT_COLORS_BORDER };
