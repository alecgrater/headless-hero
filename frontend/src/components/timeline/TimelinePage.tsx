import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import {
  Film,
  ImageIcon,
  Info,
  Layers,
  ListVideo,
  PanelsTopLeft,
  Search,
  Smartphone,
  Video,
  Zap,
  type LucideIcon,
} from "lucide-react";
import api, {
  assetUrl,
  exportLongFormSEO,
  exportLongFormThumbnail,
  exportShortFormSEO,
  exportTest,
  fetchScriptCost,
  generateEli,
  generateFX,
  generateShortFormThumbnailsAll,
  generateShortFormThumbnailsBatch,
  getRenderedShortsStatus,
  getShortFormThumbnailsStatus,
  getYouTubeOAuthStatus,
  pollEliJob,
  pollFXJob,
  pollShortFormJob,
  renderShortAll,
  renderShortBatch,
} from "../../api";
import type { ExportTestOptions } from "../../api";
import type { MediaAssignment } from "../../api";
import type { ScriptCostBreakdownItem } from "../../api";
import { showToast } from "../ToastContainer";
import type { ScriptContent } from "../../types/script";
import type { ScriptRead } from "../../types/script";
import type { SEOMetadata, ShortFormSEO, ShortFormSEOMetadata, ThumbnailConcept } from "../../types/render";
import type { SaveState } from "../../App";
import type { MicroTimelineHandle } from "./SceneMicroTimeline";
import ExportPanel from "./ExportPanel";
import ExportTestModal from "./ExportTestModal";
import MediaSourcesTab from "./MediaSourcesTab";
import SegmentsTab from "./SegmentsTab";
import PipelineSteps from "./PipelineSteps";
import PropertiesPanel from "./PropertiesPanel";
import ThumbnailModal from "./ThumbnailModal";
import TimelineLanes from "./TimelineLanes";
import VoiceSetupModal from "../brand/VoiceSetupModal";
import MiniProgressBar from "../MiniProgressBar";
import ShortFormStatusPill from "./short-form/ShortFormStatusPill";
import ShortFormTab from "./short-form/ShortFormTab";
import ShortFormThumbnailsCard from "./short-form/ShortFormThumbnailsCard";
import { Tooltip } from "../ui/Tooltip";
import { useRenderState } from "./useRenderState";
import { useTimelineState } from "./useTimelineState";
import { useMediaReview } from "./useMediaReview";
import { useOperationProgress } from "../../hooks/useOperationProgress";

import { useVoicePicker } from "./useVoicePicker";
import { useKeyboardShortcuts, ShortcutHelpOverlay } from "./useKeyboardShortcuts";

interface Props {
  scriptId: string;
  onBack: () => void;
  onSaveStateChange?: (state: SaveState) => void;
  onNavigateToSettings?: () => void;
  onRecordVoiceover?: () => void;
}

