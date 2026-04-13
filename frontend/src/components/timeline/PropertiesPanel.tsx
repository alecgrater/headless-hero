import { useCallback, useEffect, useRef, useState } from "react";
import { assetUrl, regenerateFX } from "../../api";
import type { Scene, SceneFX } from "../../types/script";
import AudioPlayer from "./AudioPlayer";

interface Props {
  scene: Scene;
  segmentIdx: number;
  segmentName: string;
  scriptId: string;
  onUpdate: (updates: Partial<Scene>) => void;
  onGenerateImage?: () => void;
  isGenerating?: boolean;
  onGenerateAudio?: () => void;
  isGeneratingAudio?: boolean;
}

export default function PropertiesPanel({
  scene,
  segmentIdx: _segmentIdx,
  segmentName,
  scriptId,
  onUpdate,
  onGenerateImage,
  isGenerating = false,
  onGenerateAudio,
  isGeneratingAudio = false,
}: Props) {
  const [narration, setNarration] = useState(scene.narration);
  const [visualPrompt, setVisualPrompt] = useState(scene.visual_prompt);
  const [isTitleCard, setIsTitleCard] = useState(scene.is_title_card);
  const [framePrompts, setFramePrompts] = useState<string[]>(scene.frame_prompts || []);
  const [frameCount, setFrameCount] = useState(scene.frame_count || 0);

  const sceneIdRef = useRef(scene.id);

  useEffect(() => {
    if (sceneIdRef.current !== scene.id) {
      sceneIdRef.current = scene.id;
      setNarration(scene.narration);
      setVisualPrompt(scene.visual_prompt);
      setIsTitleCard(scene.is_title_card);
      setFramePrompts(scene.frame_prompts || []);
      setFrameCount(scene.frame_count || 0);
    }
  }, [scene]);

  const commitField = useCallback(
    (field: keyof Scene, value: string | number | boolean) => {
      onUpdate({ [field]: value });
    },
    [onUpdate],
  );

  const [regeneratingFX, setRegeneratingFX] = useState(false);
  const [confirmOverwrite, setConfirmOverwrite] = useState<"image" | "audio" | "fx" | null>(null);

  const handleRegenerateFX = async () => {
    setRegeneratingFX(true);
    try {
      const res = await regenerateFX(scriptId, scene.id);
      if (res.ok) {
        const data = res.data as { scene_id: string; fx: SceneFX };
        onUpdate({ fx: data.fx as unknown as Record<string, unknown> });
      }
    } finally {
      setRegeneratingFX(false);
    }
  };

  return (
    <div className="flex flex-col min-h-0 flex-1 border-t border-neutral-800/60">
      {/* Header bar */}
      <div className="flex items-center px-4 py-1 border-b border-neutral-800/40 bg-neutral-900/60 shrink-0">
        <span className="text-[11px] text-neutral-600 uppercase tracking-widest font-medium">
          Scene Properties
        </span>
        <span className="text-xs text-neutral-500 ml-3">
          {segmentName} &middot; <span className="font-mono">{scene.id}</span>
        </span>
      </div>

      {/* 3-column layout: Text | Controls | Image */}
      <div className="flex-1 min-h-0 flex gap-4 px-4 py-2">

        {/* Col 1: Text editing — textareas flex-grow to fill */}
        <div className="flex-[2] flex flex-col gap-1.5 min-w-0">
          <div className="flex flex-col flex-1 min-h-0">
            <span className="text-xs font-medium text-neutral-400 mb-0.5 shrink-0">Narration</span>
            <textarea
              value={narration}
              onChange={(e) => setNarration(e.target.value)}
              onBlur={() => commitField("narration", narration)}
              className="flex-1 min-h-0 w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg p-2 border border-neutral-700/50 resize-none focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
            />
          </div>

          {(
            <div className="flex flex-col flex-1 min-h-0">
              <span className="text-xs font-medium text-neutral-400 mb-0.5 shrink-0">Visual Prompt</span>
              <textarea
                value={visualPrompt}
                onChange={(e) => setVisualPrompt(e.target.value)}
                onBlur={() => commitField("visual_prompt", visualPrompt)}
                className="flex-1 min-h-0 w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg p-2 border border-neutral-700/50 resize-none focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
              />
            </div>
          )}

          {/* Settings row pinned at bottom */}
          <div className="shrink-0 space-y-1">
            <div className="flex items-end gap-3 pt-1 border-t border-neutral-800/40">
              <label className="space-y-0.5 flex-1">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-medium text-neutral-500">Frames</span>
                  <span className="text-[10px] text-neutral-600 font-mono">{frameCount || 1}</span>
                </div>
                <input
                  type="range"
                  min={1}
                  max={8}
                  value={frameCount || 1}
                  onChange={(e) => {
                    const n = parseInt(e.target.value, 10);
                    setFrameCount(n);
                    const newPrompts = [...framePrompts];
                    while (newPrompts.length < n) newPrompts.push("");
                    while (newPrompts.length > n) newPrompts.pop();
                    setFramePrompts(newPrompts);
                    onUpdate({ frame_count: n, frame_prompts: newPrompts });
                  }}
                  className="w-full accent-violet-500"
                />
              </label>
              <label className="flex items-center gap-1 cursor-pointer pb-0.5">
                <input
                  type="checkbox"
                  checked={isTitleCard}
                  onChange={(e) => {
                    setIsTitleCard(e.target.checked);
                    commitField("is_title_card", e.target.checked);
                  }}
                  className="rounded border-neutral-600 bg-neutral-800 text-violet-500 focus:ring-violet-500"
                />
                <span className="text-[10px] font-medium text-neutral-500">TC</span>
              </label>
            </div>
          </div>
        </div>

        {/* Col 2: Controls — audio, preview, FX, frame prompts */}
        <div className="flex-[1.5] flex flex-col gap-1.5 min-w-0 min-h-0">
          {/* Audio */}
          {scene.audio_url ? (
            <div className="shrink-0 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-neutral-400">Audio</span>
                {onGenerateAudio && (
                  <button
                    onClick={() => setConfirmOverwrite("audio")}
                    disabled={isGeneratingAudio}
                    className="text-[10px] text-sky-400 hover:text-sky-300 transition-colors disabled:opacity-40 flex items-center gap-1"
                  >
                    {isGeneratingAudio ? (
                      <><span className="w-2.5 h-2.5 border border-sky-400/50 border-t-transparent rounded-full animate-spin" /> Gen...</>
                    ) : "Regen"}
                  </button>
                )}
              </div>
              <AudioPlayer src={assetUrl(scene.audio_url)} duration={scene.audio_duration_seconds} />
            </div>
          ) : onGenerateAudio ? (
            <button
              onClick={onGenerateAudio}
              disabled={isGeneratingAudio}
              className="shrink-0 w-full text-sm px-3 py-1.5 text-sky-400 bg-sky-500/10 hover:bg-sky-500/20 border border-sky-500/20 rounded-lg transition-colors font-medium disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isGeneratingAudio ? (
                <><span className="w-3.5 h-3.5 border-2 border-white/50 border-t-transparent rounded-full animate-spin" /> Generating...</>
              ) : "Generate Audio"}
            </button>
          ) : null}

          {/* FX */}
          {scene.fx && (
            <div className="shrink-0 border border-neutral-800 rounded-lg px-2.5 py-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-neutral-600 uppercase tracking-widest font-medium">FX</span>
                <button
                  onClick={() => setConfirmOverwrite("fx")}
                  disabled={regeneratingFX}
                  className="text-[10px] text-amber-400 hover:text-amber-300 transition-colors disabled:opacity-40 flex items-center gap-1"
                >
                  {regeneratingFX ? (
                    <><span className="w-2.5 h-2.5 border border-amber-400/50 border-t-transparent rounded-full animate-spin" /> Regen...</>
                  ) : "Regen"}
                </button>
              </div>
              <div className="flex flex-wrap items-center gap-2 mt-1">
                {scene.fx.zoom_punch && (
                  <div className="flex items-center gap-1">
                    <span className="text-[10px] bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded-full">zoom</span>
                    <span className="text-[10px] text-neutral-400">f{scene.fx.zoom_punch.trigger_frame} @ {scene.fx.zoom_punch.scale}x</span>
                  </div>
                )}
                {!scene.fx.zoom_punch && (
                  <p className="text-[10px] text-neutral-600 italic">No effects</p>
                )}
              </div>
            </div>
          )}

          {/* Frame prompts — overflow if many */}
          {frameCount > 1 && (
            <div className="flex-1 min-h-0 overflow-y-auto space-y-1 border-t border-neutral-800/40 pt-1">
              {framePrompts.slice(0, frameCount).map((fp, i) => (
                <label key={i} className="block">
                  <span className="text-[10px] font-medium text-neutral-500">Frame {i + 1}</span>
                  <input
                    type="text"
                    value={fp}
                    onChange={(e) => {
                      const updated = [...framePrompts];
                      updated[i] = e.target.value;
                      setFramePrompts(updated);
                    }}
                    onBlur={() => onUpdate({ frame_prompts: framePrompts })}
                    className="w-full text-xs text-neutral-200 bg-neutral-800/60 rounded px-1.5 py-1 border border-violet-700/30 focus:outline-none focus:border-violet-500/50"
                    placeholder={`Frame ${i + 1} visual...`}
                  />
                </label>
              ))}
            </div>
          )}
        </div>

        {/* Col 3: Image preview — fills full panel height */}
        <div className="flex-[1.5] flex flex-col gap-1 min-w-0 min-h-0">
          {scene.image_url ? (
            <>
              <div className="flex items-center justify-between shrink-0">
                <span className="text-xs font-medium text-neutral-400">Image</span>
                {onGenerateImage && (
                  <button
                    onClick={() => setConfirmOverwrite("image")}
                    disabled={isGenerating}
                    className="text-[10px] text-emerald-400 hover:text-emerald-300 transition-colors disabled:opacity-40 flex items-center gap-1"
                  >
                    {isGenerating ? (
                      <><span className="w-2.5 h-2.5 border border-emerald-400/50 border-t-transparent rounded-full animate-spin" /> Gen...</>
                    ) : frameCount > 1 ? `Regen ${frameCount} Frames` : "Regen"}
                  </button>
                )}
              </div>
              {scene.frame_urls && scene.frame_urls.length > 1 ? (
                <div className="flex-1 min-h-0 grid grid-cols-2 gap-1 auto-rows-fr">
                  {scene.frame_urls.map((url, i) => (
                    <img
                      key={i}
                      src={assetUrl(url)}
                      alt={`Frame ${i + 1}`}
                      className="w-full h-full object-cover rounded border border-neutral-700 min-h-0"
                    />
                  ))}
                </div>
              ) : (
                <img
                  src={assetUrl(scene.image_url)}
                  alt="Scene visual"
                  className="flex-1 min-h-0 w-full object-cover rounded-lg border border-neutral-700"
                />
              )}
            </>
          ) : onGenerateImage ? (
            <div className="flex-1 flex items-center justify-center">
              <button
                onClick={onGenerateImage}
                disabled={isGenerating}
                className="text-sm px-4 py-2 text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20 rounded-lg transition-colors font-medium disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isGenerating ? (
                  <><span className="w-3.5 h-3.5 border-2 border-white/50 border-t-transparent rounded-full animate-spin" /> Generating...</>
                ) : frameCount > 1 ? `Generate ${frameCount} Frames` : "Generate Image"}
              </button>
            </div>
          ) : null}
        </div>
      </div>

      {confirmOverwrite && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-neutral-900 border border-neutral-700 rounded-xl shadow-2xl p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold text-neutral-100 mb-2">
              Overwrite existing {confirmOverwrite === "fx" ? "FX" : confirmOverwrite}?
            </h3>
            <p className="text-sm text-neutral-400 mb-6">
              {confirmOverwrite === "image" && "This scene already has a generated image. Regenerating will overwrite it."}
              {confirmOverwrite === "audio" && "This scene already has generated audio. Regenerating will overwrite it."}
              {confirmOverwrite === "fx" && "This scene already has FX assignments. Regenerating will overwrite them."}
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setConfirmOverwrite(null)}
                className="px-4 py-2 text-sm rounded-lg text-neutral-300 hover:bg-neutral-800 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  const action = confirmOverwrite;
                  setConfirmOverwrite(null);
                  if (action === "image") onGenerateImage?.();
                  else if (action === "audio") onGenerateAudio?.();
                  else if (action === "fx") handleRegenerateFX();
                }}
                className="px-4 py-2 text-sm rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-medium transition-colors"
              >
                Overwrite & Regenerate
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
