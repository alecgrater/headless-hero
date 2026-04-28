import { useEffect, useRef, useState, type RefObject } from "react";
import type { VoiceInfo } from "../../types/audio";
import type { ScriptContent } from "../../types/script";
import MiniProgressBar from "../MiniProgressBar";

interface Props {
  // Step completion states
  titleCardGenerating: boolean;
  titleCardGenerated: boolean;
  allImagesGenerated: boolean;
  allAudioGenerated: boolean;
  allFXGenerated: boolean;
  // Batch generating states from useTimelineState
  batchGenerating: boolean;
  batchGeneratingAudio: boolean;
  hasTitleCards: boolean;
  // Generating states
  generatingFX: boolean;
  setGeneratingFX: (v: boolean) => void;
  // Handler functions
  handleGenerateTitleCards: (force?: boolean) => void;
  cancelTitleCards: () => void;
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
  content: ScriptContent;
  setContent: (content: ScriptContent) => void;
  // Export
  exportTestJobId: string | null;
  setExportTestJobId: (id: string | null) => void;
  showExportDropdown: boolean;
  setShowExportDropdown: (show: boolean) => void;
  exportDropdownRef: RefObject<HTMLDivElement | null>;
  setShowExport: (show: boolean) => void;
  setShowExportTestModal: (show: boolean) => void;
  // Staleness
  fxPotentiallyStale: boolean;
  // Eli
  allEliGenerated: boolean;
  generatingEli: boolean;
  setGeneratingEli: (v: boolean) => void;
  confirmAndGenerateEli: () => void;
  generateMissingEli: () => void;
  hasExistingEli: boolean;
  missingEliCount: number;
  eliCancelledRef: RefObject<boolean>;
  // Progress tracking
  fxEstimatedSeconds: number | null;
  fxProgressActive: boolean;
  eliEstimatedSeconds: number | null;
  eliProgressActive: boolean;
  titleCardEstimatedSeconds: number | null;
  titleCardProgressActive: boolean;
}

