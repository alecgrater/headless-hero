import { useCallback, useEffect, useRef, useState } from "react";
import { assetUrl } from "../../api";
import type { KenBurnsConfig, Scene, TextOverlayConfig } from "../../types/script";

const KEN_BURNS_EFFECTS = [
  { value: "none", label: "None" },
  { value: "zoom_in", label: "Zoom In" },
  { value: "zoom_out", label: "Zoom Out" },
  { value: "pan_left", label: "Pan Left" },
  { value: "pan_right", label: "Pan Right" },
  { value: "pan_up", label: "Pan Up" },
  { value: "pan_down", label: "Pan Down" },
] as const;

const INTENSITIES = ["subtle", "moderate", "dramatic"] as const;

const OVERLAY_POSITIONS = [
  { value: "top", label: "Top" },
  { value: "center", label: "Center" },
  { value: "bottom", label: "Bottom" },
  { value: "lower_third", label: "Lower Third" },
] as const;

const OVERLAY_STYLES = [
  { value: "default", label: "Default" },
  { value: "bold", label: "Bold" },
  { value: "subtitle", label: "Subtitle" },
  { value: "title_card", label: "Title Card" },
] as const;

const OVERLAY_ANIMATIONS = [
  { value: "none", label: "None" },
  { value: "fade_in", label: "Fade In" },
  { value: "slide_up", label: "Slide Up" },
  { value: "typewriter", label: "Typewriter" },
] as const;

interface Props {
  scene: Scene;
  segmentIdx: number;
  segmentName: string;
  isLastInSegment: boolean;
  onUpdate: (updates: Partial<Scene>) => void;
  onSplit: () => void;
  onMerge: () => void;
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
}

