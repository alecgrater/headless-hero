import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Captions, Columns3, Film, Hash, Image, Images, PanelsTopLeft, Repeat2, Route } from "lucide-react";
import { assetUrl, regenerateFX } from "../../api";
import type { Scene, SceneFX, VisualMode } from "../../types/script";
import { durationDescriptionForMode, durationLabelForMode } from "../settings/visual-modes/catalog";
import AudioPlayer from "./AudioPlayer";
import SceneMicroTimeline from "./SceneMicroTimeline";
import type { MicroTimelineHandle } from "./SceneMicroTimeline";

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
  microTimelineRef?: React.Ref<MicroTimelineHandle>;
  onSplitScene?: (splitTimeMs: number) => void;
  hideHeader?: boolean;
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
  microTimelineRef,
  onSplitScene,
  hideHeader = false,
}: Props) {
  const [narration, setNarration] = useState(scene.narration);
  const [visualPrompt, setVisualPrompt] = useState(scene.visual_prompt);
  const [galleryIndex, setGalleryIndex] = useState(0);

  const sceneIdRef = useRef(scene.id);

  useEffect(() => {
    if (sceneIdRef.current !== scene.id) {
      sceneIdRef.current = scene.id;
      setNarration(scene.narration);
      setVisualPrompt(scene.visual_prompt);
      setGalleryIndex(0);
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
  const modalFocusRef = useCallback((el: HTMLDivElement | null) => el?.focus(), []);

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

  const VISUAL_MODE_OPTIONS: { value: VisualMode; label: string; icon: ReactNode }[] = [
    { value: "video", label: "Video", icon: <Film className="h-3 w-3" /> },
    { value: "full_frame", label: "Full frame", icon: <Image className="h-3 w-3" /> },
    { value: "multi_frame", label: "Multi-frame", icon: <Images className="h-3 w-3" /> },
    { value: "continuous", label: "Continuous", icon: <Route className="h-3 w-3" /> },
    { value: "popup_sequence", label: "Popup", icon: <PanelsTopLeft className="h-3 w-3" /> },
    { value: "blink", label: "Blink", icon: <Repeat2 className="h-3 w-3" /> },
    { value: "comparison_board", label: "Compare", icon: <Columns3 className="h-3 w-3" /> },
    { value: "stat_card", label: "Stat card", icon: <Hash className="h-3 w-3" /> },
    { value: "captions", label: "Captions", icon: <Captions className="h-3 w-3" /> },
  ];
  const visualMode: VisualMode =
    scene.visual_mode ?? "full_frame";
  const durationLabel = durationLabelForMode(visualMode);
  const durationDescription = durationDescriptionForMode(visualMode);

  const setVisualMode = (mode: VisualMode) => {
    const isLayered = mode === "popup_sequence" || mode === "blink" || mode === "comparison_board" || mode === "stat_card";
    const shouldPreserveVisualLayers = isLayered && mode === visualMode;
    const update: Partial<Scene> = {
      visual_mode: mode,
      visual_layers: shouldPreserveVisualLayers ? scene.visual_layers : [],
    };
    onUpdate(update);
  };

  const sourceMeta = scene.visual_source_metadata;
  const sourceLabel = sourceMeta?.source_type
    ? sourceMeta.source_type.replace(/_/g, " ")
    : visualMode === "video"
      ? "AI video"
      : null;

  return (
    <div className="flex flex-col min-h-0 flex-1 overflow-y-auto">
      {/* Header bar */}
      {!hideHeader && (
        <div className="flex items-center px-4 py-1 border-b border-neutral-800/40 bg-neutral-900/60 shrink-0">
          <span className="text-xs text-neutral-500 ml-3">
            {segmentName} &middot; <span className="font-mono">{scene.id}</span>
          </span>
        </div>
      )}

      {/* 3-column layout: Narration | Visual Prompt | Controls */}
      <div className={`shrink-0 ${visualMode === "captions" || visualMode === "stat_card" ? "h-56" : "h-44"} flex gap-4 px-4 py-2`}>

        {/* Col 1: Narration */}
        <div className="flex-[2] flex flex-col min-w-0 min-h-0">
          <span className="text-xs font-medium text-neutral-400 mb-0.5 shrink-0">Narration</span>
          <textarea
            value={narration}
            onChange={(e) => setNarration(e.target.value)}
            onBlur={() => commitField("narration", narration)}
            className="flex-1 min-h-0 w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg p-2 border border-neutral-700/50 resize-none focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
          />
        </div>

        {/* Col 2: Visual Prompt */}
        <div className="flex-[2] flex flex-col min-w-0 min-h-0">
          <div className="flex flex-col flex-1 min-h-0">
            <span className="text-xs font-medium text-neutral-400 mb-0.5 shrink-0">Visual Prompt</span>
            <textarea
              value={visualPrompt}
              onChange={(e) => setVisualPrompt(e.target.value)}
              onBlur={() => commitField("visual_prompt", visualPrompt)}
              className="flex-1 min-h-0 w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg p-2 border border-neutral-700/50 resize-none focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
            />
          </div>
        </div>

        {/* Col 3: Visual mode selector + Generate Image + Generate Audio + FX */}
        <div className="flex-[1.2] flex flex-col justify-center gap-2 min-w-0 min-h-0 overflow-y-auto pr-1">
          {/* Visual mode selector */}
          <div className="shrink-0 flex flex-wrap gap-1">
            {VISUAL_MODE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setVisualMode(opt.value)}
                title={`Set visual mode to ${opt.label}. ${durationLabelForMode(opt.value)}`}
                className={`flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full transition-colors ${
                  visualMode === opt.value
                    ? "bg-violet-500/20 text-violet-300 font-medium"
                    : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800"
                }`}
              >
                {opt.icon}
                {opt.label}
              </button>
            ))}
          </div>
          <div className="shrink-0 rounded-lg border border-neutral-800 bg-neutral-950/40 px-2 py-1.5">
            <p className="text-[10px] font-semibold text-sky-300">{durationLabel}</p>
            <p className="mt-0.5 text-[10px] leading-snug text-neutral-500">{durationDescription}</p>
          </div>

          {visualMode === "captions" && (
            <div className="shrink-0 space-y-1.5 rounded-lg border border-red-500/20 bg-red-500/5 p-2">
              <div className="grid grid-cols-2 gap-2">
                <label className="min-w-0">
                  <span className="mb-0.5 block text-[10px] font-medium text-neutral-400">Caption text</span>
                  <input
                    type="text"
                    value={scene.caption_text ?? ""}
                    onChange={(e) => onUpdate({ caption_text: e.target.value })}
                    className="w-full rounded-md border border-neutral-700/50 bg-neutral-800/70 px-2 py-1 text-xs text-neutral-200 transition-colors placeholder:text-neutral-600 focus:border-red-500/50 focus:outline-none focus:ring-1 focus:ring-red-500/30"
                    placeholder="Optional override"
                  />
                </label>
                <label className="min-w-0">
                  <span className="mb-0.5 block text-[10px] font-medium text-neutral-400">Red emphasis</span>
                  <input
                    type="text"
                    value={scene.caption_emphasis ?? ""}
                    onChange={(e) => onUpdate({ caption_emphasis: e.target.value })}
                    className="w-full rounded-md border border-neutral-700/50 bg-neutral-800/70 px-2 py-1 text-xs text-neutral-200 transition-colors placeholder:text-neutral-600 focus:border-red-500/50 focus:outline-none focus:ring-1 focus:ring-red-500/30"
                    placeholder="Word or phrase"
                  />
                </label>
              </div>
              <p className="text-[10px] leading-snug text-neutral-500">
                Rendered in-scene with word timing; normal subtitles are suppressed.
              </p>
            </div>
          )}

          {visualMode === "stat_card" && (
            <div className="shrink-0 space-y-1.5 rounded-lg border border-amber-500/20 bg-amber-500/5 p-2">
              <div className="grid grid-cols-2 gap-2">
                <label className="min-w-0">
                  <span className="mb-0.5 block text-[10px] font-medium text-neutral-400">Stat value</span>
                  <input
                    type="text"
                    value={scene.stat_value ?? ""}
                    onChange={(e) => onUpdate({ stat_value: e.target.value })}
                    className="w-full rounded-md border border-neutral-700/50 bg-neutral-800/70 px-2 py-1 text-xs font-mono text-neutral-100 transition-colors placeholder:text-neutral-600 focus:border-amber-500/50 focus:outline-none focus:ring-1 focus:ring-amber-500/30"
                    placeholder="Big number, e.g. 85%"
                  />
                </label>
                <label className="min-w-0">
                  <span className="mb-0.5 block text-[10px] font-medium text-neutral-400">Stat label</span>
                  <input
                    type="text"
                    value={scene.stat_label ?? ""}
                    onChange={(e) => onUpdate({ stat_label: e.target.value })}
                    className="w-full rounded-md border border-neutral-700/50 bg-neutral-800/70 px-2 py-1 text-xs text-neutral-200 transition-colors placeholder:text-neutral-600 focus:border-amber-500/50 focus:outline-none focus:ring-1 focus:ring-amber-500/30"
                    placeholder="Subtitle below the number"
                  />
                </label>
              </div>
              <p className="text-[10px] leading-snug text-neutral-500">
                Renderer-owned typography over the canvas. Optional supporting icon comes from a single visual layer.
              </p>
            </div>
          )}

          {/* Generate Image button */}
          {onGenerateImage && (
            <button
              onClick={() => (scene.image_url || scene.video_url) ? setConfirmOverwrite("image") : onGenerateImage()}
              disabled={isGenerating}
              className="shrink-0 w-full text-sm px-3 py-1.5 text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20 rounded-lg transition-colors font-medium disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isGenerating ? (
                <><span className="w-3.5 h-3.5 border-2 border-white/50 border-t-transparent rounded-full animate-spin" /> Generating...</>
              ) : visualMode === "video"
                ? scene.video_url ? "Regenerate Video" : "Generate Video"
                : scene.image_url ? "Regenerate Image" : "Generate Image"}
            </button>
          )}

          {/* Generate Audio button / player */}
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
                {scene.fx.drift && (
                  <div className="flex items-center gap-1">
                    <span className="text-[10px] bg-sky-500/20 text-sky-300 px-1.5 py-0.5 rounded-full">{scene.fx.drift.motion.replace("_", " ")}</span>
                    <span className="text-[10px] text-neutral-400">{(scene.fx.drift.intensity * 100).toFixed(0)}% · {scene.fx.drift.anchor}</span>
                  </div>
                )}
                {scene.fx.zoom_punch && (
                  <div className="flex items-center gap-1">
                    <span className="text-[10px] bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded-full">zoom</span>
                    <span className="text-[10px] text-neutral-400">
                      {scene.fx.zoom_punch.trigger_word
                        ? `"${scene.fx.zoom_punch.trigger_word}" @ ${scene.fx.zoom_punch.scale}x`
                        : `f${scene.fx.zoom_punch.trigger_frame} @ ${scene.fx.zoom_punch.scale}x`}
                    </span>
                  </div>
                )}
                {!scene.fx.zoom_punch && !scene.fx.drift && (
                  <p className="text-[10px] text-neutral-600 italic">No effects</p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Image gallery */}
      {(() => {
        const expectedImageCount = scene.frame_directives?.length || 1;
        const availableImages = scene.frame_urls?.length
          ? scene.frame_urls
          : scene.image_url
            ? [scene.image_url]
            : [];
        const safeIndex = Math.min(galleryIndex, Math.max(0, availableImages.length - 1));

        return (
          <div className="shrink-0 h-80 flex items-center justify-center px-4 py-2">
            {availableImages.length > 0 ? (
              <div
                className="relative w-full h-full flex items-center justify-center focus:outline-none focus:ring-1 focus:ring-violet-500/30 rounded-lg"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "ArrowLeft" && safeIndex > 0) {
                    e.preventDefault();
                    setGalleryIndex(safeIndex - 1);
                  } else if (e.key === "ArrowRight" && safeIndex < availableImages.length - 1) {
                    e.preventDefault();
                    setGalleryIndex(safeIndex + 1);
                  }
                }}
              >
                <img
                  src={assetUrl(availableImages[safeIndex])}
                  alt={`Scene image ${safeIndex + 1}`}
                  className="max-w-full max-h-full object-contain rounded-lg"
                />
                {availableImages.length > 1 && (
                  <>
                    <button
                      onClick={() => setGalleryIndex(safeIndex - 1)}
                      disabled={safeIndex === 0}
                      className="absolute left-2 p-1 rounded-full bg-black/50 text-neutral-300 hover:text-white hover:bg-black/70 transition-colors disabled:opacity-0"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                      </svg>
                    </button>
                    <button
                      onClick={() => setGalleryIndex(safeIndex + 1)}
                      disabled={safeIndex === availableImages.length - 1}
                      className="absolute right-2 p-1 rounded-full bg-black/50 text-neutral-300 hover:text-white hover:bg-black/70 transition-colors disabled:opacity-0"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                      </svg>
                    </button>
                  </>
                )}
                <span className="absolute bottom-2 right-2 text-[10px] bg-black/60 text-neutral-300 px-1.5 py-0.5 rounded-full">
                  {safeIndex + 1}/{availableImages.length} image{availableImages.length > 1 ? "s" : ""}
                </span>
                {sourceLabel && (
                  <div className="absolute left-2 bottom-2 max-w-[70%] rounded-md bg-black/70 px-2 py-1 text-[10px] text-neutral-200 shadow">
                    <div className="flex items-center gap-1.5">
                      {sourceMeta?.fallback && (
                        <span className="rounded bg-amber-500/25 px-1 text-amber-200">fallback</span>
                      )}
                      <span className="capitalize">{sourceLabel}</span>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <span className="text-xs text-neutral-600">
                0/{expectedImageCount} image{expectedImageCount > 1 ? "s" : ""} expected
              </span>
            )}
          </div>
        );
      })()}

      {sourceMeta && (
        <div className="shrink-0 px-4 pb-2">
          <div className={`rounded-lg border px-3 py-2 text-xs ${
            sourceMeta.source_type === "scraped_web_image"
              ? "border-amber-500/30 bg-amber-500/10 text-amber-100"
              : "border-neutral-800 bg-neutral-900/70 text-neutral-300"
          }`}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium capitalize">{(sourceMeta.source_type || "visual source").replace(/_/g, " ")}</span>
              {sourceMeta.provider && <span className="text-neutral-400">via {sourceMeta.provider.replace(/_/g, " ")}</span>}
              {sourceMeta.fallback && <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] text-amber-200">fallback</span>}
            </div>
            {sourceMeta.query && (
              <p className="mt-1 text-neutral-400">Query: <span className="text-neutral-200">{sourceMeta.query}</span></p>
            )}
            {sourceMeta.reason && <p className="mt-1 text-neutral-400">{sourceMeta.reason}</p>}
            {sourceMeta.license_note && <p className="mt-1 text-amber-200">{sourceMeta.license_note}</p>}
          </div>
        </div>
      )}

      {/* Micro-timeline */}
      {scene.audio_url && (
        <div className="shrink-0 border-t border-neutral-800/40 px-4 py-2">
          <SceneMicroTimeline
            ref={microTimelineRef}
            scene={scene}
            playheadSeconds={0}
            onUpdateScene={(updates) => onUpdate(updates)}
            onSplitScene={onSplitScene ?? (() => {})}
          />
        </div>
      )}

      {confirmOverwrite && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          tabIndex={-1}
          ref={modalFocusRef}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              e.stopPropagation();
              setConfirmOverwrite(null);
            }
          }}
        >
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