export default function PipelineSteps({
  titleCardGenerating,
  titleCardGenerated,
  allImagesGenerated,
  allAudioGenerated,
  allFXGenerated,
  batchGenerating,
  batchGeneratingAudio,
  hasTitleCards,
  generatingFX,
  setGeneratingFX,
  handleGenerateTitleCards,
  cancelTitleCards,
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
  content,
  setContent,
  exportTestJobId,
  setExportTestJobId,
  showExportDropdown,
  setShowExportDropdown,
  exportDropdownRef,
  setShowExport,
  setShowExportTestModal,
  fxPotentiallyStale,
  allEliGenerated,
  generatingEli,
  setGeneratingEli,
  confirmAndGenerateEli,
  generateMissingEli,
  hasExistingEli,
  missingEliCount,
  eliCancelledRef,
  fxEstimatedSeconds,
  fxProgressActive,
  eliEstimatedSeconds,
  eliProgressActive,
  titleCardEstimatedSeconds,
  titleCardProgressActive,
}: Props) {
  const [showImagesDropdown, setShowImagesDropdown] = useState(false);
  const [showFXDropdown, setShowFXDropdown] = useState(false);
  const [showEliDropdown, setShowEliDropdown] = useState(false);
  const imagesDropdownRef = useRef<HTMLDivElement>(null);
  const fxDropdownRef = useRef<HTMLDivElement>(null);
  const eliDropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (showImagesDropdown && imagesDropdownRef.current && !imagesDropdownRef.current.contains(e.target as Node)) {
        setShowImagesDropdown(false);
      }
      if (showFXDropdown && fxDropdownRef.current && !fxDropdownRef.current.contains(e.target as Node)) {
        setShowFXDropdown(false);
      }
      if (showEliDropdown && eliDropdownRef.current && !eliDropdownRef.current.contains(e.target as Node)) {
        setShowEliDropdown(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showImagesDropdown, showFXDropdown, showEliDropdown]);

  return (
    <div className="flex items-center gap-4 px-5 py-2.5">
      {/* Pipeline steps */}
      <div className="grid items-center gap-2" style={{ gridTemplateColumns: "1fr auto 1fr auto 1fr auto 1fr auto 1fr auto 1fr" }}>

        {/* Step 1 — Title Cards */}
        <div className="flex flex-col">
          <div className="flex items-center gap-1.5">
            <span className={`w-[20px] h-[20px] rounded-full border text-[11px] font-bold flex items-center justify-center shrink-0 tabular-nums ${
              titleCardGenerating
                ? "border-violet-400 bg-violet-500/10 text-violet-300 shadow-[0_0_6px_rgba(139,92,246,0.4)] animate-[pulseDot_2s_ease-in-out_infinite]"
                : titleCardGenerated || !hasTitleCards
                  ? "border-emerald-400 bg-emerald-500/10 text-emerald-300 shadow-[0_0_6px_rgba(52,211,153,0.3)]"
                  : "border-neutral-600 text-neutral-500"
            }`}>1</span>
            {hasTitleCards && (
              <button
                onClick={titleCardGenerating ? cancelTitleCards : () => handleGenerateTitleCards(titleCardGenerated)}
                className={`text-xs px-3 py-2 border rounded-lg font-medium transition-all flex items-center justify-center gap-1.5 min-w-0 flex-1 whitespace-nowrap ${
                  titleCardGenerating
                    ? "bg-neutral-800/80 border-violet-500/40 text-neutral-200 shadow-[0_0_8px_rgba(139,92,246,0.15)] hover:border-red-500/50 hover:text-red-400"
                    : titleCardGenerated
                      ? "bg-emerald-500/8 border-emerald-500/25 text-emerald-400 hover:bg-emerald-500/15"
                      : "bg-neutral-800/80 border-neutral-700/60 text-neutral-300 hover:bg-neutral-700/80 hover:border-neutral-600"
                }`}
                title={titleCardGenerating ? "Cancel title card generation" : "Generate composite title card images for all segments"}
              >
                {titleCardGenerating ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-violet-400/60 border-t-transparent rounded-full animate-spin" />
                    Cancel
                  </>
                ) : titleCardGenerated ? (
                  "Title Cards \u2713"
                ) : (
                  "Title Cards"
                )}
              </button>
            )}
          </div>
          {titleCardGenerating && <MiniProgressBar estimatedSeconds={titleCardEstimatedSeconds} active={titleCardProgressActive} />}
        </div>

        {/* Chevron connector */}
        <svg className="w-3 h-3 text-neutral-600/60 shrink-0" viewBox="0 0 12 12" fill="none"><path d="M4 2L8 6L4 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>

        {/* Step 2 — Generate Audio (split-button with voice picker) */}
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
              onClick={batchGeneratingAudio ? cancelAudioGeneration : confirmAndGenerateAudio}
              disabled={!batchGeneratingAudio && !selectedVoiceId && voices.length > 0}
              className={`text-xs pl-3 pr-1.5 py-2 border border-r-0 rounded-l-lg font-medium transition-all flex items-center justify-center gap-1.5 min-w-0 flex-1 whitespace-nowrap disabled:opacity-40 disabled:cursor-not-allowed ${
                batchGeneratingAudio
                  ? "bg-neutral-800/80 border-violet-500/40 text-neutral-200 shadow-[0_0_8px_rgba(139,92,246,0.15)] hover:border-red-500/50 hover:text-red-400"
                  : allAudioGenerated
                    ? "bg-emerald-500/8 border-emerald-500/25 text-emerald-400 hover:bg-emerald-500/15"
                    : "bg-neutral-800/80 border-neutral-700/60 text-neutral-300 hover:bg-neutral-700/80 hover:border-neutral-600"
              }`}
              title={batchGeneratingAudio ? "Cancel audio generation" : "Generate audio for all scenes with narration"}
            >
              {batchGeneratingAudio ? (
                <span className="flex items-center gap-2">
                  <span className="w-3.5 h-3.5 border-2 border-violet-400/60 border-t-transparent rounded-full animate-spin" />
                  Cancel
                </span>
              ) : allAudioGenerated ? (
                "Generate Audio \u2713"
              ) : (
                "Generate Audio"
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
            {/* Voice picker popover */}
            {showVoicePicker && (
              <div className="absolute top-full left-0 mt-1.5 w-56 bg-neutral-800/90 border border-neutral-700/60 rounded-xl shadow-2xl z-50 py-1.5 max-h-60 overflow-y-auto">
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

        {/* Chevron connector */}
        <svg className="w-3 h-3 text-neutral-600/60 shrink-0" viewBox="0 0 12 12" fill="none"><path d="M4 2L8 6L4 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>

        {/* Step 3 — Generate Images (split-button with generate missing) */}
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
              onClick={batchGenerating ? cancelImageGeneration : confirmAndGenerateImages}
              className={`text-xs pl-3 pr-1.5 py-2 border border-r-0 rounded-l-lg font-medium transition-all flex items-center justify-center gap-1.5 min-w-0 flex-1 whitespace-nowrap ${
                batchGenerating
                  ? "bg-neutral-800/80 border-violet-500/40 text-neutral-200 shadow-[0_0_8px_rgba(139,92,246,0.15)] hover:border-red-500/50 hover:text-red-400"
                  : allImagesGenerated
                    ? "bg-emerald-500/8 border-emerald-500/25 text-emerald-400 hover:bg-emerald-500/15"
                    : "bg-neutral-800/80 border-neutral-700/60 text-neutral-300 hover:bg-neutral-700/80 hover:border-neutral-600"
              }`}
              title={batchGenerating ? "Cancel image generation" : "Generate images for all scenes with visual prompts"}
            >
              {batchGenerating ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-violet-400/60 border-t-transparent rounded-full animate-spin" />
                  Cancel
                </>
              ) : allImagesGenerated ? (
                "Generate Images \u2713"
              ) : (
                "Generate Images"
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

        {/* Chevron connector + Step 4 — Generate FX */}
        <svg className="w-3 h-3 text-neutral-600/60 shrink-0" viewBox="0 0 12 12" fill="none"><path d="M4 2L8 6L4 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
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
                onClick={generatingFX ? () => { fxCancelledRef.current = true; setGeneratingFX(false); } : confirmAndGenerateFX}
                className={`text-xs pl-3 pr-1.5 py-2 border border-r-0 rounded-l-lg font-medium transition-all flex items-center justify-center gap-1.5 min-w-0 flex-1 whitespace-nowrap ${
                  generatingFX
                    ? "bg-neutral-800/80 border-violet-500/40 text-neutral-200 shadow-[0_0_8px_rgba(139,92,246,0.15)] hover:border-red-500/50 hover:text-red-400"
                    : allFXGenerated && fxPotentiallyStale
                      ? "bg-amber-500/8 border-amber-500/25 text-amber-400 hover:bg-amber-500/15"
                      : allFXGenerated
                        ? "bg-emerald-500/8 border-emerald-500/25 text-emerald-400 hover:bg-emerald-500/15"
                        : "bg-neutral-800/80 border-neutral-700/60 text-neutral-300 hover:bg-neutral-700/80 hover:border-neutral-600"
                }`}
                title={generatingFX ? "Cancel FX generation" : fxPotentiallyStale && allFXGenerated ? "Audio changed since FX was last generated — regenerate to sync" : "Use AI to assign visual effects to all scenes"}
              >
                {generatingFX ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-violet-400/60 border-t-transparent rounded-full animate-spin" />
                    Cancel
                  </>
                ) : allFXGenerated && fxPotentiallyStale ? (
                  "Generate FX \u26A0"
                ) : allFXGenerated ? (
                  "Generate FX \u2713"
                ) : (
                  "Generate FX"
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
                <div className="absolute top-full left-0 mt-1.5 w-48 bg-neutral-800/90 border border-neutral-700/60 rounded-xl shadow-2xl z-50 py-1.5">
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

        {/* Chevron connector + Step 5 — Add Eli */}
        <svg className="w-3 h-3 text-neutral-600/60 shrink-0" viewBox="0 0 12 12" fill="none"><path d="M4 2L8 6L4 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
        <div className="flex flex-col">
          <div className="flex items-center gap-1.5">
            <span className={`w-[20px] h-[20px] rounded-full border text-[11px] font-bold flex items-center justify-center shrink-0 tabular-nums ${
              generatingEli
                ? "border-violet-400 bg-violet-500/10 text-violet-300 shadow-[0_0_6px_rgba(139,92,246,0.4)] animate-[pulseDot_2s_ease-in-out_infinite]"
                : allEliGenerated
                  ? "border-emerald-400 bg-emerald-500/10 text-emerald-300 shadow-[0_0_6px_rgba(52,211,153,0.3)]"
                  : "border-neutral-600 text-neutral-500"
            }`}>5</span>
            <div ref={eliDropdownRef} className="relative flex items-stretch flex-1">
              <button
                onClick={generatingEli ? () => { eliCancelledRef.current = true; setGeneratingEli(false); } : confirmAndGenerateEli}
                disabled={!allAudioGenerated && !generatingEli}
                className={`text-xs pl-3 pr-1.5 py-2 border border-r-0 rounded-l-lg font-medium transition-all flex items-center justify-center gap-1.5 min-w-0 flex-1 whitespace-nowrap disabled:opacity-40 disabled:cursor-not-allowed ${
                  generatingEli
                    ? "bg-neutral-800/80 border-violet-500/40 text-neutral-200 shadow-[0_0_8px_rgba(139,92,246,0.15)] hover:border-red-500/50 hover:text-red-400"
                    : allEliGenerated
                      ? "bg-emerald-500/8 border-emerald-500/25 text-emerald-400 hover:bg-emerald-500/15"
                      : "bg-neutral-800/80 border-neutral-700/60 text-neutral-300 hover:bg-neutral-700/80 hover:border-neutral-600"
                }`}
                title={!allAudioGenerated && !generatingEli ? "Generate audio first — Eli needs voiceover for mouth animation" : generatingEli ? "Cancel Eli generation" : "Add Eli character overlay to all scenes"}
              >
                {generatingEli ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-violet-400/60 border-t-transparent rounded-full animate-spin" />
                    Cancel
                  </>
                ) : allEliGenerated ? (
                  "Add Eli \u2713"
                ) : (
                  "Add Eli"
                )}
              </button>
              {!generatingEli ? (
                <button
                  onClick={() => setShowEliDropdown(!showEliDropdown)}
                  disabled={!allAudioGenerated}
                  className={`text-xs px-1.5 bg-neutral-800/80 border border-l-0 border-neutral-700/60 rounded-r-lg transition-all flex items-center ${!allAudioGenerated ? "text-neutral-600 cursor-not-allowed" : "text-neutral-400 hover:bg-neutral-700/80 hover:text-neutral-200"}`}
                  title={!allAudioGenerated ? "Generate audio first" : "Eli generation options"}
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
              {showEliDropdown && (
                <div className="absolute top-full left-0 mt-1.5 w-48 bg-neutral-800/90 border border-neutral-700/60 rounded-xl shadow-2xl z-50 py-1.5">
                  <button
                    onClick={() => { setShowEliDropdown(false); generateMissingEli(); }}
                    disabled={allEliGenerated || !hasExistingEli || !allAudioGenerated}
                    className="w-full text-left px-3 py-1.5 text-sm text-neutral-300 hover:bg-neutral-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    Generate Missing ({missingEliCount})
                  </button>
                </div>
              )}
            </div>
          </div>
          {generatingEli && <MiniProgressBar estimatedSeconds={eliEstimatedSeconds} active={eliProgressActive} />}
        </div>

        {/* Chevron connector + Step 6 — Export (split-button with Export Test dropdown) */}
        <svg className="w-3 h-3 text-neutral-600/60 shrink-0" viewBox="0 0 12 12" fill="none"><path d="M4 2L8 6L4 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
        <div className="flex items-center gap-1.5">
          <span className="w-[20px] h-[20px] rounded-full border text-[11px] font-bold flex items-center justify-center shrink-0 tabular-nums border-neutral-600 text-neutral-500">6</span>
          <div ref={exportDropdownRef} className="relative flex items-stretch flex-1">
            <button
              onClick={exportTestJobId ? () => setExportTestJobId(null) : () => setShowExport(true)}
              className={`text-xs pl-3 pr-1.5 py-2 border border-r-0 rounded-l-lg font-medium transition-all flex items-center justify-center gap-1.5 min-w-0 flex-1 whitespace-nowrap ${
                exportTestJobId
                  ? "bg-neutral-800/80 border-violet-500/40 text-neutral-200 shadow-[0_0_8px_rgba(139,92,246,0.15)] hover:border-red-500/50 hover:text-red-400"
                  : "bg-neutral-800/80 border-neutral-700/60 text-neutral-300 hover:bg-neutral-700/80 hover:border-neutral-600"
              }`}
              title={exportTestJobId ? "Cancel export test" : "Export & Render (Cmd+E)"}
            >
              {exportTestJobId ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-violet-400/60 border-t-transparent rounded-full animate-spin" />
                  Cancel
                </>
              ) : (
                "Export"
              )}
            </button>
            {!exportTestJobId ? (
              <button
                onClick={() => setShowExportDropdown(!showExportDropdown)}
                className="text-xs px-1.5 bg-neutral-800/80 border border-l-0 border-neutral-700/60 text-neutral-400 hover:bg-neutral-700/80 hover:text-neutral-200 rounded-r-lg transition-all flex items-center"
                title="Export options"
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
            {/* Export dropdown popover */}
            {showExportDropdown && (
              <div className="absolute top-full left-0 mt-1.5 w-44 bg-neutral-800/90 border border-neutral-700/60 rounded-xl shadow-2xl z-50 py-1.5">
                <button
                  onClick={() => { setShowExportDropdown(false); setShowExportTestModal(true); }}
                  className="w-full text-left px-3 py-1.5 text-sm text-neutral-300 hover:bg-neutral-700 transition-colors"
                >
                  Export Test
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
