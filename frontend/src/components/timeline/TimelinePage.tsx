import { type KeyboardEvent as ReactKeyboardEvent, type ReactNode, useCallback, useEffect, useRef, useState } from "react";
import {
  BarChart3,
  ChevronDown,
  Check,
  Film,
  ImageIcon,
  Info,
  Layers,
  ListVideo,
  PanelsTopLeft,
  Pencil,
  Search,
  Smartphone,
  Upload,
  X,
  Zap,
  type LucideIcon,
} from "lucide-react";
import api, {
  assetUrl,
  analyzeVisualTreatments,
  applyVisualTreatmentAssignments,
  ensureScriptExportsFolder,
  exportLongFormSEO,
  exportLongFormThumbnail,
  exportShortFormSEO,
  exportTest,
  fetchScriptCost,
  generateEli,
  generateFX,
  getExportFileStatus,
  generateShortFormThumbnailsAll,
  generateShortFormThumbnailsBatch,
  getProjectConfig,
  getRenderedShortsStatus,
  getShortFormThumbnailsStatus,
  getUploadSuiteStatus,
  getUploadTracking,
  getVisualTreatmentStatus,
  openPath,
  pollEliJob,
  pollFXJob,
  pollShortFormJob,
  renderShortAll,
  renderShortBatch,
  setUploadTracking as apiSetUploadTracking,
  updateVisualCanvas,
} from "../../api";
import type { ExportTestOptions } from "../../api";
import type { MediaAssignment } from "../../api";
import type { VisualTreatmentAssignment } from "../../api";
import type { ProjectConfig } from "../../api";
import type { ExportFileCategoryStatus, ExportFileStatus } from "../../api";
import type { ScriptCostBreakdownItem } from "../../api";
import { useStylePreset } from "../../contexts/StylePresetContext";
import { showToast } from "../ToastContainer";
import type { ScriptContent, UploadTracking } from "../../types/script";
import type { ScriptRead } from "../../types/script";
import type { ThumbnailConcept, ThumbnailLabelStyle } from "../../types/render";
import type { UploadSuiteStatus } from "../../api";
import type { SaveState } from "../../App";
import type { MicroTimelineHandle } from "./SceneMicroTimeline";
import ExportTestModal from "./ExportTestModal";
import MainCharacterDrawer from "./MainCharacterDrawer";
import UploadPanel from "./UploadPanel";
import MediaSourcesTab from "./MediaSourcesTab";
import SegmentsTab from "./SegmentsTab";
import PipelineSteps from "./PipelineSteps";
import PropertiesPanel from "./PropertiesPanel";
import ThumbnailModal from "./ThumbnailModal";
import TimelineLanes from "./TimelineLanes";
import VoiceSetupModal from "../brand/VoiceSetupModal";
import ScriptRatingCard from "../script/ScriptRatingCard";
import ShortFormTab from "./short-form/ShortFormTab";
import ShortFormThumbnailsCard from "./short-form/ShortFormThumbnailsCard";
import { Tooltip } from "../ui/Tooltip";
import { useRenderState } from "./useRenderState";
import { useTimelineState } from "./useTimelineState";
import { useMediaReview } from "./useMediaReview";
import { useOperationProgress } from "../../hooks/useOperationProgress";

import { useVoicePicker } from "./useVoicePicker";
import { ShortcutHelpOverlay } from "./ShortcutHelpOverlay";
import { useKeyboardShortcuts } from "./useKeyboardShortcuts";
import { FinalizationRow } from "./FinalizationRow";
import { LongFormSeoPanel, ShortFormSeoPanel } from "./SEOPanel";
import { LongFormThumbnailsPanel } from "./ThumbnailsPanel";
import { YoloProgressStrip } from "./YoloProgressStrip";
import type { ProductionTask } from "./timelineProduction";
import type { ThumbnailPhaseItem, ThumbnailPhaseStatus } from "./ThumbnailPhaseProgress";

const DEFAULT_UPLOAD_TRACKING: UploadTracking = {
  longform_youtube: false,
  shortform_youtube: false,
  shortform_instagram: false,
  shortform_tiktok: false,
};

const DISTRIBUTION_TARGETS = [
  { key: "longform_youtube" as const, label: "YouTube Long Form", shortLabel: "YouTube long", color: "text-red-500" },
  { key: "shortform_youtube" as const, label: "YouTube Short Form", shortLabel: "YouTube short", color: "text-red-400" },
  { key: "shortform_instagram" as const, label: "Insta Short Form", shortLabel: "Instagram", color: "text-pink-500" },
  { key: "shortform_tiktok" as const, label: "TikTok Short Form", shortLabel: "TikTok", color: "text-neutral-100" },
];

function DistributionIcon({
  target,
  uploaded,
  className = "w-4 h-4",
}: {
  target: keyof UploadTracking;
  uploaded: boolean;
  className?: string;
}) {
  const activeColor = DISTRIBUTION_TARGETS.find((item) => item.key === target)?.color ?? "text-neutral-100";
  const iconClass = `${className} ${uploaded ? activeColor : "text-neutral-500"}`;
  const fill = uploaded ? "currentColor" : "none";
  const stroke = uploaded ? "none" : "currentColor";

  if (target === "shortform_instagram") {
    return (
      <svg className={iconClass} viewBox="0 0 24 24" fill={fill} stroke={stroke} strokeWidth={1.5}>
        <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" />
      </svg>
    );
  }

  if (target === "shortform_tiktok") {
    return (
      <svg className={iconClass} viewBox="0 0 24 24" fill={fill} stroke={stroke} strokeWidth={1.5}>
        <path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1V9.01a6.27 6.27 0 00-.79-.05 6.34 6.34 0 00-6.34 6.34 6.34 6.34 0 006.34 6.34 6.34 6.34 0 006.33-6.34V8.95a8.19 8.19 0 004.79 1.53V7.03a4.85 4.85 0 01-1.02-.34z" />
      </svg>
    );
  }

  if (target === "shortform_youtube") {
    return (
      <svg className={iconClass} viewBox="0 0 24 24" fill={fill} stroke={stroke} strokeWidth={1.5}>
        <path d="M14.4 12c0 1.33-.53 2.53-1.4 3.4-.87.87-2.07 1.4-3.4 1.4a4.8 4.8 0 1 1 4.8-4.8zM10.8 7.2a7.2 7.2 0 1 0 0 14.4 7.2 7.2 0 0 0 0-14.4zM21 2l-4 4h3v7h-3l4 4V2z" />
      </svg>
    );
  }

  return (
    <svg className={iconClass} viewBox="0 0 24 24" fill={fill} stroke={stroke} strokeWidth={1.5}>
      <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0C.488 3.45.029 5.804 0 12c.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0C23.512 20.55 23.971 18.196 24 12c-.029-6.185-.484-8.549-4.385-8.816zM9 16V8l8 4-8 4z" />
    </svg>
  );
}

interface Props {
  scriptId: string;
  isActive?: boolean;
  onBack: () => void;
  onSaveStateChange?: (state: SaveState) => void;
  onRecordVoiceover?: () => void;
}

