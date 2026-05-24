import { useEffect, useRef, useState, type RefObject } from "react";
import type { ProjectConfig } from "../../api";
import MiniProgressBar from "../MiniProgressBar";
import { ProductionTaskButton } from "./ProductionTaskButton";
import { compactProgressText, type ProductionTask } from "./timelineProduction";

export function FinalizationRow({
  allFXGenerated,
  hasExistingFX,
  missingFXCount,
  generatingFX,
  setGeneratingFX,
  confirmAndGenerateFX,
  generateMissingFX,
  fxCancelledRef,
  fxPotentiallyStale,
  fxEstimatedSeconds,
  fxProgressActive,
  fxProgress,
  allEliGenerated,
  hasExistingEli,
  missingEliCount,
  generatingEli,
  setGeneratingEli,
  confirmAndGenerateEli,
  generateMissingEli,
  eliCancelledRef,
  eliEstimatedSeconds,
  eliProgressActive,
  eliProgress,
  eliDisabledForProject,
  projectConfig,
  onOpenMainCharacterDrawer,
  allAudioGenerated,
  allSeoDone,
  missingSeoCount,
  seoBusy,
  confirmAndGenerateSeo,
  generateMissingSeo,
  allExportsDone,
  missingExportCount,
  exportBusy,
  confirmAndExport,
  exportMissing,
  yoloModeActive,
  productionProgress,
  productionBusyTask,
  anyProductionBusy,
}: {
  allFXGenerated: boolean;
  hasExistingFX: boolean;
  missingFXCount: number;
  generatingFX: boolean;
  setGeneratingFX: (v: boolean) => void;
  confirmAndGenerateFX: () => void;
  generateMissingFX: () => void;
  fxCancelledRef: RefObject<boolean>;
  fxPotentiallyStale: boolean;
  fxEstimatedSeconds: number | null;
  fxProgressActive: boolean;
  fxProgress: number | null;
  allEliGenerated: boolean;
  hasExistingEli: boolean;
  missingEliCount: number;
  generatingEli: boolean;
  setGeneratingEli: (v: boolean) => void;
  confirmAndGenerateEli: () => void;
  generateMissingEli: () => void;
  eliCancelledRef: RefObject<boolean>;
  eliEstimatedSeconds: number | null;
  eliProgressActive: boolean;
  eliProgress: number | null;
  eliDisabledForProject: boolean;
  projectConfig: ProjectConfig | null;
  onOpenMainCharacterDrawer: () => void;
  allAudioGenerated: boolean;
  allSeoDone: boolean;
  missingSeoCount: number;
  seoBusy: boolean;
  confirmAndGenerateSeo: () => void;
  generateMissingSeo: () => void;
  allExportsDone: boolean;
  missingExportCount: number;
  exportBusy: boolean;
  confirmAndExport: () => void;
  exportMissing: () => void;
  yoloModeActive: boolean;
  productionProgress: number | null;
  productionBusyTask: ProductionTask | null;
  anyProductionBusy: boolean;
}) {
  const [showEliDropdown, setShowEliDropdown] = useState(false);
  const [showFXDropdown, setShowFXDropdown] = useState(false);
  const eliDropdownRef = useRef<HTMLDivElement>(null);
  const fxDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!showEliDropdown && !showFXDropdown) return;
    const handler = (e: MouseEvent) => {
      if (showEliDropdown && eliDropdownRef.current && !eliDropdownRef.current.contains(e.target as Node)) setShowEliDropdown(false);
      if (showFXDropdown && fxDropdownRef.current && !fxDropdownRef.current.contains(e.target as Node)) setShowFXDropdown(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showEliDropdown, showFXDropdown]);

  const seoProgress = productionBusyTask === "seo-combined" ? productionProgress : null;
  const exportProgress = productionBusyTask === "export-combined" ? productionProgress : null;

  return (
    <div className="px-5 py-2 border-t border-neutral-900/80 shrink-0">
      <div className="grid w-full items-center gap-2 min-w-0" style={{ gridTemplateColumns: "minmax(0,1fr) auto minmax(0,1fr) auto minmax(0,1fr) auto minmax(0,1fr)" }}>
        {/* Step 4 — FX (under YOLO MODE) */}
        <div className="flex flex-col">
          <div className="flex items-center gap-1.5">
            <span className={`w-[20px] h-[20px] rounded-full border text-[11px] font-bold flex items-center justify-center shrink-0 tabular-nums ${
              generatingFX
                ? "border-violet-400/80 bg-violet-500/10 text-violet-300 shadow-[0_0_6px_rgba(139,92,246,0.25)] animate-[pulseDot_2s_ease-in-out_infinite]"
                : allFXGenerated && fxPotentiallyStale
                  ? "border-amber-400 bg-amber-500/10 text-amber-300 shadow-[0_0_6px_rgba(245,158,11,0.3)]"
                  : allFXGenerated
                    ? "border-emerald-400 bg-emerald-500/10 text-emerald-300 shadow-[0_0_6px_rgba(52,211,153,0.3)]"
                    : "border-neutral-700 text-neutral-600"
            }`}>4</span>
            <div ref={fxDropdownRef} className="relative flex items-stretch flex-1">
              <button
                onClick={generatingFX ? (yoloModeActive ? undefined : () => { fxCancelledRef.current = true; setGeneratingFX(false); }) : confirmAndGenerateFX}
                className={`text-xs pl-3 pr-1.5 py-2 border border-r-0 rounded-l-lg font-medium transition-all flex items-center justify-center gap-1.5 min-w-0 flex-1 whitespace-nowrap ${
                  generatingFX
                    ? `bg-neutral-900/80 border-violet-500/35 text-neutral-200 ${yoloModeActive ? "cursor-default" : "hover:border-red-500/50 hover:text-red-400"}`
                    : allFXGenerated && fxPotentiallyStale
                      ? "bg-amber-500/8 border-amber-500/25 text-amber-400 hover:bg-amber-500/15"
                      : allFXGenerated
                        ? "bg-emerald-500/8 border-emerald-500/25 text-emerald-400 hover:bg-emerald-500/15"
                        : "bg-neutral-900/55 border-neutral-800 text-neutral-400 hover:bg-neutral-800/70 hover:border-neutral-700 hover:text-neutral-200"
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
                  className="text-xs px-1.5 bg-neutral-900/55 border border-l-0 border-neutral-800 text-neutral-500 hover:bg-neutral-800/70 hover:text-neutral-200 rounded-r-lg transition-all flex items-center"
                  title="FX generation options"
                >
                  <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none">
                    <path d="M3 5L6 8L9 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              ) : (
                <span className="text-xs px-1.5 bg-neutral-800/80 border border-l-0 border-violet-500/40 rounded-r-lg flex items-center">
                  <svg className="w-3 h-3 text-neutral-700" viewBox="0 0 12 12" fill="none">
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

        <svg className="w-3 h-3 text-neutral-600/60 shrink-0" viewBox="0 0 12 12" fill="none">
          <path d="M4 2L8 6L4 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>

        {/* Step 5 — Eli OR Main Character (when Eli disabled for project) */}
        {eliDisabledForProject ? (
          <div className="flex flex-col">
            <div className="flex items-center gap-1.5">
              <span className={`w-[20px] h-[20px] rounded-full border text-[11px] font-bold flex items-center justify-center shrink-0 tabular-nums ${
                projectConfig?.main_character_reference_url
                  ? "border-emerald-400 bg-emerald-500/10 text-emerald-300 shadow-[0_0_6px_rgba(52,211,153,0.3)]"
                  : "border-neutral-700 text-neutral-600"
              }`}>5</span>
              <button
                type="button"
                onClick={onOpenMainCharacterDrawer}
                className={`text-xs px-3 py-2 border rounded-lg font-medium transition-all flex items-center justify-center gap-1.5 min-w-0 flex-1 whitespace-nowrap ${
                  projectConfig?.main_character_reference_url
                    ? "bg-emerald-500/8 border-emerald-500/25 text-emerald-400 hover:bg-emerald-500/15"
                    : "bg-neutral-900/55 border-neutral-800 text-neutral-400 hover:bg-neutral-800/70 hover:border-neutral-700 hover:text-neutral-200"
                }`}
                title={projectConfig?.main_character_reference_url ? "Main character reference is generated. Click to view or edit." : "Main character reference is not yet generated. Click to generate."}
              >
                {projectConfig?.main_character_reference_url ? "Main character ✓" : "Main character"}
              </button>
            </div>
          </div>
        ) : (
        <div className="flex flex-col">
          <div className="flex items-center gap-1.5">
            <span className={`w-[20px] h-[20px] rounded-full border text-[11px] font-bold flex items-center justify-center shrink-0 tabular-nums ${
              generatingEli
                ? "border-violet-400/80 bg-violet-500/10 text-violet-300 shadow-[0_0_6px_rgba(139,92,246,0.25)] animate-[pulseDot_2s_ease-in-out_infinite]"
                : allEliGenerated
                  ? "border-emerald-400 bg-emerald-500/10 text-emerald-300 shadow-[0_0_6px_rgba(52,211,153,0.3)]"
                  : "border-neutral-700 text-neutral-600"
            }`}>5</span>
            <div ref={eliDropdownRef} className="relative flex items-stretch flex-1">
              <button
                onClick={generatingEli ? (yoloModeActive ? undefined : () => { eliCancelledRef.current = true; setGeneratingEli(false); }) : confirmAndGenerateEli}
                disabled={eliDisabledForProject || (!allAudioGenerated && !generatingEli)}
                className={`text-xs pl-3 pr-1.5 py-2 border border-r-0 rounded-l-lg font-medium transition-all flex items-center justify-center gap-1.5 min-w-0 flex-1 whitespace-nowrap disabled:opacity-40 disabled:cursor-not-allowed ${
                  generatingEli
                    ? `bg-neutral-900/80 border-violet-500/35 text-neutral-200 ${yoloModeActive ? "cursor-default" : "hover:border-red-500/50 hover:text-red-400"}`
                    : allEliGenerated
                      ? "bg-emerald-500/8 border-emerald-500/25 text-emerald-400 hover:bg-emerald-500/15"
                      : "bg-neutral-900/55 border-neutral-800 text-neutral-400 hover:bg-neutral-800/70 hover:border-neutral-700 hover:text-neutral-200"
                }`}
                title={eliDisabledForProject ? "Eli is disabled for this project. The main character is integrated into scene images instead." : !allAudioGenerated && !generatingEli ? "Generate audio first — Eli needs voiceover for mouth animation" : generatingEli ? (yoloModeActive ? "Generating Eli" : "Cancel Eli generation") : "Add Eli character overlay to all scenes"}
              >
                {generatingEli ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-violet-400/60 border-t-transparent rounded-full animate-spin" />
                    {yoloModeActive ? compactProgressText(eliProgress) : "Cancel"}
                  </>
                ) : allEliGenerated ? (
                  "Eli ✓"
                ) : (
                  "Eli"
                )}
              </button>
              {!generatingEli ? (
                <button
                  onClick={() => setShowEliDropdown(!showEliDropdown)}
                  disabled={eliDisabledForProject || !allAudioGenerated}
                  className={`text-xs px-1.5 bg-neutral-900/55 border border-l-0 border-neutral-800 rounded-r-lg transition-all flex items-center ${eliDisabledForProject || !allAudioGenerated ? "text-neutral-600 cursor-not-allowed opacity-40" : "text-neutral-500 hover:bg-neutral-800/70 hover:text-neutral-200"}`}
                  title={eliDisabledForProject ? "Eli is disabled for this project. The main character is integrated into scene images instead." : !allAudioGenerated ? "Generate audio first" : "Eli generation options"}
                >
                  <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none">
                    <path d="M3 5L6 8L9 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              ) : (
                <span className="text-xs px-1.5 bg-neutral-800/80 border border-l-0 border-violet-500/40 rounded-r-lg flex items-center">
                  <svg className="w-3 h-3 text-neutral-700" viewBox="0 0 12 12" fill="none">
                    <path d="M3 5L6 8L9 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </span>
              )}
              {showEliDropdown && (
                <div className="absolute top-full left-0 mt-1.5 w-48 bg-neutral-800/90 border border-neutral-700/60 rounded-xl shadow-2xl z-50 py-1.5">
                  <button
                    onClick={() => { setShowEliDropdown(false); generateMissingEli(); }}
                    disabled={eliDisabledForProject || allEliGenerated || !hasExistingEli || !allAudioGenerated}
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
        )}

        <svg className="w-3 h-3 text-neutral-600/60 shrink-0" viewBox="0 0 12 12" fill="none">
          <path d="M4 2L8 6L4 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>

        {/* Step 6 — SEO (under Audio) */}
        <ProductionTaskButton
          stepNumber={6}
          label="SEO"
          done={allSeoDone}
          busy={seoBusy}
          disabled={anyProductionBusy && !seoBusy}
          missingCount={missingSeoCount}
          progress={seoProgress}
          onRunAll={confirmAndGenerateSeo}
          onRunMissing={generateMissingSeo}
          missingLabel="Generate Missing"
          allTitle="Generate long-form + short-form SEO and export markdown files"
        />

        <svg className="w-3 h-3 text-neutral-600/60 shrink-0" viewBox="0 0 12 12" fill="none">
          <path d="M4 2L8 6L4 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>

        {/* Step 7 — Export (under Images) */}
        <ProductionTaskButton
          stepNumber={7}
          label="Export"
          done={allExportsDone}
          busy={exportBusy}
          disabled={anyProductionBusy && !exportBusy}
          missingCount={missingExportCount}
          progress={exportProgress}
          onRunAll={confirmAndExport}
          onRunMissing={exportMissing}
          missingLabel="Render Missing"
          allTitle="Render the long-form video and all short-form videos"
        />
      </div>
    </div>
  );
}
