import { useEffect, useRef, useState, type RefObject } from "react";
import type { VoiceInfo } from "../../types/audio";
import MiniProgressBar from "../MiniProgressBar";

interface Props {
  // Step completion states
  thumbnailsBusy: boolean;
  allThumbnailsDone: boolean;
  hasExistingThumbnails: boolean;
  missingThumbnailCount: number;
  allImagesGenerated: boolean;
  allAudioGenerated: boolean;
  allFXGenerated: boolean;
  // Batch generating states from useTimelineState
  batchGenerating: boolean;
  batchGeneratingAudio: boolean;
  // Generating states
  generatingFX: boolean;
  setGeneratingFX: (v: boolean) => void;
  // Handler functions
  confirmAndGenerateThumbnails: () => void;
  generateMissingThumbnails: () => void;
  cancelThumbnails: () => void;
  confirmAndGenerateImages: () => void;
  confirmAndGenerateAudio: () => void;
  confirmAndGenerateFX: () => void;
  generateMissingImages: () => void;
  generateMissingAudio: () => void;
  generateMissingFX: () => void;
  hasExistingImages: boolean;
  hasExistingAudio: boolean;
  hasExistingFX: boolean;
  missingImageCount: number;
  missingAudioCount: number;
  missingFXCount: number;
  cancelImageGeneration: () => void;
  cancelAudioGeneration: () => void;
  // Cancel refs
  fxCancelledRef: RefObject<boolean>;
  // Voice picker
  showVoicePicker: boolean;
  setShowVoicePicker: (show: boolean) => void;
  voices: VoiceInfo[];
  selectedVoiceId: string;
  setSelectedVoiceId: (id: string) => void;
  voicePickerRef: RefObject<HTMLDivElement | null>;
  onRecordVoiceover?: () => void;
  // Staleness
  fxPotentiallyStale: boolean;
  // Progress tracking
  fxEstimatedSeconds: number | null;
  fxProgressActive: boolean;
  thumbnailsEstimatedSeconds: number | null;
  thumbnailsProgressActive: boolean;
  yoloModeActive: boolean;
  thumbnailsProgress: number | null;
  audioProgress: number | null;
  imageProgress: number | null;
  fxProgress: number | null;
}

function compactProgressText(progress: number | null) {
  if (progress == null) return "Running";
  return `${Math.round(progress * 100)}%`;
}

