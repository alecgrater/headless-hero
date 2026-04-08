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
  onPreviewScene?: () => void;
  isPreviewingScene?: boolean;
  previewVideoUrl?: string | null;
  previewMode?: boolean;
  onPrevScene?: () => void;
  onNextScene?: () => void;
  onFetchMedia?: () => void;
  isFetchingMedia?: boolean;
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
  onPreviewScene,
  isPreviewingScene = false,
  previewVideoUrl,
  previewMode = false,
  onPrevScene,
  onNextScene,
  onFetchMedia,
  isFetchingMedia = false,
}: Props) {
  const [narration, setNarration] = useState(scene.narration);
  const [visualPrompt, setVisualPrompt] = useState(scene.visual_prompt);
  const [textOverlay, setTextOverlay] = useState(scene.text_overlay);
  const [duration, setDuration] = useState(
    String(scene.duration_estimate_seconds),
  );
  const [isTitleCard, setIsTitleCard] = useState(scene.is_title_card);
  const [searchQuery, setSearchQuery] = useState(scene.search_query || "");
  const [framePrompts, setFramePrompts] = useState<string[]>(scene.frame_prompts || []);
  const [frameCount, setFrameCount] = useState(scene.frame_count || 0);

  const sceneIdRef = useRef(scene.id);

  useEffect(() => {
    if (sceneIdRef.current !== scene.id) {
      sceneIdRef.current = scene.id;
      setNarration(scene.narration);
      setVisualPrompt(scene.visual_prompt);
      setTextOverlay(scene.text_overlay);
      setDuration(String(scene.duration_estimate_seconds));
      setIsTitleCard(scene.is_title_card);
      setSearchQuery(scene.search_query || "");
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

      {/* Content — flex row, fills all remaining space, NO scroll */}
      <div className="flex-1 min-h-0 flex gap-4 px-4 py-2">
        {/* Left column: text fields that stretch to fill */}
        <div className="flex-1 flex flex-col gap-1.5 min-w-0">
          {/* Narration — grows to fill */}
          <div className="flex flex-col flex-1 min-h-0">
            <span className="text-xs font-medium text-neutral-400 mb-0.5 shrink-0">Narration</span>
            <textarea
              value={narration}
              onChange={(e) => setNarration(e.target.value)}
              onBlur={() => commitField("narration", narration)}
              className="flex-1 min-h-0 w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg p-2 border border-neutral-700/50 resize-none focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
            />
          </div>

          {/* Visual Prompt — grows to fill (hidden for real media types) */}
          {(!scene.media_type || scene.media_type === "ai_generated") && (
            <div className="flex flex-col flex-1 min-h-0">
              <span className="text-xs font-medium text-neutral-400 mb-0.5 shrink-0">
                Visual Prompt
              </span>
              <textarea
                value={visualPrompt}
                onChange={(e) => setVisualPrompt(e.target.value)}
                onBlur={() => commitField("visual_prompt", visualPrompt)}
                className="flex-1 min-h-0 w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg p-2 border border-neutral-700/50 resize-none focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
              />
            </div>
          )}

          {/* Search Query (for real media types) */}
          {scene.media_type && scene.media_type !== "ai_generated" && (
            <div className="shrink-0">
              <span className="text-xs font-medium text-neutral-400">YouTube Search Query</span>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onBlur={() => commitField("search_query", searchQuery)}
                placeholder="e.g. Halo Infinite gameplay 4K"
                className="w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg px-2 py-1.5 border border-red-700/50 focus:outline-none focus:border-red-500/50 focus:ring-1 focus:ring-red-500/30 mt-0.5"
              />
            </div>
          )}

          {/* Fetch Media button (for real media types) */}
          {scene.media_type && scene.media_type !== "ai_generated" && scene.search_query && onFetchMedia && (
            <button
              onClick={onFetchMedia}
              disabled={isFetchingMedia}
              className="shrink-0 w-full text-sm px-3 py-1.5 text-red-400 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded-lg transition-colors font-medium disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isFetchingMedia ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-red-400/50 border-t-transparent rounded-full animate-spin" />
                  Fetching...
                </>
              ) : scene.video_clip_url || (scene.media_type === "hardware_image" && scene.image_url) ? (
                "Re-fetch Media"
              ) : (
                "Fetch Media"
              )}
            </button>
          )}

          {/* Text Overlay + compact settings — fixed at bottom */}
          <div className="shrink-0 space-y-1.5">
            <div>
              <span className="text-xs font-medium text-neutral-400">Text Overlay</span>
              <input
                type="text"
                value={textOverlay}
                onChange={(e) => setTextOverlay(e.target.value)}
                onBlur={() => commitField("text_overlay", textOverlay)}
                className="w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg px-2 py-1.5 border border-neutral-700/50 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30 mt-0.5"
              />
            </div>

            {/* Compact settings row */}
            <div className="flex items-end gap-3 pt-1 border-t border-neutral-800/40">
              <label className="space-y-0.5">
                <span className="text-[10px] font-medium text-neutral-500">Media</span>
                <select
                  value={scene.media_type || "ai_generated"}
                  onChange={(e) => onUpdate({ media_type: e.target.value as Scene["media_type"] })}
                  className={`block text-xs text-neutral-200 bg-neutral-800/60 rounded px-1.5 py-1 border focus:outline-none focus:border-violet-500/50 ${
                    scene.media_type && scene.media_type !== "ai_generated"
                      ? "border-red-500/50"
                      : "border-neutral-700/50"
                  }`}
                >
                  <option value="ai_generated">AI Generated</option>
                  <option value="gameplay_clip">Gameplay</option>
                  <option value="hardware_image">Hardware</option>
                </select>
              </label>

              <label className="space-y-0.5">
                <span className="text-[10px] font-medium text-neutral-500">Duration</span>
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
                  className="block w-16 text-xs text-neutral-200 bg-neutral-800/60 rounded px-1.5 py-1 border border-neutral-700/50 focus:outline-none focus:border-violet-500/50"
                />
              </label>

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

        {/* Right column: media previews + actions */}
        <div className="flex-1 flex flex-col gap-1.5 min-w-0">
          {/* Image preview — grows to fill available space */}
          {scene.image_url ? (
            <div className="flex flex-col flex-1 min-h-0 gap-1">
              <div className="flex items-center justify-between shrink-0">
                <span className="text-xs font-medium text-neutral-400">Image</span>
                {onGenerateImage && (
                  <button
                    onClick={() => setConfirmOverwrite("image")}
                    disabled={isGenerating}
                    className="text-[10px] text-emerald-400 hover:text-emerald-300 transition-colors disabled:opacity-40 flex items-center gap-1"
                  >
                    {isGenerating ? (
                      <>
                        <span className="w-2.5 h-2.5 border border-emerald-400/50 border-t-transparent rounded-full animate-spin" />
                        Generating...
                      </>
                    ) : frameCount > 1 ? (
                      `Regen ${frameCount} Frames`
                    ) : (
                      "Regen"
                    )}
                  </button>
                )}
              </div>
              {scene.frame_urls && scene.frame_urls.length > 1 ? (
                <div className="flex-1 min-h-0 grid grid-cols-3 gap-1">
                  {scene.frame_urls.map((url, i) => (
                    <img
                      key={i}
                      src={assetUrl(url)}
                      alt={`Frame ${i + 1}`}
                      className="w-full h-full object-cover rounded border border-neutral-700"
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
            </div>
          ) : onGenerateImage ? (
            <button
              onClick={onGenerateImage}
              disabled={isGenerating}
              className="shrink-0 w-full text-sm px-3 py-1.5 text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20 rounded-lg transition-colors font-medium disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isGenerating ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
                  Generating...
                </>
              ) : frameCount > 1 ? (
                `Generate ${frameCount} Frames`
              ) : (
                "Generate Image"
              )}
            </button>
          ) : null}

          {/* Video Clip Preview (for gameplay clips) */}
          {scene.video_clip_url && (
            <div className="shrink-0 space-y-1">
              <span className="text-xs font-medium text-neutral-400">Gameplay Clip</span>
              <video
                key={scene.video_clip_url}
                src={assetUrl(scene.video_clip_url)}
                controls
                className="w-full rounded-lg border border-red-700/50 max-h-24"
              />
            </div>
          )}

          {/* Audio — compact */}
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
                      <>
                        <span className="w-2.5 h-2.5 border border-sky-400/50 border-t-transparent rounded-full animate-spin" />
                        Generating...
                      </>
                    ) : (
                      "Regen"
                    )}
                  </button>
                )}
              </div>
              <AudioPlayer
                src={assetUrl(scene.audio_url)}
                duration={scene.audio_duration_seconds}
              />
            </div>
          ) : onGenerateAudio ? (
            <button
              onClick={onGenerateAudio}
              disabled={isGeneratingAudio}
              className="shrink-0 w-full text-sm px-3 py-1.5 text-sky-400 bg-sky-500/10 hover:bg-sky-500/20 border border-sky-500/20 rounded-lg transition-colors font-medium disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isGeneratingAudio ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
                  Generating...
                </>
              ) : (
                "Generate Audio"
              )}
            </button>
          ) : null}

          {/* Preview Mode: Video Player */}
          {previewMode && (
            <div className="shrink-0 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-neutral-600 uppercase tracking-widest font-medium">Preview</span>
                <div className="flex items-center gap-1">
                  <button onClick={onPrevScene} className="text-xs px-1.5 py-0.5 bg-neutral-800 hover:bg-neutral-700 rounded transition-colors text-neutral-400" title="Previous scene">&#9664;</button>
                  <button onClick={onNextScene} className="text-xs px-1.5 py-0.5 bg-neutral-800 hover:bg-neutral-700 rounded transition-colors text-neutral-400" title="Next scene">&#9654;</button>
                </div>
              </div>
              {previewVideoUrl ? (
                <video key={previewVideoUrl} src={assetUrl(previewVideoUrl)} controls autoPlay className="w-full rounded-lg border border-neutral-700 max-h-28" />
              ) : scene.image_url ? (
                <div className="relative">
                  <img src={assetUrl(scene.image_url)} alt="Scene visual" className="w-full rounded-lg border border-neutral-700 opacity-60 max-h-28 object-cover" />
                  {isPreviewingScene && (
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="w-5 h-5 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
                    </div>
                  )}
                </div>
              ) : null}
              {scene.image_url && scene.audio_url && onPreviewScene && (
                <button
                  onClick={onPreviewScene}
                  disabled={isPreviewingScene}
                  className="w-full text-sm px-3 py-1.5 bg-violet-600 hover:bg-violet-500 text-white rounded-lg transition-colors font-medium disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {isPreviewingScene ? (
                    <><span className="w-3.5 h-3.5 border-2 border-white/50 border-t-transparent rounded-full animate-spin" /> Rendering...</>
                  ) : previewVideoUrl ? "Re-render" : "Render Preview"}
                </button>
              )}
            </div>
          )}

          {/* Video Preview (non-preview-mode) */}
          {!previewMode && scene.image_url && scene.audio_url && onPreviewScene && (
            <div className="shrink-0">
              {previewVideoUrl && (
                <video key={previewVideoUrl} src={assetUrl(previewVideoUrl)} controls className="w-full rounded-lg border border-neutral-700 max-h-24 mb-1" />
              )}
              <button
                onClick={onPreviewScene}
                disabled={isPreviewingScene}
                className="w-full text-sm px-3 py-1.5 bg-violet-600 hover:bg-violet-500 text-white rounded-lg transition-colors font-medium disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {isPreviewingScene ? (
                  <><span className="w-3.5 h-3.5 border-2 border-white/50 border-t-transparent rounded-full animate-spin" /> Rendering...</>
                ) : previewVideoUrl ? "Re-render Preview" : "Preview Scene"}
              </button>
            </div>
          )}

          {/* FX Summary — compact */}
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
                {scene.fx.kinetic_captions && scene.fx.kinetic_captions.words.length > 0 && (
                  <div className="flex items-center gap-1">
                    <span className="text-[10px] bg-sky-500/20 text-sky-300 px-1.5 py-0.5 rounded-full">captions</span>
                    <span className="text-[10px] text-neutral-400">{scene.fx.kinetic_captions.words.length}w</span>
                  </div>
                )}
                {scene.fx.zoom_punch && (
                  <div className="flex items-center gap-1">
                    <span className="text-[10px] bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded-full">zoom</span>
                    <span className="text-[10px] text-neutral-400">f{scene.fx.zoom_punch.trigger_frame} @ {scene.fx.zoom_punch.scale}x</span>
                  </div>
                )}
                {!scene.fx.kinetic_captions && !scene.fx.zoom_punch && (
                  <p className="text-[10px] text-neutral-600 italic">No effects</p>
                )}
              </div>
            </div>
          )}

          {/* Per-frame prompts (only when frames > 1) */}
          {frameCount > 1 && (
            <div className="shrink-0 space-y-1 border-t border-neutral-800/40 pt-1">
              {framePrompts.slice(0, frameCount).map((fp, i) => (
                <label key={i} className="block">
                  <span className="text-[10px] font-medium text-neutral-500">Frame {i + 1}</span>
                  <textarea
                    value={fp}
                    onChange={(e) => {
                      const updated = [...framePrompts];
                      updated[i] = e.target.value;
                      setFramePrompts(updated);
                    }}
                    onBlur={() => onUpdate({ frame_prompts: framePrompts })}
                    className="w-full text-xs text-neutral-200 bg-neutral-800/60 rounded p-1.5 border border-violet-700/30 resize-none focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
                    rows={1}
                    placeholder={`Frame ${i + 1} visual...`}
                  />
                </label>
              ))}
            </div>
          )}
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