export default function PropertiesPanel({
  scene,
  segmentIdx: _segmentIdx,
  segmentName,
  isLastInSegment,
  onUpdate,
  onSplit,
  onMerge,
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
}: Props) {
  const [narration, setNarration] = useState(scene.narration);
  const [visualPrompt, setVisualPrompt] = useState(scene.visual_prompt);
  const [visualPromptB, setVisualPromptB] = useState(scene.visual_prompt_b || "");
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
      setVisualPromptB(scene.visual_prompt_b || "");
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

  const updateKenBurns = useCallback(
    (patch: Partial<KenBurnsConfig>) => {
      const current: KenBurnsConfig = scene.ken_burns ?? { effect: "none", intensity: "moderate" };
      onUpdate({ ken_burns: { ...current, ...patch } });
    },
    [onUpdate, scene.ken_burns],
  );

  const updateTextOverlayConfig = useCallback(
    (patch: Partial<TextOverlayConfig>) => {
      const current: TextOverlayConfig = scene.text_overlay_config ?? {
        position: "lower_third",
        style: "default",
        animation: "fade_in",
        show_at: 0,
        duration: 0,
      };
      onUpdate({ text_overlay_config: { ...current, ...patch } });
    },
    [onUpdate, scene.text_overlay_config],
  );

  const kenBurns = scene.ken_burns ?? { effect: "none", intensity: "moderate" };
  const overlayConfig = scene.text_overlay_config ?? {
    position: "lower_third",
    style: "default",
    animation: "fade_in",
    show_at: 0,
    duration: 0,
  };

  return (
    <aside className="w-[320px] shrink-0 border-l border-neutral-800/60 overflow-y-auto p-4 space-y-4">
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
              className="w-full text-sm px-3 py-2 text-violet-400 bg-violet-500/10 hover:bg-violet-500/20 border border-violet-500/20 rounded-lg transition-colors font-medium disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isPreviewingScene ? (
                <>
                  <span className="w-4 h-4 border-2 border-violet-400/50 border-t-transparent rounded-full animate-spin" />
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

      {/* Visual Prompt */}
      <label className="block space-y-1">
        <span className="text-xs font-medium text-neutral-400">
          Visual Prompt{scene.is_animated ? " (A)" : ""}
        </span>
        <textarea
          value={visualPrompt}
          onChange={(e) => setVisualPrompt(e.target.value)}
          onBlur={() => commitField("visual_prompt", visualPrompt)}
          className="w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg p-2.5 border border-neutral-700/50 resize-none focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
          rows={3}
        />
      </label>

      {/* Animated A/B Flip Toggle */}
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={scene.is_animated || false}
          onChange={(e) => {
            onUpdate({ is_animated: e.target.checked });
          }}
          className="rounded border-neutral-600 bg-neutral-800 text-amber-500 focus:ring-amber-500"
        />
        <span className="text-sm text-neutral-300">Animated (A/B flip)</span>
      </label>

      {/* Visual Prompt B (only when animated) */}
      {scene.is_animated && (
        <label className="block space-y-1">
          <span className="text-xs font-medium text-neutral-400">
            Visual Prompt (B)
          </span>
          <textarea
            value={visualPromptB}
            onChange={(e) => setVisualPromptB(e.target.value)}
            onBlur={() => commitField("visual_prompt_b", visualPromptB)}
            className="w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg p-2.5 border border-amber-700/50 resize-none focus:outline-none focus:border-amber-500/50 focus:ring-1 focus:ring-amber-500/30"
            rows={3}
            placeholder="Describe the second visual state (B)..."
          />
        </label>
      )}

      {/* Image Preview / Generate */}
      {scene.image_url ? (
        <div className="space-y-2">
          {scene.is_animated && scene.image_url_b ? (
            <div className="grid grid-cols-2 gap-1">
              <div className="space-y-1">
                <span className="text-[10px] text-neutral-500 uppercase">A</span>
                <img
                  src={assetUrl(scene.image_url)}
                  alt="Scene visual A"
                  className="w-full h-[96px] object-cover rounded-lg border border-neutral-700"
                />
              </div>
              <div className="space-y-1">
                <span className="text-[10px] text-neutral-500 uppercase">B</span>
                <img
                  src={assetUrl(scene.image_url_b)}
                  alt="Scene visual B"
                  className="w-full h-[96px] object-cover rounded-lg border border-amber-700/50"
                />
              </div>
            </div>
          ) : (
            <img
              src={assetUrl(scene.image_url)}
              alt="Scene visual"
              className="w-full h-[200px] object-cover rounded-lg border border-neutral-700"
            />
          )}
          {onGenerateImage && (
            <button
              onClick={onGenerateImage}
              disabled={isGenerating}
              className="w-full text-sm px-3 py-2 text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isGenerating ? (
                <>
                  <span className="w-4 h-4 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
                  Generating...
                </>
              ) : scene.is_animated ? (
                "Regenerate Images (A+B)"
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
          ) : scene.is_animated ? (
            "Generate Images (A+B)"
          ) : (
            "Generate Image"
          )}
        </button>
      ) : null}

      {/* Audio Preview / Generate */}
      {scene.audio_url ? (
        <div className="space-y-2">
          <div className="text-xs font-medium text-neutral-400">Audio</div>
          <audio
            src={assetUrl(scene.audio_url)}
            controls
            className="w-full h-8"
          />
          {scene.audio_duration_seconds ? (
            <div className="text-xs text-neutral-500">
              Duration: {scene.audio_duration_seconds.toFixed(1)}s
            </div>
          ) : null}
          {onGenerateAudio && (
            <button
              onClick={onGenerateAudio}
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
              className="w-full text-sm px-3 py-2 text-violet-400 bg-violet-500/10 hover:bg-violet-500/20 border border-violet-500/20 rounded-lg transition-colors font-medium disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isPreviewingScene ? (
                <>
                  <span className="w-4 h-4 border-2 border-violet-400/50 border-t-transparent rounded-full animate-spin" />
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

      {/* Motion Effect (Ken Burns) */}
      <div className="border-t border-neutral-800 pt-3 space-y-2">
        <div className="text-[11px] text-neutral-600 uppercase tracking-widest font-medium">
          Motion Effect
        </div>
        <label className="block space-y-1">
          <span className="text-xs font-medium text-neutral-400">Effect</span>
          <select
            value={kenBurns.effect}
            onChange={(e) => updateKenBurns({ effect: e.target.value as KenBurnsConfig["effect"] })}
            className="w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg px-2.5 py-2 border border-neutral-700/50 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
          >
            {KEN_BURNS_EFFECTS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        {kenBurns.effect !== "none" && (
          <div className="space-y-1">
            <span className="text-xs font-medium text-neutral-400">Intensity</span>
            <div className="flex gap-1">
              {INTENSITIES.map((level) => (
                <button
                  key={level}
                  onClick={() => updateKenBurns({ intensity: level })}
                  className={`flex-1 text-xs py-1.5 rounded-lg border transition-colors ${
                    kenBurns.intensity === level
                      ? "bg-violet-600 border-violet-500 text-white"
                      : "bg-neutral-800 border-neutral-700 text-neutral-400 hover:border-neutral-600"
                  }`}
                >
                  {level.charAt(0).toUpperCase() + level.slice(1)}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Text Overlay Style (only when text_overlay is non-empty) */}
      {scene.text_overlay && (
        <div className="border-t border-neutral-800 pt-3 space-y-2">
          <div className="text-[11px] text-neutral-600 uppercase tracking-widest font-medium">
            Text Overlay Style
          </div>
          <label className="block space-y-1">
            <span className="text-xs font-medium text-neutral-400">Position</span>
            <select
              value={overlayConfig.position}
              onChange={(e) => updateTextOverlayConfig({ position: e.target.value as TextOverlayConfig["position"] })}
              className="w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg px-2.5 py-2 border border-neutral-700/50 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
            >
              {OVERLAY_POSITIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block space-y-1">
            <span className="text-xs font-medium text-neutral-400">Style</span>
            <select
              value={overlayConfig.style}
              onChange={(e) => updateTextOverlayConfig({ style: e.target.value as TextOverlayConfig["style"] })}
              className="w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg px-2.5 py-2 border border-neutral-700/50 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
            >
              {OVERLAY_STYLES.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block space-y-1">
            <span className="text-xs font-medium text-neutral-400">Animation</span>
            <select
              value={overlayConfig.animation}
              onChange={(e) => updateTextOverlayConfig({ animation: e.target.value as TextOverlayConfig["animation"] })}
              className="w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg px-2.5 py-2 border border-neutral-700/50 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
            >
              {OVERLAY_ANIMATIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <div className="grid grid-cols-2 gap-2">
            <label className="block space-y-1">
              <span className="text-xs font-medium text-neutral-400">Show At (s)</span>
              <input
                type="number"
                min={0}
                step={0.1}
                value={overlayConfig.show_at}
                onChange={(e) => {
                  const n = parseFloat(e.target.value);
                  if (!isNaN(n) && n >= 0) updateTextOverlayConfig({ show_at: n });
                }}
                className="w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg px-2.5 py-2 border border-neutral-700/50 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-medium text-neutral-400">Duration (s)</span>
              <input
                type="number"
                min={0}
                step={0.1}
                value={overlayConfig.duration}
                onChange={(e) => {
                  const n = parseFloat(e.target.value);
                  if (!isNaN(n) && n >= 0) updateTextOverlayConfig({ duration: n });
                }}
                className="w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg px-2.5 py-2 border border-neutral-700/50 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
              />
            </label>
          </div>
          <p className="text-[10px] text-neutral-600">Duration 0 = visible for entire scene</p>
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

      {/* Split / Merge */}
      <div className="border-t border-neutral-800 pt-4 space-y-2">
        <div className="text-xs text-neutral-500 uppercase tracking-wider font-semibold mb-2">
          Scene Actions
        </div>
        <button
          onClick={onSplit}
          className="w-full text-sm px-3 py-2 border border-neutral-700/50 text-neutral-400 bg-transparent hover:bg-neutral-800 rounded-lg transition-colors"
        >
          Split Scene
        </button>
        <button
          onClick={onMerge}
          disabled={isLastInSegment}
          className="w-full text-sm px-3 py-2 border border-neutral-700/50 text-neutral-400 bg-transparent hover:bg-neutral-800 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Merge with Next
        </button>
      </div>
    </aside>
  );
}
