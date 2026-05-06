import { useCallback, useEffect, useRef, useState } from "react";
import { assetUrl, regenerateFX, uploadSceneMedia } from "../../api";
import type { Scene, SceneFX } from "../../types/script";
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
  const [uploading, setUploading] = useState(false);
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

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      const result = await uploadSceneMedia(scriptId, scene.id, file);
      if (result.media_type === "video") {
        onUpdate({ upload_url: result.url, video_url: result.url, media_source: "user_upload" });
      } else {
        onUpdate({ upload_url: result.url, image_url: result.url, media_source: "user_upload" });
      }
    } catch {
      // uploadSceneMedia throws on error — toast handled by interceptor
    } finally {
      setUploading(false);
    }
  };

  const MEDIA_SOURCE_OPTIONS: { value: string; label: string }[] = [
    { value: "ai", label: "AI Generated" },
    { value: "stock_photo", label: "Stock Photo" },
    { value: "gameplay_video", label: "Gameplay" },
    { value: "user_upload", label: "Upload" },
  ];

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
      <div className="shrink-0 max-h-44 flex gap-4 px-4 py-2">

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

        {/* Col 2: Visual Prompt + Upload zone */}
        <div className="flex-[2] flex flex-col min-w-0 min-h-0">
          {(scene.media_source === "user_upload") ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-2 min-h-0">
              {(scene.upload_url || scene.image_url) ? (
                <>
                  <img
                    src={assetUrl(scene.upload_url || scene.image_url || "")}
                    alt="Uploaded"
                    className="flex-1 min-h-0 w-full object-cover rounded-lg border border-neutral-700"
                  />
                  <label className="text-[10px] text-neutral-500 hover:text-neutral-300 cursor-pointer transition-colors shrink-0">
                    Replace
                    <input type="file" className="hidden" accept="image/*,video/*" onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) handleUpload(f);
                    }} />
                  </label>
                </>
              ) : (
                <label className={`w-full flex-1 flex flex-col items-center justify-center gap-1 border-2 border-dashed border-neutral-700 rounded-lg cursor-pointer hover:border-violet-500/50 transition-colors ${uploading ? "opacity-50" : ""}`}>
                  {uploading ? (
                    <span className="w-5 h-5 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <>
                      <svg className="w-6 h-6 text-neutral-500" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                      </svg>
                      <span className="text-xs text-neutral-500">Drop or click to upload</span>
                    </>
                  )}
                  <input type="file" className="hidden" accept="image/*,video/*" onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleUpload(f);
                  }} />
                </label>
              )}
            </div>
          ) : (
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
        </div>

        {/* Col 3: Media source selector + Generate Image + Generate Audio + FX */}
        <div className="flex-[1.2] flex flex-col gap-2 min-w-0 min-h-0">
          {/* Media source selector */}
          <div className="shrink-0 flex flex-wrap gap-1">
            {MEDIA_SOURCE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => onUpdate({ media_source: opt.value as Scene["media_source"] })}
                className={`text-[10px] px-2 py-0.5 rounded-full transition-colors ${
                  (scene.media_source || "ai") === opt.value
                    ? "bg-violet-500/20 text-violet-300 font-medium"
                    : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Generate Image button */}
          {onGenerateImage && (
            <button
              onClick={() => scene.image_url ? setConfirmOverwrite("image") : onGenerateImage()}
              disabled={isGenerating}
              className="shrink-0 w-full text-sm px-3 py-1.5 text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20 rounded-lg transition-colors font-medium disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isGenerating ? (
                <><span className="w-3.5 h-3.5 border-2 border-white/50 border-t-transparent rounded-full animate-spin" /> Generating...</>
              ) : scene.image_url ? "Regenerate Image" : "Generate Image"}
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
          <div className="shrink-0 h-72 flex items-center justify-center px-4 py-2">
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
              </div>
            ) : (
              <span className="text-xs text-neutral-600">
                0/{expectedImageCount} image{expectedImageCount > 1 ? "s" : ""} expected
              </span>
            )}
          </div>
        );
      })()}

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
