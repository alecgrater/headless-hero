import { useCallback, useEffect, useRef, useState } from "react";
import type { Scene } from "../../types/script";

interface Props {
  scene: Scene;
  segmentIdx: number;
  segmentName: string;
  isLastInSegment: boolean;
  onUpdate: (updates: Partial<Scene>) => void;
  onSplit: () => void;
  onMerge: () => void;
}

export default function PropertiesPanel({
  scene,
  segmentIdx: _segmentIdx,
  segmentName,
  isLastInSegment,
  onUpdate,
  onSplit,
  onMerge,
}: Props) {
  const [narration, setNarration] = useState(scene.narration);
  const [visualPrompt, setVisualPrompt] = useState(scene.visual_prompt);
  const [textOverlay, setTextOverlay] = useState(scene.text_overlay);
  const [duration, setDuration] = useState(
    String(scene.duration_estimate_seconds),
  );
  const [isTitleCard, setIsTitleCard] = useState(scene.is_title_card);

  const sceneIdRef = useRef(scene.id);

  // Sync when scene selection changes
  useEffect(() => {
    if (sceneIdRef.current !== scene.id) {
      sceneIdRef.current = scene.id;
      setNarration(scene.narration);
      setVisualPrompt(scene.visual_prompt);
      setTextOverlay(scene.text_overlay);
      setDuration(String(scene.duration_estimate_seconds));
      setIsTitleCard(scene.is_title_card);
    }
  }, [scene]);

  const commitField = useCallback(
    (field: keyof Scene, value: string | number | boolean) => {
      onUpdate({ [field]: value });
    },
    [onUpdate],
  );

  return (
    <aside className="w-[320px] shrink-0 border-l border-neutral-800 overflow-y-auto p-4 space-y-4">
      <div className="text-xs text-neutral-500 uppercase tracking-wider font-semibold">
        Scene Properties
      </div>

      <div className="text-xs text-neutral-500 space-y-0.5">
        <div>
          ID: <span className="font-mono text-neutral-400">{scene.id}</span>
        </div>
        <div>
          Segment: <span className="text-neutral-400">{segmentName}</span>
        </div>
      </div>

      {/* Narration */}
      <label className="block space-y-1">
        <span className="text-xs font-medium text-neutral-400">Narration</span>
        <textarea
          value={narration}
          onChange={(e) => setNarration(e.target.value)}
          onBlur={() => commitField("narration", narration)}
          className="w-full text-sm text-neutral-200 bg-neutral-800 rounded-lg p-2.5 border border-neutral-700 resize-none focus:outline-none focus:ring-1 focus:ring-violet-500"
          rows={5}
        />
      </label>

      {/* Visual Prompt */}
      <label className="block space-y-1">
        <span className="text-xs font-medium text-neutral-400">
          Visual Prompt
        </span>
        <textarea
          value={visualPrompt}
          onChange={(e) => setVisualPrompt(e.target.value)}
          onBlur={() => commitField("visual_prompt", visualPrompt)}
          className="w-full text-sm text-neutral-200 bg-neutral-800 rounded-lg p-2.5 border border-neutral-700 resize-none focus:outline-none focus:ring-1 focus:ring-violet-500"
          rows={3}
        />
      </label>

      {/* Text Overlay */}
      <label className="block space-y-1">
        <span className="text-xs font-medium text-neutral-400">
          Text Overlay
        </span>
        <input
          type="text"
          value={textOverlay}
          onChange={(e) => setTextOverlay(e.target.value)}
          onBlur={() => commitField("text_overlay", textOverlay)}
          className="w-full text-sm text-neutral-200 bg-neutral-800 rounded-lg px-2.5 py-2 border border-neutral-700 focus:outline-none focus:ring-1 focus:ring-violet-500"
        />
      </label>

      {/* Duration */}
      <label className="block space-y-1">
        <span className="text-xs font-medium text-neutral-400">
          Duration (seconds)
        </span>
        <input
          type="number"
          min={1}
          max={120}
          step={0.5}
          value={duration}
          onChange={(e) => setDuration(e.target.value)}
          onBlur={() => {
            const n = parseFloat(duration);
            if (!isNaN(n) && n > 0) {
              commitField("duration_estimate_seconds", n);
            }
          }}
          className="w-full text-sm text-neutral-200 bg-neutral-800 rounded-lg px-2.5 py-2 border border-neutral-700 focus:outline-none focus:ring-1 focus:ring-violet-500"
        />
      </label>

      {/* Title Card Toggle */}
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={isTitleCard}
          onChange={(e) => {
            setIsTitleCard(e.target.checked);
            commitField("is_title_card", e.target.checked);
          }}
          className="rounded border-neutral-600 bg-neutral-800 text-violet-500 focus:ring-violet-500"
        />
        <span className="text-sm text-neutral-300">Title Card</span>
      </label>

      {/* Split / Merge */}
      <div className="border-t border-neutral-800 pt-4 space-y-2">
        <div className="text-xs text-neutral-500 uppercase tracking-wider font-semibold mb-2">
          Scene Actions
        </div>
        <button
          onClick={onSplit}
          className="w-full text-sm px-3 py-2 bg-neutral-800 hover:bg-neutral-700 rounded-lg transition-colors text-neutral-300"
        >
          Split Scene
        </button>
        <button
          onClick={onMerge}
          disabled={isLastInSegment}
          className="w-full text-sm px-3 py-2 bg-neutral-800 hover:bg-neutral-700 rounded-lg transition-colors text-neutral-300 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Merge with Next
        </button>
      </div>
    </aside>
  );
}