export default function TimelinePage({ scriptId, onBack, onSaveStateChange, onNavigateToSettings, onRecordVoiceover }: Props) {
  const [script, setScript] = useState<ScriptRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetch = async () => {
      setLoading(true);
      try {
        const res = await api.get(`/api/scripts/${scriptId}`);
        if (cancelled) return;
        if (res.ok) {
          setScript(res.data as ScriptRead);
        } else {
          setError("Failed to load script");
        }
      } catch {
        if (!cancelled) setError("Could not reach the backend.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetch();
    return () => {
      cancelled = true;
    };
  }, [scriptId]);

  if (loading) {
    return (
      <div className="text-center py-20 space-y-4">
        <div className="inline-block w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-neutral-400">Loading timeline...</p>
      </div>
    );
  }

  if (error || !script) {
    return (
      <div className="text-center py-20 space-y-4">
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300 inline-block">
          {error ?? "Script not found"}
        </div>
        <div>
          <button
            onClick={onBack}
            className="text-sm px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 rounded-lg transition-colors text-neutral-300"
          >
            &larr; Go Back
          </button>
        </div>
      </div>
    );
  }

  return <TimelineEditor scriptId={scriptId} initialContent={script.script} title={script.topic_title} onBack={onBack} onSaveStateChange={onSaveStateChange} onNavigateToSettings={onNavigateToSettings} onRecordVoiceover={onRecordVoiceover} />;
}

interface BatchProgressProps {
  progress: {
    total: number;
    completed: number;
    failed: number;
    currentSceneName: string | null;
    startedAt: number | null;
    initialEstimatedSeconds?: number | null;
  };
  label: string;
}

function BatchProgressBar({ progress, label }: BatchProgressProps) {
  if (progress.total === 0) return null;
  const done = progress.completed + progress.failed;
  const pct = done / progress.total;
  const elapsed = progress.startedAt ? (Date.now() - progress.startedAt) / 1000 : 0;
  const avgPerScene = done > 0 ? elapsed / done : 0;
  const perSceneRemaining = (progress.total - done) * avgPerScene;

  // Use per-scene average once scenes start completing; fall back to initial estimate
  let etaStr = "";
  if (done > 0 && perSceneRemaining > 0) {
    etaStr = perSceneRemaining < 60
      ? `~${Math.round(perSceneRemaining)}s left`
      : `~${Math.round(perSceneRemaining / 60)}m left`;
  } else if (done === 0 && progress.initialEstimatedSeconds && progress.initialEstimatedSeconds > 0) {
    const initRemaining = Math.max(0, progress.initialEstimatedSeconds - elapsed);
    if (initRemaining > 0) {
      etaStr = initRemaining < 60
        ? `~${Math.round(initRemaining)}s left`
        : `~${Math.round(initRemaining / 60)}m left`;
    }
  }

  // For progress bar: use per-scene pct when available, else time-based from initial estimate
  let barPct = pct;
  if (done === 0 && progress.initialEstimatedSeconds && progress.initialEstimatedSeconds > 0) {
    barPct = Math.min(0.95, Math.pow(elapsed / progress.initialEstimatedSeconds, 2));
  }

  const allDone = done >= progress.total;

  return (
    <div className={`px-4 py-2 border-b border-neutral-800 shrink-0 ${allDone ? "bg-emerald-500/10" : "bg-violet-500/10"}`}>
      <div className="flex items-center gap-3 text-xs">
        {!allDone && (
          <span className="w-3 h-3 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
        )}
        <span className="text-neutral-300">
          {allDone ? (
            progress.failed > 0 ? (
              <>Done &middot; {progress.completed} of {progress.total} generated, {progress.failed} failed</>
            ) : (
              <>All {progress.total} {label} generated &#10003;</>
            )
          ) : (
            <>Generating {label} &middot; {done} of {progress.total} done{progress.currentSceneName && <span className="text-neutral-500 ml-1">({progress.currentSceneName})</span>}</>
          )}
        </span>
        {etaStr && <span className="text-neutral-500">{etaStr}</span>}
        <div className="flex-1 h-1.5 bg-neutral-800 rounded-full overflow-hidden ml-2">
          <div
            className={`h-full rounded-full transition-all duration-300 ${allDone ? "bg-emerald-500" : "bg-violet-500"}`}
            style={{ width: `${barPct * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
}

function formatCost(cost: number) {
  if (cost === 0) return "$0.00";
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(2)}`;
}

function formatCostMetrics(item: ScriptCostBreakdownItem) {
  const parts: string[] = [];
  if (item.call_count > 0) parts.push(`${item.call_count} call${item.call_count !== 1 ? "s" : ""}`);
  if (item.images > 0) parts.push(`${item.images} image${item.images !== 1 ? "s" : ""}`);
  if (item.characters > 0) parts.push(`${item.characters.toLocaleString()} chars`);
  if (item.input_tokens + item.output_tokens > 0) {
    parts.push(`${(item.input_tokens + item.output_tokens).toLocaleString()} tok`);
  }
  return parts.join(" · ");
}

function CostBreakdownPopover({
  totalCost,
  breakdown,
}: {
  totalCost: number;
  breakdown: ScriptCostBreakdownItem[];
}) {
  return (
    <div className="absolute right-0 top-8 z-40 w-80 rounded-lg border border-neutral-700 bg-neutral-950 shadow-2xl shadow-black/50">
      <div className="flex items-center justify-between border-b border-neutral-800 px-3 py-2">
        <span className="text-xs font-semibold text-neutral-200">Cost breakdown</span>
        <span className="text-xs font-mono text-emerald-300">{formatCost(totalCost)}</span>
      </div>
      <div className="max-h-80 overflow-y-auto py-1">
        {breakdown.length > 0 ? (
          breakdown.map((item) => (
            <div key={`${item.task}-${item.service}-${item.operation}-${item.model}`} className="px-3 py-2 hover:bg-neutral-900 transition-colors">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium text-neutral-100">{item.task}</p>
                  <p className="mt-0.5 truncate text-[11px] text-neutral-500">
                    {[item.service, item.model].filter(Boolean).join(" · ")}
                  </p>
                  <p className="mt-1 text-[11px] text-neutral-500">{formatCostMetrics(item)}</p>
                </div>
                <span className="shrink-0 text-xs font-mono text-emerald-300">
                  {formatCost(item.total_cost)}
                </span>
              </div>
            </div>
          ))
        ) : (
          <div className="px-3 py-5 text-center text-xs text-neutral-500">
            No tracked API usage yet.
          </div>
        )}
      </div>
    </div>
  );
}

function sceneProgressCounter(step: string, progress: number, total: number): string {
  const match = step.match(/(\d+)\s*\/\s*(\d+)/);
  if (match) return `${match[1]}/${match[2]}`;
  if (total <= 0) return "";

  const current = Math.min(total, Math.max(1, Math.floor(progress * total) + 1));
  return `${current}/${total}`;
}

type ViewerFormat = "long-form" | "short-form";
type ViewerAsset = "render" | "thumbnails" | "seo";

const FORMAT_OPTIONS: { key: ViewerFormat; label: string; Icon: LucideIcon }[] = [
  { key: "long-form", label: "Long Form", Icon: Film },
  { key: "short-form", label: "Short Form", Icon: Smartphone },
];

const ASSET_OPTIONS: { key: ViewerAsset; label: string; Icon: LucideIcon }[] = [
  { key: "render", label: "Render", Icon: Video },
  { key: "thumbnails", label: "Thumbnails", Icon: ImageIcon },
  { key: "seo", label: "SEO", Icon: Search },
];

const VIEWER_TAB_OPTIONS: { key: "timeline" | "media-sources" | "segments"; label: string; Icon: LucideIcon }[] = [
  { key: "timeline", label: "Timeline", Icon: ListVideo },
  { key: "media-sources", label: "Media Sources", Icon: PanelsTopLeft },
  { key: "segments", label: "Segments", Icon: Layers },
];
type ProductionTask = "lf-seo" | "sf-thumbnails" | "sf-seo" | "sf-renders";

function getCreationStatus(content: ScriptContent) {
  const allScenes = content.segments.flatMap((seg) => seg.scenes);
  const nonTitleScenes = allScenes.filter((sc) => !sc.is_title_card);
  const titleScenes = allScenes.filter((sc) => sc.is_title_card);
  const narratedScenes = allScenes.filter((sc) => sc.narration);
  const imageScenes = nonTitleScenes.filter((sc) => sc.visual_prompt);
  const eliScenes = nonTitleScenes.filter((sc) => sc.narration && !sc.contains_person);

  const titleCardsDone = titleScenes.length === 0 || titleScenes.every((sc) => sc.image_url);
  const audioDone = narratedScenes.length === 0 || narratedScenes.every((sc) => sc.audio_url);
  const imagesDone = imageScenes.length === 0 || imageScenes.every((sc) => sc.image_url || sc.frame_urls?.length || sc.video_url);
  const fxDone = nonTitleScenes.length === 0 || nonTitleScenes.every((sc) => sc.fx);
  const eliDone = eliScenes.length === 0 || eliScenes.every((sc) => sc.eli_overlay);

  return {
    titleCardsDone,
    audioDone,
    imagesDone,
    fxDone,
    eliDone,
    missingFXCount: nonTitleScenes.filter((sc) => !sc.fx).length,
    missingEliCount: eliScenes.filter((sc) => !sc.eli_overlay).length,
    eliSceneCount: eliScenes.length,
    hasTitleCards: titleScenes.length > 0,
  };
}

function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);
  return (
    <button
      onClick={async () => {
        setFailed(false);
        try {
          await navigator.clipboard.writeText(text);
        } catch {
          setFailed(true);
          setTimeout(() => setFailed(false), 1800);
          return;
        }
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      className={`text-xs px-2 py-1 bg-neutral-800 hover:bg-neutral-700 rounded transition-all duration-150 ${
        failed ? "text-red-400 scale-105" : copied ? "text-emerald-400 scale-105" : "text-neutral-400 scale-100"
      }`}
    >
      {failed ? "Copy failed" : copied ? "Copied!" : label}
    </button>
  );
}

function TagList({ tags }: { tags: string[] }) {
  const tagString = tags.join(", ");
  return (
    <div className="space-y-1">
      <p className="text-xs text-neutral-400 whitespace-pre-wrap select-all cursor-text bg-neutral-900/50 rounded p-2">
        {tagString}
      </p>
      <span className={`text-[10px] ${tagString.length > 500 ? "text-red-400" : "text-neutral-500"}`}>
        {tagString.length}/500 characters
      </span>
    </div>
  );
}

function formatShortFormSEO(item: ShortFormSEO): string {
  const sections = [
    `Short ${item.index}`,
    `Title:\n${item.title}`,
    `Description:\n${item.description}`,
  ];
  if (item.hashtags.length > 0) sections.push(`Hashtags:\n${item.hashtags.join(" ")}`);
  if (item.tags.length > 0) sections.push(`YouTube Tags:\n${item.tags.join(", ")}`);
  return sections.join("\n\n");
}

function compactProgressText(progress: number | null) {
  if (progress == null) return "";
  return `${Math.round(progress * 100)}%`;
}

function ProductionTaskButton({
  stepNumber,
  label,
  done,
  busy,
  missingCount,
  progress,
  disabled,
  onRunAll,
  onRunMissing,
  missingLabel,
  allTitle,
}: {
  stepNumber: number;
  label: string;
  done: boolean;
  busy: boolean;
  missingCount: number;
  progress: number | null;
  disabled: boolean;
  onRunAll: () => void;
  onRunMissing: () => void;
  missingLabel: string;
  allTitle: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const buttonStateClass = busy
    ? "bg-neutral-800/80 border-violet-500/40 text-neutral-200 shadow-[0_0_8px_rgba(139,92,246,0.15)]"
    : done
      ? "bg-emerald-500/8 border-emerald-500/25 text-emerald-400 hover:bg-emerald-500/15"
      : "bg-neutral-800/80 border-neutral-700/60 text-neutral-300 hover:bg-neutral-700/80 hover:border-neutral-600";
  const stepClass = busy
    ? "border-violet-400 bg-violet-500/10 text-violet-300 shadow-[0_0_6px_rgba(139,92,246,0.4)] animate-[pulseDot_2s_ease-in-out_infinite]"
    : done
      ? "border-emerald-400 bg-emerald-500/10 text-emerald-300 shadow-[0_0_6px_rgba(52,211,153,0.3)]"
      : "border-neutral-600 text-neutral-500";

  return (
    <div ref={ref} className="relative flex items-center gap-1.5 min-w-0">
      <span className={`w-[20px] h-[20px] rounded-full border text-[11px] font-bold flex items-center justify-center shrink-0 tabular-nums ${stepClass}`}>
        {stepNumber}
      </span>
      <div className="flex items-stretch flex-1 min-w-0">
        <button
          type="button"
          onClick={onRunAll}
          disabled={busy || disabled}
          className={`text-xs pl-3 pr-2 py-2 border border-r-0 rounded-l-lg font-medium transition-all flex items-center justify-center gap-1.5 flex-1 whitespace-nowrap disabled:opacity-50 ${buttonStateClass}`}
          title={allTitle}
        >
          {busy ? (
            <>
              <span className="w-3.5 h-3.5 border-2 border-violet-400/60 border-t-transparent rounded-full animate-spin" />
              {compactProgressText(progress) || "Running"}
            </>
          ) : done ? (
            `${label} ✓`
          ) : (
            label
          )}
        </button>
        <button
          type="button"
          onClick={() => setOpen((show) => !show)}
          disabled={busy || disabled}
          className="text-xs px-1.5 bg-neutral-800/80 border border-l-0 border-neutral-700/60 text-neutral-400 hover:bg-neutral-700/80 hover:text-neutral-200 rounded-r-lg transition-all flex items-center disabled:opacity-50"
          title={`${label} options`}
        >
          <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none">
            <path d="M3 5L6 8L9 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
      {open && (
        <div className="absolute top-full left-7 mt-1.5 w-56 bg-neutral-800/90 border border-neutral-700/60 rounded-xl shadow-2xl z-50 py-1.5">
          <button
            onClick={() => {
              setOpen(false);
              onRunMissing();
            }}
            disabled={missingCount === 0}
            className="w-full text-left px-3 py-1.5 text-sm text-neutral-300 hover:bg-neutral-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {missingLabel} ({missingCount})
          </button>
        </div>
      )}
    </div>
  );
}

function ProductionWorkflowRow({
  segmentCount,
  lfSeoDone,
  sfSeoDone,
  sfSeoMissingCount,
  sfThumbnailsDone,
  sfThumbnailsMissingCount,
  sfRendersDone,
  sfRendersMissingCount,
  busyTask,
  progress,
  seoGenerating,
  shortFormSeoGenerating,
  onGenerateLfSeo,
  onGenerateMissingLfSeo,
  onGenerateSfThumbnails,
  onGenerateMissingSfThumbnails,
  onGenerateSfSeo,
  onGenerateMissingSfSeo,
  onRenderSfVideos,
  onRenderMissingSfVideos,
}: {
  segmentCount: number;
  lfSeoDone: boolean;
  sfSeoDone: boolean;
  sfSeoMissingCount: number;
  sfThumbnailsDone: boolean;
  sfThumbnailsMissingCount: number;
  sfRendersDone: boolean;
  sfRendersMissingCount: number;
  busyTask: ProductionTask | null;
  progress: number | null;
  seoGenerating: boolean;
  shortFormSeoGenerating: boolean;
  onGenerateLfSeo: () => void;
  onGenerateMissingLfSeo: () => void;
  onGenerateSfThumbnails: () => void;
  onGenerateMissingSfThumbnails: () => void;
  onGenerateSfSeo: () => void;
  onGenerateMissingSfSeo: () => void;
  onRenderSfVideos: () => void;
  onRenderMissingSfVideos: () => void;
}) {
  const anyBusy = busyTask !== null || seoGenerating || shortFormSeoGenerating;
  const lfSeoBusy = seoGenerating || busyTask === "lf-seo";
  const sfSeoBusy = shortFormSeoGenerating || busyTask === "sf-seo";
  const sfThumbnailsBusy = busyTask === "sf-thumbnails";
  const sfRendersBusy = busyTask === "sf-renders";

  return (
    <div className="px-5 py-2 border-t border-neutral-800/60 shrink-0">
      <div className="grid w-full items-center gap-2 min-w-0" style={{ gridTemplateColumns: "max-content auto max-content auto max-content auto max-content auto max-content" }}>
        <ProductionTaskButton
          stepNumber={6}
          label="Generate LF SEO"
          done={lfSeoDone}
          busy={lfSeoBusy}
          disabled={anyBusy && !lfSeoBusy}
          missingCount={lfSeoDone ? 0 : 1}
          progress={busyTask === "lf-seo" ? progress : null}
          onRunAll={onGenerateLfSeo}
          onRunMissing={onGenerateMissingLfSeo}
          missingLabel="Generate Missing"
          allTitle="Generate long-form YouTube title, description, and tags"
        />
        <svg className="w-3 h-3 text-neutral-600/60 shrink-0" viewBox="0 0 12 12" fill="none">
          <path d="M4 2L8 6L4 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <ProductionTaskButton
          stepNumber={7}
          label="Generate SF Thumbnails"
          done={sfThumbnailsDone}
          busy={sfThumbnailsBusy}
          disabled={anyBusy && !sfThumbnailsBusy}
          missingCount={sfThumbnailsMissingCount}
          progress={busyTask === "sf-thumbnails" ? progress : null}
          onRunAll={onGenerateSfThumbnails}
          onRunMissing={onGenerateMissingSfThumbnails}
          missingLabel="Generate Missing"
          allTitle={`Generate vertical thumbnails for all ${segmentCount} short-form videos`}
        />
        <svg className="w-3 h-3 text-neutral-600/60 shrink-0" viewBox="0 0 12 12" fill="none">
          <path d="M4 2L8 6L4 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <ProductionTaskButton
          stepNumber={8}
          label="Generate SF SEO"
          done={sfSeoDone}
          busy={sfSeoBusy}
          disabled={anyBusy && !sfSeoBusy}
          missingCount={sfSeoMissingCount}
          progress={busyTask === "sf-seo" ? progress : null}
          onRunAll={onGenerateSfSeo}
          onRunMissing={onGenerateMissingSfSeo}
          missingLabel="Generate Missing"
          allTitle={`Generate upload SEO for all ${segmentCount} short-form videos`}
        />
        <svg className="w-3 h-3 text-neutral-600/60 shrink-0" viewBox="0 0 12 12" fill="none">
          <path d="M4 2L8 6L4 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <ProductionTaskButton
          stepNumber={9}
          label="Render SF Videos"
          done={sfRendersDone}
          busy={sfRendersBusy}
          disabled={anyBusy && !sfRendersBusy}
          missingCount={sfRendersMissingCount}
          progress={busyTask === "sf-renders" ? progress : null}
          onRunAll={onRenderSfVideos}
          onRunMissing={onRenderMissingSfVideos}
          missingLabel="Render Missing"
          allTitle={`Render all ${segmentCount} short-form videos`}
        />
        <svg className="w-3 h-3 invisible shrink-0" viewBox="0 0 12 12" fill="none" aria-hidden="true">
          <path d="M4 2L8 6L4 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <div aria-hidden="true" />
      </div>
    </div>
  );
}

function ExportSplitButton({
  exportTestJobId,
  showExportDropdown,
  exportDropdownRef,
  onOpenExport,
  onCancelExportTest,
  onToggleExportDropdown,
  onOpenExportTest,
}: {
  exportTestJobId: string | null;
  showExportDropdown: boolean;
  exportDropdownRef: RefObject<HTMLDivElement | null>;
  onOpenExport: () => void;
  onCancelExportTest: () => void;
  onToggleExportDropdown: () => void;
  onOpenExportTest: () => void;
}) {
  return (
    <div ref={exportDropdownRef} className="relative flex items-stretch shrink-0">
      <button
        onClick={exportTestJobId ? onCancelExportTest : onOpenExport}
        className={`text-xs pl-3 pr-2 py-2 border border-r-0 rounded-l-lg font-medium transition-all flex items-center justify-center gap-1.5 min-w-[7rem] whitespace-nowrap ${
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
          onClick={onToggleExportDropdown}
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
      {showExportDropdown && (
        <div className="absolute top-full right-0 mt-1.5 w-44 bg-neutral-800/90 border border-neutral-700/60 rounded-xl shadow-2xl z-50 py-1.5">
          <button
            onClick={onOpenExportTest}
            className="w-full text-left px-3 py-1.5 text-sm text-neutral-300 hover:bg-neutral-700 transition-colors"
          >
            Export Test
          </button>
        </div>
      )}
    </div>
  );
}

function ViewerSwitchRow({
  format,
  asset,
  activeTab,
  onFormatChange,
  onAssetChange,
  onTabChange,
}: {
  format: ViewerFormat;
  asset: ViewerAsset;
  activeTab: "timeline" | "media-sources" | "segments";
  onFormatChange: (format: ViewerFormat) => void;
  onAssetChange: (asset: ViewerAsset) => void;
  onTabChange: (tab: "timeline" | "media-sources" | "segments") => void;
}) {
  const renderTabSelector = format === "long-form" && asset === "render";

  return (
    <div className="px-5 py-2 border-t border-b border-neutral-800/60 shrink-0">
      <div className="flex items-center gap-3">
        <div className="inline-flex items-center p-1 bg-neutral-800/60 rounded-xl border border-neutral-700/40">
          {FORMAT_OPTIONS.map(({ key, label, Icon }) => (
            <button
              key={key}
              onClick={() => onFormatChange(key)}
              className={`flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium rounded-lg transition-all duration-200 whitespace-nowrap ${
                format === key ? "bg-violet-500/20 text-violet-100 shadow-sm" : "text-neutral-400 hover:text-neutral-200"
              }`}
            >
              <Icon className="w-3.5 h-3.5 shrink-0" />
              {label}
            </button>
          ))}
        </div>
        <div className="h-6 w-px bg-neutral-800" />
        <div className="inline-flex items-center p-1 bg-neutral-800/60 rounded-xl border border-neutral-700/40">
          {ASSET_OPTIONS.map(({ key, label, Icon }) => (
            <button
              key={key}
              onClick={() => onAssetChange(key)}
              className={`flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium rounded-lg transition-all duration-200 whitespace-nowrap ${
                asset === key ? "bg-violet-500/20 text-violet-100 shadow-sm" : "text-neutral-400 hover:text-neutral-200"
              }`}
            >
              <Icon className="w-3.5 h-3.5 shrink-0" />
              {label}
            </button>
          ))}
        </div>
        {renderTabSelector && (
          <>
            <div className="h-6 w-px bg-neutral-800" />
            <div className="inline-flex items-center p-1 bg-neutral-800/60 rounded-xl border border-neutral-700/40">
              {VIEWER_TAB_OPTIONS.map(({ key, label, Icon }) => (
                <button
                  key={key}
                  onClick={() => onTabChange(key)}
                  className={`relative flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium rounded-lg transition-all duration-200 whitespace-nowrap ${
                    activeTab === key ? "bg-violet-500/20 text-violet-100 shadow-sm" : "text-neutral-400 hover:text-neutral-200"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5 shrink-0" />
                  {label}
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function LongFormThumbnailsPanel({
  thumbnails,
  generating,
  onGenerate,
  onExport,
  exporting,
  progress,
}: {
  thumbnails: ThumbnailConcept[];
  generating: boolean;
  onGenerate: () => void;
  onExport: () => void;
  exporting: boolean;
  progress: { estimatedSeconds: number | null; active: boolean };
}) {
  return (
    <div className="flex-1 overflow-y-auto p-5">
      <section className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider">Long-Form Thumbnails</h3>
            <p className="text-xs text-neutral-500">{thumbnails.length} concept{thumbnails.length !== 1 ? "s" : ""} available</p>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <button
              onClick={onGenerate}
              disabled={generating}
              className="text-sm px-4 py-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-40 rounded-lg font-medium transition-colors flex items-center gap-2"
            >
              {generating && <span className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />}
              {generating ? "Regenerating..." : thumbnails.length > 0 ? "Regenerate Thumbnail" : "Generate Thumbnail"}
            </button>
            <button
              onClick={onExport}
              disabled={exporting || generating}
              className="text-sm px-4 py-2 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 disabled:opacity-40 rounded-lg font-medium transition-colors flex items-center gap-2"
            >
              {exporting && <span className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />}
              {exporting ? "Exporting..." : "Export"}
            </button>
          </div>
        </div>
        {generating && <MiniProgressBar estimatedSeconds={progress.estimatedSeconds} active={progress.active} />}
        {thumbnails.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {thumbnails.map((thumbnail) => (
              <article key={thumbnail.idx} className="rounded-lg border border-neutral-800 bg-neutral-900/70 overflow-hidden">
                {thumbnail.image_url ? (
                  <img
                    src={assetUrl(thumbnail.image_url)}
                    alt={thumbnail.title_text}
                    className="w-full aspect-video object-cover"
                  />
                ) : (
                  <div className="w-full aspect-video bg-red-500/10 flex items-center justify-center text-xs text-red-400 p-3">
                    {thumbnail.error ?? "No image generated"}
                  </div>
                )}
                <div className="p-3 flex items-center justify-between gap-3">
                  <p className="text-sm text-neutral-200 truncate">{thumbnail.title_text}</p>
                  {thumbnail.image_url && (
                    <a
                      href={assetUrl(thumbnail.image_url)}
                      download
                      className="text-xs px-2.5 py-1 bg-neutral-800 hover:bg-neutral-700 rounded text-neutral-300 transition-colors"
                    >
                      Download
                    </a>
                  )}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-neutral-800 bg-neutral-900/40 p-10 text-center">
            <p className="text-sm text-neutral-500">No long-form thumbnail concepts yet.</p>
          </div>
        )}
      </section>
    </div>
  );
}

function LongFormSeoPanel({
  metadata,
  generating,
  onGenerate,
  onExport,
  exporting,
  progress,
}: {
  metadata: SEOMetadata | null;
  generating: boolean;
  onGenerate: () => void;
  onExport: () => void;
  exporting: boolean;
  progress: { estimatedSeconds: number | null; active: boolean };
}) {
  return (
    <div className="flex-1 overflow-y-auto p-5">
      <section className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider">Long-Form SEO</h3>
            <p className="text-xs text-neutral-500">YouTube title, timestamped description, and tags.</p>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <button
              onClick={onGenerate}
              disabled={generating}
              className="text-sm px-4 py-2 bg-teal-600 hover:bg-teal-500 disabled:opacity-40 rounded-lg font-medium transition-colors flex items-center gap-2"
            >
              {generating && <span className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />}
              {generating ? "Generating..." : metadata ? "Regenerate Long SEO" : "Generate Long SEO"}
            </button>
            <button
              onClick={onExport}
              disabled={exporting || generating}
              className="text-sm px-4 py-2 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 disabled:opacity-40 rounded-lg font-medium transition-colors flex items-center gap-2"
            >
              {exporting && <span className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />}
              {exporting ? "Exporting..." : "Export"}
            </button>
          </div>
        </div>
        {generating && <MiniProgressBar estimatedSeconds={progress.estimatedSeconds} active={progress.active} />}
        {metadata ? (
          <div className="bg-neutral-900/80 border border-neutral-800 rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-neutral-400 uppercase">YouTube</span>
              <CopyButton text={`Title:\n${metadata.youtube.title}\n\nDescription:\n${metadata.youtube.description}\n\nTags:\n${metadata.youtube.tags.join(", ")}`} />
            </div>
            <p className="text-sm font-medium text-neutral-200">{metadata.youtube.title}</p>
            <p className="text-xs text-neutral-400 whitespace-pre-wrap">{metadata.youtube.description}</p>
            <TagList tags={metadata.youtube.tags} />
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-neutral-800 bg-neutral-900/40 p-10 text-center">
            <p className="text-sm text-neutral-500">No long-form SEO generated yet.</p>
          </div>
        )}
      </section>
    </div>
  );
}

function ShortFormSeoPanel({
  metadata,
  segmentCount,
  generating,
  onGenerate,
  onExport,
  exporting,
  progress,
}: {
  metadata: ShortFormSEOMetadata | null;
  segmentCount: number;
  generating: boolean;
  onGenerate: () => void;
  onExport: () => void;
  exporting: boolean;
  progress: { estimatedSeconds: number | null; active: boolean };
}) {
  const shorts = metadata?.shorts ?? [];
  return (
    <div className="flex-1 overflow-y-auto p-5">
      <section className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider">Short-Form SEO</h3>
            <p className="text-xs text-neutral-500">{shorts.length}/{segmentCount} shorts packaged for upload.</p>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <button
              onClick={onGenerate}
              disabled={generating}
              className="text-sm px-4 py-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-40 rounded-lg font-medium transition-colors flex items-center gap-2"
            >
              {generating && <span className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />}
              {generating ? "Generating..." : metadata ? "Regenerate Short SEO" : `Generate All ${segmentCount} Short SEO`}
            </button>
            <button
              onClick={onExport}
              disabled={exporting || generating}
              className="text-sm px-4 py-2 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 disabled:opacity-40 rounded-lg font-medium transition-colors flex items-center gap-2"
            >
              {exporting && <span className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />}
              {exporting ? "Exporting..." : "Export"}
            </button>
          </div>
        </div>
        {generating && <MiniProgressBar estimatedSeconds={progress.estimatedSeconds} active={progress.active} />}
        {shorts.length > 0 ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between rounded-lg border border-sky-500/20 bg-sky-500/10 px-3 py-2">
              <span className="text-xs text-sky-200">{shorts.length}/{segmentCount} shorts packaged</span>
              <CopyButton label="Copy All" text={shorts.map(formatShortFormSEO).join("\n\n---\n\n")} />
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              {shorts.slice().sort((a, b) => a.index - b.index).map((item) => (
                <article key={item.index} className="bg-neutral-900/80 border border-neutral-800 rounded-lg p-4 space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <span className="text-xs font-semibold text-neutral-400 uppercase">Short {item.index}</span>
                      <p className="mt-1 text-sm font-medium text-neutral-200">{item.title}</p>
                    </div>
                    <CopyButton text={formatShortFormSEO(item)} />
                  </div>
                  <p className="text-xs text-neutral-400 whitespace-pre-wrap">{item.description}</p>
                  {item.hashtags.length > 0 && (
                    <p className="text-xs text-sky-300 whitespace-pre-wrap select-all cursor-text bg-neutral-950/70 rounded p-2">
                      {item.hashtags.join(" ")}
                    </p>
                  )}
                  <TagList tags={item.tags} />
                </article>
              ))}
            </div>
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-neutral-800 bg-neutral-900/40 p-10 text-center">
            <p className="text-sm text-neutral-500">No short-form SEO generated yet.</p>
          </div>
        )}
      </section>
    </div>
  );
}

function TimelineEditor({
  scriptId,
  initialContent,
  title,
  onBack,
  onSaveStateChange,
  onNavigateToSettings,
  onRecordVoiceover,
}: {
  scriptId: string;
  initialContent: ScriptContent;
  title: string;
  onBack: () => void;
  onSaveStateChange?: (state: SaveState) => void;
  onNavigateToSettings?: () => void;
  onRecordVoiceover?: () => void;
}) {
  const state = useTimelineState(scriptId, initialContent);
  const render = useRenderState(
    scriptId,
    title,
    initialContent.seo_metadata,
    initialContent.short_form_seo_metadata,
  );
  // Operation progress tracking
  const fxProgress = useOperationProgress("fx_generation");
  const eliProgress = useOperationProgress("eli_generation");
  const titleCardProgress = useOperationProgress("title_card_generation");

  // Voice picker hook
  const voicePicker = useVoicePicker();

  const [showExport, setShowExport] = useState(false);
  const [exportInitialTab, setExportInitialTab] = useState<"render-long" | "render-short">("render-long");

  function openExportPanel() {
    setExportInitialTab("render-long");
    setShowExport(true);
  }

  function openExportOnShortForm() {
    setExportInitialTab("render-short");
    setShowExport(true);
  }
  const [showVoiceSetup, setShowVoiceSetup] = useState(false);
  const [pendingAudioAction, setPendingAudioAction] = useState<"all" | string | null>(null);
  const [generatingFX, setGeneratingFX] = useState(false);
  const [fxStep, setFxStep] = useState<string>("");
  const [fxProgressPct, setFxProgressPct] = useState<number>(0);
  const [generatingEli, setGeneratingEli] = useState(false);
  const [eliStep, setEliStep] = useState<string>("");
  const [eliProgressPct, setEliProgressPct] = useState<number>(0);
  const [eliProgressTotal, setEliProgressTotal] = useState<number>(0);
  const [confirmOverwrite, setConfirmOverwrite] = useState<"images" | "audio" | "fx" | "eli" | null>(null);
  const [pixelsPerSecond, setPixelsPerSecond] = useState(20);
  const [exportTestJobId, setExportTestJobId] = useState<string | null>(null);
  const [exportTestStep, setExportTestStep] = useState("");
  const [exportTestProgress, setExportTestProgress] = useState(0);
  const [exportTestEstimatedSeconds, setExportTestEstimatedSeconds] = useState<number | null>(null);
  const [showExportTestModal, setShowExportTestModal] = useState(false);
  const [titleCardGenerating, setTitleCardGenerating] = useState(false);
  const [titleCardGenerated, setTitleCardGenerated] = useState(false);
  const [titleCardTimestamp, setTitleCardTimestamp] = useState(0);
  const [thumbnailsInline, setThumbnailsInline] = useState<ThumbnailConcept[]>([]);
  const [thumbnailsInlineGenerating, setThumbnailsInlineGenerating] = useState(false);
  const [showThumbnailModal, setShowThumbnailModal] = useState(false);
  const [totalCost, setTotalCost] = useState<number>(0);
  const [costBreakdown, setCostBreakdown] = useState<ScriptCostBreakdownItem[]>([]);
  const [showCostBreakdown, setShowCostBreakdown] = useState(false);
  const [lastAudioGenTimestamp, setLastAudioGenTimestamp] = useState(0);
  const [lastFXGenTimestamp, setLastFXGenTimestamp] = useState(0);
  const [yoloRunning, setYoloRunning] = useState(false);
  const [youtubeConnected, setYoutubeConnected] = useState(false);
  const [yoloStep, setYoloStep] = useState<string | null>(null);
  const [yoloError, setYoloError] = useState<string | null>(null);
  const [yoloRenderRunning, setYoloRenderRunning] = useState(false);
  const [yoloRenderError, setYoloRenderError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"timeline" | "media-sources" | "segments">("timeline");
  const [viewerFormat, setViewerFormat] = useState<ViewerFormat>("long-form");
  const [viewerAsset, setViewerAsset] = useState<ViewerAsset>("render");
  const [sfThumbnailPaths, setSfThumbnailPaths] = useState<Record<number, string | undefined>>({});
  const [sfRenderPaths, setSfRenderPaths] = useState<Record<number, string | undefined>>({});
  const [productionBusyTask, setProductionBusyTask] = useState<ProductionTask | null>(null);
  const [productionProgress, setProductionProgress] = useState<number | null>(null);
  const [productionError, setProductionError] = useState<string | null>(null);
  const yoloCancelledRef = useRef(false);
  const productionBusyRef = useRef(false);
  const microTimelineRef = useRef<MicroTimelineHandle>(null);
  const costBreakdownRef = useRef<HTMLDivElement>(null);

  const media = useMediaReview({ scriptId, content: state.content });

  // Auto-switch to Media Sources tab when new assignments arrive
  useEffect(() => {
    if (media.hasPendingReview) setActiveTab("media-sources");
  }, [media.hasPendingReview]);

  const refreshShortFormThumbnailStatus = useCallback(async () => {
    try {
      const status = await getShortFormThumbnailsStatus(scriptId);
      setSfThumbnailPaths(status.paths);
      return status.paths;
    } catch {
      setSfThumbnailPaths({});
      return {};
    }
  }, [scriptId]);

  const refreshShortFormRenderStatus = useCallback(async () => {
    try {
      const status = await getRenderedShortsStatus(scriptId);
      setSfRenderPaths(status.paths);
      return status.paths;
    } catch {
      setSfRenderPaths({});
      return {};
    }
  }, [scriptId]);

  useEffect(() => {
    void refreshShortFormThumbnailStatus();
    void refreshShortFormRenderStatus();
  }, [refreshShortFormThumbnailStatus, refreshShortFormRenderStatus]);

  const refreshCost = useCallback(async () => {
    const data = await fetchScriptCost(scriptId);
    setTotalCost(data.total_cost);
    setCostBreakdown(data.breakdown);
  }, [scriptId]);

  // Fetch cost on mount
  useEffect(() => { refreshCost(); }, [refreshCost]);

  useEffect(() => {
    if (!showCostBreakdown) return;

    function handlePointerDown(event: PointerEvent) {
      const target = event.target;
      if (!(target instanceof Node)) return;
      if (costBreakdownRef.current?.contains(target)) return;
      setShowCostBreakdown(false);
    }

    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, [showCostBreakdown]);

  // Check YouTube connection on mount
  useEffect(() => {
    getYouTubeOAuthStatus().then((s) => setYoutubeConnected(s.youtube.connected));
  }, []);

  // Refresh cost when image or audio batch generation completes
  const imgDone = state.batchImageProgress.total > 0 && (state.batchImageProgress.completed + state.batchImageProgress.failed) >= state.batchImageProgress.total;
  const audioDone = state.batchAudioProgress.total > 0 && (state.batchAudioProgress.completed + state.batchAudioProgress.failed) >= state.batchAudioProgress.total;
  useEffect(() => { if (imgDone) refreshCost(); }, [imgDone, refreshCost]);
  useEffect(() => { if (audioDone) refreshCost(); }, [audioDone, refreshCost]);

  // Track audio/FX generation timestamps for staleness detection
  const prevBatchAudio = useRef(false);
  const prevSingleAudioCount = useRef(0);
  useEffect(() => {
    // Detect batch audio completion (was generating, now done)
    if (prevBatchAudio.current && !state.batchGeneratingAudio) {
      setLastAudioGenTimestamp(Date.now());
    }
    prevBatchAudio.current = state.batchGeneratingAudio;
  }, [state.batchGeneratingAudio]);
  useEffect(() => {
    // Detect single-scene audio completion (generating set was non-empty, now empty)
    const count = state.generatingAudioSceneIds.size;
    if (prevSingleAudioCount.current > 0 && count === 0) {
      setLastAudioGenTimestamp(Date.now());
    }
    prevSingleAudioCount.current = count;
  }, [state.generatingAudioSceneIds]);

  // Export split-button dropdown state
  const [showExportDropdown, setShowExportDropdown] = useState(false);
  const exportDropdownRef = useRef<HTMLDivElement>(null);

  // Auto-load thumbnails from disk on mount
  useEffect(() => {
    (async () => {
      try {
        const res = await api.get(`/api/thumbnail/${scriptId}`);
        if (res.ok) {
          const data = res.data as { concepts: ThumbnailConcept[] };
          if (data.concepts.length > 0) setThumbnailsInline(data.concepts);
        }
      } catch (_) { /* thumbnails are optional */ }
    })();
  }, [scriptId]);

  // Close export dropdown on outside click
  useEffect(() => {
    if (!showExportDropdown) return;
    const handler = (e: MouseEvent) => {
      if (exportDropdownRef.current && !exportDropdownRef.current.contains(e.target as Node)) {
        setShowExportDropdown(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showExportDropdown]);

  // Cancel refs for single async operations
  const fxCancelledRef = useRef(false);
  const eliCancelledRef = useRef(false);
  const titleCardCancelledRef = useRef(false);
  const thumbnailsCancelledRef = useRef(false);

  // Fetch render estimate when export panel opens
  useEffect(() => {
    if (!showExport) return;
    const scenes = state.content.segments.flatMap((seg) => seg.scenes);
    const sceneCount = scenes.length;
    const totalAudioDuration = scenes.reduce(
      (sum, sc) => sum + (sc.audio_duration_seconds ?? 0),
      0,
    );
    if (sceneCount > 0) {
      render.fetchEstimate(sceneCount, totalAudioDuration);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showExport]);

  // Surface save state to App top bar
  useEffect(() => {
    onSaveStateChange?.({
      isDirty: state.isDirty,
      saveStatus: state.saveStatus,
      save: state.save,
      canUndo: state.canUndo,
      undo: state.undo,
    });
  }, [state.isDirty, state.saveStatus, state.canUndo, state.save, state.undo, onSaveStateChange]);

  // JIT voice check: if no voice selected and no voices available, show modal
  const tryGenerateAudio = (action: "all" | "missing" | string) => {
    if (!voicePicker.selectedVoiceId && voicePicker.voices.length === 0) {
      setPendingAudioAction(action);
      setShowVoiceSetup(true);
      return;
    }
    if (action === "all") {
      state.generateAllAudio(voicePicker.selectedVoiceId);
    } else if (action === "missing") {
      state.generateAllAudio(voicePicker.selectedVoiceId, true);
    } else {
      state.generateAudio(action, voicePicker.selectedVoiceId);
    }
  };

  const handleVoiceSelected = (voiceId: string) => {
    voicePicker.setSelectedVoiceId(voiceId);
    setShowVoiceSetup(false);
    if (pendingAudioAction === "all") {
      state.generateAllAudio(voiceId);
    } else if (pendingAudioAction === "missing") {
      state.generateAllAudio(voiceId, true);
    } else if (pendingAudioAction) {
      state.generateAudio(pendingAudioAction, voiceId);
    }
    setPendingAudioAction(null);
  };

  // Find which segment the selected scene is in
  const selectedScene = state.selectedSceneId
    ? (() => {
        for (let si = 0; si < state.content.segments.length; si++) {
          const sc = state.content.segments[si].scenes.find(
            (s) => s.id === state.selectedSceneId,
          );
          if (sc) {
            return {
              scene: sc,
              segIdx: si,
              segName: state.content.segments[si].name,
            };
          }
        }
        return null;
      })()
    : null;

  // Build flat scene list for keyboard navigation
  const allSceneIds = state.content.segments.flatMap((seg) =>
    seg.scenes.map((sc) => sc.id),
  );

  const selectPrevScene = useCallback(() => {
    const idx = state.selectedSceneId ? allSceneIds.indexOf(state.selectedSceneId) : -1;
    if (idx > 0) state.selectScene(allSceneIds[idx - 1]);
    else if (allSceneIds.length > 0) state.selectScene(allSceneIds[allSceneIds.length - 1]);
  }, [allSceneIds, state]);

  const selectNextScene = useCallback(() => {
    const idx = state.selectedSceneId ? allSceneIds.indexOf(state.selectedSceneId) : -1;
    if (idx < allSceneIds.length - 1) state.selectScene(allSceneIds[idx + 1]);
    else if (allSceneIds.length > 0) state.selectScene(allSceneIds[0]);
  }, [allSceneIds, state]);

  const toggleAudioPreview = useCallback(() => {
    const audioEl = document.querySelector("aside audio") as HTMLAudioElement | null;
    if (audioEl) {
      if (audioEl.paused) audioEl.play();
      else audioEl.pause();
    }
  }, []);

  const deleteScene = useCallback(() => {
    // We don't actually delete scenes — split/merge is the pattern. No-op for safety.
  }, []);

  const { showHelp, setShowHelp } = useKeyboardShortcuts({
    selectPrevScene,
    selectNextScene,
    undo: state.undo,
    save: state.save,
    generateImage: () => {
      if (state.selectedSceneId) state.generateImage(state.selectedSceneId);
    },
    generateAllImages: () => state.generateAllImages(),
    openExport: () => openExportPanel(),
    toggleAudioPreview,
    deleteScene,
    splitAtPlayhead: () => {
      // Split is available via waveform click in SceneMicroTimeline — no direct
      // playhead access from TimelinePage, so this remains a no-op here.
    },
    placeMarker: () => {
      microTimelineRef.current?.placeMarkerAtPlayhead();
    },
    nudgeBack: (large: boolean) => {
      microTimelineRef.current?.nudge(large ? -10 : -1);
    },
    nudgeForward: (large: boolean) => {
      microTimelineRef.current?.nudge(large ? 10 : 1);
    },
    selectLane: (lane: number) => {
      const lanes: Array<"images" | "fx" | "inout"> = ["images", "fx", "inout"];
      microTimelineRef.current?.setSelectedLane(lanes[lane - 1] ?? null);
    },
    deselectMicroTimeline: () => {
      microTimelineRef.current?.setSelectedLane(null);
    },
    deleteMarker: () => {
      if (microTimelineRef.current?.hasSelectedMarker()) {
        microTimelineRef.current.deleteSelectedMarker();
      }
      // If no marker selected, intentionally do nothing
    },
  });

  // Scene stats
  const allScenes = state.content.segments.flatMap((seg) => seg.scenes);
  const sceneCount = allScenes.length;
  const segmentCount = state.content.segments.length;

  const [longFormSeoExporting, setLongFormSeoExporting] = useState(false);
  const [shortFormSeoExporting, setShortFormSeoExporting] = useState(false);
  const [longFormThumbnailExporting, setLongFormThumbnailExporting] = useState(false);

  const handleExportLongFormSEO = useCallback(async () => {
    if (!render.seoMetadata) {
      showToast("Generate Long SEO before exporting.", "info");
      return;
    }
    setLongFormSeoExporting(true);
    try {
      const result = await exportLongFormSEO(scriptId);
      const fileLabel = result.files[0] ?? "SEO file";
      showToast(`Saved ${fileLabel} to ${result.folder_path}`, "success");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed to export long-form SEO");
    } finally {
      setLongFormSeoExporting(false);
    }
  }, [render.seoMetadata, scriptId]);

  const handleExportShortFormSEO = useCallback(async () => {
    if (!render.shortFormSeoMetadata) {
      showToast("Generate Short SEO before exporting.", "info");
      return;
    }
    setShortFormSeoExporting(true);
    try {
      const result = await exportShortFormSEO(scriptId);
      showToast(`Saved ${result.files.length} short SEO files to ${result.folder_path}`, "success");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed to export short-form SEO");
    } finally {
      setShortFormSeoExporting(false);
    }
  }, [render.shortFormSeoMetadata, scriptId]);

  const handleExportLongFormThumbnail = useCallback(async () => {
    const hasThumbnail = render.thumbnails.some((t) => Boolean(t.image_url));
    if (!hasThumbnail) {
      showToast("Generate a thumbnail before exporting.", "info");
      return;
    }
    setLongFormThumbnailExporting(true);
    try {
      const result = await exportLongFormThumbnail(scriptId);
      showToast(`Saved ${result.file} to ${result.folder_path}`, "success");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed to export thumbnail");
    } finally {
      setLongFormThumbnailExporting(false);
    }
  }, [render.thumbnails, scriptId]);

  const totalDurationSec = allScenes.reduce(
    (sum, sc) => sum + (sc.duration_estimate_seconds ?? 0),
    0,
  );
  const durationMin = Math.floor(totalDurationSec / 60);
  const durationSec = Math.round(totalDurationSec % 60);
  const durationStr = `${durationMin}:${String(durationSec).padStart(2, "0")}`;
  const totalWords = allScenes.reduce(
    (sum, sc) => sum + (sc.narration ? sc.narration.split(/\s+/).filter(Boolean).length : 0),
    0,
  );

  // Media source counts (exclude title cards)
  const mediaCounts = allScenes
    .filter((sc) => !sc.is_title_card)
    .reduce(
      (acc, sc) => {
        const src = sc.media_source ?? "ai";
        acc[src] = (acc[src] ?? 0) + 1;
        return acc;
      },
      {} as Record<string, number>,
    );

  // Check if assets already exist for overwrite confirmation
  const hasExistingImages = allScenes.some((sc) => !sc.is_title_card && (sc.image_url || sc.frame_urls?.length));
  const hasExistingAudio = allScenes.some((sc) => sc.audio_url);
  const hasExistingFX = allScenes.some((sc) => sc.fx);

  // Check if ALL scenes are complete for each step (for completion checkmarks)
  const nonTitleScenes = allScenes.filter((sc) => !sc.is_title_card);
  const titleScenes = allScenes.filter((sc) => sc.is_title_card);
  // Audio generates for ALL scenes with narration (including title cards)
  const narratedScenes = allScenes.filter((sc) => sc.narration);
  // Image scenes: non-title scenes that have a visual_prompt (excludes aha_subtitle which are text-on-black)
  const imageScenes = nonTitleScenes.filter((sc) => sc.visual_prompt);
  // Title cards complete when all title card scenes have an image
  const allTitleCardsGenerated = titleScenes.length > 0 && titleScenes.every((sc) => sc.image_url);
  const allImagesGenerated = imageScenes.length > 0 && imageScenes.every((sc) => sc.image_url || sc.frame_urls?.length || sc.video_url);
  const allAudioGenerated = narratedScenes.length > 0 && narratedScenes.every((sc) => sc.audio_url);
  const allFXGenerated = nonTitleScenes.length > 0 && nonTitleScenes.every((sc) => sc.fx);

  // Missing counts for "Generate Missing (N)" labels
  const missingImageCount = imageScenes.filter((sc) => !sc.image_url && !sc.frame_urls?.length && !sc.video_url).length;
  const missingAudioCount = narratedScenes.filter((sc) => !sc.audio_url).length;
  const missingFXCount = nonTitleScenes.filter((sc) => !sc.fx).length;

  // Eli generates for narrated non-title scenes without a person (backend skips contains_person)
  const eliScenes = nonTitleScenes.filter((sc) => sc.narration && !sc.contains_person);
  const allEliGenerated = eliScenes.length > 0 && eliScenes.every((sc) => sc.eli_overlay);
  const hasExistingEli = allScenes.some((sc) => sc.eli_overlay);
  const missingEliCount = eliScenes.filter((sc) => !sc.eli_overlay).length;
  const sfThumbnailCount = Object.values(sfThumbnailPaths).filter(Boolean).length;
  const sfRenderCount = Object.values(sfRenderPaths).filter(Boolean).length;
  const shortFormSeoCount = render.shortFormSeoMetadata?.shorts.length ?? 0;
  const lfSeoDone = render.seoMetadata != null;
  const sfSeoDone = segmentCount > 0 && shortFormSeoCount >= segmentCount;
  const sfThumbnailsDone = segmentCount > 0 && sfThumbnailCount >= segmentCount;
  const sfRendersDone = segmentCount > 0 && sfRenderCount >= segmentCount;
  const sfSeoMissingCount = Math.max(0, segmentCount - shortFormSeoCount);
  const sfThumbnailMissingCount = Math.max(0, segmentCount - sfThumbnailCount);
  const sfRenderMissingCount = Math.max(0, segmentCount - sfRenderCount);

  const confirmAndGenerateImages = () => {
    if (hasExistingImages) {
      setConfirmOverwrite("images");
    } else {
      state.generateAllImages();
    }
  };

  const confirmAndGenerateAudio = () => {
    if (hasExistingAudio) {
      setConfirmOverwrite("audio");
    } else {
      tryGenerateAudio("all");
    }
  };

  const confirmAndGenerateFX = () => {
    if (hasExistingFX) {
      setConfirmOverwrite("fx");
    } else {
      handleGenerateFX();
    }
  };

  const handleGenerateFX = async () => {
    const sceneCount = state.content.segments.reduce((n, seg) => n + seg.scenes.length, 0);
    fxCancelledRef.current = false;
    setGeneratingFX(true);
    setFxStep("");
    setFxProgressPct(0);
    fxProgress.start(sceneCount);
    try {
      const res = await generateFX(scriptId);
      if (fxCancelledRef.current) return;
      if (res.ok) {
        const { job_id } = res.data as { job_id: string };
        await pollFXJob(job_id, (status) => {
          if (status.current_step) setFxStep(status.current_step);
          if (typeof status.progress === "number") setFxProgressPct(status.progress);
        });
        if (fxCancelledRef.current) return;
        const refreshed = await api.get(`/api/scripts/${scriptId}`);
        if (refreshed.ok && !fxCancelledRef.current) {
          const data = refreshed.data as { script: ScriptContent };
          state.setContent(data.script);
        }
      }
    } finally {
      setGeneratingFX(false);
      setFxStep("");
      setFxProgressPct(0);
      fxProgress.end(sceneCount);
      setLastFXGenTimestamp(Date.now());
      refreshCost();
    }
  };

  const generateMissingImages = () => state.generateAllImages(true);
  const generateMissingAudio = () => tryGenerateAudio("missing");
  const generateMissingFX = async () => {
    const sceneCount = missingFXCount;
    fxCancelledRef.current = false;
    setGeneratingFX(true);
    setFxStep("");
    setFxProgressPct(0);
    fxProgress.start(sceneCount);
    try {
      const res = await generateFX(scriptId, true);
      if (fxCancelledRef.current) return;
      if (res.ok) {
        const { job_id } = res.data as { job_id: string };
        await pollFXJob(job_id, (status) => {
          if (status.current_step) setFxStep(status.current_step);
          if (typeof status.progress === "number") setFxProgressPct(status.progress);
        });
        if (fxCancelledRef.current) return;
        const refreshed = await api.get(`/api/scripts/${scriptId}`);
        if (refreshed.ok && !fxCancelledRef.current) {
          const data = refreshed.data as { script: ScriptContent };
          state.setContent(data.script);
        }
      }
    } finally {
      setGeneratingFX(false);
      setFxStep("");
      setFxProgressPct(0);
      fxProgress.end(sceneCount);
      setLastFXGenTimestamp(Date.now());
    }
  };

  const handleGenerateEli = async () => {
    const sceneCount = eliScenes.length;
    eliCancelledRef.current = false;
    setGeneratingEli(true);
    setEliStep("");
    setEliProgressPct(0);
    setEliProgressTotal(sceneCount);
    eliProgress.start(sceneCount);
    try {
      const res = await generateEli(scriptId);
      if (eliCancelledRef.current) return;
      if (!res.ok) return;
      const { job_id } = res.data as { job_id: string };
      await pollEliJob(job_id, (status) => {
        if (status.current_step) setEliStep(status.current_step);
        if (typeof status.progress === "number") setEliProgressPct(status.progress);
      });
      if (eliCancelledRef.current) return;
      const refreshed = await api.get(`/api/scripts/${scriptId}`);
      if (refreshed.ok && !eliCancelledRef.current) {
        const data = refreshed.data as { script: ScriptContent };
        state.setContent(data.script);
      }
    } finally {
      setGeneratingEli(false);
      setEliStep("");
      setEliProgressPct(0);
      setEliProgressTotal(0);
      eliProgress.end(sceneCount);
      refreshCost();
    }
  };

  const confirmAndGenerateEli = () => {
    if (hasExistingEli) {
      setConfirmOverwrite("eli");
    } else {
      handleGenerateEli();
    }
  };

  const generateMissingEli = async () => {
    const sceneCount = missingEliCount;
    eliCancelledRef.current = false;
    setGeneratingEli(true);
    setEliStep("");
    setEliProgressPct(0);
    setEliProgressTotal(sceneCount);
    eliProgress.start(sceneCount);
    try {
      const res = await generateEli(scriptId, true);
      if (eliCancelledRef.current) return;
      if (!res.ok) return;
      const { job_id } = res.data as { job_id: string };
      await pollEliJob(job_id, (status) => {
        if (status.current_step) setEliStep(status.current_step);
        if (typeof status.progress === "number") setEliProgressPct(status.progress);
      });
      if (eliCancelledRef.current) return;
      const refreshed = await api.get(`/api/scripts/${scriptId}`);
      if (refreshed.ok && !eliCancelledRef.current) {
        const data = refreshed.data as { script: ScriptContent };
        state.setContent(data.script);
      }
    } finally {
      setGeneratingEli(false);
      setEliStep("");
      setEliProgressPct(0);
      setEliProgressTotal(0);
      eliProgress.end(sceneCount);
      refreshCost();
    }
  };

  const runProductionTask = async (task: ProductionTask, action: () => Promise<void>) => {
    if (productionBusyRef.current) return;
    productionBusyRef.current = true;
    setProductionBusyTask(task);
    setProductionProgress(null);
    setProductionError(null);
    try {
      await action();
    } catch (err) {
      setProductionError(err instanceof Error ? err.message : "Production task failed");
    } finally {
      productionBusyRef.current = false;
      setProductionBusyTask(null);
      setProductionProgress(null);
    }
  };

  const handleGenerateLfSeo = () => {
    void runProductionTask("lf-seo", async () => {
      await render.generateSEO();
    });
  };

  const handleGenerateMissingLfSeo = () => {
    if (lfSeoDone) return;
    handleGenerateLfSeo();
  };

  const handleGenerateSfSeo = () => {
    void runProductionTask("sf-seo", async () => {
      await render.generateShortFormSEO();
    });
  };

  const handleGenerateMissingSfSeo = () => {
    if (sfSeoDone) return;
    handleGenerateSfSeo();
  };

  const handleGenerateSfThumbnails = () => {
    void runProductionTask("sf-thumbnails", async () => {
      const { job_id } = await generateShortFormThumbnailsAll(scriptId);
      await pollShortFormJob(job_id, (status) => {
        if (typeof status.progress === "number") setProductionProgress(status.progress);
      });
      await refreshShortFormThumbnailStatus();
    });
  };

  const handleGenerateMissingSfThumbnails = () => {
    void runProductionTask("sf-thumbnails", async () => {
      const refreshed = await refreshShortFormThumbnailStatus();
      const indices = state.content.segments.map((_, idx) => idx).filter((idx) => !refreshed[idx]);
      if (indices.length === 0) return;
      const { job_id } = await generateShortFormThumbnailsBatch(scriptId, indices);
      await pollShortFormJob(job_id, (status) => {
        if (typeof status.progress === "number") setProductionProgress(status.progress);
      });
      await refreshShortFormThumbnailStatus();
    });
  };

  const handleRenderSfVideos = () => {
    void runProductionTask("sf-renders", async () => {
      const { job_id } = await renderShortAll(scriptId);
      await pollShortFormJob(job_id, (status) => {
        if (typeof status.progress === "number") setProductionProgress(status.progress);
      });
      await refreshShortFormRenderStatus();
    });
  };

  const handleRenderMissingSfVideos = () => {
    void runProductionTask("sf-renders", async () => {
      const refreshed = await refreshShortFormRenderStatus();
      const indices = state.content.segments.map((_, idx) => idx).filter((idx) => !refreshed[idx]);
      if (indices.length === 0) return;
      const { job_id } = await renderShortBatch(scriptId, indices);
      await pollShortFormJob(job_id, (status) => {
        if (typeof status.progress === "number") setProductionProgress(status.progress);
      });
      await refreshShortFormRenderStatus();
    });
  };

  const refreshScriptContent = useCallback(async () => {
    const refreshed = await api.get(`/api/scripts/${scriptId}`);
    if (!refreshed.ok) {
      throw new Error("Could not refresh project status");
    }
    const data = refreshed.data as { script: ScriptContent };
    state.setContent(data.script);
    return data.script;
  }, [scriptId, state]);

  const runMissingFXForYolo = useCallback(async (sceneCount: number) => {
    fxCancelledRef.current = false;
    setGeneratingFX(true);
    setFxStep("");
    setFxProgressPct(0);
    fxProgress.start(sceneCount);
    try {
      const res = await generateFX(scriptId, true);
      if (yoloCancelledRef.current) return;
      if (!res.ok) throw new Error("FX generation request failed");
      const { job_id } = res.data as { job_id: string };
      await pollFXJob(job_id, (status) => {
        if (status.current_step) setFxStep(status.current_step);
        if (typeof status.progress === "number") setFxProgressPct(status.progress);
      });
      if (!yoloCancelledRef.current) await refreshScriptContent();
    } finally {
      setGeneratingFX(false);
      setFxStep("");
      setFxProgressPct(0);
      fxProgress.end(sceneCount);
      setLastFXGenTimestamp(Date.now());
      refreshCost();
    }
  }, [fxProgress, refreshCost, refreshScriptContent, scriptId]);

  const runMissingEliForYolo = useCallback(async (sceneCount: number) => {
    eliCancelledRef.current = false;
    setGeneratingEli(true);
    setEliStep("");
    setEliProgressPct(0);
    setEliProgressTotal(sceneCount);
    eliProgress.start(sceneCount);
    try {
      const res = await generateEli(scriptId, true);
      if (yoloCancelledRef.current) return;
      if (!res.ok) throw new Error("Eli generation request failed");
      const { job_id } = res.data as { job_id: string };
      await pollEliJob(job_id, (status) => {
        if (status.current_step) setEliStep(status.current_step);
        if (typeof status.progress === "number") setEliProgressPct(status.progress);
      });
      if (!yoloCancelledRef.current) await refreshScriptContent();
    } finally {
      setGeneratingEli(false);
      setEliStep("");
      setEliProgressPct(0);
      setEliProgressTotal(0);
      eliProgress.end(sceneCount);
      refreshCost();
    }
  }, [eliProgress, refreshCost, refreshScriptContent, scriptId]);

  const runYoloCreationPipeline = useCallback(async (voiceId: string) => {
    let latest = await refreshScriptContent();
    let status = getCreationStatus(latest);

    if (!status.titleCardsDone && status.hasTitleCards) {
      setYoloStep("Title Cards");
      titleCardCancelledRef.current = false;
      setTitleCardGenerating(true);
      titleCardProgress.start(latest.segments.length);
      try {
        await state.generateTitleCardsStandalone(false);
        if (yoloCancelledRef.current) return false;
        setTitleCardGenerated(true);
        setTitleCardTimestamp(Date.now());
        thumbnailsCancelledRef.current = false;
        setThumbnailsInlineGenerating(true);
        try {
          const res = await api.post("/api/thumbnail/recomposite", {
            script_id: scriptId,
          });
          if (res.ok && !thumbnailsCancelledRef.current) {
            const data = res.data as { concepts: ThumbnailConcept[] };
            setThumbnailsInline(data.concepts);
          }
        } finally {
          setThumbnailsInlineGenerating(false);
        }
      } finally {
        setTitleCardGenerating(false);
        titleCardProgress.end(latest.segments.length);
      }
      latest = await refreshScriptContent();
      status = getCreationStatus(latest);
      if (yoloCancelledRef.current) return false;
    }

    if (!status.audioDone) {
      setYoloStep("Generate Audio");
      await state.generateAllAudio(voiceId, true);
      latest = await refreshScriptContent();
      status = getCreationStatus(latest);
      if (!status.audioDone) {
        throw new Error("Audio generation did not complete for every narrated scene");
      }
      if (yoloCancelledRef.current) return false;
    }

    if (!status.imagesDone) {
      setYoloStep("Generate Images");
      await state.generateAllImages(true);
      latest = await refreshScriptContent();
      status = getCreationStatus(latest);
      if (!status.imagesDone) {
        throw new Error("Image generation did not complete for every visual scene");
      }
      if (yoloCancelledRef.current) return false;
    }

    if (!status.fxDone) {
      setYoloStep("Generate FX");
      await runMissingFXForYolo(status.missingFXCount);
      latest = await refreshScriptContent();
      status = getCreationStatus(latest);
      if (!status.fxDone) {
        throw new Error("FX generation did not complete for every scene");
      }
      if (yoloCancelledRef.current) return false;
    }

    if (!status.eliDone) {
      setYoloStep("Add Eli");
      await runMissingEliForYolo(status.missingEliCount || status.eliSceneCount);
      latest = await refreshScriptContent();
      status = getCreationStatus(latest);
      if (!status.eliDone) {
        throw new Error("Eli generation did not complete for every eligible scene");
      }
      if (yoloCancelledRef.current) return false;
    }

    return true;
  }, [
    refreshScriptContent,
    runMissingEliForYolo,
    runMissingFXForYolo,
    scriptId,
    state,
    titleCardProgress,
  ]);

  const cancelYolo = () => {
    yoloCancelledRef.current = true;
    titleCardCancelledRef.current = true;
    thumbnailsCancelledRef.current = true;
    fxCancelledRef.current = true;
    eliCancelledRef.current = true;
    state.cancelImageGeneration();
    state.cancelAudioGeneration();
    setYoloRunning(false);
    setYoloStep(null);
  };

  const handleYolo = async () => {
    if (!voicePicker.selectedVoiceId) {
      setYoloError("Select a voice in settings before running YOLO");
      return;
    }

    setYoloError(null);
    setYoloRunning(true);
    yoloCancelledRef.current = false;
    let currentStep = "";

    try {
      currentStep = "YOLO Mode";
      await runYoloCreationPipeline(voicePicker.selectedVoiceId);
    } catch (err) {
      if (!yoloCancelledRef.current) {
        setYoloError(`Failed during ${currentStep}: ${err instanceof Error ? err.message : "Unknown error"}`);
      }
    } finally {
      if (!yoloCancelledRef.current) {
        setYoloRunning(false);
        setYoloStep(null);
      }
    }
  };

  const handleGenerateTitleCards = async (force = false) => {
    const segCount = state.content.segments.length;
    titleCardCancelledRef.current = false;
    setTitleCardGenerating(true);
    titleCardProgress.start(segCount);
    try {
      await state.generateTitleCardsStandalone(force);
      if (!titleCardCancelledRef.current) {
        setTitleCardGenerated(true);
        setTitleCardTimestamp(Date.now());
        await handleRecompositeThumbnailInline();
      }
    } finally {
      setTitleCardGenerating(false);
      titleCardProgress.end(segCount);
    }
  };

  const cancelTitleCards = () => {
    titleCardCancelledRef.current = true;
    setTitleCardGenerating(false);
  };

  const handleRecompositeThumbnailInline = async () => {
    thumbnailsCancelledRef.current = false;
    setThumbnailsInlineGenerating(true);
    try {
      const res = await api.post("/api/thumbnail/recomposite", {
        script_id: scriptId,
      });
      if (res.ok && !thumbnailsCancelledRef.current) {
        const data = res.data as { concepts: ThumbnailConcept[] };
        setThumbnailsInline(data.concepts);
      }
    } finally {
      setThumbnailsInlineGenerating(false);
    }
  };

  const handleYoloRender = useCallback(async () => {
    if (yoloRenderRunning) return;
    if (!voicePicker.selectedVoiceId) {
      setYoloRenderError("Select a voice in settings before running YOLO render");
      return;
    }

    setYoloRenderRunning(true);
    setYoloRenderError(null);
    setYoloStep(null);
    yoloCancelledRef.current = false;
    productionBusyRef.current = true;
    setProductionError(null);
    try {
      const creationComplete = await runYoloCreationPipeline(voicePicker.selectedVoiceId);
      if (!creationComplete || yoloCancelledRef.current) return;

      let latest = await refreshScriptContent();
      const segmentTotal = latest.segments.length;

      if (!render.seoMetadata) {
        setYoloStep("Generate LF SEO");
        setProductionBusyTask("lf-seo");
        setProductionProgress(null);
        await render.generateSEO();
      }

      const thumbnailPaths = await refreshShortFormThumbnailStatus();
      const missingThumbnailIndices = latest.segments
        .map((_, idx) => idx)
        .filter((idx) => !thumbnailPaths[idx]);
      if (missingThumbnailIndices.length > 0) {
        setYoloStep("Generate SF Thumbnails");
        setProductionBusyTask("sf-thumbnails");
        setProductionProgress(0);
        const { job_id } = missingThumbnailIndices.length === segmentTotal
          ? await generateShortFormThumbnailsAll(scriptId)
          : await generateShortFormThumbnailsBatch(scriptId, missingThumbnailIndices);
        await pollShortFormJob(job_id, (status) => {
          if (typeof status.progress === "number") setProductionProgress(status.progress);
        });
        await refreshShortFormThumbnailStatus();
      }

      const shortSeoCount = render.shortFormSeoMetadata?.shorts.length ?? 0;
      if (segmentTotal > 0 && shortSeoCount < segmentTotal) {
        setYoloStep("Generate SF SEO");
        setProductionBusyTask("sf-seo");
        setProductionProgress(null);
        await render.generateShortFormSEO();
      }

      const rendered = await refreshShortFormRenderStatus();
      const missingRenderIndices = latest.segments
        .map((_, idx) => idx)
        .filter((idx) => !rendered[idx]);
      if (missingRenderIndices.length > 0) {
        setYoloStep("Render SF Videos");
        setProductionBusyTask("sf-renders");
        setProductionProgress(0);
        const { job_id } = missingRenderIndices.length === segmentTotal
          ? await renderShortAll(scriptId)
          : await renderShortBatch(scriptId, missingRenderIndices);
        await pollShortFormJob(job_id, (status) => {
          if (typeof status.progress === "number") setProductionProgress(status.progress);
        });
        await refreshShortFormRenderStatus();
      }

      setProductionBusyTask(null);
      setProductionProgress(null);
      setYoloStep("Export Bundle");
      await render.yoloRender(() => {
        setShowExport(true);
        setExportInitialTab("render-long");
      });
      await refreshScriptContent();
      await refreshShortFormThumbnailStatus();
      await refreshShortFormRenderStatus();
    } catch (err) {
      setYoloRenderError(err instanceof Error ? err.message : "YOLO render failed");
    } finally {
      productionBusyRef.current = false;
      setProductionBusyTask(null);
      setProductionProgress(null);
      setYoloRenderRunning(false);
      setYoloStep(null);
    }
  }, [
    refreshScriptContent,
    refreshShortFormRenderStatus,
    refreshShortFormThumbnailStatus,
    render,
    runYoloCreationPipeline,
    scriptId,
    voicePicker.selectedVoiceId,
    yoloRenderRunning,
  ]);

  // Export test: start + poll
  const handleExportTest = async (options: ExportTestOptions) => {
    setShowExportTestModal(false);
    try {
      const { job_id } = await exportTest(scriptId, options);
      setExportTestJobId(job_id);
      setExportTestStep("Starting...");
      setExportTestProgress(0);
      setExportTestEstimatedSeconds(null);
    } catch {
      setExportTestJobId(null);
      setExportTestStep("");
      setExportTestProgress(0);
      setExportTestEstimatedSeconds(null);
    }
  };

  useEffect(() => {
    if (!exportTestJobId) return;
    let cancelled = false;
    const poll = async () => {
      while (!cancelled) {
        await new Promise((r) => setTimeout(r, 1500));
        if (cancelled) break;
        const res = await api.get(`/api/render/status/${exportTestJobId}`);
        if (!res.ok || cancelled) break;
        const data = res.data as { status: string; progress: number; current_step: string; error: string | null; estimated_seconds: number | null };
        setExportTestStep(data.current_step);
        setExportTestProgress(data.progress);
        if (data.estimated_seconds != null) setExportTestEstimatedSeconds(data.estimated_seconds);
        if (data.status === "completed") {
          setExportTestJobId(null);
          setExportTestStep("");
          setExportTestProgress(0);
          // Reload script to pick up new assets
          const refreshed = await api.get(`/api/scripts/${scriptId}`);
          if (refreshed.ok) {
            const d = refreshed.data as { script: ScriptContent };
            state.setContent(d.script);
          }
          break;
        }
        if (data.status === "failed") {
          setExportTestJobId(null);
          setExportTestStep("");
          setExportTestProgress(0);
          break;
        }
      }
    };
    poll();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [exportTestJobId]);

  // Handle scene selection
  const handleSelectScene = (sceneId: string) => {
    state.selectScene(sceneId);
  };

  // Handle time-based scene split via backend
  const handleSplitSceneAtTime = useCallback(async (splitTimeMs: number) => {
    if (!state.selectedSceneId) return;
    // Clear debounce to prevent auto-save race condition
    const saved = await state.save();
    if (!saved) return;
    const res = await api.post(`/api/scripts/${scriptId}/split-scene`, {
      scene_id: state.selectedSceneId,
      split_time_ms: splitTimeMs,
    });
    if (res.ok) {
      const data = res.data as { script: ScriptContent };
      state.setContent(data.script);
    }
  }, [scriptId, state]);

  const yoloArea = (() => {
    const creationRemaining: string[] = [];
    if (!allTitleCardsGenerated && state.hasTitleCards) creationRemaining.push("Title Cards");
    if (!allAudioGenerated) creationRemaining.push("Audio");
    if (!allImagesGenerated) creationRemaining.push("Images");
    if (!allFXGenerated) creationRemaining.push("FX");
    if (!allEliGenerated) creationRemaining.push("Eli");
    const renderRemaining = [...creationRemaining];
    if (!lfSeoDone) renderRemaining.push("LF SEO");
    if (!sfThumbnailsDone) renderRemaining.push("SF Thumbnails");
    if (!sfRendersDone) renderRemaining.push("SF Videos");
    if (!sfSeoDone) renderRemaining.push("SF SEO");
    const allDone = creationRemaining.length === 0;

    const yoloButtonBaseClass = "group relative flex h-7 w-[9.5rem] shrink-0 items-center justify-center overflow-hidden rounded-lg px-4 text-center text-xs font-bold leading-tight text-white/95 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 hover:scale-[1.02] disabled:opacity-50 disabled:hover:scale-100";
    const yoloButtonContentClass = "relative flex min-w-0 items-center justify-center gap-1.5 text-center";
    const yoloInfoClass = "flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-neutral-700/60 bg-neutral-900 text-neutral-500 transition-colors hover:border-neutral-500 hover:text-neutral-200";
    const yoloModeDescription = `Runs every unfinished creation step in order. Missing title cards, narration audio, scene images, FX, and Eli animation are generated automatically, then the timeline refreshes with the new assets. Currently pending: ${creationRemaining.join(", ") || "none"}.`;
    const yoloRenderDescription = `Runs the full 1-9 pipeline from the next unfinished task, then renders long-form video and exports the bundle. Currently pending: ${renderRemaining.join(", ") || "final export only"}.`;

    const yoloInfo = (content: string, label: string) => (
      <Tooltip content={content} side="bottom">
        <span className={yoloInfoClass} aria-label={label}>
          <Info size={14} />
        </span>
      </Tooltip>
    );

    const yoloRenderButton = (
      <button
        onClick={handleYoloRender}
        disabled={yoloRenderRunning || yoloRunning}
        className={`${yoloButtonBaseClass} bg-gradient-to-r from-sky-500/80 via-emerald-400/70 to-amber-400/70 shadow-[0_0_15px_rgba(14,165,233,0.2)] hover:shadow-[0_0_22px_rgba(14,165,233,0.35)] focus-visible:ring-sky-500`}
      >
        <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent animate-[shimmer_2s_ease-in-out_infinite]" />
        <span className={yoloButtonContentClass}>
          {yoloRenderRunning ? (
            <span className="w-3 h-3 border-2 border-white/70 border-t-transparent rounded-full animate-spin" />
          ) : (
            <Zap size={14} />
          )}
          YOLO MODE
        </span>
      </button>
    );

    if (yoloRunning) {
      return (
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs text-fuchsia-300/70 font-medium truncate max-w-[14rem]">{yoloStep}</span>
          <span className="w-3 h-3 border-2 border-fuchsia-400/60 border-t-transparent rounded-full animate-spin" />
          <button
            onClick={cancelYolo}
            className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-red-500/70 hover:bg-red-500/90 text-white transition-colors"
          >
            Cancel YOLO
          </button>
        </div>
      );
    }

    if (allDone) {
      return (
        <div className="flex items-center gap-2 shrink-0">
          {yoloRenderError && (
            <span className="text-[11px] text-red-400 truncate max-w-[14rem]">{yoloRenderError}</span>
          )}
          {yoloRenderRunning && yoloStep && (
            <span className="text-xs text-sky-300/75 font-medium truncate max-w-[14rem]">{yoloStep}</span>
          )}
          {yoloRenderButton}
          {yoloInfo(yoloRenderDescription, "YOLO render details")}
        </div>
      );
    }

    return (
      <div className="flex items-center gap-2 shrink-0">
        {yoloError && (
          <span className="text-[11px] text-red-400 truncate max-w-[12rem]">{yoloError}</span>
        )}
        {yoloRenderError && (
          <span className="text-[11px] text-red-400 truncate max-w-[12rem]">{yoloRenderError}</span>
        )}
        {yoloRenderRunning && yoloStep && (
          <span className="text-xs text-sky-300/75 font-medium truncate max-w-[12rem]">{yoloStep}</span>
        )}
        <button
          onClick={handleYolo}
          className={`${yoloButtonBaseClass} bg-gradient-to-r from-violet-500/80 via-fuchsia-400/70 to-amber-400/70 shadow-[0_0_15px_rgba(168,85,247,0.2)] hover:shadow-[0_0_22px_rgba(168,85,247,0.35)] focus-visible:ring-violet-500`}
        >
          <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent animate-[shimmer_2s_ease-in-out_infinite]" />
          <span className={yoloButtonContentClass}>
            <Zap size={14} />
            YOLO MODE
          </span>
        </button>
        {yoloInfo(yoloModeDescription, "YOLO mode details")}
        <span className="w-px h-4 bg-neutral-700/50" />
        {yoloRenderButton}
        {yoloInfo(yoloRenderDescription, "YOLO render details")}
      </div>
    );
  })();

  return (
    <div className="flex flex-col h-[calc(100vh-105px)]">
      {/* Header — Title + Pipeline + Thumbnail */}
      <div className="flex border-b border-neutral-800/60 shrink-0">
        {/* Left — Title, Pipeline, Export */}
        <div className="flex flex-col flex-1 min-w-0">
          {/* Row 1 — Navigation + Title */}
          <div className="flex items-center gap-4 px-5 py-2.5 border-b border-neutral-800/60">
            <button
              onClick={onBack}
              className="text-sm px-3 py-1.5 text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 rounded-lg transition-colors"
            >
              &larr; Back
            </button>
            <h2 className="text-base font-semibold truncate flex-1 min-w-0" title={title}>{title}</h2>
            {yoloArea}
            <ExportSplitButton
              exportTestJobId={exportTestJobId}
              showExportDropdown={showExportDropdown}
              exportDropdownRef={exportDropdownRef}
              onOpenExport={openExportPanel}
              onCancelExportTest={() => setExportTestJobId(null)}
              onToggleExportDropdown={() => setShowExportDropdown((show) => !show)}
              onOpenExportTest={() => {
                setShowExportDropdown(false);
                setShowExportTestModal(true);
              }}
            />
          </div>

          {/* Stats Row + Viewer Switch */}
          {(() => {
            const sep = (key: string) => (
              <span key={key} className="w-px h-4 bg-neutral-700/50" />
            );

            const statItems: React.ReactNode[] = [];
            statItems.push(
              <span key="scenes" className="text-xs text-neutral-400 bg-neutral-800/60 px-4 py-1 rounded-md tabular-nums">
                {sceneCount} scene{sceneCount !== 1 ? "s" : ""}
              </span>
            );
            statItems.push(
              <span key="segs" className="text-xs text-neutral-400 bg-neutral-800/60 px-4 py-1 rounded-md tabular-nums">
                {segmentCount} seg{segmentCount !== 1 ? "s" : ""}
              </span>
            );
            statItems.push(
              <span key="duration" className="text-xs text-neutral-400 bg-neutral-800/60 px-4 py-1 rounded-md tabular-nums font-mono">
                {durationStr}
              </span>
            );
            if (totalWords > 0) {
              statItems.push(
                <span key="words" className="text-xs text-neutral-400 bg-neutral-800/60 px-4 py-1 rounded-md tabular-nums">
                  {totalWords.toLocaleString()} words
                </span>
              );
            }
            statItems.push(
              <div key="cost" ref={costBreakdownRef} className="relative">
                <button
                  type="button"
                  onClick={() => setShowCostBreakdown((show) => !show)}
                  className="text-xs text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 px-4 py-1 rounded-md tabular-nums font-medium transition-colors"
                  title="Show cost breakdown"
                >
                  {formatCost(totalCost)}
                </button>
                {showCostBreakdown && (
                  <CostBreakdownPopover totalCost={totalCost} breakdown={costBreakdown} />
                )}
              </div>
            );
            if (mediaCounts.ai) {
              statItems.push(
                <span key="ai" className="text-xs text-violet-300 bg-violet-500/10 px-4 py-1 rounded-md tabular-nums">
                  {mediaCounts.ai} AI
                </span>
              );
            }
            if (mediaCounts.gameplay_video) {
              statItems.push(
                <span key="gameplay" className="text-xs text-sky-300 bg-sky-500/10 px-4 py-1 rounded-md tabular-nums">
                  {mediaCounts.gameplay_video} gameplay
                </span>
              );
            }
            if (mediaCounts.stock_photo) {
              statItems.push(
                <span key="stock" className="text-xs text-amber-300 bg-amber-500/10 px-4 py-1 rounded-md tabular-nums">
                  {mediaCounts.stock_photo} stock
                </span>
              );
            }
            if (mediaCounts.user_upload) {
              statItems.push(
                <span key="upload" className="text-xs text-emerald-300 bg-emerald-500/10 px-4 py-1 rounded-md tabular-nums">
                  {mediaCounts.user_upload} upload{mediaCounts.user_upload !== 1 ? "s" : ""}
                </span>
              );
            }
            statItems.push(
              <ShortFormStatusPill
                key="short-form"
                scriptId={scriptId}
                segmentCount={state.content.segments.length}
                onClick={openExportOnShortForm}
              />
            );

            const interleavedStats: React.ReactNode[] = [];
            statItems.forEach((item, i) => {
              if (i > 0) interleavedStats.push(sep(`sep-${i}`));
              interleavedStats.push(item);
            });

            return (
              <>
                <div className={`px-5 py-2 border-t border-neutral-800/60 shrink-0 ${yoloRunning ? "bg-fuchsia-500/5" : ""}`}>
                  <div className="flex items-center gap-1.5 min-w-0">
                    {interleavedStats}
                  </div>
                </div>
                <ViewerSwitchRow
                  format={viewerFormat}
                  asset={viewerAsset}
                  activeTab={activeTab}
                  onFormatChange={setViewerFormat}
                  onAssetChange={setViewerAsset}
                  onTabChange={setActiveTab}
                />
              </>
            );
          })()}

          <PipelineSteps
            titleCardGenerating={titleCardGenerating}
            titleCardGenerated={titleCardGenerated || allTitleCardsGenerated}
            allImagesGenerated={allImagesGenerated}
            allAudioGenerated={allAudioGenerated}
            allFXGenerated={allFXGenerated}
            batchGenerating={state.batchGenerating}
            batchGeneratingAudio={state.batchGeneratingAudio}
            hasTitleCards={state.hasTitleCards}
            generatingFX={generatingFX}
            setGeneratingFX={setGeneratingFX}
            handleGenerateTitleCards={handleGenerateTitleCards}
            cancelTitleCards={cancelTitleCards}
            confirmAndGenerateImages={confirmAndGenerateImages}
            confirmAndGenerateAudio={confirmAndGenerateAudio}
            confirmAndGenerateFX={confirmAndGenerateFX}
            generateMissingImages={generateMissingImages}
            generateMissingAudio={generateMissingAudio}
            generateMissingFX={generateMissingFX}
            hasExistingImages={hasExistingImages}
            hasExistingAudio={hasExistingAudio}
            hasExistingFX={hasExistingFX}
            missingImageCount={missingImageCount}
            missingAudioCount={missingAudioCount}
            missingFXCount={missingFXCount}
            cancelImageGeneration={state.cancelImageGeneration}
            cancelAudioGeneration={state.cancelAudioGeneration}
            fxCancelledRef={fxCancelledRef}
            showVoicePicker={voicePicker.showVoicePicker}
            setShowVoicePicker={voicePicker.setShowVoicePicker}
            voices={voicePicker.voices}
            selectedVoiceId={voicePicker.selectedVoiceId}
            setSelectedVoiceId={voicePicker.setSelectedVoiceId}
            voicePickerRef={voicePicker.voicePickerRef}
            onRecordVoiceover={onRecordVoiceover}
            fxPotentiallyStale={lastAudioGenTimestamp > 0 && lastAudioGenTimestamp > lastFXGenTimestamp}
            allEliGenerated={allEliGenerated}
            generatingEli={generatingEli}
            setGeneratingEli={setGeneratingEli}
            confirmAndGenerateEli={confirmAndGenerateEli}
            generateMissingEli={generateMissingEli}
            hasExistingEli={hasExistingEli}
            missingEliCount={missingEliCount}
            eliCancelledRef={eliCancelledRef}
            fxEstimatedSeconds={fxProgress.estimatedSeconds}
            fxProgressActive={fxProgress.active}
            eliEstimatedSeconds={eliProgress.estimatedSeconds}
            eliProgressActive={eliProgress.active}
            titleCardEstimatedSeconds={titleCardProgress.estimatedSeconds}
            titleCardProgressActive={titleCardProgress.active}
          />

          <ProductionWorkflowRow
            segmentCount={segmentCount}
            lfSeoDone={lfSeoDone}
            sfSeoDone={sfSeoDone}
            sfSeoMissingCount={sfSeoMissingCount}
            sfThumbnailsDone={sfThumbnailsDone}
            sfThumbnailsMissingCount={sfThumbnailMissingCount}
            sfRendersDone={sfRendersDone}
            sfRendersMissingCount={sfRenderMissingCount}
            busyTask={productionBusyTask}
            progress={productionProgress}
            seoGenerating={render.seoGenerating}
            shortFormSeoGenerating={render.shortFormSeoGenerating}
            onGenerateLfSeo={handleGenerateLfSeo}
            onGenerateMissingLfSeo={handleGenerateMissingLfSeo}
            onGenerateSfThumbnails={handleGenerateSfThumbnails}
            onGenerateMissingSfThumbnails={handleGenerateMissingSfThumbnails}
            onGenerateSfSeo={handleGenerateSfSeo}
            onGenerateMissingSfSeo={handleGenerateMissingSfSeo}
            onRenderSfVideos={handleRenderSfVideos}
            onRenderMissingSfVideos={handleRenderMissingSfVideos}
          />
          {productionError && (
            <div className="px-5 pb-2 text-[11px] text-red-400">{productionError}</div>
          )}
        </div>

        {/* Right — Thumbnail Preview */}
        <div className="shrink-0 border-l border-neutral-800/60 px-4 py-2.5 flex items-center justify-center">
          <button
            onClick={() => setShowThumbnailModal(true)}
            className="relative group"
            title="Click to manage thumbnails"
          >
            {thumbnailsInline.length > 0 && thumbnailsInline[0].image_url ? (
              <div className="relative">
                <img
                  src={assetUrl(thumbnailsInline[0].image_url)}
                  alt="Thumbnail preview"
                  className="h-56 aspect-video object-cover rounded-lg border border-neutral-700 group-hover:border-violet-500 transition-colors"
                />
                {thumbnailsInlineGenerating && (
                  <div className="absolute inset-0 bg-black/50 rounded-lg flex items-center justify-center">
                    <span className="w-5 h-5 border-2 border-violet-400 border-t-transparent rounded-full animate-spin" />
                  </div>
                )}
              </div>
            ) : (
              <div className={`h-56 aspect-video rounded-lg border border-dashed flex items-center justify-center transition-colors ${
                thumbnailsInlineGenerating
                  ? "border-violet-500/50 bg-violet-500/5"
                  : "border-neutral-700 bg-neutral-900/40 group-hover:border-violet-500/50"
              }`}>
                {thumbnailsInlineGenerating ? (
                  <span className="w-5 h-5 border-2 border-violet-400 border-t-transparent rounded-full animate-spin" />
                ) : (
                  <span className="text-[11px] text-neutral-600">No Thumbnail</span>
                )}
              </div>
            )}
          </button>
        </div>
      </div>

      {/* Batch Progress Bars */}
      <BatchProgressBar progress={state.batchImageProgress} label="images" />
      <BatchProgressBar progress={state.batchAudioProgress} label="audio" />
      {generatingFX && (
        <div className="px-4 py-2 border-b border-neutral-800 shrink-0 bg-amber-500/10">
          <div className="flex items-center gap-3 text-xs">
            <span className="w-3 h-3 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-neutral-300">
              Generating FX assignments with AI{fxStep ? ` · ${fxStep}` : "..."}
            </span>
            <div className="flex-1 h-1.5 bg-neutral-800 rounded-full overflow-hidden ml-2">
              <div
                className="h-full rounded-full bg-amber-500 transition-all"
                style={{ width: `${Math.max(4, Math.round(fxProgressPct * 100))}%` }}
              />
            </div>
          </div>
        </div>
      )}
      {generatingEli && (
        <div className="px-4 py-2 border-b border-neutral-800 shrink-0 bg-teal-500/10">
          <div className="flex items-center gap-3 text-xs">
            <span className="w-3 h-3 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-neutral-300">
              Generating Eli animation keyframes with AI · {sceneProgressCounter(eliStep, eliProgressPct, eliProgressTotal)}
            </span>
            <div className="flex-1 h-1.5 bg-neutral-800 rounded-full overflow-hidden ml-2">
              <div
                className="h-full rounded-full bg-teal-500 transition-all"
                style={{ width: `${Math.max(4, Math.round(eliProgressPct * 100))}%` }}
              />
            </div>
          </div>
        </div>
      )}
      {exportTestJobId && (() => {
        const remaining = exportTestEstimatedSeconds && exportTestProgress > 0 && exportTestProgress < 1
          ? Math.max(0, Math.round(exportTestEstimatedSeconds * (1 - exportTestProgress)))
          : null;
        const etaStr = remaining !== null && remaining > 0
          ? remaining >= 60
            ? `~${Math.ceil(remaining / 60)}m left`
            : `~${remaining}s left`
          : "";
        return (
        <div className="px-4 py-2 border-b border-neutral-800 shrink-0 bg-rose-500/10">
          <div className="flex items-center gap-3 text-xs">
            <span className="w-3 h-3 border-2 border-rose-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-neutral-300">
              Export Test &middot; {exportTestStep || "Starting..."}
            </span>
            <div className="flex-1 h-1.5 bg-neutral-800 rounded-full overflow-hidden ml-2">
              <div
                className="h-full rounded-full bg-rose-500 transition-all duration-500"
                style={{ width: `${exportTestProgress * 100}%` }}
              />
            </div>
            {etaStr && <span className="text-neutral-500">{etaStr}</span>}
            <span className="text-neutral-500 tabular-nums">{Math.round(exportTestProgress * 100)}%</span>
          </div>
        </div>
        );
      })()}
      {titleCardGenerating && (
        <div className="px-4 py-2 border-b border-neutral-800 shrink-0 bg-violet-500/10">
          <div className="flex items-center gap-3 text-xs">
            <span className="w-3 h-3 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-neutral-300">
              Generating title card composites...
            </span>
            <div className="flex-1 h-1.5 bg-neutral-800 rounded-full overflow-hidden ml-2">
              <div className="h-full rounded-full bg-violet-500 animate-pulse" style={{ width: "60%" }} />
            </div>
          </div>
        </div>
      )}
      {titleCardGenerated && !titleCardGenerating && (
        <div className="px-4 py-2 border-b border-neutral-800 shrink-0 bg-neutral-900/60">
          <div className="flex items-center gap-4">
            <span className="text-xs text-neutral-500 shrink-0">Title Cards:</span>
            <div className="flex gap-3">
              <div className="space-y-0.5">
                <img
                  src={assetUrl(`/static/projects/${scriptId}/images/composite_title_card.png`) + `?t=${titleCardTimestamp}`}
                  alt="Thumbnail"
                  className="h-16 aspect-video object-cover rounded border border-neutral-700"
                />
                <p className="text-[10px] text-neutral-500">With title</p>
              </div>
              <div className="space-y-0.5">
                <img
                  src={assetUrl(`/static/projects/${scriptId}/images/composite_title_card_notitle.png`) + `?t=${titleCardTimestamp}`}
                  alt="Title Slide"
                  className="h-16 aspect-video object-cover rounded border border-neutral-700"
                />
                <p className="text-[10px] text-neutral-500">No title</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {viewerFormat === "long-form" && viewerAsset === "thumbnails" ? (
        <LongFormThumbnailsPanel
          thumbnails={render.thumbnails}
          generating={render.thumbnailsGenerating}
          onGenerate={() => void render.recompositeThumbnail()}
          onExport={() => void handleExportLongFormThumbnail()}
          exporting={longFormThumbnailExporting}
          progress={render.thumbnailProgress}
        />
      ) : viewerFormat === "long-form" && viewerAsset === "seo" ? (
        <LongFormSeoPanel
          metadata={render.seoMetadata}
          generating={render.seoGenerating}
          onGenerate={() => void render.generateSEO()}
          onExport={() => void handleExportLongFormSEO()}
          exporting={longFormSeoExporting}
          progress={render.seoProgress}
        />
      ) : viewerFormat === "short-form" && viewerAsset === "render" ? (
        <div className="flex-1 overflow-y-auto p-5">
          <ShortFormTab
            scriptId={scriptId}
            segments={state.content.segments.map((s) => ({ name: s.name }))}
            shortFormSeoMetadata={render.shortFormSeoMetadata}
            onUploadComplete={() => undefined}
            onRenderedStatusChange={() => void refreshShortFormRenderStatus()}
          />
        </div>
      ) : viewerFormat === "short-form" && viewerAsset === "thumbnails" ? (
        <div className="flex-1 overflow-y-auto p-5">
          <ShortFormThumbnailsCard
            scriptId={scriptId}
            segments={state.content.segments.map((s) => ({ name: s.name }))}
            onStatusChange={() => void refreshShortFormThumbnailStatus()}
          />
        </div>
      ) : viewerFormat === "short-form" && viewerAsset === "seo" ? (
        <ShortFormSeoPanel
          metadata={render.shortFormSeoMetadata}
          segmentCount={segmentCount}
          generating={render.shortFormSeoGenerating}
          onGenerate={() => void render.generateShortFormSEO()}
          onExport={() => void handleExportShortFormSEO()}
          exporting={shortFormSeoExporting}
          progress={render.shortFormSeoProgress}
        />
      ) : activeTab === "media-sources" ? (
        <MediaSourcesTab
          scriptId={scriptId}
          content={state.content}
          mediaAssignments={media.mediaAssignments}
          mediaAnalyzing={media.mediaAnalyzing}
          mediaReviewDismissed={media.mediaReviewDismissed}
          onAnalyzeMedia={media.handleAnalyzeMedia}
          onBeforeAssignmentsApply={() => state.save()}
          onAssignmentsSaved={async (assignments: MediaAssignment[]) => {
            media.setMediaAssignments(assignments);
            const refreshed = await api.get(`/api/scripts/${scriptId}`);
            if (refreshed.ok) {
              const data = refreshed.data as { script: ScriptContent };
              state.setContent(data.script);
            }
          }}
          onApproved={() => {
            media.setMediaReviewDismissed(true);
            state.generateAllImages();
            setActiveTab("timeline");
          }}
        />
      ) : activeTab === "segments" ? (
        <SegmentsTab
          content={state.content}
          scriptId={scriptId}
          selectedSceneId={state.selectedSceneId}
          onSelectScene={(id) => state.selectScene(id)}
          onUpdateScene={(id, updates) => state.updateScene(id, updates)}
          onGenerateImage={(id) => state.generateImage(id)}
          onGenerateAudio={(id) => tryGenerateAudio(id)}
          generatingSceneIds={state.generatingSceneIds}
          generatingAudioSceneIds={state.generatingAudioSceneIds}
        />
      ) : (
      /* Vertical layout: Timeline on top (full width), Properties below */
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Zoom slider — always visible above timeline */}
        <div className="px-5 py-1.5 border-b border-neutral-800/60 shrink-0">
          <div className="flex items-center gap-3 w-full">
            <span className="text-[11px] text-neutral-500 shrink-0">Zoom</span>
            <input
              type="range"
              min={0}
              max={100}
              value={pixelsPerSecond}
              onChange={(e) => setPixelsPerSecond(parseInt(e.target.value, 10))}
              className="flex-1 w-full accent-violet-500"
              style={{ minWidth: 0 }}
            />
            <span className="text-[11px] text-neutral-500 font-mono shrink-0">{pixelsPerSecond}</span>
          </div>
        </div>

        {/* Main timeline area — full width */}
        <div className="overflow-auto p-4 shrink-0">
          <TimelineLanes
            content={state.content}
            selectedSceneId={state.selectedSceneId}
            onSelectScene={handleSelectScene}
            pixelsPerSecond={pixelsPerSecond}
          />
        </div>

        {/* Bottom panel: Properties */}
        {selectedScene ? (
          <div className="flex-1 min-h-0 border-t border-neutral-800/60">
            <PropertiesPanel
              scene={selectedScene.scene}
              segmentIdx={selectedScene.segIdx}
              segmentName={selectedScene.segName}
              scriptId={scriptId}
              onUpdate={(updates) =>
                state.updateScene(selectedScene.scene.id, updates)
              }
              onGenerateImage={() =>
                state.generateImage(selectedScene.scene.id)
              }
              isGenerating={state.generatingSceneIds.has(selectedScene.scene.id)}
              onGenerateAudio={() =>
                tryGenerateAudio(selectedScene.scene.id)
              }
              isGeneratingAudio={state.generatingAudioSceneIds.has(selectedScene.scene.id)}
              microTimelineRef={microTimelineRef}
              onSplitScene={handleSplitSceneAtTime}
            />
          </div>
        ) : (
          <div className="flex-1 border-t border-neutral-800/60 px-4 py-3 flex items-center justify-center">
            <p className="text-sm text-neutral-600">
              Select a scene to preview
            </p>
          </div>
        )}
      </div>
      )}

      {showExportTestModal && (
        <ExportTestModal
          onRun={handleExportTest}
          onClose={() => setShowExportTestModal(false)}
        />
      )}

      {showThumbnailModal && (
        <ThumbnailModal
          thumbnails={thumbnailsInline}
          generating={thumbnailsInlineGenerating}
          onGenerate={handleRecompositeThumbnailInline}
          onClose={() => setShowThumbnailModal(false)}
          scriptId={scriptId}
          segments={state.content.segments.map((s) => ({ name: s.name }))}
        />
      )}

      {showExport && (
        <ExportPanel
          youtubeStatus={render.youtubeStatus}
          youtubeUrl={render.youtubeUrl}
          onStartYoutubeRender={render.startYoutubeRender}
          thumbnails={render.thumbnails}
          thumbnailsGenerating={render.thumbnailsGenerating}
          onRecompositeThumbnail={() => render.recompositeThumbnail()}
          seoMetadata={render.seoMetadata}
          seoGenerating={render.seoGenerating}
          onGenerateSEO={render.generateSEO}
          shortFormSeoMetadata={render.shortFormSeoMetadata}
          shortFormSeoGenerating={render.shortFormSeoGenerating}
          onGenerateShortFormSEO={render.generateShortFormSEO}
          estimatedSeconds={render.estimatedSeconds}
          exportBundleLoading={render.exportBundleLoading}
          exportBundleResult={render.exportBundleResult}
          onYoloExport={render.yoloRender}
          exportPhase={render.exportPhase}
          exportStatus={render.exportStatus}
          thumbnailProgress={render.thumbnailProgress}
          seoProgress={render.seoProgress}
          shortFormSeoProgress={render.shortFormSeoProgress}
          exportBundleProgress={render.exportBundleProgress}
          youtubeConnected={youtubeConnected}
          onYoutubeConnectionChange={setYoutubeConnected}
          onNavigateToSettings={() => {
            setShowExport(false);
            onNavigateToSettings?.();
          }}
          seoTitle={title}
          seoDescription=""
          seoTags={[]}
          projectTitle={title}
          onClose={() => setShowExport(false)}
          scriptId={scriptId}
          segments={state.content.segments.map((s) => ({ name: s.name }))}
          initialTab={exportInitialTab}
        />
      )}

      {showVoiceSetup && (
        <VoiceSetupModal
          brandName=""
          onVoiceSelected={handleVoiceSelected}
          onClose={() => {
            setShowVoiceSetup(false);
            setPendingAudioAction(null);
          }}
        />
      )}

      {confirmOverwrite && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-neutral-900 border border-neutral-700 rounded-xl shadow-2xl p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold text-neutral-100 mb-2">
              Overwrite existing {confirmOverwrite}?
            </h3>
            <p className="text-sm text-neutral-400 mb-6">
              {confirmOverwrite === "images" && "Some scenes already have generated images. Regenerating will overwrite them."}
              {confirmOverwrite === "audio" && "Some scenes already have generated audio. Regenerating will overwrite them."}
              {confirmOverwrite === "fx" && "Some scenes already have FX assignments. Regenerating will overwrite them."}
              {confirmOverwrite === "eli" && "Some scenes already have Eli overlays. Regenerating will overwrite them."}
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
                  if (action === "images") state.generateAllImages();
                  else if (action === "audio") tryGenerateAudio("all");
                  else if (action === "fx") handleGenerateFX();
                  else if (action === "eli") handleGenerateEli();
                }}
                className="px-4 py-2 text-sm rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-medium transition-colors"
              >
                Overwrite & Regenerate
              </button>
            </div>
          </div>
        </div>
      )}

      {showHelp && <ShortcutHelpOverlay onClose={() => setShowHelp(false)} />}
    </div>
  );
}