export default function PipelineSteps({
  thumbnailsBusy,
  allThumbnailsDone,
  hasExistingThumbnails,
  missingThumbnailCount,
  allImagesGenerated,
  allAudioGenerated,
  allFXGenerated,
  batchGenerating,
  batchGeneratingAudio,
  generatingFX,
  setGeneratingFX,
  confirmAndGenerateThumbnails,
  generateMissingThumbnails,
  cancelThumbnails,
  confirmAndGenerateImages,
  confirmAndGenerateAudio,
  confirmAndGenerateFX,
  generateMissingImages,
  generateMissingAudio,
  generateMissingFX,
  hasExistingImages,
  hasExistingAudio,
  hasExistingFX,
  missingImageCount,
  missingAudioCount,
  missingFXCount,
  cancelImageGeneration,
  cancelAudioGeneration,
  fxCancelledRef,
  showVoicePicker,
  setShowVoicePicker,
  voices,
  selectedVoiceId,
  setSelectedVoiceId,
  voicePickerRef,
  onRecordVoiceover,
  fxPotentiallyStale,
  fxEstimatedSeconds,
  fxProgressActive,
  thumbnailsEstimatedSeconds,
  thumbnailsProgressActive,
  yoloModeActive,
  thumbnailsProgress,
  audioProgress,
  imageProgress,
  fxProgress,
}: Props) {
  const [showThumbnailsDropdown, setShowThumbnailsDropdown] = useState(false);
  const [showImagesDropdown, setShowImagesDropdown] = useState(false);
  const [showFXDropdown, setShowFXDropdown] = useState(false);
  const thumbnailsDropdownRef = useRef<HTMLDivElement>(null);
  const imagesDropdownRef = useRef<HTMLDivElement>(null);
  const fxDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (showThumbnailsDropdown && thumbnailsDropdownRef.current && !thumbnailsDropdownRef.current.contains(e.target as Node)) {
        setShowThumbnailsDropdown(false);
      }
      if (showImagesDropdown && imagesDropdownRef.current && !imagesDropdownRef.current.contains(e.target as Node)) {
        setShowImagesDropdown(false);
      }
      if (showFXDropdown && fxDropdownRef.current && !fxDropdownRef.current.contains(e.target as Node)) {
        setShowFXDropdown(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showThumbnailsDropdown, showImagesDropdown, showFXDropdown]);

  return (
    <div className="flex items-center gap-4 px-5 py-2.5">
      <div className="grid w-full items-center gap-2 min-w-0" style={{ gridTemplateColumns: "minmax(0,1fr) auto minmax(0,1fr) auto minmax(0,1fr) auto minmax(0,1fr)" }}>

        {/* Step 1 — Thumbnails */}
        <div className="flex flex-col">
          <div className="flex items-center gap-1.5">
            <span className={`w-[20px] h-[20px] rounded-full border text-[11px] font-bold flex items-center justify-center shrink-0 tabular-nums ${
              thumbnailsBusy
                ? "border-violet-400 bg-violet-500/10 text-violet-300 shadow-[0_0_6px_rgba(139,92,246,0.4)] animate-[pulseDot_2s_ease-in-out_infinite]"
                : allThumbnailsDone
                  ? "border-emerald-400 bg-emerald-500/10 text-emerald-300 shadow-[0_0_6px_rgba(52,211,153,0.3)]"
                  : "border-neutral-600 text-neutral-500"
            }`}>1</span>
            <div ref={thumbnailsDropdownRef} className="relative flex items-stretch flex-1">
              <button
                onClick={thumbnailsBusy ? (yoloModeActive ? undefined : cancelThumbnails) : confirmAndGenerateThumbnails}
                className={`text-xs pl-3 pr-1.5 py-2 border border-r-0 rounded-l-lg font-medium transition-all flex items-center justify-center gap-1.5 min-w-0 flex-1 whitespace-nowrap ${
                  thumbnailsBusy
                    ? `bg-neutral-800/80 border-violet-500/40 text-neutral-200 shadow-[0_0_8px_rgba(139,92,246,0.15)] ${yoloModeActive ? "cursor-default" : "hover:border-red-500/50 hover:text-red-400"}`
                    : allThumbnailsDone
                      ? "bg-emerald-500/8 border-emerald-500/25 text-emerald-400 hover:bg-emerald-500/15"
                      : "bg-neutral-800/80 border-neutral-700/60 text-neutral-300 hover:bg-neutral-700/80 hover:border-neutral-600"
                }`}
                title={thumbnailsBusy ? (yoloModeActive ? "Generating thumbnails" : "Cancel thumbnail generation") : "Generate title cards, short-form thumbnails, and long-form thumbnail"}
              >
                {thumbnailsBusy ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-violet-400/60 border-t-transparent rounded-full animate-spin" />
                    {yoloModeActive ? compactProgressText(thumbnailsProgress) : "Cancel"}
                  </>
                ) : allThumbnailsDone ? (
                  "Thumbnails ✓"
                ) : (
                  "Thumbnails"
                )}
              </button>
              {!thumbnailsBusy ? (
                <button
                  onClick={() => setShowThumbnailsDropdown(!showThumbnailsDropdown)}
                  className="text-xs px-1.5 bg-neutral-800/80 border border-l-0 border-neutral-700/60 text-neutral-400 hover:bg-neutral-700/80 hover:text-neutral-200 rounded-r-lg transition-all flex items-center"
                  title="Thumbnail generation options"
                >
                  <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none">
                    <path d="M3 5L6 8L9 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              ) : (
                <span className="text-xs px-1.5 bg-neutral-800/80 border border-l-0 border-violet-500/40 rounded-r-lg flex items-center">
                  <svg className="w-3 h-3 text-neutral-600" viewBox="0 0 12 12" fill="none">
                    <path d="M3 5L6 8L9 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </span>
              )}
              {showThumbnailsDropdown && (
                <div className="absolute top-full left-0 mt-1.5 w-56 bg-neutral-800/90 border border-neutral-700/60 rounded-xl shadow-2xl z-50 py-1.5">
                  <button
                    onClick={() => { setShowThumbnailsDropdown(false); generateMissingThumbnails(); }}
                    disabled={allThumbnailsDone || !hasExistingThumbnails || missingThumbnailCount === 0}
                    className="w-full text-left px-3 py-1.5 text-sm text-neutral-300 hover:bg-neutral-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    Generate Missing ({missingThumbnailCount})
                  </button>
                </div>
              )}
            </div>
          </div>
          {thumbnailsBusy && <MiniProgressBar estimatedSeconds={thumbnailsEstimatedSeconds} active={thumbnailsProgressActive} />}
        </div>

        <svg className="w-3 h-3 text-neutral-600/60 shrink-0" viewBox="0 0 12 12" fill="none"><path d="M4 2L8 6L4 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>

        {/* Step 2 — Audio (split-button with voice picker) */}
        <div className="flex items-center gap-1.5">
          <span className={`w-[20px] h-[20px] rounded-full border text-[11px] font-bold flex items-center justify-center shrink-0 tabular-nums ${
            batchGeneratingAudio
              ? "border-violet-400 bg-violet-500/10 text-violet-300 shadow-[0_0_6px_rgba(139,92,246,0.4)] animate-[pulseDot_2s_ease-in-out_infinite]"
              : allAudioGenerated
                ? "border-emerald-400 bg-emerald-500/10 text-emerald-300 shadow-[0_0_6px_rgba(52,211,153,0.3)]"
                : "border-neutral-600 text-neutral-500"
          }`}>2</span>
          <div ref={voicePickerRef} className="relative flex items-stretch flex-1">
            <button
              onClick={batchGeneratingAudio ? (yoloModeActive ? undefined : cancelAudioGeneration) : confirmAndGenerateAudio}
              disabled={!batchGeneratingAudio && !selectedVoiceId && voices.length > 0}
              className={`text-xs pl-3 pr-1.5 py-2 border border-r-0 rounded-l-lg font-medium transition-all flex items-center justify-center gap-1.5 min-w-0 flex-1 whitespace-nowrap disabled:opacity-40 disabled:cursor-not-allowed ${
                batchGeneratingAudio
                  ? `bg-neutral-800/80 border-violet-500/40 text-neutral-200 shadow-[0_0_8px_rgba(139,92,246,0.15)] ${yoloModeActive ? "cursor-default" : "hover:border-red-500/50 hover:text-red-400"}`
                  : allAudioGenerated
                    ? "bg-emerald-500/8 border-emerald-500/25 text-emerald-400 hover:bg-emerald-500/15"
                    : "bg-neutral-800/80 border-neutral-700/60 text-neutral-300 hover:bg-neutral-700/80 hover:border-neutral-600"
              }`}
              title={batchGeneratingAudio ? (yoloModeActive ? "Generating audio" : "Cancel audio generation") : "Generate audio for all scenes with narration"}
            >
              {batchGeneratingAudio ? (
                <span className="flex items-center gap-2">
                  <span className="w-3.5 h-3.5 border-2 border-violet-400/60 border-t-transparent rounded-full animate-spin" />
                  {yoloModeActive ? compactProgressText(audioProgress) : "Cancel"}
                </span>
              ) : allAudioGenerated ? (
                "Audio ✓"
              ) : (
                "Audio"
              )}
            </button>
            {!batchGeneratingAudio && (
              <button
                onClick={() => setShowVoicePicker(!showVoicePicker)}
                className="text-xs px-1.5 bg-neutral-800/80 border border-l-0 border-neutral-700/60 text-neutral-400 hover:bg-neutral-700/80 hover:text-neutral-200 rounded-r-lg transition-all flex items-center"
                title="Select voice"
              >
                <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none">
                  <path d="M3 5L6 8L9 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            )}
            {batchGeneratingAudio && (
              <span className="text-xs px-1.5 bg-neutral-800/80 border border-l-0 border-violet-500/40 rounded-r-lg flex items-center">
                <svg className="w-3 h-3 text-neutral-600" viewBox="0 0 12 12" fill="none">
                  <path d="M3 5L6 8L9 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
            )}
            {showVoicePicker && (
              <div className="absolute top-full left-0 mt-1.5 w-56 bg-neutral-800/90 border border-neutral-700/60 rounded-xl shadow-2xl z-50 py-1.5 max-h-60 overflow-y-auto">
                {onRecordVoiceover && (
                  <>
                    <button
                      onClick={() => { setShowVoicePicker(false); onRecordVoiceover(); }}
                      className="w-full text-left px-3 py-1.5 text-sm text-amber-300 hover:bg-neutral-700 transition-colors flex items-center gap-2"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
                      </svg>
                      Record Your Own
                    </button>
                    <div className="border-t border-neutral-700 my-1" />
                  </>
                )}
                {!allAudioGenerated && hasExistingAudio && (
                  <>
                    <button
                      onClick={() => { setShowVoicePicker(false); generateMissingAudio(); }}
                      className="w-full text-left px-3 py-1.5 text-sm text-sky-300 hover:bg-neutral-700 transition-colors"
                    >
                      Generate Missing ({missingAudioCount})
                    </button>
                    <div className="border-t border-neutral-700 my-1" />
                  </>
                )}
                {voices.length === 0 ? (
                  <div className="px-3 py-2 text-xs text-neutral-500">No voices available</div>
                ) : (
                  voices.map((v) => (
                    <button
                      key={v.voice_id}
                      onClick={() => { setSelectedVoiceId(v.voice_id); setShowVoicePicker(false); }}
                      className={`w-full text-left px-3 py-1.5 text-sm transition-colors flex items-center justify-between ${
                        v.voice_id === selectedVoiceId
                          ? "bg-violet-500/15 text-violet-300"
                          : "text-neutral-300 hover:bg-neutral-700"
                      }`}
                    >
                      <span>{v.name}</span>
                      {v.voice_id === selectedVoiceId && (
                        <svg className="w-3.5 h-3.5 text-violet-400" viewBox="0 0 14 14" fill="none">
                          <path d="M2 7L5.5 10.5L12 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      )}
                    </button>
                  ))
                )}
              </div>
            )}
          </div>
        </div>

        <svg className="w-3 h-3 text-neutral-600/60 shrink-0" viewBox="0 0 12 12" fill="none"><path d="M4 2L8 6L4 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>

        {/* Step 3 — Images */}
        <div className="flex items-center gap-1.5">
          <span className={`w-[20px] h-[20px] rounded-full border text-[11px] font-bold flex items-center justify-center shrink-0 tabular-nums ${
            batchGenerating
              ? "border-violet-400 bg-violet-500/10 text-violet-300 shadow-[0_0_6px_rgba(139,92,246,0.4)] animate-[pulseDot_2s_ease-in-out_infinite]"
              : allImagesGenerated
                ? "border-emerald-400 bg-emerald-500/10 text-emerald-300 shadow-[0_0_6px_rgba(52,211,153,0.3)]"
                : "border-neutral-600 text-neutral-500"
          }`}>3</span>
          <div ref={imagesDropdownRef} className="relative flex items-stretch flex-1">
            <button
              onClick={batchGenerating ? (yoloModeActive ? undefined : cancelImageGeneration) : confirmAndGenerateImages}
              className={`text-xs pl-3 pr-1.5 py-2 border border-r-0 rounded-l-lg font-medium transition-all flex items-center justify-center gap-1.5 min-w-0 flex-1 whitespace-nowrap ${
                batchGenerating
                  ? `bg-neutral-800/80 border-violet-500/40 text-neutral-200 shadow-[0_0_8px_rgba(139,92,246,0.15)] ${yoloModeActive ? "cursor-default" : "hover:border-red-500/50 hover:text-red-400"}`
                  : allImagesGenerated
                    ? "bg-emerald-500/8 border-emerald-500/25 text-emerald-400 hover:bg-emerald-500/15"
                    : "bg-neutral-800/80 border-neutral-700/60 text-neutral-300 hover:bg-neutral-700/80 hover:border-neutral-600"
              }`}
              title={batchGenerating ? (yoloModeActive ? "Generating images" : "Cancel image generation") : "Generate images for all scenes with visual prompts"}
            >
              {batchGenerating ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-violet-400/60 border-t-transparent rounded-full animate-spin" />
                  {yoloModeActive ? compactProgressText(imageProgress) : "Cancel"}
                </>
              ) : allImagesGenerated ? (
                "Images ✓"
              ) : (
                "Images"
              )}
            </button>
            {!batchGenerating ? (
              <button
                onClick={() => setShowImagesDropdown(!showImagesDropdown)}
                className="text-xs px-1.5 bg-neutral-800/80 border border-l-0 border-neutral-700/60 text-neutral-400 hover:bg-neutral-700/80 hover:text-neutral-200 rounded-r-lg transition-all flex items-center"
                title="Image generation options"
              >
                <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none">
                  <path d="M3 5L6 8L9 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            ) : (
              <span className="text-xs px-1.5 bg-neutral-800/80 border border-l-0 border-violet-500/40 rounded-r-lg flex items-center">
                <svg className="w-3 h-3 text-neutral-600" viewBox="0 0 12 12" fill="none">
                  <path d="M3 5L6 8L9 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
            )}
            {showImagesDropdown && (
              <div className="absolute top-full left-0 mt-1.5 w-48 bg-neutral-800/90 border border-neutral-700/60 rounded-xl shadow-2xl z-50 py-1.5">
                <button
                  onClick={() => { setShowImagesDropdown(false); generateMissingImages(); }}
                  disabled={allImagesGenerated || !hasExistingImages}
                  className="w-full text-left px-3 py-1.5 text-sm text-neutral-300 hover:bg-neutral-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Generate Missing ({missingImageCount})
                </button>
              </div>
            )}
          </div>
        </div>

        <svg className="w-3 h-3 text-neutral-600/60 shrink-0" viewBox="0 0 12 12" fill="none"><path d="M4 2L8 6L4 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>

        {/* Step 4 — FX */}
        <div className="flex flex-col">
          <div className="flex items-center gap-1.5">
            <span className={`w-[20px] h-[20px] rounded-full border text-[11px] font-bold flex items-center justify-center shrink-0 tabular-nums ${
              generatingFX
                ? "border-violet-400 bg-violet-500/10 text-violet-300 shadow-[0_0_6px_rgba(139,92,246,0.4)] animate-[pulseDot_2s_ease-in-out_infinite]"
                : allFXGenerated && fxPotentiallyStale
                  ? "border-amber-400 bg-amber-500/10 text-amber-300 shadow-[0_0_6px_rgba(245,158,11,0.3)]"
                  : allFXGenerated
                    ? "border-emerald-400 bg-emerald-500/10 text-emerald-300 shadow-[0_0_6px_rgba(52,211,153,0.3)]"
                    : "border-neutral-600 text-neutral-500"
            }`}>4</span>
            <div ref={fxDropdownRef} className="relative flex items-stretch flex-1">
              <button
                onClick={generatingFX ? (yoloModeActive ? undefined : () => { fxCancelledRef.current = true; setGeneratingFX(false); }) : confirmAndGenerateFX}
                className={`text-xs pl-3 pr-1.5 py-2 border border-r-0 rounded-l-lg font-medium transition-all flex items-center justify-center gap-1.5 min-w-0 flex-1 whitespace-nowrap ${
                  generatingFX
                    ? `bg-neutral-800/80 border-violet-500/40 text-neutral-200 shadow-[0_0_8px_rgba(139,92,246,0.15)] ${yoloModeActive ? "cursor-default" : "hover:border-red-500/50 hover:text-red-400"}`
                    : allFXGenerated && fxPotentiallyStale
                      ? "bg-amber-500/8 border-amber-500/25 text-amber-400 hover:bg-amber-500/15"
                      : allFXGenerated
                        ? "bg-emerald-500/8 border-emerald-500/25 text-emerald-400 hover:bg-emerald-500/15"
                        : "bg-neutral-800/80 border-neutral-700/60 text-neutral-300 hover:bg-neutral-700/80 hover:border-neutral-600"
                }`}
                title={generatingFX ? (yoloModeActive ? "Generating FX" : "Cancel FX generation") : fxPotentiallyStale && allFXGenerated ? "Audio changed since FX was last generated — regenerate to sync" : "Use AI to assign visual effects to all scenes"}
              >
                {generatingFX ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-violet-400/60 border-t-transparent rounded-full animate-spin" />
                    {yoloModeActive ? compactProgressText(fxProgress) : "Cancel"}
                  </>
                ) : allFXGenerated && fxPotentiallyStale ? (
                  "FX ⚠"
                ) : allFXGenerated ? (
                  "FX ✓"
                ) : (
                  "FX"
                )}
              </button>
              {!generatingFX ? (
                <button
                  onClick={() => setShowFXDropdown(!showFXDropdown)}
                  className="text-xs px-1.5 bg-neutral-800/80 border border-l-0 border-neutral-700/60 text-neutral-400 hover:bg-neutral-700/80 hover:text-neutral-200 rounded-r-lg transition-all flex items-center"
                  title="FX generation options"
                >
                  <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none">
                    <path d="M3 5L6 8L9 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              ) : (
                <span className="text-xs px-1.5 bg-neutral-800/80 border border-l-0 border-violet-500/40 rounded-r-lg flex items-center">
                  <svg className="w-3 h-3 text-neutral-600" viewBox="0 0 12 12" fill="none">
                    <path d="M3 5L6 8L9 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </span>
              )}
              {showFXDropdown && (
                <div className="absolute top-full right-0 mt-1.5 w-48 bg-neutral-800/90 border border-neutral-700/60 rounded-xl shadow-2xl z-50 py-1.5">
                  <button
                    onClick={() => { setShowFXDropdown(false); generateMissingFX(); }}
                    disabled={allFXGenerated || !hasExistingFX}
                    className="w-full text-left px-3 py-1.5 text-sm text-neutral-300 hover:bg-neutral-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    Generate Missing ({missingFXCount})
                  </button>
                </div>
              )}
            </div>
          </div>
          {generatingFX && <MiniProgressBar estimatedSeconds={fxEstimatedSeconds} active={fxProgressActive} />}
        </div>

      </div>
    </div>
  );
}
