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
  collapsed?: boolean;
  onToggle?: () => void;
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
  collapsed = false,
  onToggle,
}: Props) {
  const [narration, setNarration] = useState(scene.narration);
  const [visualPrompt, setVisualPrompt] = useState(scene.visual_prompt);
  const [textOverlay, setTextOverlay] = useState(scene.text_overlay);
  const [duration, setDuration] = useState(
    String(scene.duration_estimate_seconds),
  );
  const [isTitleCard, setIsTitleCard] = useState(scene.is_title_card);
  const [searchQuery, setSearchQuery] = useState(scene.search_query || "");
  const [promptExpanded, setPromptExpanded] = useState(false);
  const [framePrompts, setFramePrompts] = useState<string[]>(scene.frame_prompts || []);
  const [frameCount, setFrameCount] = useState(scene.frame_count || 0);

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
      setSearchQuery(scene.search_query || "");
      setPromptExpanded(false);
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

  if (collapsed) {
    return (
      <aside className="w-10 shrink-0 border-l border-neutral-800/60 flex flex-col items-center pt-3 transition-all duration-300">
        {onToggle && (
          <button
            onClick={onToggle}
            className="text-neutral-500 hover:text-neutral-300 text-sm transition-colors"
            title="Expand properties"
          >
            &#x2039;
          </button>
        )}
      </aside>
    );
  }

  return (
    <aside className="w-[320px] shrink-0 border-l border-neutral-800/60 overflow-y-auto p-4 space-y-4 transition-all duration-300">
      {/* Panel header with collapse control */}
      {onToggle && (
        <div className="flex items-center -mt-1 -mx-1 mb-1">
          <button
            onClick={onToggle}
            className="text-neutral-500 hover:text-neutral-300 text-sm px-1 transition-colors"
            title="Collapse panel"
          >
            &#x203A;
          </button>
        </div>
      )}

      {/* Preview Mode: Video Player at Top */}
      {previewMode && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-[11px] text-neutral-600 uppercase tracking-widest font-medium">
              Preview</div>
            <div className="flex items-center gap-1">
              <button
                onClick={onPrevScene}
                className="text-xs px-2 py-1 bg-neutral-800 hover:bg-neutral-700 rounded transition-colors text-neutral-400"
                title="Previous scene"
              >
                &#9664;
              </button>
              <button
                onClick={onNextScene}
                className="text-xs px-2 py-1 bg-neutral-800 hover:bg-neutral-700 rounded transition-colors text-neutral-400"
                title="Next scene"
              >
                &#9654;
              </button>
            </div>
          </div>
          {previewVideoUrl ? (
            <video
              key={previewVideoUrl}
              src={assetUrl(previewVideoUrl)}
              controls
              autoPlay
              className="w-full rounded-lg border border-neutral-700"
            />
          ) : scene.image_url ? (
            <div className="relative">
              <img
                src={assetUrl(scene.image_url)}
                alt="Scene visual"
                className="w-full rounded-lg border border-neutral-700 opacity-60"
              />
              {isPreviewingScene ? (
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="w-6 h-6 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : null}
            </div>
          ) : null}
          {scene.image_url && scene.audio_url && onPreviewScene && (
            <button
              onClick={onPreviewScene}
              disabled={isPreviewingScene}
              className="w-full text-sm px-3 py-2.5 bg-violet-600 hover:bg-violet-500 text-white rounded-lg transition-colors font-medium disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isPreviewingScene ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
                  Rendering...
                </>
              ) : previewVideoUrl ? (
                "Re-render Preview"
              ) : (
                "Render Preview"
              )}
            </button>
          )}
        </div>
      )}

      <div className="text-[11px] text-neutral-600 uppercase tracking-widest font-medium">
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
          className="w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg p-2.5 border border-neutral-700/50 resize-none focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
          rows={5}
        />
      </label>

      {/* Media Type */}
      <label className="block space-y-1">
        <span className="text-xs font-medium text-neutral-400">Media Type</span>
        <select
          value={scene.media_type || "ai_generated"}
          onChange={(e) => onUpdate({ media_type: e.target.value as Scene["media_type"] })}
          className={`w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg px-2.5 py-2 border focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30 ${
            scene.media_type && scene.media_type !== "ai_generated"
              ? "border-red-500/50"
              : "border-neutral-700/50"
          }`}
        >
          <option value="ai_generated">AI Generated</option>
          <option value="gameplay_clip">Gameplay Clip</option>
          <option value="hardware_image">Hardware Image</option>
        </select>
      </label>

      {/* Search Query (for real media types) */}
      {scene.media_type && scene.media_type !== "ai_generated" && (
        <label className="block space-y-1">
          <span className="text-xs font-medium text-neutral-400">
            YouTube Search Query
          </span>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onBlur={() => commitField("search_query", searchQuery)}
            placeholder="e.g. Halo Infinite gameplay 4K"
            className="w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg px-2.5 py-2 border border-red-700/50 focus:outline-none focus:border-red-500/50 focus:ring-1 focus:ring-red-500/30"
          />
        </label>
      )}

      {/* Fetch Media button (for real media types) */}
      {scene.media_type && scene.media_type !== "ai_generated" && scene.search_query && onFetchMedia && (
        <button
          onClick={onFetchMedia}
          disabled={isFetchingMedia}
          className="w-full text-sm px-3 py-2 text-red-400 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded-lg transition-colors font-medium disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {isFetchingMedia ? (
            <>
              <span className="w-4 h-4 border-2 border-red-400/50 border-t-transparent rounded-full animate-spin" />
              Fetching...
            </>
          ) : scene.video_clip_url || (scene.media_type === "hardware_image" && scene.image_url) ? (
            "Re-fetch Media"
          ) : (
            "Fetch Media"
          )}
        </button>
      )}

      {/* Visual Prompt (hidden for real media types) */}
      {(!scene.media_type || scene.media_type === "ai_generated") && (
        <label className="block space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-neutral-400">
              Visual Prompt
            </span>
            <button
              onClick={() => setPromptExpanded(!promptExpanded)}
              className="text-[10px] text-neutral-600 hover:text-neutral-400 transition-colors"
            >
              {promptExpanded ? "Collapse" : "Expand"}
            </button>
          </div>
          <textarea
            value={visualPrompt}
            onChange={(e) => setVisualPrompt(e.target.value)}
            onBlur={() => commitField("visual_prompt", visualPrompt)}
            className="w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg p-2.5 border border-neutral-700/50 resize-none focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
            rows={promptExpanded ? 10 : 4}
          />
        </label>
      )}

      {/* Multi-Frame / Animation Controls */}
      <div className="border border-neutral-800 rounded-lg p-3 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-neutral-400">Frame Budget</span>
          <span className="text-xs text-neutral-500 font-mono">{frameCount || 1}</span>
        </div>
        <input
          type="range"
          min={1}
          max={8}
          value={frameCount || 1}
          onChange={(e) => {
            const n = parseInt(e.target.value, 10);
            setFrameCount(n);
            // Resize frame_prompts array
            const newPrompts = [...framePrompts];
            while (newPrompts.length < n) newPrompts.push("");
            while (newPrompts.length > n) newPrompts.pop();
            setFramePrompts(newPrompts);
            onUpdate({ frame_count: n, frame_prompts: newPrompts });
          }}
          className="w-full accent-violet-500"
        />
        <p className="text-[10px] text-neutral-600">
          1 = static image, 2-8 = crossfade animation between frames
        </p>

        {/* Per-frame prompt textareas */}
        {frameCount > 1 && (
          <div className="space-y-2 mt-2">
            {framePrompts.slice(0, frameCount).map((fp, i) => (
              <label key={i} className="block space-y-1">
                <span className="text-[10px] font-medium text-neutral-500">
                  Frame {i + 1}
                </span>
                <textarea
                  value={fp}
                  onChange={(e) => {
                    const updated = [...framePrompts];
                    updated[i] = e.target.value;
                    setFramePrompts(updated);
                  }}
                  onBlur={() => {
                    onUpdate({ frame_prompts: framePrompts });
                  }}
                  className="w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg p-2 border border-violet-700/30 resize-none focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
                  rows={2}
                  placeholder={`Describe frame ${i + 1} visual...`}
                />
              </label>
            ))}
          </div>
        )}

        {/* Frame image preview strip */}
        {scene.frame_urls && scene.frame_urls.length > 1 && (
          <div className="flex gap-1 overflow-x-auto mt-2 pb-1">
            {scene.frame_urls.map((url, i) => (
              <img
                key={i}
                src={assetUrl(url)}
                alt={`Frame ${i + 1}`}
                className="h-14 w-auto rounded border border-neutral-700 shrink-0"
              />
            ))}
          </div>
        )}

      </div>

      {/* Video Clip Preview (for gameplay clips) */}
      {scene.video_clip_url && (
        <div className="space-y-2">
          <div className="text-xs font-medium text-neutral-400">Gameplay Clip</div>
          <video
            key={scene.video_clip_url}
            src={assetUrl(scene.video_clip_url)}
            controls
            className="w-full rounded-lg border border-red-700/50"
          />
        </div>
      )}

      {/* Image Preview / Generate (for ai_generated and hardware_image) */}
      {scene.image_url ? (
        <div className="space-y-2">
          {scene.frame_urls && scene.frame_urls.length > 1 ? (
            <div className="grid grid-cols-3 gap-1">
              {scene.frame_urls.map((url, i) => (
                <img
                  key={i}
                  src={assetUrl(url)}
                  alt={`Frame ${i + 1}`}
                  className="w-full object-cover rounded border border-neutral-700 h-[64px]"
                />
              ))}
            </div>
          ) : (
            <img
              src={assetUrl(scene.image_url)}
              alt="Scene visual"
              className={`w-full object-cover rounded-lg border border-neutral-700 h-[200px]`}
            />
          )}
          {onGenerateImage && (
            <button
              onClick={() => setConfirmOverwrite("image")}
              disabled={isGenerating}
              className="w-full text-sm px-3 py-2 text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isGenerating ? (
                <>
                  <span className="w-4 h-4 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
                  Generating...
                </>
              ) : frameCount > 1 ? (
                `Regenerate ${frameCount} Frames`
              ) : (
                "Regenerate Image"
              )}
            </button>
          )}
        </div>
      ) : onGenerateImage ? (
        <button
          onClick={onGenerateImage}
          disabled={isGenerating}
          className="w-full text-sm px-3 py-2 text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20 rounded-lg transition-colors font-medium disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {isGenerating ? (
            <>
              <span className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
              Generating...
            </>
          ) : frameCount > 1 ? (
            `Generate ${frameCount} Frames`
          ) : (
            "Generate Image"
          )}
        </button>
      ) : null}

      {/* Audio Preview / Generate */}
      {scene.audio_url ? (
        <div className="space-y-2">
          <div className="text-xs font-medium text-neutral-400">Audio</div>
          <AudioPlayer
            src={assetUrl(scene.audio_url)}
            duration={scene.audio_duration_seconds}
          />
          {onGenerateAudio && (
            <button
              onClick={() => setConfirmOverwrite("audio")}
              disabled={isGeneratingAudio}
              className="w-full text-sm px-3 py-2 text-sky-400 bg-sky-500/10 hover:bg-sky-500/20 border border-sky-500/20 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isGeneratingAudio ? (
                <>
                  <span className="w-4 h-4 border-2 border-sky-500 border-t-transparent rounded-full animate-spin" />
                  Generating...
                </>
              ) : (
                "Regenerate Audio"
              )}
            </button>
          )}
        </div>
      ) : onGenerateAudio ? (
        <button
          onClick={onGenerateAudio}
          disabled={isGeneratingAudio}
          className="w-full text-sm px-3 py-2 text-sky-400 bg-sky-500/10 hover:bg-sky-500/20 border border-sky-500/20 rounded-lg transition-colors font-medium disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {isGeneratingAudio ? (
            <>
              <span className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
              Generating...
            </>
          ) : (
            "Generate Audio"
          )}
        </button>
      ) : null}

      {/* Scene Video Preview */}
      {scene.image_url && scene.audio_url && (
        <div className="space-y-2">
          <div className="text-xs font-medium text-neutral-400">Video Preview</div>
          {previewVideoUrl && (
            <video
              key={previewVideoUrl}
              src={assetUrl(previewVideoUrl)}
              controls
              className="w-full rounded-lg border border-neutral-700"
            />
          )}
          {onPreviewScene && (
            <button
              onClick={onPreviewScene}
              disabled={isPreviewingScene}
              className="w-full text-sm px-3 py-2.5 bg-violet-600 hover:bg-violet-500 text-white rounded-lg transition-colors font-medium disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isPreviewingScene ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
                  Rendering...
                </>
              ) : previewVideoUrl ? (
                "Re-render Preview"
              ) : (
                "Preview Scene"
              )}
            </button>
          )}
        </div>
      )}

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
          className="w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg px-2.5 py-2 border border-neutral-700/50 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
        />
      </label>

      {/* FX Summary (read-only) — shown when FX is assigned */}
      {scene.fx && (
        <div className="border-t border-neutral-800 pt-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-[11px] text-neutral-600 uppercase tracking-widest font-medium">
              Visual Effects
            </div>
            <button
              onClick={() => setConfirmOverwrite("fx")}
              disabled={regeneratingFX}
              className="text-[10px] text-amber-400 hover:text-amber-300 transition-colors disabled:opacity-40 flex items-center gap-1"
            >
              {regeneratingFX ? (
                <>
                  <span className="w-2.5 h-2.5 border border-amber-400/50 border-t-transparent rounded-full animate-spin" />
                  Regenerating...
                </>
              ) : (
                "Regenerate"
              )}
            </button>
          </div>
          <div className="space-y-1.5">
            {scene.fx.kinetic_captions && scene.fx.kinetic_captions.words.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-[10px] bg-sky-500/20 text-sky-300 px-1.5 py-0.5 rounded-full">
                  kinetic captions
                </span>
                <span className="text-xs text-neutral-400">
                  {scene.fx.kinetic_captions.words.length} word{scene.fx.kinetic_captions.words.length !== 1 ? "s" : ""}
                </span>
              </div>
            )}
            {scene.fx.zoom_punch && (
              <div className="flex items-center gap-2">
                <span className="text-[10px] bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded-full">
                  zoom punch
                </span>
                <span className="text-xs text-neutral-400">
                  frame {scene.fx.zoom_punch.trigger_frame} @ {scene.fx.zoom_punch.scale}x
                </span>
              </div>
            )}
            {!scene.fx.kinetic_captions && !scene.fx.zoom_punch && (
              <p className="text-[10px] text-neutral-600 italic">No effects assigned</p>
            )}
          </div>
        </div>
      )}

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
          className="w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg px-2.5 py-2 border border-neutral-700/50 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
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

    </aside>
  );
}