export default function TimelinePage({ scriptId, isActive = true, onBack, onSaveStateChange, onRecordVoiceover }: Props) {
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

  return <TimelineEditor scriptId={scriptId} isActive={isActive} initialContent={script.script} title={script.topic_title} onTitleUpdated={setScript} onBack={onBack} onSaveStateChange={onSaveStateChange} onRecordVoiceover={onRecordVoiceover} />;
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
  const [now, setNow] = useState<number | null>(null);

  useEffect(() => {
    if (!progress.startedAt || progress.completed + progress.failed >= progress.total) {
      const reset = window.setTimeout(() => setNow(null), 0);
      return () => window.clearTimeout(reset);
    }

    const updateNow = () => setNow(Date.now());
    const immediate = window.setTimeout(updateNow, 0);
    const interval = window.setInterval(updateNow, 1000);

    return () => {
      window.clearTimeout(immediate);
      window.clearInterval(interval);
    };
  }, [progress.completed, progress.failed, progress.startedAt, progress.total]);

  if (progress.total === 0) return null;
  const done = progress.completed + progress.failed;
  const pct = done / progress.total;
  const elapsed = progress.startedAt && now ? Math.max(0, (now - progress.startedAt) / 1000) : 0;
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

function CostBreakdownPanel({
  totalCost,
  breakdown,
}: {
  totalCost: number;
  breakdown: ScriptCostBreakdownItem[];
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-neutral-800 bg-neutral-950/60">
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

function formatScenePercent(count: number, total: number) {
  if (total === 0) return "0%";
  return `${Math.round((count / total) * 100)}%`;
}

function MediaBreakdownPanel({
  modeCounts,
  totalScenes,
}: {
  modeCounts: Record<string, number>;
  totalScenes: number;
}) {
  const rows = [
    { key: "full_frame", label: "Full frame", color: "text-violet-300", count: modeCounts.full_frame ?? 0 },
    { key: "video", label: "Video", color: "text-fuchsia-300", count: modeCounts.video ?? 0 },
    { key: "popup_sequence", label: "Popup sequence", color: "text-sky-300", count: modeCounts.popup_sequence ?? 0 },
    { key: "flipflop", label: "Flip-flop", color: "text-emerald-300", count: modeCounts.flipflop ?? 0 },
    { key: "comparison_board", label: "Comparison board", color: "text-amber-300", count: modeCounts.comparison_board ?? 0 },
    { key: "captions", label: "Captions", color: "text-red-300", count: modeCounts.captions ?? 0 },
  ];

  return (
    <div className="overflow-hidden rounded-lg border border-neutral-800 bg-neutral-950/60">
      <div className="flex items-center justify-between border-b border-neutral-800 px-3 py-2">
        <span className="text-xs font-semibold text-neutral-200">Visual mode mix</span>
        <span className="text-xs font-mono text-neutral-400">
          {totalScenes} scene{totalScenes !== 1 ? "s" : ""}
        </span>
      </div>
      <div className="py-1">
        {rows.map((row) => (
          <div key={row.key} className="px-3 py-2">
            <div className="flex items-center justify-between gap-3">
              <span className={`text-xs font-medium ${row.color}`}>{row.label}</span>
              <span className="text-xs font-mono text-neutral-200">
                {row.count}/{totalScenes} = {formatScenePercent(row.count, totalScenes)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ExportFileBreakdownPanel({
  status,
  segmentCount,
}: {
  status: ExportFileStatus | null;
  segmentCount: number;
}) {
  const fallbackTotal = segmentCount * 3 + 3;
  const rows: Array<[string, ExportFileCategoryStatus]> = status
    ? [
        ["longform_video", status.categories.longform_video],
        ["longform_thumbnail", status.categories.longform_thumbnail],
        ["longform_seo", status.categories.longform_seo],
        ["shortform_videos", status.categories.shortform_videos],
        ["shortform_thumbnails", status.categories.shortform_thumbnails],
        ["shortform_seo", status.categories.shortform_seo],
      ].filter((entry): entry is [string, ExportFileCategoryStatus] => Boolean(entry[1]))
    : [];

  return (
    <div className="overflow-hidden rounded-lg border border-neutral-800 bg-neutral-950/60">
      <div className="flex items-center justify-between border-b border-neutral-800 px-3 py-2">
        <span className="text-xs font-semibold text-neutral-200">Exported files</span>
        <span className="text-xs font-mono text-sky-300 tabular-nums">
          {status ? `${status.exported}/${status.total}` : `0/${fallbackTotal}`}
        </span>
      </div>
      <div className="py-1">
        {rows.length > 0 ? (
          rows.map(([key, row]) => (
            <div key={key} className="px-3 py-2">
              <div className="flex items-center justify-between gap-3">
                <span className="text-xs font-medium text-neutral-300">{row.label}</span>
                <span className="text-xs font-mono text-neutral-200 tabular-nums">
                  {row.exported}/{row.total}
                </span>
              </div>
            </div>
          ))
        ) : (
          <div className="px-3 py-5 text-center text-xs text-neutral-500">
            Export folder status is unavailable.
          </div>
        )}
      </div>
      {status && (
        <div className="border-t border-neutral-800 px-3 py-2">
          <p className="truncate text-[11px] text-neutral-500" title={status.folder_path}>
            {status.folder_path}
          </p>
        </div>
      )}
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
type ViewerTab = "timeline" | "media-sources" | "segments";
type ViewerNavKey = ViewerTab | "thumbnails" | "seo";

const FORMAT_OPTIONS: { key: ViewerFormat; label: string; Icon: LucideIcon }[] = [
  { key: "long-form", label: "Long Form", Icon: Film },
  { key: "short-form", label: "Short Form", Icon: Smartphone },
];

const VIEWER_NAV_OPTIONS: { key: ViewerNavKey; label: string; Icon: LucideIcon }[] = [
  { key: "segments", label: "Segments", Icon: Layers },
  { key: "media-sources", label: "Visual Modes", Icon: PanelsTopLeft },
  { key: "timeline", label: "Timeline", Icon: ListVideo },
  { key: "thumbnails", label: "Thumbnails", Icon: ImageIcon },
  { key: "seo", label: "SEO", Icon: Search },
];
function getCreationStatus(content: ScriptContent, projectConfig?: ProjectConfig | null) {
  const allScenes = content.segments.flatMap((seg) => seg.scenes);
  const nonTitleScenes = allScenes.filter((sc) => !sc.is_title_card);
  const titleScenes = allScenes.filter((sc) => sc.is_title_card);
  const narratedScenes = allScenes.filter((sc) => sc.narration);
  const imageScenes = nonTitleScenes.filter((sc) => sc.visual_prompt);
  const eliScenes = nonTitleScenes.filter((sc) => sc.narration && !sc.contains_person);

  const eliDisabledForProject = projectConfig?.eli_enabled === false;

  const titleCardsDone = titleScenes.length === 0 || titleScenes.every((sc) => sc.image_url);
  const audioDone = narratedScenes.length === 0 || narratedScenes.every((sc) => sc.audio_url);
  const imagesDone = imageScenes.length === 0 || imageScenes.every((sc) => sc.image_url || sc.frame_urls?.length || sc.video_url);
  const fxDone = nonTitleScenes.length === 0 || nonTitleScenes.every((sc) => sc.fx);
  const eliDone = eliDisabledForProject || eliScenes.length === 0 || eliScenes.every((sc) => sc.eli_overlay);

  return {
    titleCardsDone,
    audioDone,
    imagesDone,
    fxDone,
    eliDone,
    missingFXCount: nonTitleScenes.filter((sc) => !sc.fx).length,
    missingEliCount: eliDisabledForProject ? 0 : eliScenes.filter((sc) => !sc.eli_overlay).length,
    eliSceneCount: eliDisabledForProject ? 0 : eliScenes.length,
    hasTitleCards: titleScenes.length > 0,
  };
}

function batchProgressValue(progress: { total: number; completed: number; failed: number }) {
  if (progress.total <= 0) return null;
  return Math.min(1, (progress.completed + progress.failed) / progress.total);
}

function UploadButton({
  checking,
  onOpenUpload,
}: {
  checking: boolean;
  onOpenUpload: () => void;
}) {
  return (
    <div className="relative flex items-stretch shrink-0">
      <button
        type="button"
        onClick={onOpenUpload}
        disabled={checking}
        className="flex min-w-[7rem] items-center justify-center gap-1.5 whitespace-nowrap rounded-lg border border-neutral-700/60 bg-neutral-800/80 px-3 py-2 text-xs font-medium text-neutral-300 transition-all hover:border-neutral-600 hover:bg-neutral-700/80 disabled:cursor-wait disabled:opacity-60"
        title="Open upload suite (Cmd+E)"
      >
        {checking ? <span className="h-3.5 w-3.5 rounded-full border-2 border-violet-400/60 border-t-transparent animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
        Upload
      </button>
    </div>
  );
}

function FinderIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <rect x="4" y="5" width="24" height="22" rx="5" fill="#5bbcff" />
      <path d="M16 5h7a5 5 0 0 1 5 5v12a5 5 0 0 1-5 5h-7V5Z" fill="#1d7ff2" />
      <path d="M16 7v18" stroke="#0b1630" strokeWidth="1.5" strokeLinecap="round" opacity="0.65" />
      <path d="M10 12v3" stroke="#0b1630" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M22 12v3" stroke="#0b1630" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M10 21c2.8 1.8 8.9 1.8 12 0" stroke="#0b1630" strokeWidth="1.6" strokeLinecap="round" fill="none" />
    </svg>
  );
}

function OpenExportsButton({
  opening,
  onOpen,
}: {
  opening: boolean;
  onOpen: () => void;
}) {
  return (
    <div className="inline-flex shrink-0">
      <Tooltip content="Open exports folder in Finder">
        <button
          type="button"
          onClick={onOpen}
          disabled={opening}
          className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-neutral-700/60 bg-neutral-800/80 text-neutral-300 transition-colors hover:border-neutral-600 hover:bg-neutral-700/80 disabled:cursor-wait disabled:opacity-60"
          title="Open exports folder in Finder"
        >
          {opening ? (
            <span className="h-4 w-4 rounded-full border-2 border-sky-300/70 border-t-transparent animate-spin" />
          ) : (
            <FinderIcon />
          )}
        </button>
      </Tooltip>
    </div>
  );
}

function normalizeCanvasHex(value: string): string | null {
  const text = value.trim().replace(/^#/, "");
  if (!/^[0-9a-fA-F]{6}$/.test(text)) return null;
  return `#${text.toUpperCase()}`;
}

function CanvasColorButton({
  color,
  updating,
  onSelect,
}: {
  color: string;
  updating: boolean;
  onSelect: (color: string) => void;
}) {
  const textInputRef = useRef<HTMLInputElement | null>(null);
  const popoverRef = useRef<HTMLDivElement | null>(null);
  const [draft, setDraft] = useState(color);
  const [open, setOpen] = useState(false);
  const normalizedDraft = normalizeCanvasHex(draft);
  const activeColor = normalizeCanvasHex(color) ?? "#F6C54A";
  const previewColor = normalizedDraft ?? activeColor;
  const invalid = draft.trim().length > 0 && !normalizedDraft;

  useEffect(() => {
    setDraft(color);
  }, [color]);

  useEffect(() => {
    if (!open) return;
    const handlePointerDown = (event: MouseEvent) => {
      if (popoverRef.current?.contains(event.target as Node)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    textInputRef.current?.focus();
    textInputRef.current?.select();
  }, [open]);

  const commitDraft = useCallback((close = false) => {
    if (!normalizedDraft) {
      setDraft(activeColor);
      if (close) setOpen(false);
      return;
    }
    setDraft(normalizedDraft);
    if (normalizedDraft !== activeColor) onSelect(normalizedDraft);
    if (close) setOpen(false);
  }, [activeColor, normalizedDraft, onSelect]);

  const handleTextKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      commitDraft(true);
    } else if (event.key === "Escape") {
      setDraft(activeColor);
      setOpen(false);
    }
  };

  return (
    <div
      ref={popoverRef}
      className={`relative inline-flex h-9 shrink-0 items-center gap-1.5 rounded-lg border bg-neutral-950/70 px-1.5 transition-colors focus-within:border-violet-500 ${
        invalid ? "border-amber-400/70" : "border-neutral-800 hover:border-violet-500/35"
      } ${updating ? "opacity-70" : ""}`}
      title="Canvas color"
    >
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="dialog"
        disabled={updating}
        className="inline-flex h-full items-center gap-1.5 text-xs font-medium text-neutral-200 transition-colors hover:text-violet-100 disabled:cursor-wait"
      >
        <span
          className="h-5 w-7 shrink-0 rounded-sm border border-neutral-300/80"
          style={{ backgroundColor: previewColor }}
          aria-hidden="true"
        />
        <span>Canvas</span>
      </button>
      {open ? (
        <div
          role="dialog"
          aria-label="Edit canvas color"
          className="absolute right-0 top-10 z-50 w-64 rounded-xl border border-neutral-800 bg-neutral-950 p-3 shadow-2xl shadow-black/50"
        >
          <div className="mb-2 flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold text-neutral-100">Canvas color</p>
              <p className="text-[11px] text-neutral-500">Background for layered scenes.</p>
            </div>
            <span
              className="h-8 w-10 shrink-0 rounded-md border border-neutral-300/80"
              style={{ backgroundColor: previewColor }}
              aria-hidden="true"
            />
          </div>
          <input
            type="color"
            value={previewColor}
            onChange={(event) => {
              const nextColor = normalizeCanvasHex(event.target.value);
              if (!nextColor) return;
              setDraft(nextColor);
              onSelect(nextColor);
            }}
            disabled={updating}
            className="mb-3 h-16 w-full cursor-pointer rounded-lg border border-neutral-800 bg-neutral-900 p-1 disabled:cursor-wait"
            aria-label="Select canvas color"
          />
          <label className="block text-[11px] font-medium text-neutral-400" htmlFor="canvas-color-hex">
            Hex value
          </label>
          <input
            id="canvas-color-hex"
            ref={textInputRef}
            type="text"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onBlur={() => commitDraft()}
            onKeyDown={handleTextKeyDown}
            disabled={updating}
            maxLength={7}
            aria-label="Canvas color hex value"
            aria-invalid={invalid}
            className={`mt-1 h-9 w-full rounded-lg border bg-neutral-900 px-3 font-mono text-sm font-semibold uppercase text-neutral-100 outline-none transition-colors placeholder:text-neutral-600 disabled:cursor-wait ${
              invalid ? "border-amber-400/70 focus:border-amber-300" : "border-neutral-800 focus:border-violet-500"
            }`}
            placeholder="#F6C54A"
          />
        </div>
      ) : null}
    </div>
  );
}

function ProjectDetailsButton({
  onClick,
}: {
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group inline-flex h-9 shrink-0 items-center gap-1.5 rounded-lg border border-neutral-800 bg-neutral-900/55 px-2.5 text-xs font-medium text-neutral-200 transition-colors hover:border-violet-500/35 hover:bg-neutral-800/70 hover:text-violet-100"
      title="Open project details"
    >
      <Info className="h-4 w-4 text-violet-300/90" />
      <span>Project details</span>
      <span className="hidden items-center gap-1 text-xs text-neutral-400 2xl:inline-flex">
        <span className="text-neutral-600">·</span>
        <span>stats, costs, media, exports</span>
      </span>
      <ChevronDown className="h-3.5 w-3.5 text-neutral-500 transition-transform group-hover:translate-y-0.5 group-hover:text-violet-300" />
    </button>
  );
}

function DetailMetric({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "emerald" | "sky" | "violet";
}) {
  const toneClass = {
    neutral: "text-neutral-100",
    emerald: "text-emerald-300",
    sky: "text-sky-300",
    violet: "text-violet-300",
  }[tone];

  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-950/50 px-3 py-2">
      <div className="text-[11px] uppercase tracking-[0.08em] text-neutral-500">{label}</div>
      <div className={`mt-1 truncate text-sm font-semibold tabular-nums ${toneClass}`}>{value}</div>
    </div>
  );
}

function DetailAccordion({
  id,
  title,
  summary,
  openSection,
  setOpenSection,
  children,
}: {
  id: string;
  title: string;
  summary: string;
  openSection: string | null;
  setOpenSection: (section: string | null) => void;
  children: ReactNode;
}) {
  const open = openSection === id;

  return (
    <div className="overflow-hidden rounded-lg border border-neutral-800 bg-neutral-950/35">
      <button
        type="button"
        onClick={() => setOpenSection(open ? null : id)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left transition-colors hover:bg-neutral-800/50"
      >
        <span className="min-w-0">
          <span className="block text-sm font-medium text-neutral-100">{title}</span>
          <span className="block truncate text-xs text-neutral-500">{summary}</span>
        </span>
        <ChevronDown className={`h-4 w-4 shrink-0 text-neutral-500 transition-transform duration-200 ${open ? "rotate-180 text-neutral-300" : ""}`} />
      </button>
      <div className={`grid transition-all duration-300 ease-out ${open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"}`}>
        <div className="min-h-0 overflow-hidden">
          <div className="border-t border-neutral-800 p-3">{children}</div>
        </div>
      </div>
    </div>
  );
}

function DistributionTrackingPanel({
  tracking,
  updating,
  onToggle,
  onOpenUploadSuite,
}: {
  tracking: UploadTracking;
  updating: Partial<Record<keyof UploadTracking, boolean>>;
  onToggle: (key: keyof UploadTracking) => void;
  onOpenUploadSuite: () => void;
}) {
  const anyUpdating = Object.values(updating).some(Boolean);

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={onOpenUploadSuite}
        className="flex w-full items-center justify-center gap-2 rounded-lg bg-violet-600 px-3 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-violet-500"
      >
        <Upload className="h-4 w-4" />
        Upload suite
      </button>
      {DISTRIBUTION_TARGETS.map(({ key, label }) => {
        const isUploaded = tracking[key];
        const isUpdating = updating[key];
        return (
          <button
            key={key}
            type="button"
            onClick={() => onToggle(key)}
            disabled={anyUpdating}
            aria-pressed={isUploaded}
            className={`flex w-full items-center justify-between gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors ${
              isUploaded
                ? "border-emerald-500/40 bg-emerald-500/10 hover:bg-emerald-500/20"
                : "border-neutral-800 bg-neutral-950/50 hover:border-neutral-700 hover:bg-neutral-800/60"
            } disabled:cursor-wait disabled:opacity-60`}
          >
            <span className="flex min-w-0 items-center gap-3">
              {isUpdating ? (
                <span className="h-5 w-5 rounded-full border border-neutral-400 border-t-transparent animate-spin" />
              ) : (
                <DistributionIcon target={key} uploaded={isUploaded} className="h-5 w-5" />
              )}
              <span className="truncate text-sm font-medium text-neutral-200">{label}</span>
            </span>
            <span className={`text-xs font-medium ${isUploaded ? "text-emerald-300" : "text-neutral-500"}`}>
              {isUploaded ? "Uploaded" : "Not uploaded"}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function ProjectDetailsModal({
  open,
  onClose,
  sceneCount,
  segmentCount,
  durationStr,
  totalWords,
  projectConfig,
  activePresetName,
  totalCost,
  costBreakdown,
  mediaCounts,
  mediaSceneTotal,
  aiScenePercent,
  exportStatus,
  uploadTracking,
  trackingUpdating,
  onToggleUploadTracking,
  onOpenUploadSuite,
}: {
  open: boolean;
  onClose: () => void;
  sceneCount: number;
  segmentCount: number;
  durationStr: string;
  totalWords: number;
  projectConfig: ProjectConfig | null;
  activePresetName: string | null;
  totalCost: number;
  costBreakdown: ScriptCostBreakdownItem[];
  mediaCounts: Record<string, number>;
  mediaSceneTotal: number;
  aiScenePercent: string;
  exportStatus: ExportFileStatus | null;
  uploadTracking: UploadTracking;
  trackingUpdating: Partial<Record<keyof UploadTracking, boolean>>;
  onToggleUploadTracking: (key: keyof UploadTracking) => void;
  onOpenUploadSuite: () => void;
}) {
  const [openSection, setOpenSection] = useState<string | null>(null);
  const fallbackExportTotal = segmentCount * 3 + 3;
  const exported = exportStatus?.exported ?? 0;
  const exportTotal = exportStatus?.total ?? fallbackExportTotal;
  const uploadedCount = DISTRIBUTION_TARGETS.filter(({ key }) => uploadTracking[key]).length;
  const eliStatus = projectConfig == null || projectConfig.eli_enabled ? "On" : "Off";
  const styleStatus =
    projectConfig && projectConfig.eli_enabled === false && projectConfig.style_preset_enabled
      ? activePresetName ?? "Set"
      : "Off";

  useEffect(() => {
    if (!open) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose, open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/65 px-4 py-10" onClick={onClose}>
      <style>{`
        @keyframes projectDetailsBackdrop {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes projectDetailsWindow {
          from { opacity: 0; transform: translateY(-18px) scale(0.96); filter: blur(6px); }
          to { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
        }
      `}</style>
      <div
        className="w-full max-w-3xl animate-[projectDetailsWindow_220ms_cubic-bezier(0.16,1,0.3,1)] rounded-lg border border-neutral-700 bg-neutral-900 shadow-2xl shadow-black/60"
        role="dialog"
        aria-modal="true"
        aria-labelledby="project-details-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-neutral-800 px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-500/15 text-violet-300">
              <BarChart3 className="h-4 w-4" />
            </span>
            <div>
              <h3 id="project-details-title" className="text-sm font-semibold text-neutral-100">
                Project Details
              </h3>
              <p className="text-xs text-neutral-500">Stats, costs, media mix, exports, and distribution.</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-md text-neutral-500 transition-colors hover:bg-neutral-800 hover:text-neutral-200"
            aria-label="Close project details"
          >
            <X size={16} />
          </button>
        </div>

        <div className="max-h-[calc(100vh-10rem)] overflow-y-auto p-4">
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <DetailMetric label="Eli" value={eliStatus} tone={eliStatus === "On" ? "emerald" : "neutral"} />
            <DetailMetric label="Style" value={styleStatus} tone={styleStatus === "Off" ? "neutral" : "violet"} />
            <DetailMetric label="Scenes" value={sceneCount.toLocaleString()} />
            <DetailMetric label="Segments" value={segmentCount.toLocaleString()} />
            <DetailMetric label="Duration" value={durationStr} />
            <DetailMetric label="Words" value={totalWords > 0 ? totalWords.toLocaleString() : "0"} />
            <DetailMetric label="Cost" value={formatCost(totalCost)} tone="emerald" />
            <DetailMetric label="Exports" value={`${exported}/${exportTotal}`} tone="sky" />
          </div>

          <div className="mt-4 space-y-2">
            <DetailAccordion
              id="cost"
              title="Cost Breakdown"
              summary={`${formatCost(totalCost)} across ${costBreakdown.length} tracked item${costBreakdown.length !== 1 ? "s" : ""}`}
              openSection={openSection}
              setOpenSection={setOpenSection}
            >
              <CostBreakdownPanel totalCost={totalCost} breakdown={costBreakdown} />
            </DetailAccordion>

            <DetailAccordion
              id="media"
              title="Visual Mode Mix"
              summary={`${aiScenePercent} assigned across ${mediaSceneTotal} visual scene${mediaSceneTotal !== 1 ? "s" : ""}`}
              openSection={openSection}
              setOpenSection={setOpenSection}
            >
              <MediaBreakdownPanel modeCounts={mediaCounts} totalScenes={mediaSceneTotal} />
            </DetailAccordion>

            <DetailAccordion
              id="exports"
              title="Exported Files"
              summary={`${exported}/${exportTotal} files in the project export folder`}
              openSection={openSection}
              setOpenSection={setOpenSection}
            >
              <div className="space-y-3">
                <ExportFileBreakdownPanel status={exportStatus} segmentCount={segmentCount} />
              </div>
            </DetailAccordion>

            <DetailAccordion
              id="distribution"
              title="Distribution"
              summary={`${uploadedCount}/4 destinations marked uploaded`}
              openSection={openSection}
              setOpenSection={setOpenSection}
            >
              <DistributionTrackingPanel
                tracking={uploadTracking}
                updating={trackingUpdating}
                onToggle={onToggleUploadTracking}
                onOpenUploadSuite={onOpenUploadSuite}
              />
            </DetailAccordion>
          </div>
        </div>
      </div>
    </div>
  );
}

function ViewerSwitchRow({
  format,
  asset,
  activeTab,
  exportsFolderOpening,
  onFormatChange,
  onAssetChange,
  onTabChange,
  onOpenProjectDetails,
  onOpenExportsFolder,
  canvasColor,
  canvasColorUpdating,
  onSelectCanvasColor,
}: {
  format: ViewerFormat;
  asset: ViewerAsset;
  activeTab: ViewerTab;
  exportsFolderOpening: boolean;
  onFormatChange: (format: ViewerFormat) => void;
  onAssetChange: (asset: ViewerAsset) => void;
  onTabChange: (tab: ViewerTab) => void;
  onOpenProjectDetails: () => void;
  onOpenExportsFolder: () => void;
  canvasColor: string;
  canvasColorUpdating: boolean;
  onSelectCanvasColor: (color: string) => void;
}) {
  const activeNavKey: ViewerNavKey = asset === "render" ? activeTab : asset;
  const handleNavChange = (key: ViewerNavKey) => {
    if (key === "thumbnails" || key === "seo") {
      onAssetChange(key);
      return;
    }

    onAssetChange("render");
    onTabChange(key);
  };

  return (
    <div className="shrink-0 border-y border-neutral-900/80 px-5 py-2">
      <div className="flex min-w-0 items-center gap-2">
        <div className="inline-flex shrink-0 items-center rounded-xl border border-neutral-800/80 bg-neutral-900/45 p-1">
          {FORMAT_OPTIONS.map(({ key, label, Icon }) => (
            <button
              key={key}
              onClick={() => onFormatChange(key)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg transition-all duration-200 whitespace-nowrap ${
                format === key ? "bg-violet-500/20 text-violet-100 shadow-sm" : "text-neutral-500 hover:text-neutral-200"
              }`}
            >
              <Icon className="w-3.5 h-3.5 shrink-0" />
              {label}
            </button>
          ))}
        </div>
        <div className="inline-flex min-w-0 flex-1 items-center overflow-x-auto rounded-xl border border-neutral-800/80 bg-neutral-900/45 p-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {VIEWER_NAV_OPTIONS.map(({ key, label, Icon }) => {
            const isActiveNav = activeNavKey === key;
            return (
              <button
                key={key}
                onClick={() => handleNavChange(key)}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg transition-all duration-200 whitespace-nowrap ${
                  isActiveNav ? "bg-violet-500/20 text-violet-100 shadow-sm" : "text-neutral-500 hover:text-neutral-200"
                }`}
              >
                <Icon className="w-3.5 h-3.5 shrink-0" />
                {label}
              </button>
            );
          })}
        </div>
        <div className="ml-auto inline-flex shrink-0 items-center gap-2">
          <ProjectDetailsButton onClick={onOpenProjectDetails} />
          <CanvasColorButton
            color={canvasColor}
            updating={canvasColorUpdating}
            onSelect={onSelectCanvasColor}
          />
          <OpenExportsButton opening={exportsFolderOpening} onOpen={onOpenExportsFolder} />
        </div>
      </div>
    </div>
  );
}

function TimelineEditor({
  scriptId,
  isActive = true,
  initialContent,
  title,
  onTitleUpdated,
  onBack,
  onSaveStateChange,
  onRecordVoiceover,
}: {
  scriptId: string;
  isActive?: boolean;
  initialContent: ScriptContent;
  title: string;
  onTitleUpdated?: (script: ScriptRead) => void;
  onBack: () => void;
  onSaveStateChange?: (state: SaveState) => void;
  onRecordVoiceover?: () => void;
}) {
  const state = useTimelineState(scriptId, initialContent);
  const [editableTitle, setEditableTitle] = useState(title);
  const [titleDraft, setTitleDraft] = useState(title);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleSaving, setTitleSaving] = useState(false);
  const render = useRenderState(
    scriptId,
    editableTitle,
    initialContent.seo_metadata,
    initialContent.short_form_seo_metadata,
    initialContent.format_id,
  );
  // Operation progress tracking
  const fxProgress = useOperationProgress("fx_generation");
  const eliProgress = useOperationProgress("eli_generation");
  const titleCardProgress = useOperationProgress("title_card_generation");

  // Voice picker hook
  const voicePicker = useVoicePicker();

  const [showUpload, setShowUpload] = useState(false);
  const [uploadSuite, setUploadSuite] = useState<UploadSuiteStatus | null>(null);
  const [uploadSuiteChecking, setUploadSuiteChecking] = useState(false);
  const [exportsFolderOpening, setExportsFolderOpening] = useState(false);

  const openUploadPanel = useCallback(async () => {
    if (uploadSuiteChecking) return;
    setUploadSuiteChecking(true);
    try {
      const suite = await getUploadSuiteStatus(scriptId);
      if (!suite.ready) {
        const details = suite.missing.slice(0, 4).join(", ");
        const suffix = suite.missing.length > 4 ? `, +${suite.missing.length - 4} more` : "";
        showToast(`Upload suite is not ready. Missing: ${details}${suffix}`);
        return;
      }
      setUploadSuite(suite);
      setShowUpload(true);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed to check upload suite");
    } finally {
      setUploadSuiteChecking(false);
    }
  }, [scriptId, uploadSuiteChecking]);

  const handleOpenExportsFolder = useCallback(async () => {
    if (exportsFolderOpening) return;
    setExportsFolderOpening(true);
    try {
      const { folder_path } = await ensureScriptExportsFolder(scriptId);
      await openPath(folder_path);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed to open exports folder");
    } finally {
      setExportsFolderOpening(false);
    }
  }, [exportsFolderOpening, scriptId]);

  const [showVoiceSetup, setShowVoiceSetup] = useState(false);
  const [pendingAudioAction, setPendingAudioAction] = useState<"all" | string | null>(null);
  const [generatingFX, setGeneratingFX] = useState(false);
  const [fxStep, setFxStep] = useState<string>("");
  const [fxProgressPct, setFxProgressPct] = useState<number>(0);
  const [generatingEli, setGeneratingEli] = useState(false);
  const [eliStep, setEliStep] = useState<string>("");
  const [eliProgressPct, setEliProgressPct] = useState<number>(0);
  const [eliProgressTotal, setEliProgressTotal] = useState<number>(0);
  const [confirmOverwrite, setConfirmOverwrite] = useState<"images" | "audio" | "fx" | "eli" | "thumbnails" | "seo" | "export" | null>(null);
  const [thumbnailsOverwriteInfo, setThumbnailsOverwriteInfo] = useState<{
    titleCards: boolean;
    shortForm: boolean;
    longForm: boolean;
  } | null>(null);
  const pixelsPerSecond = 26;
  const [exportTestJobId, setExportTestJobId] = useState<string | null>(null);
  const [exportTestStep, setExportTestStep] = useState("");
  const [exportTestProgress, setExportTestProgress] = useState(0);
  const [exportTestEstimatedSeconds, setExportTestEstimatedSeconds] = useState<number | null>(null);
  const [showExportTestModal, setShowExportTestModal] = useState(false);
  const [titleCardGenerating, setTitleCardGenerating] = useState(false);
  const [thumbnailsInline, setThumbnailsInline] = useState<ThumbnailConcept[]>([]);
  const [thumbnailsInlineGenerating, setThumbnailsInlineGenerating] = useState(false);
  const [thumbnailLabelStyleInline, setThumbnailLabelStyleInline] = useState<ThumbnailLabelStyle>("time_periods");
  const [showThumbnailModal, setShowThumbnailModal] = useState(false);
  const [totalCost, setTotalCost] = useState<number>(0);
  const [costBreakdown, setCostBreakdown] = useState<ScriptCostBreakdownItem[]>([]);
  const [showProjectDetails, setShowProjectDetails] = useState(false);
  const [exportFileStatus, setExportFileStatus] = useState<ExportFileStatus | null>(null);
  const [uploadTracking, setUploadTracking] = useState<UploadTracking>(DEFAULT_UPLOAD_TRACKING);
  const [trackingUpdating, setTrackingUpdating] = useState<Partial<Record<keyof UploadTracking, boolean>>>({});
  const [lastAudioGenTimestamp, setLastAudioGenTimestamp] = useState(0);
  const [lastFXGenTimestamp, setLastFXGenTimestamp] = useState(0);
  const [yoloStep, setYoloStep] = useState<string | null>(null);
  const [yoloRenderRunning, setYoloRenderRunning] = useState(false);
  const [yoloStopping, setYoloStopping] = useState(false);
  const [titleCardProgressPct, setTitleCardProgressPct] = useState<number | null>(null);
  const [thumbnailPhases, setThumbnailPhases] = useState<ThumbnailPhaseItem[]>([]);
  const [activeTab, setActiveTab] = useState<ViewerTab>("timeline");
  const [viewerFormat, setViewerFormat] = useState<ViewerFormat>("long-form");
  const [viewerAsset, setViewerAsset] = useState<ViewerAsset>("render");
  const [sfThumbnailPaths, setSfThumbnailPaths] = useState<Record<number, string | undefined>>({});
  const [sfRenderPaths, setSfRenderPaths] = useState<Record<number, string | undefined>>({});
  const [productionBusyTask, setProductionBusyTask] = useState<ProductionTask | null>(null);
  const [productionProgress, setProductionProgress] = useState<number | null>(null);
  const [productionError, setProductionError] = useState<string | null>(null);
  const [projectConfig, setProjectConfig] = useState<ProjectConfig | null>(null);
  const [showMainCharacterDrawer, setShowMainCharacterDrawer] = useState(false);
  const [canvasColorUpdating, setCanvasColorUpdating] = useState(false);
  const [visualTreatmentAssignments, setVisualTreatmentAssignments] = useState<VisualTreatmentAssignment[] | null>(null);
  const [visualTreatmentAnalyzing, setVisualTreatmentAnalyzing] = useState(false);
  const [visualTreatmentJobId, setVisualTreatmentJobId] = useState<string | null>(null);
  const { activePreset } = useStylePreset();
  const yoloCancelledRef = useRef(false);
  const yoloStoppingRef = useRef(false);
  const productionBusyRef = useRef(false);
  const microTimelineRef = useRef<MicroTimelineHandle>(null);
  const activeScriptIdRef = useRef(scriptId);

  const media = useMediaReview({ scriptId, content: state.content });

  useEffect(() => {
    setEditableTitle(title);
    setTitleDraft(title);
    setEditingTitle(false);
  }, [scriptId, title]);

  useEffect(() => {
    activeScriptIdRef.current = scriptId;
    setVisualTreatmentJobId(null);
    setVisualTreatmentAssignments(null);
    setVisualTreatmentAnalyzing(false);
  }, [scriptId]);

  useEffect(() => {
    if (!visualTreatmentJobId) return;

    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    const poll = async () => {
      try {
        const status = await getVisualTreatmentStatus(visualTreatmentJobId);
        if (cancelled) return;
        if (status.status === "completed") {
          setVisualTreatmentAssignments(status.assignments ?? []);
          setVisualTreatmentAnalyzing(false);
          setVisualTreatmentJobId(null);
          showToast("Visual modes analyzed.", "success");
          return;
        }
        if (status.status === "failed" || status.status === "cancelled") {
          setVisualTreatmentAnalyzing(false);
          setVisualTreatmentJobId(null);
          showToast(status.error || "Visual mode analysis failed");
          return;
        }
        timeoutId = setTimeout(poll, 1200);
      } catch (err) {
        if (cancelled) return;
        setVisualTreatmentAnalyzing(false);
        setVisualTreatmentJobId(null);
        showToast(err instanceof Error ? err.message : "Failed to check visual mode status");
      }
    };

    timeoutId = setTimeout(poll, 1200);

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [scriptId, visualTreatmentJobId]);

  useEffect(() => {
    if (!scriptId) return;
    let cancelled = false;
    (async () => {
      const res = await getProjectConfig(scriptId);
      if (!cancelled && res.ok) {
        setProjectConfig(res.data as ProjectConfig);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [scriptId]);

  // Auto-switch to visual modes tab when new assignments arrive
  useEffect(() => {
    if (media.hasPendingReview) setActiveTab("media-sources");
  }, [media.hasPendingReview]);

  const handleSelectCanvasColor = useCallback(async (color: string) => {
    try {
      const requestScriptId = scriptId;
      setCanvasColorUpdating(true);
      const saved = await state.save();
      if (activeScriptIdRef.current !== requestScriptId) return;
      if (!saved) {
        showToast("Save your timeline changes before updating the canvas color.");
        return;
      }
      const result = await updateVisualCanvas(requestScriptId, color);
      if (activeScriptIdRef.current !== requestScriptId) return;
      state.setContent(result.script);
      showToast("Canvas color updated.", "success");
    } catch (err) {
      if (activeScriptIdRef.current !== scriptId) return;
      showToast(err instanceof Error ? err.message : "Failed to update canvas color");
    } finally {
      if (activeScriptIdRef.current === scriptId) setCanvasColorUpdating(false);
    }
  }, [scriptId, state]);

  const handleAnalyzeVisualTreatments = useCallback(async () => {
    try {
      const saved = await state.save();
      if (activeScriptIdRef.current !== scriptId) return;
      if (!saved) {
        showToast("Save your timeline changes before analyzing visual modes.");
        return;
      }
      setVisualTreatmentAnalyzing(true);
      setVisualTreatmentAssignments(null);
      const { job_id } = await analyzeVisualTreatments(scriptId);
      if (activeScriptIdRef.current !== scriptId) return;
      setVisualTreatmentJobId(job_id);
    } catch (err) {
      setVisualTreatmentAnalyzing(false);
      showToast(err instanceof Error ? err.message : "Failed to analyze visual modes");
    }
  }, [scriptId, state]);

  const handleApplyVisualTreatments = useCallback(async (assignments: VisualTreatmentAssignment[]) => {
    try {
      const requestScriptId = scriptId;
      const saved = await state.save();
      if (activeScriptIdRef.current !== requestScriptId) return;
      if (!saved) {
        showToast("Save your timeline changes before applying visual modes.");
        return;
      }
      const result = await applyVisualTreatmentAssignments(requestScriptId, assignments);
      if (activeScriptIdRef.current !== requestScriptId) return;
      state.setContent(result.script);
      setVisualTreatmentAssignments(assignments);
      showToast("Visual modes applied.", "success");
    } catch (err) {
      if (activeScriptIdRef.current !== scriptId) return;
      showToast(err instanceof Error ? err.message : "Failed to apply visual modes");
    }
  }, [scriptId, state]);

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

  const handleShortFormThumbnailStatusChange = useCallback((paths?: Record<number, string | undefined>) => {
    if (paths) {
      setSfThumbnailPaths(paths);
      return;
    }
    void refreshShortFormThumbnailStatus();
  }, [refreshShortFormThumbnailStatus]);

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

  const refreshUploadTracking = useCallback(async () => {
    try {
      const tracking = await getUploadTracking(scriptId);
      setUploadTracking(tracking);
    } catch {
      // Upload tracking should not block timeline editing.
    }
  }, [scriptId]);

  const refreshExportFileStatus = useCallback(async () => {
    try {
      setExportFileStatus(await getExportFileStatus(scriptId));
    } catch {
      setExportFileStatus(null);
    }
  }, [scriptId]);

  // Fetch cost on mount
  useEffect(() => { refreshCost(); }, [refreshCost]);
  useEffect(() => { void refreshExportFileStatus(); }, [refreshExportFileStatus]);

  useEffect(() => {
    if (isActive) void refreshUploadTracking();
  }, [isActive, refreshUploadTracking]);

  useEffect(() => {
    if (!showProjectDetails) return;
    void refreshUploadTracking();
    void refreshCost();
    void refreshExportFileStatus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setShowProjectDetails(false);
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [refreshCost, refreshExportFileStatus, refreshUploadTracking, showProjectDetails]);

  const handleToggleUploadTracking = useCallback(async (key: keyof UploadTracking) => {
    if (Object.values(trackingUpdating).some(Boolean)) return;
    const next = !uploadTracking[key];
    setUploadTracking((prev) => ({ ...prev, [key]: next }));
    setTrackingUpdating((prev) => ({ ...prev, [key]: true }));
    try {
      const updated = await apiSetUploadTracking(scriptId, { [key]: next });
      setUploadTracking(updated);
    } catch {
      setUploadTracking((prev) => ({ ...prev, [key]: !next }));
    } finally {
      setTrackingUpdating((prev) => ({ ...prev, [key]: false }));
    }
  }, [scriptId, trackingUpdating, uploadTracking]);

  const handleOpenDistributionUpload = useCallback(() => {
    setShowProjectDetails(false);
    void openUploadPanel();
  }, [openUploadPanel]);

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

  // Auto-load thumbnails from disk on mount
  useEffect(() => {
    (async () => {
      try {
        const res = await api.get(`/api/thumbnail/${scriptId}`);
        if (res.ok) {
          const data = res.data as { concepts: ThumbnailConcept[] };
          setThumbnailsInline(data.concepts);
        }
      } catch { /* thumbnails are optional */ }
    })();
  }, [scriptId]);

  // Cancel refs for single async operations
  const fxCancelledRef = useRef(false);
  const eliCancelledRef = useRef(false);
  const titleCardCancelledRef = useRef(false);
  const thumbnailsCancelledRef = useRef(false);

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

  const mainCharacterReferenceReady =
    projectConfig?.eli_enabled !== false ||
    Boolean(projectConfig.main_character_reference_url);

  const requireMainCharacterReference = useCallback(() => {
    if (mainCharacterReferenceReady) return true;
    setShowMainCharacterDrawer(true);
    showToast("Create and select a main character reference before generating images.", "info");
    return false;
  }, [mainCharacterReferenceReady]);

  const generateImageWithCharacterGate = useCallback((sceneId: string) => {
    if (!requireMainCharacterReference()) return;
    void state.generateImage(sceneId);
  }, [requireMainCharacterReference, state]);

  const generateAllImagesWithCharacterGate = useCallback((missingOnly = false) => {
    if (!requireMainCharacterReference()) return;
    void state.generateAllImages(missingOnly);
  }, [requireMainCharacterReference, state]);

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
      if (state.selectedSceneId) generateImageWithCharacterGate(state.selectedSceneId);
    },
    generateAllImages: () => generateAllImagesWithCharacterGate(),
    openUpload: () => {
      void openUploadPanel();
    },
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

  // Visual mode counts (exclude title cards)
  const mediaCounts = allScenes
    .filter((sc) => !sc.is_title_card)
    .reduce(
      (acc, sc) => {
        const mode = sc.visual_mode ?? "full_frame";
        acc[mode] = (acc[mode] ?? 0) + 1;
        return acc;
      },
      {} as Record<string, number>,
    );
  const mediaSceneTotal = allScenes.filter((sc) => !sc.is_title_card).length;
  const aiSceneCount = Object.values(mediaCounts).reduce((sum, count) => sum + count, 0);
  const aiScenePercent = formatScenePercent(aiSceneCount, mediaSceneTotal);

  // Check if assets already exist for overwrite confirmation
  const hasExistingImages = allScenes.some((sc) => !sc.is_title_card && (sc.image_url || sc.frame_urls?.length));
  const hasExistingAudio = allScenes.some((sc) => sc.audio_url);
  const hasExistingFX = allScenes.some((sc) => sc.fx);

  const startTitleEdit = () => {
    setTitleDraft(editableTitle);
    setEditingTitle(true);
  };

  const cancelTitleEdit = () => {
    setTitleDraft(editableTitle);
    setEditingTitle(false);
  };

  const saveTitleEdit = async () => {
    const nextTitle = titleDraft.trim();
    if (!nextTitle || nextTitle === editableTitle || titleSaving) {
      cancelTitleEdit();
      return;
    }

    setTitleSaving(true);
    try {
      if (state.isDirty) {
        const saved = await state.save();
        if (!saved) return;
      }
      const res = await api.put(`/api/scripts/${scriptId}/title`, { title: nextTitle });
      if (!res.ok) return;
      const updated = res.data as ScriptRead;
      setEditableTitle(updated.topic_title);
      setTitleDraft(updated.topic_title);
      state.setContent(updated.script);
      onTitleUpdated?.(updated);
      setEditingTitle(false);
      showToast("Title updated.", "success");
    } finally {
      setTitleSaving(false);
    }
  };

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
  const sfThumbnailCount = state.content.segments.filter((_, idx) => sfThumbnailPaths[idx]).length;
  const sfRenderCount = Object.values(sfRenderPaths).filter(Boolean).length;
  const shortFormSeoCount = render.shortFormSeoMetadata?.shorts.length ?? 0;
  const lfSeoDone = render.seoMetadata != null;
  const sfSeoDone = segmentCount > 0 && shortFormSeoCount >= segmentCount;
  const sfThumbnailsDone = segmentCount > 0 && sfThumbnailCount >= segmentCount;
  const sfRendersDone = segmentCount > 0 && sfRenderCount >= segmentCount;
  const sfSeoMissingCount = Math.max(0, segmentCount - shortFormSeoCount);
  const sfThumbnailMissingCount = Math.max(0, segmentCount - sfThumbnailCount);
  const sfRenderMissingCount = Math.max(0, segmentCount - sfRenderCount);

  // Combined Thumbnails (title cards + SF thumbnails + LF thumbnail)
  const lfThumbnailDone = thumbnailsInline.length > 0 && !!thumbnailsInline[0]?.image_url;
  const titleCardsApplicable = state.hasTitleCards;
  const titleCardsAllDone = !titleCardsApplicable || allTitleCardsGenerated;
  const titleCardsMissingCount = titleCardsApplicable ? titleScenes.filter((sc) => !sc.image_url).length : 0;
  const sfApplicable = segmentCount > 0;
  const sfThumbnailsAllDone = !sfApplicable || sfThumbnailsDone;
  const allThumbnailsDone = titleCardsAllDone && sfThumbnailsAllDone && lfThumbnailDone;
  const hasExistingThumbnails =
    (titleCardsApplicable && titleScenes.some((sc) => sc.image_url)) ||
    sfThumbnailCount > 0 ||
    lfThumbnailDone;
  const missingThumbnailCount =
    titleCardsMissingCount + sfThumbnailMissingCount + (lfThumbnailDone ? 0 : 1);
  const thumbnailsBusy =
    titleCardGenerating ||
    productionBusyTask === "sf-thumbnails" ||
    thumbnailsInlineGenerating ||
    productionBusyTask === "thumbnails-combined";

  // Combined SEO (LF SEO + SF SEO + auto-export markdown)
  const allSeoDone = lfSeoDone && (segmentCount === 0 || sfSeoDone);
  const hasExistingSeo = lfSeoDone || shortFormSeoCount > 0;
  const missingSeoCount = (lfSeoDone ? 0 : 1) + sfSeoMissingCount;
  const seoBusy =
    render.seoGenerating ||
    render.shortFormSeoGenerating ||
    productionBusyTask === "lf-seo" ||
    productionBusyTask === "sf-seo" ||
    productionBusyTask === "seo-combined";

  // Combined Export (LF render + SF renders)
  const lfRenderDone = render.youtubeUrl != null;
  const lfRendering = render.youtubeStatus?.status === "running" || render.youtubeStatus?.status === "pending";
  const allExportsDone = lfRenderDone && (segmentCount === 0 || sfRendersDone);
  const hasExistingExports = lfRenderDone || sfRenderCount > 0;
  const missingExportCount = (lfRenderDone ? 0 : 1) + sfRenderMissingCount;
  const exportBusy =
    lfRendering ||
    productionBusyTask === "sf-renders" ||
    productionBusyTask === "export-combined";

  const anyProductionBusy =
    productionBusyTask !== null ||
    render.seoGenerating ||
    render.shortFormSeoGenerating ||
    lfRendering ||
    titleCardGenerating ||
    thumbnailsInlineGenerating;

  const confirmAndGenerateImages = () => {
    if (!requireMainCharacterReference()) return;
    if (hasExistingImages) {
      setConfirmOverwrite("images");
    } else {
      generateAllImagesWithCharacterGate();
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

  const generateMissingImages = () => generateAllImagesWithCharacterGate(true);
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

  const setThumbnailPhase = (
    key: string,
    status: ThumbnailPhaseStatus,
    detail?: string,
  ) => {
    setThumbnailPhases((prev) =>
      prev.map((phase) =>
        phase.key === key ? { ...phase, status, detail: detail ?? phase.detail } : phase,
      ),
    );
  };

  const resetThumbnailPhaseProgress = (missingOnly: boolean) => {
    setThumbnailPhases([
      {
        key: "title-cards",
        label: "Title cards",
        status: titleCardsApplicable && (!missingOnly || !titleCardsAllDone) ? "pending" : "skipped",
        detail: titleCardsApplicable
          ? titleCardsAllDone && missingOnly
            ? "Already complete"
            : `${titleScenes.length} chapter images`
          : "No title-card scenes",
      },
      {
        key: "short-form",
        label: "Short-form thumbnails",
        status: sfApplicable && (!missingOnly || !sfThumbnailsAllDone) ? "pending" : "skipped",
        detail: sfApplicable
          ? sfThumbnailsAllDone && missingOnly
            ? "Already complete"
            : `${segmentCount} vertical covers`
          : "No segments",
      },
      {
        key: "long-form",
        label: "Long-form thumbnail",
        status: !missingOnly || !lfThumbnailDone ? "pending" : "skipped",
        detail: lfThumbnailDone && missingOnly ? "Already complete" : "Active YouTube thumbnail",
      },
    ]);
  };

  const titleCardPhaseDetail = (currentStep?: string | null, fallbackProgress?: number) => {
    if (currentStep) {
      try {
        const parsed = JSON.parse(currentStep) as { completed?: number[]; total?: number };
        if (Array.isArray(parsed.completed) && typeof parsed.total === "number") {
          return `${parsed.completed.length} of ${parsed.total} chapter images`;
        }
      } catch {
        // Non-JSON current_step values are normal near job completion.
      }
    }
    if (typeof fallbackProgress === "number" && titleScenes.length > 0) {
      return `${Math.round(fallbackProgress * titleScenes.length)} of ${titleScenes.length} chapter images`;
    }
    return `${titleScenes.length} chapter images`;
  };

  // Combined Thumbnails handler — runs title cards + SF thumbnails + LF thumbnail
  const runThumbnailsCombined = (missingOnly: boolean) => {
    if (!requireMainCharacterReference()) return;
    void runProductionTask("thumbnails-combined", async () => {
      const isCancelled = () => titleCardCancelledRef.current || thumbnailsCancelledRef.current;
      let titleCardsRegenerated = false;

      // Reset cancel flags at the start of a fresh run
      titleCardCancelledRef.current = false;
      thumbnailsCancelledRef.current = false;
      resetThumbnailPhaseProgress(missingOnly);

      // 1. Title cards
      if (titleCardsApplicable && (!missingOnly || !titleCardsAllDone)) {
        const segCount = state.content.segments.length;
        setTitleCardGenerating(true);
        setTitleCardProgressPct(0);
        setThumbnailPhase("title-cards", "running", `0 of ${segCount} chapter images`);
        titleCardProgress.start(segCount);
        try {
          await state.generateTitleCardsStandalone(!missingOnly, (status) => {
            if (typeof status.progress === "number") setTitleCardProgressPct(status.progress);
            setThumbnailPhase("title-cards", "running", titleCardPhaseDetail(status.current_step, status.progress));
          });
          if (!isCancelled()) {
            setTitleCardProgressPct(1);
            setThumbnailPhase("title-cards", "done", `${segCount} of ${segCount} chapter images`);
            titleCardsRegenerated = true;
          }
        } finally {
          setTitleCardGenerating(false);
          setTitleCardProgressPct(null);
          titleCardProgress.end(segCount);
        }
        if (isCancelled()) return;
      } else {
        setThumbnailPhase(
          "title-cards",
          "skipped",
          titleCardsApplicable ? "Already complete" : "No title-card scenes",
        );
      }

      // 2. Short-form thumbnails
      if (!isCancelled() && sfApplicable && (!missingOnly || !sfThumbnailsAllDone)) {
        const refreshed = missingOnly ? await refreshShortFormThumbnailStatus() : null;
        if (missingOnly && refreshed) {
          const indices = state.content.segments.map((_, idx) => idx).filter((idx) => !refreshed[idx]);
          if (indices.length > 0) {
            setThumbnailPhase("short-form", "running", `0 of ${indices.length} missing covers`);
            const { job_id } = await generateShortFormThumbnailsBatch(scriptId, indices);
            await pollShortFormJob(job_id, (status) => {
              if (isCancelled()) return;
              if (typeof status.progress === "number") setProductionProgress(status.progress);
              if (typeof status.progress === "number") {
                setThumbnailPhase(
                  "short-form",
                  "running",
                  `${Math.round(status.progress * indices.length)} of ${indices.length} missing covers`,
                );
              }
            });
            if (!isCancelled()) {
              await refreshShortFormThumbnailStatus();
              setThumbnailPhase("short-form", "done", `${indices.length} missing covers generated`);
            }
          } else {
            setThumbnailPhase("short-form", "skipped", "Already complete");
          }
        } else {
          setThumbnailPhase("short-form", "running", `0 of ${segmentCount} vertical covers`);
          const { job_id } = await generateShortFormThumbnailsAll(scriptId);
          await pollShortFormJob(job_id, (status) => {
            if (isCancelled()) return;
            if (typeof status.progress === "number") setProductionProgress(status.progress);
            if (typeof status.progress === "number") {
              setThumbnailPhase(
                "short-form",
                "running",
                `${Math.round(status.progress * segmentCount)} of ${segmentCount} vertical covers`,
              );
            }
          });
          if (!isCancelled()) {
            await refreshShortFormThumbnailStatus();
            setThumbnailPhase("short-form", "done", `${segmentCount} vertical covers`);
          }
        }
      } else {
        setThumbnailPhase("short-form", "skipped", sfApplicable ? "Already complete" : "No segments");
      }

      // 3. Long-form thumbnail.
      //   - missingOnly: only generate when the main thumbnail is absent.
      //   - full regen: also recomposite when title cards were regenerated, since the
      //     youtube-listicle composite depends on per-segment circle images.
      const shouldRecomposite = missingOnly
        ? !lfThumbnailDone
        : (titleCardsRegenerated || !lfThumbnailDone);
      if (!isCancelled() && shouldRecomposite) {
        setThumbnailPhase("long-form", "running", "Compositing active YouTube thumbnail");
        await handleRecompositeThumbnailInline();
        if (!isCancelled()) setThumbnailPhase("long-form", "done", "Active YouTube thumbnail ready");
      } else {
        setThumbnailPhase("long-form", "skipped", lfThumbnailDone ? "Already complete" : "No update needed");
      }
    });
  };

  const confirmAndGenerateThumbnails = async () => {
    if (!requireMainCharacterReference()) return;
    const [longFormThumbnails, shortFormPaths, latestContent] = await Promise.all([
      refreshLongFormThumbnailsInline(false),
      refreshShortFormThumbnailStatus(),
      refreshScriptContent(),
    ]);
    const hasExistingLongFormThumbnail = longFormThumbnails.some((concept) => concept.image_url);
    const hasExistingTitleCards = latestContent.segments.some((segment) =>
      segment.scenes.some((scene) => scene.is_title_card && scene.image_url),
    );
    const hasExistingShortFormThumbnails = Object.values(shortFormPaths).some(Boolean);
    if (hasExistingTitleCards || hasExistingShortFormThumbnails || hasExistingLongFormThumbnail) {
      setThumbnailsOverwriteInfo({
        titleCards: hasExistingTitleCards,
        shortForm: hasExistingShortFormThumbnails,
        longForm: hasExistingLongFormThumbnail,
      });
      setConfirmOverwrite("thumbnails");
    } else {
      runThumbnailsCombined(false);
    }
  };

  const generateMissingThumbnails = () => {
    runThumbnailsCombined(true);
  };

  const cancelThumbnailsCombined = () => {
    // Flips both refs so any in-flight phase observes cancel.
    // - titleCardCancelledRef: checked between phases
    // - thumbnailsCancelledRef: checked inside handleRecompositeThumbnailInline (phase 3)
    titleCardCancelledRef.current = true;
    thumbnailsCancelledRef.current = true;
    setTitleCardGenerating(false);
  };

  // Combined SEO handler — runs LF SEO + SF SEO + auto-export markdown
  const runSeoCombined = (missingOnly: boolean) => {
    void runProductionTask("seo-combined", async () => {
      if (!missingOnly || !lfSeoDone) {
        await render.generateSEO();
      }
      if (segmentCount > 0 && (!missingOnly || !sfSeoDone)) {
        await render.generateShortFormSEO();
      }
      // Auto-export markdown for both. Surface failures via toast but
      // don't fail the whole task — generation already succeeded.
      try {
        await exportLongFormSEO(scriptId);
      } catch (err) {
        showToast(`Long-form SEO markdown export failed: ${err instanceof Error ? err.message : "unknown error"}`);
      }
      if (segmentCount > 0) {
        try {
          await exportShortFormSEO(scriptId);
        } catch (err) {
          showToast(`Short-form SEO markdown export failed: ${err instanceof Error ? err.message : "unknown error"}`);
        }
      }
    });
  };

  const confirmAndGenerateSeo = () => {
    if (hasExistingSeo) {
      setConfirmOverwrite("seo");
    } else {
      runSeoCombined(false);
    }
  };

  const generateMissingSeo = () => {
    runSeoCombined(true);
  };

  // Combined Export handler — renders LF + all SF videos
  const runExportCombined = (missingOnly: boolean) => {
    void runProductionTask("export-combined", async () => {
      if (!missingOnly || !lfRenderDone) {
        const jobId = await render.startYoutubeRender();
        if (jobId) {
          // Poll the new jobId directly. Avoids relying on youtubeStatusRef,
          // which can read a stale "completed"/"failed" status from a prior
          // run before useRenderState's effect commits the reset.
          for (;;) {
            const res = await api.get(`/api/render/status/${jobId}`);
            if (res.ok) {
              const status = res.data as { status: string; error?: string };
              if (status.status === "completed") break;
              if (status.status === "failed") {
                throw new Error(status.error ?? "Long-form render failed");
              }
            }
            await new Promise((r) => setTimeout(r, 1500));
          }
        }
      }
      if (sfApplicable && (!missingOnly || !sfRendersDone)) {
        const refreshed = missingOnly ? await refreshShortFormRenderStatus() : null;
        if (missingOnly && refreshed) {
          const indices = state.content.segments.map((_, idx) => idx).filter((idx) => !refreshed[idx]);
          if (indices.length > 0) {
            const { job_id } = await renderShortBatch(scriptId, indices);
            await pollShortFormJob(job_id, (status) => {
              if (typeof status.progress === "number") setProductionProgress(status.progress);
            });
            await refreshShortFormRenderStatus();
          }
        } else {
          const { job_id } = await renderShortAll(scriptId);
          await pollShortFormJob(job_id, (status) => {
            if (typeof status.progress === "number") setProductionProgress(status.progress);
          });
          await refreshShortFormRenderStatus();
        }
      }
    });
  };

  const confirmAndExport = () => {
    if (hasExistingExports) {
      setConfirmOverwrite("export");
    } else {
      runExportCombined(false);
    }
  };

  const exportMissing = () => {
    runExportCombined(true);
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

  const refreshLongFormThumbnailsInline = useCallback(async (respectCancellation = true) => {
    const res = await api.get(`/api/thumbnail/${scriptId}`);
    if (!res.ok || (respectCancellation && thumbnailsCancelledRef.current)) return [];
    const data = res.data as { concepts: ThumbnailConcept[]; label_style?: ThumbnailLabelStyle | null };
    setThumbnailsInline(data.concepts);
    if (data.label_style) setThumbnailLabelStyleInline(data.label_style);
    return data.concepts;
  }, [scriptId]);

  const ensureLongFormThumbnailForYolo = useCallback(async () => {
    thumbnailsCancelledRef.current = false;
    setThumbnailsInlineGenerating(true);
    try {
      const existing = await refreshLongFormThumbnailsInline();
      if (existing.some((concept) => concept.image_url)) return;
      if (state.content.format_id && state.content.format_id !== "youtube-listicle") return;

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
  }, [refreshLongFormThumbnailsInline, scriptId, state.content.format_id]);

  const runYoloCreationPipeline = useCallback(async (voiceId: string) => {
    let latest = await refreshScriptContent();
    let status = getCreationStatus(latest, projectConfig);

    if (!requireMainCharacterReference()) return false;

    if (!status.titleCardsDone && status.hasTitleCards) {
      setYoloStep("Title Cards");
      titleCardCancelledRef.current = false;
      setTitleCardGenerating(true);
      setTitleCardProgressPct(0);
      titleCardProgress.start(latest.segments.length);
      try {
        await state.generateTitleCardsStandalone(false, (status) => {
          if (typeof status.progress === "number") setTitleCardProgressPct(status.progress);
        });
        if (yoloCancelledRef.current) return false;
        setTitleCardProgressPct(1);
        thumbnailsCancelledRef.current = false;
        setThumbnailsInlineGenerating(true);
        try {
          const existing = await refreshLongFormThumbnailsInline();
          if (!existing.some((concept) => concept.image_url) && !(latest.format_id && latest.format_id !== "youtube-listicle")) {
            const res = await api.post("/api/thumbnail/recomposite", {
              script_id: scriptId,
            });
            if (res.ok && !thumbnailsCancelledRef.current) {
              const data = res.data as { concepts: ThumbnailConcept[] };
              setThumbnailsInline(data.concepts);
            }
          }
        } finally {
          setThumbnailsInlineGenerating(false);
        }
      } finally {
        setTitleCardGenerating(false);
        setTitleCardProgressPct(null);
        titleCardProgress.end(latest.segments.length);
      }
      latest = await refreshScriptContent();
      status = getCreationStatus(latest, projectConfig);
      if (yoloCancelledRef.current) return false;
    }

    if (!status.audioDone) {
      setYoloStep("Generate Audio");
      await state.generateAllAudio(voiceId, true);
      latest = await refreshScriptContent();
      status = getCreationStatus(latest, projectConfig);
      if (!status.audioDone) {
        throw new Error("Audio generation did not complete for every narrated scene");
      }
      if (yoloCancelledRef.current) return false;
    }

    if (!status.imagesDone) {
      setYoloStep("Generate Images");
      await state.generateAllImages(true);
      latest = await refreshScriptContent();
      status = getCreationStatus(latest, projectConfig);
      if (!status.imagesDone) {
        throw new Error("Image generation did not complete for every visual scene");
      }
      if (yoloCancelledRef.current) return false;
    }

    if (!status.fxDone) {
      setYoloStep("Generate FX");
      await runMissingFXForYolo(status.missingFXCount);
      latest = await refreshScriptContent();
      status = getCreationStatus(latest, projectConfig);
      if (!status.fxDone) {
        throw new Error("FX generation did not complete for every scene");
      }
      if (yoloCancelledRef.current) return false;
    }

    if (!status.eliDone) {
      setYoloStep("Add Eli");
      await runMissingEliForYolo(status.missingEliCount || status.eliSceneCount);
      latest = await refreshScriptContent();
      status = getCreationStatus(latest, projectConfig);
      if (!status.eliDone) {
        throw new Error("Eli generation did not complete for every eligible scene");
      }
      if (yoloCancelledRef.current) return false;
    }

    await ensureLongFormThumbnailForYolo();
    if (yoloCancelledRef.current) return false;

    return true;
  }, [
    ensureLongFormThumbnailForYolo,
    refreshScriptContent,
    refreshLongFormThumbnailsInline,
    requireMainCharacterReference,
    runMissingEliForYolo,
    runMissingFXForYolo,
    scriptId,
    state,
    titleCardProgress,
    projectConfig,
  ]);

  const handleRecompositeThumbnailInline = useCallback(async () => {
    thumbnailsCancelledRef.current = false;
    setThumbnailsInlineGenerating(true);
    try {
      if (state.content.format_id === "life-as-a") {
        // life-as-a uses the split-progression Gemini call — re-roll and regenerate.
        const res = await api.post("/api/thumbnail/regenerate-split-progression", {
          script_id: scriptId,
          style: thumbnailLabelStyleInline,
        });
        if (res.ok && !thumbnailsCancelledRef.current) {
          const data = res.data as { concepts: ThumbnailConcept[]; label_style?: ThumbnailLabelStyle | null };
          setThumbnailsInline(data.concepts);
          if (data.label_style) setThumbnailLabelStyleInline(data.label_style);
        }
      } else if (state.content.format_id && state.content.format_id !== "youtube-listicle") {
        // Other non-composite-grid formats reuse the cinematic thumbnail produced at
        // title-card generation time; just refresh the existing thumbnail URL.
        const res = await api.get(`/api/thumbnail/${scriptId}`);
        if (res.ok && !thumbnailsCancelledRef.current) {
          const data = res.data as { concepts: ThumbnailConcept[] };
          setThumbnailsInline(data.concepts);
        }
      } else {
        const res = await api.post("/api/thumbnail/recomposite", {
          script_id: scriptId,
        });
        if (res.ok && !thumbnailsCancelledRef.current) {
          const data = res.data as { concepts: ThumbnailConcept[] };
          setThumbnailsInline(data.concepts);
        }
      }
    } finally {
      setThumbnailsInlineGenerating(false);
    }
  }, [scriptId, state.content.format_id, thumbnailLabelStyleInline]);

  const confirmLongFormThumbnailOverwrite = useCallback(async () => {
    const existing = await refreshLongFormThumbnailsInline(false);
    if (!existing.some((concept) => concept.image_url)) return true;
    return window.confirm(
      "Warning: a long-form thumbnail already exists. Regenerating will overwrite the current active thumbnail. Continue?",
    );
  }, [refreshLongFormThumbnailsInline]);

  const handleRecompositeThumbnailInlineWithWarning = useCallback(async () => {
    if (!(await confirmLongFormThumbnailOverwrite())) return;
    await handleRecompositeThumbnailInline();
  }, [confirmLongFormThumbnailOverwrite, handleRecompositeThumbnailInline]);

  const handleRenderLongFormThumbnailWithWarning = useCallback(async () => {
    if (!(await confirmLongFormThumbnailOverwrite())) return;
    await render.recompositeThumbnail();
    await refreshLongFormThumbnailsInline(false);
  }, [confirmLongFormThumbnailOverwrite, refreshLongFormThumbnailsInline, render]);

  const handleSetActiveLongformThumbnail = useCallback(async (idx: number) => {
    await render.setActiveLongformThumbnail(idx);
    await refreshLongFormThumbnailsInline(false);
  }, [refreshLongFormThumbnailsInline, render]);

  const refreshThumbnailCompletionStatus = useCallback(async () => {
    await Promise.allSettled([
      refreshLongFormThumbnailsInline(false),
      refreshShortFormThumbnailStatus(),
      refreshScriptContent(),
    ]);
  }, [refreshLongFormThumbnailsInline, refreshScriptContent, refreshShortFormThumbnailStatus]);

  const openThumbnailModal = () => {
    setShowThumbnailModal(true);
    void refreshThumbnailCompletionStatus();
  };

  const requestYoloStop = useCallback(async () => {
    if (yoloStoppingRef.current) return;
    yoloStoppingRef.current = true;
    setYoloStopping(true);
    yoloCancelledRef.current = true;
    titleCardCancelledRef.current = true;
    thumbnailsCancelledRef.current = true;
    fxCancelledRef.current = true;
    eliCancelledRef.current = true;
    state.cancelAudioGeneration();
    state.cancelImageGeneration();
    setTitleCardGenerating(false);
    setThumbnailsInlineGenerating(false);
    setGeneratingFX(false);
    setGeneratingEli(false);
    setProductionBusyTask(null);
    setProductionProgress(null);
    showToast("Stopping YOLO render and backend work...", "info");
    try {
      if (api.stopYoloProcesses) {
        await api.stopYoloProcesses();
        return;
      }
      const res = await api.post("/dev/api/kill-all");
      if (!res.ok) throw new Error("Could not reach backend kill switch");
      const data = res.data as { cancelled?: number };
      const cancelled = data.cancelled ?? 0;
      showToast(`Stopped YOLO task (${cancelled} backend item${cancelled === 1 ? "" : "s"} cancelled)`, "success");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Could not stop backend work");
    } finally {
      setYoloStopping(false);
      yoloStoppingRef.current = false;
    }
  }, [state]);

  const handleYoloRender = useCallback(async () => {
    if (yoloRenderRunning) {
      await requestYoloStop();
      return;
    }
    if (!voicePicker.selectedVoiceId) {
      showToast("Select a voice in settings before running YOLO render");
      return;
    }

    setYoloRenderRunning(true);
    setYoloStopping(false);
    yoloStoppingRef.current = false;
    setYoloStep(null);
    yoloCancelledRef.current = false;
    productionBusyRef.current = true;
    setProductionError(null);
    try {
      const creationComplete = await runYoloCreationPipeline(voicePicker.selectedVoiceId);
      if (!creationComplete || yoloCancelledRef.current) return;

      const latest = await refreshScriptContent();
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
        void openUploadPanel();
      });
      await refreshScriptContent();
      await refreshShortFormThumbnailStatus();
      await refreshShortFormRenderStatus();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "YOLO render failed");
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
    openUploadPanel,
    render,
    requestYoloStop,
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

  const yoloSubProgress = (() => {
    if (!yoloRenderRunning || !yoloStep) return null;
    if (yoloStep === "Title Cards") return titleCardProgressPct;
    if (yoloStep === "Generate Audio") return batchProgressValue(state.batchAudioProgress);
    if (yoloStep === "Generate Images") return batchProgressValue(state.batchImageProgress);
    if (yoloStep === "Generate FX") return fxProgressPct;
    if (yoloStep === "Add Eli") return eliProgressPct;
    if (yoloStep === "Generate SF Thumbnails" || yoloStep === "Render SF Videos") return productionProgress;
    if (yoloStep === "Export Bundle") return render.exportStatus?.progress ?? null;
    return null;
  })();

  const yoloProgressDetail = (() => {
    if (!yoloRenderRunning || !yoloStep) return null;
    if (yoloStep === "Generate Audio") return state.batchAudioProgress.currentSceneName;
    if (yoloStep === "Generate Images") return state.batchImageProgress.currentSceneName;
    if (yoloStep === "Generate FX") return fxStep || null;
    if (yoloStep === "Add Eli") return sceneProgressCounter(eliStep, eliProgressPct, eliProgressTotal) || null;
    if (yoloStep === "Export Bundle") return render.exportStatus?.label ?? null;
    return null;
  })();

  const yoloButton = (
    <button
      onClick={handleYoloRender}
      disabled={yoloStopping}
      title={yoloRenderRunning ? "Stop YOLO render and cancel backend work" : "Run the full YOLO pipeline"}
      className={`group relative flex h-9 w-full shrink-0 items-center justify-center overflow-hidden rounded-lg px-4 text-center text-xs font-bold leading-tight text-white/95 shadow-[0_10px_28px_rgba(0,0,0,0.22)] transition-all hover:scale-[1.01] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 disabled:cursor-wait disabled:opacity-60 disabled:hover:scale-100 ${
        yoloRenderRunning
          ? "bg-red-600/85 hover:bg-red-500 hover:shadow-[0_0_22px_rgba(239,68,68,0.35)]"
          : "border border-white/10 bg-gradient-to-r from-sky-500/70 via-emerald-400/60 to-amber-400/60 hover:shadow-[0_16px_34px_rgba(14,165,233,0.16)]"
      }`}
    >
      {!yoloRenderRunning && (
        <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent opacity-50" />
      )}
      <span className="relative flex min-w-0 items-center justify-center gap-1.5 text-center">
        {yoloRenderRunning || yoloStopping ? (
          <span className="w-3 h-3 border-2 border-white/70 border-t-transparent rounded-full animate-spin" />
        ) : (
          <Zap size={14} />
        )}
        {yoloStopping ? "STOPPING" : yoloRenderRunning ? "STOP YOLO" : "YOLO MODE"}
      </span>
    </button>
  );

  return (
    <div className="flex flex-col h-[calc(100vh-105px)]">
      {/* Header — Title + Pipeline + Thumbnail */}
      <div className="flex shrink-0 border-b border-neutral-900 bg-neutral-950/45">
        {/* Left — Title, Pipeline, Export */}
        <div className="flex flex-col flex-1 min-w-0">
          {/* Row 1 — Navigation + Title */}
          <div className="flex items-center gap-4 px-5 py-2.5 border-b border-neutral-900/80">
            <button
              onClick={onBack}
              className="text-sm px-3 py-1.5 text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 rounded-lg transition-colors"
            >
              &larr; Back
            </button>
            <div className="flex min-w-0 flex-1 items-center gap-2">
              {editingTitle ? (
                <>
                  <input
                    value={titleDraft}
                    onChange={(event) => setTitleDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") void saveTitleEdit();
                      if (event.key === "Escape") cancelTitleEdit();
                    }}
                    autoFocus
                    disabled={titleSaving}
                    className="h-8 min-w-0 flex-1 rounded-md border border-violet-500/40 bg-neutral-900 px-2.5 text-sm font-semibold text-neutral-100 outline-none transition-colors placeholder:text-neutral-500 focus:border-violet-400"
                  />
                  <button
                    type="button"
                    onClick={() => void saveTitleEdit()}
                    disabled={titleSaving}
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-emerald-500/15 text-emerald-300 transition-colors hover:bg-emerald-500/25 disabled:opacity-50"
                    title="Save title"
                  >
                    <Check size={15} />
                  </button>
                  <button
                    type="button"
                    onClick={cancelTitleEdit}
                    disabled={titleSaving}
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-neutral-800 text-neutral-400 transition-colors hover:bg-neutral-700 hover:text-neutral-200 disabled:opacity-50"
                    title="Cancel title edit"
                  >
                    <X size={15} />
                  </button>
                </>
              ) : (
                <>
                  <h2 className="min-w-0 truncate text-base font-semibold" title={editableTitle}>{editableTitle}</h2>
                  <button
                    type="button"
                    onClick={startTitleEdit}
                    className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-neutral-500 transition-colors hover:bg-neutral-800 hover:text-neutral-200"
                    title="Edit video title"
                  >
                    <Pencil size={14} />
                  </button>
                </>
              )}
            </div>
            <UploadButton
              checking={uploadSuiteChecking}
              onOpenUpload={() => void openUploadPanel()}
            />
          </div>

          <ViewerSwitchRow
            format={viewerFormat}
            asset={viewerAsset}
            activeTab={activeTab}
            exportsFolderOpening={exportsFolderOpening}
            canvasColor={state.content.visual_canvas?.background_color ?? "#F6C54A"}
            canvasColorUpdating={canvasColorUpdating}
            onFormatChange={setViewerFormat}
            onAssetChange={setViewerAsset}
            onTabChange={setActiveTab}
            onOpenProjectDetails={() => setShowProjectDetails(true)}
            onOpenExportsFolder={() => void handleOpenExportsFolder()}
            onSelectCanvasColor={handleSelectCanvasColor}
          />
          <ProjectDetailsModal
            open={showProjectDetails}
            onClose={() => setShowProjectDetails(false)}
            sceneCount={sceneCount}
            segmentCount={segmentCount}
            durationStr={durationStr}
            totalWords={totalWords}
            projectConfig={projectConfig}
            activePresetName={activePreset?.name || null}
            totalCost={totalCost}
            costBreakdown={costBreakdown}
            mediaCounts={mediaCounts}
            mediaSceneTotal={mediaSceneTotal}
            aiScenePercent={aiScenePercent}
            exportStatus={exportFileStatus}
            uploadTracking={uploadTracking}
            trackingUpdating={trackingUpdating}
            onToggleUploadTracking={handleToggleUploadTracking}
            onOpenUploadSuite={handleOpenDistributionUpload}
          />

          <PipelineSteps
            yoloButton={yoloButton}
            thumbnailsBusy={thumbnailsBusy}
            allThumbnailsDone={allThumbnailsDone}
            hasExistingThumbnails={hasExistingThumbnails}
            missingThumbnailCount={missingThumbnailCount}
            allImagesGenerated={allImagesGenerated}
            allAudioGenerated={allAudioGenerated}
            batchGenerating={state.batchGenerating}
            batchGeneratingAudio={state.batchGeneratingAudio}
            confirmAndGenerateThumbnails={confirmAndGenerateThumbnails}
            generateMissingThumbnails={generateMissingThumbnails}
            cancelThumbnails={cancelThumbnailsCombined}
            confirmAndGenerateImages={confirmAndGenerateImages}
            confirmAndGenerateAudio={confirmAndGenerateAudio}
            generateMissingImages={generateMissingImages}
            generateMissingAudio={generateMissingAudio}
            hasExistingImages={hasExistingImages}
            hasExistingAudio={hasExistingAudio}
            missingImageCount={missingImageCount}
            missingAudioCount={missingAudioCount}
            cancelImageGeneration={state.cancelImageGeneration}
            cancelAudioGeneration={state.cancelAudioGeneration}
            showVoicePicker={voicePicker.showVoicePicker}
            setShowVoicePicker={voicePicker.setShowVoicePicker}
            voices={voicePicker.voices}
            selectedVoiceId={voicePicker.selectedVoiceId}
            setSelectedVoiceId={voicePicker.setSelectedVoiceId}
            voicePickerRef={voicePicker.voicePickerRef}
            onRecordVoiceover={onRecordVoiceover}
            thumbnailsEstimatedSeconds={titleCardProgress.estimatedSeconds}
            thumbnailsProgressActive={titleCardProgress.active}
            yoloModeActive={yoloRenderRunning}
            thumbnailsProgress={titleCardProgressPct}
            thumbnailPhases={thumbnailPhases}
            audioProgress={batchProgressValue(state.batchAudioProgress)}
            imageProgress={batchProgressValue(state.batchImageProgress)}
          />

          <FinalizationRow
            allFXGenerated={allFXGenerated}
            hasExistingFX={hasExistingFX}
            missingFXCount={missingFXCount}
            generatingFX={generatingFX}
            setGeneratingFX={setGeneratingFX}
            confirmAndGenerateFX={confirmAndGenerateFX}
            generateMissingFX={generateMissingFX}
            fxCancelledRef={fxCancelledRef}
            fxPotentiallyStale={lastAudioGenTimestamp > 0 && lastAudioGenTimestamp > lastFXGenTimestamp}
            fxEstimatedSeconds={fxProgress.estimatedSeconds}
            fxProgressActive={fxProgress.active}
            fxProgress={fxProgressPct}
            allEliGenerated={allEliGenerated}
            hasExistingEli={hasExistingEli}
            missingEliCount={missingEliCount}
            generatingEli={generatingEli}
            setGeneratingEli={setGeneratingEli}
            confirmAndGenerateEli={confirmAndGenerateEli}
            generateMissingEli={generateMissingEli}
            eliCancelledRef={eliCancelledRef}
            eliEstimatedSeconds={eliProgress.estimatedSeconds}
            eliProgressActive={eliProgress.active}
            eliProgress={eliProgressPct}
            eliDisabledForProject={projectConfig != null && !projectConfig.eli_enabled}
            projectConfig={projectConfig}
            onOpenMainCharacterDrawer={() => setShowMainCharacterDrawer(true)}
            allAudioGenerated={allAudioGenerated}
            allSeoDone={allSeoDone}
            missingSeoCount={missingSeoCount}
            seoBusy={seoBusy}
            confirmAndGenerateSeo={confirmAndGenerateSeo}
            generateMissingSeo={generateMissingSeo}
            allExportsDone={allExportsDone}
            missingExportCount={missingExportCount}
            exportBusy={exportBusy}
            confirmAndExport={confirmAndExport}
            exportMissing={exportMissing}
            yoloModeActive={yoloRenderRunning}
            productionProgress={productionProgress}
            productionBusyTask={productionBusyTask}
            anyProductionBusy={anyProductionBusy}
          />
          {yoloRenderRunning && (
            <YoloProgressStrip
              step={yoloStep}
              subProgress={yoloSubProgress}
              detail={yoloProgressDetail}
            />
          )}
          {productionError && (
            <div className="px-5 pb-2 text-[11px] text-red-400">{productionError}</div>
          )}
        </div>

        {/* Right — Thumbnail Preview */}
        <div className="flex shrink-0 items-center justify-center border-l border-neutral-900 bg-neutral-950/35 px-5 py-3">
          <button
            onClick={openThumbnailModal}
            className="group relative rounded-xl p-1.5 transition-all hover:bg-neutral-900/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950"
            title="Click to manage thumbnails"
          >
            {thumbnailsInline.length > 0 && thumbnailsInline[0].image_url ? (
              <div className="relative overflow-hidden rounded-xl border border-neutral-800 bg-neutral-900 shadow-[0_18px_42px_rgba(0,0,0,0.34)] transition-colors group-hover:border-neutral-700">
                <img
                  src={assetUrl(thumbnailsInline[0].image_url)}
                  alt="Thumbnail preview"
                  className="h-36 aspect-video object-cover xl:h-40 2xl:h-44"
                />
                <div className="pointer-events-none absolute inset-0 rounded-xl ring-1 ring-inset ring-white/5" />
                {thumbnailsInlineGenerating && (
                  <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-black/50">
                    <span className="w-5 h-5 border-2 border-violet-400 border-t-transparent rounded-full animate-spin" />
                  </div>
                )}
              </div>
            ) : (
              <div className={`flex h-36 aspect-video items-center justify-center rounded-xl border border-dashed shadow-[0_18px_42px_rgba(0,0,0,0.24)] transition-colors xl:h-40 2xl:h-44 ${
                thumbnailsInlineGenerating
                  ? "border-violet-500/50 bg-violet-500/5"
                  : "border-neutral-800 bg-neutral-900/35 group-hover:border-neutral-700"
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
      {viewerFormat === "long-form" && viewerAsset === "thumbnails" ? (
        <LongFormThumbnailsPanel
          thumbnails={render.thumbnails}
          generating={render.thumbnailsGenerating}
          onGenerate={() => void handleRenderLongFormThumbnailWithWarning()}
          onExport={() => void handleExportLongFormThumbnail()}
          exporting={longFormThumbnailExporting}
          progress={render.thumbnailProgress}
          formatId={state.content.format_id}
          thumbnailLabelStyle={render.thumbnailLabelStyle}
          onThumbnailLabelStyleChange={render.setThumbnailLabelStyle}
          onSetActiveThumbnail={handleSetActiveLongformThumbnail}
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
      ) : viewerFormat === "short-form" && viewerAsset === "thumbnails" ? (
        <div className="flex-1 overflow-y-auto p-5">
          <ShortFormThumbnailsCard
            scriptId={scriptId}
            segments={state.content.segments.map((s) => ({ name: s.name }))}
            onStatusChange={handleShortFormThumbnailStatusChange}
            canGenerateImages={mainCharacterReferenceReady}
            onBlockedGeneration={requireMainCharacterReference}
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
          visualTreatmentAssignments={visualTreatmentAssignments}
          visualTreatmentAnalyzing={visualTreatmentAnalyzing}
          onAnalyzeVisualTreatments={handleAnalyzeVisualTreatments}
          onApplyVisualTreatments={handleApplyVisualTreatments}
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
            generateAllImagesWithCharacterGate();
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
          onGenerateImage={generateImageWithCharacterGate}
          onGenerateAudio={(id) => tryGenerateAudio(id)}
          generatingSceneIds={state.generatingSceneIds}
          generatingAudioSceneIds={state.generatingAudioSceneIds}
        />
      ) : viewerFormat === "short-form" && viewerAsset === "render" ? (
        <div className="flex-1 overflow-y-auto p-5">
          <ShortFormTab
            scriptId={scriptId}
            segments={state.content.segments.map((s) => ({ name: s.name }))}
            shortFormSeoMetadata={render.shortFormSeoMetadata}
            onUploadComplete={refreshUploadTracking}
            onRenderedStatusChange={() => void refreshShortFormRenderStatus()}
          />
        </div>
      ) : (
      /* Vertical layout: Timeline on top (full width), Properties below */
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Main timeline area — full width */}
        <div className="overflow-auto p-4 shrink-0 space-y-4">
          <ScriptRatingCard rating={state.content.script_rating} />
          <TimelineLanes
            content={state.content}
            selectedSceneId={state.selectedSceneId}
            onSelectScene={handleSelectScene}
            pixelsPerSecond={pixelsPerSecond}
            projectConfig={projectConfig}
          />
        </div>

        {/* Bottom panel: Properties */}
        {selectedScene ? (
          <div className="flex-1 min-h-0 border-t border-neutral-900/80">
            <PropertiesPanel
              scene={selectedScene.scene}
              segmentIdx={selectedScene.segIdx}
              segmentName={selectedScene.segName}
              scriptId={scriptId}
              onUpdate={(updates) =>
                state.updateScene(selectedScene.scene.id, updates)
              }
              onGenerateImage={() =>
                generateImageWithCharacterGate(selectedScene.scene.id)
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
          onGenerate={handleRecompositeThumbnailInlineWithWarning}
          onClose={() => setShowThumbnailModal(false)}
          onShortFormStatusChange={handleShortFormThumbnailStatusChange}
          scriptId={scriptId}
          segments={state.content.segments.map((s) => ({ name: s.name }))}
          formatId={state.content.format_id}
          thumbnailLabelStyle={thumbnailLabelStyleInline}
          onThumbnailLabelStyleChange={setThumbnailLabelStyleInline}
          onSetActiveThumbnail={handleSetActiveLongformThumbnail}
        />
      )}

      {showMainCharacterDrawer && projectConfig && (
        <MainCharacterDrawer
          scriptId={scriptId}
          config={projectConfig}
          onClose={() => setShowMainCharacterDrawer(false)}
          onUpdated={(next) => setProjectConfig(next)}
        />
      )}

      {showUpload && uploadSuite && (
        <UploadPanel
          suite={uploadSuite}
          onClose={() => setShowUpload(false)}
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
              {confirmOverwrite === "thumbnails" && (() => {
                const info = thumbnailsOverwriteInfo;
                if (!info) return null;
                const overwriteParts: string[] = [];
                if (info.titleCards) overwriteParts.push("title cards");
                if (info.shortForm) overwriteParts.push("short-form thumbnails");
                const overwriteSentence = overwriteParts.length > 0
                  ? `Existing ${overwriteParts.join(" and ")} will be overwritten.`
                  : "";
                const longFormSentence = info.longForm
                  ? "The current long-form thumbnail will be archived (not deleted) — a new one is saved alongside it."
                  : "";
                return [overwriteSentence, longFormSentence].filter(Boolean).join(" ");
              })()}
              {confirmOverwrite === "seo" && "SEO has already been generated. Continuing will regenerate and re-export the markdown files. Use the dropdown's \"Generate Missing\" option to only fill in what's missing."}
              {confirmOverwrite === "export" && "Some videos have already been rendered. Continuing will re-render them. Use the dropdown's \"Render Missing\" option to only render what's missing."}
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
                  if (action === "images") generateAllImagesWithCharacterGate();
                  else if (action === "audio") tryGenerateAudio("all");
                  else if (action === "fx") handleGenerateFX();
                  else if (action === "eli") handleGenerateEli();
                  else if (action === "thumbnails") runThumbnailsCombined(false);
                  else if (action === "seo") runSeoCombined(false);
                  else if (action === "export") runExportCombined(false);
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
