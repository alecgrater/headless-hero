import { useCallback, useEffect, useState } from "react";
import api, {
  assetUrl,
  clearAllCharacterFrames,
  generateCharacterFrames,
  generateCharacterReferences,
  generateCharacterVariants,
  generateMissingCharacterFrames,
  getCharacterFrames,
  getCharacterReferences,
  getCharacterStatus,
  regenerateCharacterFrame,
  reprocessCharacterBackgrounds,
  selectCharacterReference,
} from "../../api";
import type { EliPosition } from "../../types/brand";
import EliPositionPicker from "../shared/EliPositionPicker";

interface FrameEntry {
  id: string;
  file_closed: string;
  file_open: string;
  expression: string;
  pose: string;
  gesture: string;
  variant_count: number;
}

interface Manifest {
  canonical_frame: string | null;
  generated_at: string | null;
  frames: FrameEntry[];
  missing_count: number;
}

export default function CharacterSection() {
  // Reference state
  const [references, setReferences] = useState<string[]>([]);
  const [selectedRef, setSelectedRef] = useState<string | null>(null);
  const [pendingRef, setPendingRef] = useState<string | null>(null);
  const [refJobId, setRefJobId] = useState<string | null>(null);
  const [refProgress, setRefProgress] = useState({ completed: 0, total: 15, current_label: "" });

  // Frame state
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [loading, setLoading] = useState(true);
  const [frameJobId, setFrameJobId] = useState<string | null>(null);
  const [frameProgress, setFrameProgress] = useState({ completed: 0, total: 0, current_label: "" });
  const [regeneratingId, setRegeneratingId] = useState<string | null>(null);

  // Variant state
  const [variantJobId, setVariantJobId] = useState<string | null>(null);
  const [variantProgress, setVariantProgress] = useState({ completed: 0, total: 0, current_label: "" });

  // Reprocess state
  const [reprocessJobId, setReprocessJobId] = useState<string | null>(null);
  const [reprocessProgress, setReprocessProgress] = useState({ completed: 0, total: 0, current_label: "" });

  // Overlay position state
  const [eliPosition, setEliPosition] = useState<EliPosition>({ x: 1410, y: 720 });

  const fetchManifest = useCallback(async () => {
    const res = await getCharacterFrames();
    if (res.ok) {
      setManifest(res.data as Manifest);
    }
    setLoading(false);
  }, []);

  const fetchReferences = useCallback(async () => {
    const data = await getCharacterReferences();
    setReferences(data.references);
    setSelectedRef(data.selected);
  }, []);

  useEffect(() => {
    fetchManifest();
    fetchReferences();
    // Fetch current brand eli_position
    api.get("/api/brand").then((res) => {
      if (res.ok) {
        const brand = res.data as { eli_position: EliPosition | null };
        if (brand.eli_position) setEliPosition(brand.eli_position);
      }
    });
  }, [fetchManifest, fetchReferences]);

  // Poll reference generation job
  useEffect(() => {
    if (!refJobId) return;
    const interval = setInterval(async () => {
      const res = await getCharacterStatus(refJobId);
      if (!res.ok) return;
      const status = res.data as { status: string; completed: number; total: number; current_label: string };
      setRefProgress({ completed: status.completed, total: status.total, current_label: status.current_label });
      if (status.status === "completed" || status.status === "failed") {
        setRefJobId(null);
        fetchReferences();
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [refJobId, fetchReferences]);

  // Poll frame generation job
  useEffect(() => {
    if (!frameJobId) return;
    const interval = setInterval(async () => {
      const res = await getCharacterStatus(frameJobId);
      if (!res.ok) return;
      const status = res.data as { status: string; completed: number; total: number; current_label: string };
      setFrameProgress({ completed: status.completed, total: status.total, current_label: status.current_label });
      if (status.status === "completed" || status.status === "failed") {
        setFrameJobId(null);
        fetchManifest();
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [frameJobId, fetchManifest]);

  // Poll variant generation job
  useEffect(() => {
    if (!variantJobId) return;
    const interval = setInterval(async () => {
      const res = await getCharacterStatus(variantJobId);
      if (!res.ok) return;
      const status = res.data as { status: string; completed: number; total: number; current_label: string };
      setVariantProgress({ completed: status.completed, total: status.total, current_label: status.current_label });
      if (status.status === "completed" || status.status === "failed") {
        setVariantJobId(null);
        fetchManifest();
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [variantJobId, fetchManifest]);

  // Poll reprocess job
  useEffect(() => {
    if (!reprocessJobId) return;
    const interval = setInterval(async () => {
      const res = await getCharacterStatus(reprocessJobId);
      if (!res.ok) return;
      const status = res.data as { status: string; completed: number; total: number; current_label: string };
      setReprocessProgress({ completed: status.completed, total: status.total, current_label: status.current_label });
      if (status.status === "completed" || status.status === "failed") {
        setReprocessJobId(null);
        fetchManifest();
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [reprocessJobId, fetchManifest]);

  const handleGenerateReferences = async () => {
    const result = await generateCharacterReferences();
    setRefJobId(result.job_id);
    setRefProgress({ completed: 0, total: 15, current_label: "Starting..." });
  };

  const handleSelectReference = async () => {
    if (!pendingRef) return;
    const result = await selectCharacterReference(pendingRef);
    setSelectedRef(result.selected);
    setPendingRef(null);
  };

  const handleGenerateFrames = async () => {
    const result = await generateCharacterFrames();
    setFrameJobId(result.job_id);
    setFrameProgress({ completed: 0, total: 300, current_label: "Starting..." });
  };

  const handleGenerateMissing = async () => {
    const result = await generateMissingCharacterFrames();
    setFrameJobId(result.job_id);
    setFrameProgress({ completed: 0, total: 0, current_label: "Starting..." });
  };

  const handleGenerateVariants = async () => {
    const result = await generateCharacterVariants();
    setVariantJobId(result.job_id);
    setVariantProgress({ completed: 0, total: 0, current_label: "Starting..." });
  };

  const handleReprocessBackgrounds = async () => {
    const result = await reprocessCharacterBackgrounds();
    setReprocessJobId(result.job_id);
    setReprocessProgress({ completed: 0, total: 0, current_label: "Starting..." });
  };

  const handleRegenerate = async (frameId: string) => {
    setRegeneratingId(frameId);
    await regenerateCharacterFrame(frameId);
    await fetchManifest();
    setRegeneratingId(null);
  };

  const handleClearAll = async () => {
    if (!confirm("Delete all frames and references? You'll need to regenerate everything.")) return;
    await clearAllCharacterFrames();
    setManifest(null);
    setReferences([]);
    setSelectedRef(null);
    setPendingRef(null);
  };

  const frameCount = manifest?.frames?.length ?? 0;
  const missingCount = manifest?.missing_count ?? 0;
  const isGeneratingRefs = !!refJobId;
  const isGeneratingFrames = !!frameJobId;
  const isGeneratingVariants = !!variantJobId;
  const isReprocessing = !!reprocessJobId;
  const refPct = refProgress.total > 0 ? refProgress.completed / refProgress.total : 0;
  const framePct = frameProgress.total > 0 ? frameProgress.completed / frameProgress.total : 0;
  const variantPct = variantProgress.total > 0 ? variantProgress.completed / variantProgress.total : 0;
  const reprocessPct = reprocessProgress.total > 0 ? reprocessProgress.completed / reprocessProgress.total : 0;
  const hasSelectedRef = !!selectedRef;

  // Count frames needing variants (variant_count > 1)
  const framesNeedingVariants = (manifest?.frames ?? []).filter((f) => (f.variant_count ?? 1) > 1).length;
  const tier1Count = (manifest?.frames ?? []).filter((f) => (f.variant_count ?? 1) === 5).length;
  const tier2Count = (manifest?.frames ?? []).filter((f) => (f.variant_count ?? 1) === 3).length;

  // Group frames by expression
  const grouped = (manifest?.frames ?? []).reduce(
    (acc, frame) => {
      const key = frame.expression;
      if (!acc[key]) acc[key] = [];
      acc[key].push(frame);
      return acc;
    },
    {} as Record<string, FrameEntry[]>,
  );

  if (loading) {
    return (
      <div className="p-6">
        <div className="text-neutral-400 text-sm">Loading character data...</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-neutral-100">Eli Character Frames</h2>
          <p className="text-sm text-neutral-400 mt-1">
            Two-step process: first select a reference style, then generate all pose frames from it.
          </p>
        </div>
        {(frameCount > 0 || hasSelectedRef || references.length > 0) && (
          <button
            onClick={handleClearAll}
            disabled={isGeneratingRefs || isGeneratingFrames}
            className="text-xs px-3 py-1.5 bg-red-900/40 hover:bg-red-800/60 text-red-400 hover:text-red-300 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition-colors"
          >
            Delete All Frames
          </button>
        )}
      </div>

      {/* ===== SECTION 1: Reference Image ===== */}
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-neutral-200 uppercase tracking-wider">
            Step 1: Reference Image
          </h3>
          {hasSelectedRef && (
            <span className="text-xs px-2 py-0.5 bg-emerald-500/20 text-emerald-400 rounded-full">
              Selected
            </span>
          )}
        </div>

        {/* Selected reference display */}
        {hasSelectedRef && !isGeneratingRefs && (
          <div className="flex items-start gap-4">
            <div className="relative w-32 shrink-0">
              <img
                src={assetUrl(`/static/character/references/${selectedRef}`)}
                alt="Selected reference"
                className="w-full rounded-lg border-2 border-emerald-500/50"
              />
              <div className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-emerald-500 rounded-full flex items-center justify-center">
                <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
            </div>
            <div className="flex flex-col gap-2 pt-1">
              <span className="text-xs text-neutral-400">Current reference: {selectedRef}</span>
              <button
                onClick={handleGenerateReferences}
                disabled={isGeneratingRefs}
                className="text-xs px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 rounded-lg text-neutral-300 transition-colors w-fit"
              >
                Change Reference
              </button>
            </div>
          </div>
        )}

        {/* Generate references button (when none exist) */}
        {!hasSelectedRef && references.length === 0 && !isGeneratingRefs && (
          <button
            onClick={handleGenerateReferences}
            disabled={isGeneratingRefs}
            className="text-sm px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
          >
            Generate Reference Images
          </button>
        )}

        {/* Progress bar for reference generation */}
        {isGeneratingRefs && (
          <div className="space-y-2">
            <div className="flex items-center gap-3 text-xs text-neutral-300">
              <span className="w-3 h-3 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
              <span>{refProgress.completed} / {refProgress.total} candidates</span>
              <span className="text-neutral-500">{refProgress.current_label}</span>
            </div>
            <div className="h-1.5 bg-neutral-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-violet-500 rounded-full transition-all duration-300"
                style={{ width: `${refPct * 100}%` }}
              />
            </div>
          </div>
        )}

        {/* Reference candidate grid */}
        {references.length > 0 && !hasSelectedRef && !isGeneratingRefs && (
          <div className="space-y-3">
            <p className="text-xs text-neutral-400">
              Click to select a reference style, then confirm with "Use This Reference".
            </p>
            <div className="grid grid-cols-5 gap-3">
              {references.map((ref) => (
                <button
                  key={ref}
                  onClick={() => setPendingRef(ref)}
                  className={`relative rounded-lg overflow-hidden border-2 transition-all ${
                    pendingRef === ref
                      ? "border-violet-500 ring-2 ring-violet-500/30 scale-[1.02]"
                      : "border-neutral-700/50 hover:border-neutral-500"
                  }`}
                >
                  <img
                    src={assetUrl(`/static/character/references/${ref}`)}
                    alt={ref}
                    className="w-full aspect-video object-cover"
                  />
                  {pendingRef === ref && (
                    <div className="absolute inset-0 bg-violet-500/10" />
                  )}
                  <div className="px-1.5 py-1 text-[9px] text-neutral-500 truncate">{ref}</div>
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleSelectReference}
                disabled={!pendingRef}
                className="text-sm px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
              >
                Use This Reference
              </button>
              <button
                onClick={handleGenerateReferences}
                className="text-sm px-4 py-2 bg-neutral-800 hover:bg-neutral-700 rounded-lg text-neutral-300 transition-colors"
              >
                Regenerate Candidates
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ===== SECTION 2: Frame Library ===== */}
      <div className={`space-y-4 ${!hasSelectedRef ? "opacity-40 pointer-events-none" : ""}`}>
        <h3 className="text-sm font-semibold text-neutral-200 uppercase tracking-wider">
          Step 2: Frame Library
        </h3>

        {/* Status + Actions */}
        <div className="flex items-center gap-4">
          <div className="text-sm text-neutral-300">
            {frameCount > 0 ? (
              <span className="text-emerald-400">
                {frameCount * 2} frames generated
                {missingCount > 0 && (
                  <span className="text-amber-400 ml-2">({missingCount * 2} missing)</span>
                )}
              </span>
            ) : (
              <span className="text-neutral-500">No frames generated yet</span>
            )}
          </div>

          {missingCount > 0 && (
            <button
              onClick={handleGenerateMissing}
              disabled={isGeneratingFrames || !hasSelectedRef}
              className="text-sm px-4 py-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
            >
              Generate Missing ({missingCount * 2})
            </button>
          )}

          <button
            onClick={handleGenerateFrames}
            disabled={isGeneratingFrames || !hasSelectedRef}
            className="text-sm px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
          >
            {isGeneratingFrames ? "Generating..." : frameCount > 0 ? "Regenerate All" : "Generate All Frames"}
          </button>

          {frameCount > 0 && (
            <button
              onClick={handleReprocessBackgrounds}
              disabled={isReprocessing || isGeneratingFrames}
              className="text-sm px-4 py-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
            >
              {isReprocessing ? "Fixing..." : "Fix Backgrounds"}
            </button>
          )}
        </div>

        {/* Progress bar for background reprocessing */}
        {isReprocessing && (
          <div className="space-y-2">
            <div className="flex items-center gap-3 text-xs text-neutral-300">
              <span className="w-3 h-3 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
              <span>{reprocessProgress.completed} / {reprocessProgress.total} frames checked</span>
              <span className="text-neutral-500">{reprocessProgress.current_label}</span>
            </div>
            <div className="h-1.5 bg-neutral-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-amber-500 rounded-full transition-all duration-300"
                style={{ width: `${reprocessPct * 100}%` }}
              />
            </div>
          </div>
        )}

        {/* Progress bar for frame generation */}
        {isGeneratingFrames && (
          <div className="space-y-2">
            <div className="flex items-center gap-3 text-xs text-neutral-300">
              <span className="w-3 h-3 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
              <span>{frameProgress.completed} / {frameProgress.total} frames</span>
              <span className="text-neutral-500">{frameProgress.current_label}</span>
            </div>
            <div className="h-1.5 bg-neutral-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-violet-500 rounded-full transition-all duration-300"
                style={{ width: `${framePct * 100}%` }}
              />
            </div>
          </div>
        )}

        {/* Frame grid grouped by expression */}
        {Object.entries(grouped).map(([expression, frames]) => (
          <div key={expression}>
            <h3 className="text-sm font-medium text-neutral-300 mb-2 capitalize">{expression}</h3>
            <div className="grid grid-cols-4 gap-3">
              {frames.map((frame) => (
                <div
                  key={frame.id}
                  className="group relative bg-neutral-800 rounded-lg overflow-hidden border border-neutral-700/50 hover:border-neutral-600 transition-colors"
                >
                  <div className="flex">
                    <img
                      src={assetUrl(`/static/character/frames/${frame.file_closed}`)}
                      alt={`${frame.id} closed`}
                      className="w-1/2 aspect-square object-cover"
                    />
                    <img
                      src={assetUrl(`/static/character/frames/${frame.file_open}`)}
                      alt={`${frame.id} open`}
                      className="w-1/2 aspect-square object-cover"
                    />
                  </div>
                  <div className="px-2 py-1.5">
                    <div className="text-[10px] text-neutral-400 truncate">{frame.pose}</div>
                    {frame.gesture !== "none" && (
                      <div className="text-[9px] text-neutral-500">{frame.gesture}</div>
                    )}
                  </div>
                  {/* Regenerate overlay */}
                  <button
                    onClick={() => handleRegenerate(frame.id)}
                    disabled={regeneratingId === frame.id}
                    className="absolute inset-0 flex items-center justify-center bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <span className="text-xs text-neutral-200 font-medium">
                      {regeneratingId === frame.id ? "Regenerating..." : "Regenerate"}
                    </span>
                  </button>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* ===== SECTION 2.5: Frame Variants ===== */}
      <div className={`space-y-4 ${frameCount === 0 ? "opacity-40 pointer-events-none" : ""}`}>
        <h3 className="text-sm font-semibold text-neutral-200 uppercase tracking-wider">
          Step 3: Frame Variants
        </h3>
        <p className="text-xs text-neutral-400">
          Generate body micro-variations per expression for a more alive/animated character.
          {tier1Count > 0 && (
            <span className="ml-1">
              Tier 1 ({tier1Count} frames): 5 variants each. Tier 2 ({tier2Count} frames): 3 variants each.
            </span>
          )}
        </p>

        <div className="flex items-center gap-4">
          <button
            onClick={handleGenerateVariants}
            disabled={isGeneratingVariants || isGeneratingFrames || frameCount === 0}
            className="text-sm px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
          >
            {isGeneratingVariants ? "Generating..." : "Generate Variants"}
          </button>
          {framesNeedingVariants > 0 && (
            <span className="text-xs text-neutral-400">
              {framesNeedingVariants} frames will get variants
            </span>
          )}
        </div>

        {isGeneratingVariants && (
          <div className="space-y-2">
            <div className="flex items-center gap-3 text-xs text-neutral-300">
              <span className="w-3 h-3 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
              <span>{variantProgress.completed} / {variantProgress.total} variant frames</span>
              <span className="text-neutral-500">{variantProgress.current_label}</span>
            </div>
            <div className="h-1.5 bg-neutral-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-violet-500 rounded-full transition-all duration-300"
                style={{ width: `${variantPct * 100}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* ===== SECTION 3: Overlay Position ===== */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-neutral-200 uppercase tracking-wider">
          Overlay Position (Default)
        </h3>
        <p className="text-xs text-neutral-400">
          Set the default position for the Eli overlay on all videos. Can be overridden per-video in the timeline.
        </p>
        <EliPositionPicker
          value={eliPosition}
          onChange={(pos) => {
            setEliPosition(pos);
            api.put("/api/brand", { eli_position: pos });
          }}
        />
      </div>
    </div>
  );
}
