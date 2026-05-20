import { useCallback, useEffect, useRef, useState } from "react";
import {
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
  Video,
  X,
  Zap,
  type LucideIcon,
} from "lucide-react";
import api, {
  assetUrl,
  ensureScriptExportsFolder,
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
  getUploadSuiteStatus,
  getUploadTracking,
  openPath,
  pollEliJob,
  pollFXJob,
  pollRenderJob,
  pollShortFormJob,
  renderShortAll,
  renderShortBatch,
  setUploadTracking as apiSetUploadTracking,
} from "../../api";
import type { ExportTestOptions } from "../../api";
import type { MediaAssignment } from "../../api";
import type { ScriptCostBreakdownItem } from "../../api";
import { showToast } from "../ToastContainer";
import type { ScriptContent, UploadTracking } from "../../types/script";
import type { ScriptRead } from "../../types/script";
import type { SEOMetadata, ShortFormSEO, ShortFormSEOMetadata, ThumbnailConcept } from "../../types/render";
import type { UploadSuiteStatus } from "../../api";
import type { SaveState } from "../../App";
import type { MicroTimelineHandle } from "./SceneMicroTimeline";
import ExportTestModal from "./ExportTestModal";
import UploadPanel from "./UploadPanel";
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

function DistributionTrackingButton({
  tracking,
  onClick,
}: {
  tracking: UploadTracking;
  onClick: () => void;
}) {
  const uploadedCount = DISTRIBUTION_TARGETS.filter(({ key }) => tracking[key]).length;

  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex h-7 shrink-0 items-center gap-1.5 whitespace-nowrap text-xs px-2.5 bg-neutral-800 hover:bg-neutral-700 rounded-md text-neutral-300 tabular-nums transition-colors"
      title="Open distribution tracking"
    >
      <span className="flex items-center gap-1.5">
        {DISTRIBUTION_TARGETS.map(({ key }) => (
          <DistributionIcon key={key} target={key} uploaded={tracking[key]} className="w-3.5 h-3.5" />
        ))}
      </span>
      <span>{uploadedCount}/4 uploaded</span>
    </button>
  );
}

function DistributionTrackingModal({
  tracking,
  updating,
  onToggle,
  onOpenUploadSuite,
  onClose,
}: {
  tracking: UploadTracking;
  updating: Partial<Record<keyof UploadTracking, boolean>>;
  onToggle: (key: keyof UploadTracking) => void;
  onOpenUploadSuite: () => void;
  onClose: () => void;
}) {
  const anyUpdating = Object.values(updating).some(Boolean);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4" onClick={onClose}>
      <div
        className="w-full max-w-sm rounded-lg border border-neutral-700 bg-neutral-900 shadow-2xl shadow-black/50"
        role="dialog"
        aria-modal="true"
        aria-labelledby="distribution-tracking-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-neutral-800 px-4 py-3">
          <h3 id="distribution-tracking-title" className="text-sm font-semibold text-neutral-100">
            Distribution Tracking
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-md text-neutral-500 hover:text-neutral-200 hover:bg-neutral-800 transition-colors"
            aria-label="Close distribution tracking"
          >
            <span aria-hidden="true">&times;</span>
          </button>
        </div>
        <div className="space-y-2 p-3">
          <div className="mb-2 flex items-center gap-3 rounded-lg border border-neutral-800 bg-neutral-950/40 p-2">
            <button
              type="button"
              onClick={onOpenUploadSuite}
              className="flex shrink-0 items-center justify-center gap-2 rounded-lg bg-violet-600 px-3 py-2.5 text-sm font-semibold text-white hover:bg-violet-500 transition-colors"
            >
              <Upload className="h-4 w-4" />
              Upload
            </button>
            <p className="text-xs leading-5 text-neutral-400">
              Opens the upload suite for exported videos and upload metadata.
            </p>
          </div>
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
                className={`w-full flex items-center justify-between gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors ${
                  isUploaded
                    ? "border-emerald-500/40 bg-emerald-500/10 hover:bg-emerald-500/20"
                    : "border-neutral-800 bg-neutral-950/50 hover:border-neutral-700 hover:bg-neutral-800/60"
                } disabled:opacity-60 disabled:cursor-wait`}
              >
                <span className="flex items-center gap-3 min-w-0">
                  {isUpdating ? (
                    <span className="w-5 h-5 rounded-full border border-neutral-400 border-t-transparent animate-spin" />
                  ) : (
                    <DistributionIcon target={key} uploaded={isUploaded} className="w-5 h-5" />
                  )}
                  <span className="text-sm font-medium text-neutral-200 truncate">{label}</span>
                </span>
                <span className={`text-xs font-medium ${isUploaded ? "text-emerald-300" : "text-neutral-500"}`}>
                  {isUploaded ? "Uploaded" : "Not uploaded"}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
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

function formatScenePercent(count: number, total: number) {
  if (total === 0) return "0%";
  return `${Math.round((count / total) * 100)}%`;
}

function MediaBreakdownPopover({
  mediaCounts,
  totalScenes,
}: {
  mediaCounts: Record<string, number>;
  totalScenes: number;
}) {
  const rows = [
    { key: "ai", label: "AI", color: "text-violet-300", count: mediaCounts.ai ?? 0 },
    { key: "gameplay_video", label: "Gameplay", color: "text-sky-300", count: mediaCounts.gameplay_video ?? 0 },
    { key: "stock_photo", label: "Stock Photo", color: "text-amber-300", count: mediaCounts.stock_photo ?? 0 },
    { key: "user_upload", label: "Upload", color: "text-emerald-300", count: mediaCounts.user_upload ?? 0 },
  ];

  return (
    <div className="absolute right-0 top-8 z-40 w-72 rounded-lg border border-neutral-700 bg-neutral-950 shadow-2xl shadow-black/50">
      <div className="flex items-center justify-between border-b border-neutral-800 px-3 py-2">
        <span className="text-xs font-semibold text-neutral-200">Media source mix</span>
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
type ProductionTask = "lf-seo" | "sf-thumbnails" | "sf-seo" | "sf-renders" | "thumbnails-combined" | "seo-combined" | "export-combined";

const YOLO_PROGRESS_STEPS = [
  "Title Cards",
  "Generate Audio",
  "Generate Images",
  "Generate FX",
  "Add Eli",
  "Generate LF SEO",
  "Generate SF Thumbnails",
  "Generate SF SEO",
  "Render SF Videos",
  "Export Bundle",
] as const;

function clampProgress(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

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
  const hashtags = item.hashtags.join(" ");
  const tags = item.tags.join(", ");
  return [
    `# Short ${item.index}`,
    "# Youtube",
    `## Title\n\n${item.title}`,
    `## Description\n\n${item.description}`,
    `## Hashtags\n\n${hashtags}`,
    `## SEO Tags\n\n${tags}`,
    "# Tiktok / Insta",
    item.title,
    item.description,
    hashtags,
    tags,
  ].join("\n\n");
}

function compactProgressText(progress: number | null) {
  if (progress == null) return "";
  return `${Math.round(progress * 100)}%`;
}

function batchProgressValue(progress: { total: number; completed: number; failed: number }) {
  if (progress.total <= 0) return null;
  return Math.min(1, (progress.completed + progress.failed) / progress.total);
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

function FinalizationRow({
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
  allSeoDone,
  missingSeoCount,
  seoBusy,
  confirmAndGenerateSeo,
  generateMissingSeo,
  allExportsDone,
  hasExistingExports,
  missingExportCount,
  exportBusy,
  confirmAndExport,
  exportMissing,
  yoloModeActive,
  productionProgress,
  productionBusyTask,
}: {
  allEliGenerated: boolean;
  hasExistingEli: boolean;
  missingEliCount: number;
  generatingEli: boolean;
  setGeneratingEli: (v: boolean) => void;
  confirmAndGenerateEli: () => void;
  generateMissingEli: () => void;
  eliCancelledRef: React.RefObject<boolean>;
  eliEstimatedSeconds: number | null;
  eliProgressActive: boolean;
  eliProgress: number | null;
  allSeoDone: boolean;
  missingSeoCount: number;
  seoBusy: boolean;
  confirmAndGenerateSeo: () => void;
  generateMissingSeo: () => void;
  allExportsDone: boolean;
  hasExistingExports: boolean;
  missingExportCount: number;
  exportBusy: boolean;
  confirmAndExport: () => void;
  exportMissing: () => void;
  yoloModeActive: boolean;
  productionProgress: number | null;
  productionBusyTask: ProductionTask | null;
}) {
  const [showEliDropdown, setShowEliDropdown] = useState(false);
  const eliDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!showEliDropdown) return;
    const handler = (e: MouseEvent) => {
      if (eliDropdownRef.current && !eliDropdownRef.current.contains(e.target as Node)) setShowEliDropdown(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showEliDropdown]);

  const seoProgress = productionBusyTask === "seo-combined" ? productionProgress : null;
  const exportProgress = productionBusyTask === "export-combined" ? productionProgress : null;

  return (
    <div className="px-5 py-2 border-t border-neutral-800/60 shrink-0">
      <div className="grid w-full items-center gap-2 min-w-0" style={{ gridTemplateColumns: "minmax(0,1fr) auto minmax(0,1fr) auto minmax(0,1fr) auto minmax(0,1fr)" }}>
        {/* Step 5 — Eli (under Thumbnails) */}
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
                onClick={generatingEli ? (yoloModeActive ? undefined : () => { eliCancelledRef.current = true; setGeneratingEli(false); }) : confirmAndGenerateEli}
                className={`text-xs pl-3 pr-1.5 py-2 border border-r-0 rounded-l-lg font-medium transition-all flex items-center justify-center gap-1.5 min-w-0 flex-1 whitespace-nowrap ${
                  generatingEli
                    ? `bg-neutral-800/80 border-violet-500/40 text-neutral-200 shadow-[0_0_8px_rgba(139,92,246,0.15)] ${yoloModeActive ? "cursor-default" : "hover:border-red-500/50 hover:text-red-400"}`
                    : allEliGenerated
                      ? "bg-emerald-500/8 border-emerald-500/25 text-emerald-400 hover:bg-emerald-500/15"
                      : "bg-neutral-800/80 border-neutral-700/60 text-neutral-300 hover:bg-neutral-700/80 hover:border-neutral-600"
                }`}
                title={generatingEli ? (yoloModeActive ? "Generating Eli" : "Cancel Eli generation") : "Add Eli character overlay to all scenes"}
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
                  className="text-xs px-1.5 bg-neutral-800/80 border border-l-0 border-neutral-700/60 text-neutral-400 hover:bg-neutral-700/80 hover:text-neutral-200 rounded-r-lg transition-all flex items-center"
                  title="Eli generation options"
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
                    disabled={allEliGenerated || !hasExistingEli}
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

        <svg className="w-3 h-3 text-neutral-600/60 shrink-0" viewBox="0 0 12 12" fill="none">
          <path d="M4 2L8 6L4 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>

        {/* Step 6 — SEO (under Audio) */}
        <ProductionTaskButton
          stepNumber={6}
          label="SEO"
          done={allSeoDone}
          busy={seoBusy}
          disabled={false}
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
          disabled={false}
          missingCount={missingExportCount}
          progress={exportProgress}
          onRunAll={confirmAndExport}
          onRunMissing={exportMissing}
          missingLabel={hasExistingExports ? "Render Missing" : "Render Missing"}
          allTitle="Render the long-form video and all short-form videos"
        />

        <svg className="w-3 h-3 invisible shrink-0" viewBox="0 0 12 12" fill="none" aria-hidden="true">
          <path d="M4 2L8 6L4 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        {/* Empty 4th column under FX */}
        <div aria-hidden="true" />
      </div>
    </div>
  );
}

function YoloProgressStrip({
  step,
  subProgress,
  detail,
}: {
  step: string | null;
  subProgress: number | null;
  detail?: string | null;
}) {
  const rawStepIndex = YOLO_PROGRESS_STEPS.findIndex((item) => item === step);
  const stepIndex = rawStepIndex >= 0 ? rawStepIndex : 0;
  const stepNumber = stepIndex + 1;
  const stepCount = YOLO_PROGRESS_STEPS.length;
  const currentStep = step ?? "Starting";
  const boundedSubProgress = clampProgress(subProgress);
  const totalProgress = rawStepIndex >= 0 ? (stepIndex + boundedSubProgress) / stepCount : 0.03;
  const percent = Math.round(clampProgress(totalProgress) * 100);
  const visibleBarPercent = Math.max(3, percent);

  return (
    <div className="px-5 py-2 border-t border-b border-sky-500/15 shrink-0 bg-sky-500/10">
      <div className="flex items-center gap-3 text-xs">
        <span className="w-3 h-3 shrink-0 rounded-full border-2 border-sky-300 border-t-transparent animate-spin" />
        <span className="shrink-0 font-semibold text-sky-200 tabular-nums">
          YOLO Step {stepNumber}/{stepCount}
        </span>
        <span className="min-w-0 truncate text-neutral-200">
          {currentStep}
          {detail && <span className="text-neutral-400"> · {detail}</span>}
        </span>
        <div className="h-1.5 min-w-[10rem] flex-1 overflow-hidden rounded-full bg-neutral-800">
          <div
            className="h-full rounded-full bg-sky-400 transition-all duration-500"
            style={{ width: `${visibleBarPercent}%` }}
          />
        </div>
        <span className="shrink-0 text-neutral-400 tabular-nums">{percent}%</span>
      </div>
    </div>
  );
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
    <div className="ml-auto inline-flex shrink-0">
      <Tooltip content="Open exports folder in Finder">
        <button
          type="button"
          onClick={onOpen}
          disabled={opening}
          className="inline-flex h-7 w-9 items-center justify-center rounded-md border border-neutral-700/60 bg-neutral-800/80 text-neutral-300 transition-colors hover:border-neutral-600 hover:bg-neutral-700/80 disabled:cursor-wait disabled:opacity-60"
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
  const [showMediaBreakdown, setShowMediaBreakdown] = useState(false);
  const [showDistributionTracking, setShowDistributionTracking] = useState(false);
  const [uploadTracking, setUploadTracking] = useState<UploadTracking>(DEFAULT_UPLOAD_TRACKING);
  const [trackingUpdating, setTrackingUpdating] = useState<Partial<Record<keyof UploadTracking, boolean>>>({});
  const [lastAudioGenTimestamp, setLastAudioGenTimestamp] = useState(0);
  const [lastFXGenTimestamp, setLastFXGenTimestamp] = useState(0);
  const [yoloStep, setYoloStep] = useState<string | null>(null);
  const [yoloRenderRunning, setYoloRenderRunning] = useState(false);
  const [yoloRenderError, setYoloRenderError] = useState<string | null>(null);
  const [titleCardProgressPct, setTitleCardProgressPct] = useState<number | null>(null);
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
  const mediaBreakdownRef = useRef<HTMLDivElement>(null);

  const media = useMediaReview({ scriptId, content: state.content });

  useEffect(() => {
    setEditableTitle(title);
    setTitleDraft(title);
    setEditingTitle(false);
  }, [scriptId, title]);

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

  const refreshUploadTracking = useCallback(async () => {
    try {
      const tracking = await getUploadTracking(scriptId);
      setUploadTracking(tracking);
    } catch {
      // Upload tracking should not block timeline editing.
    }
  }, [scriptId]);

  // Fetch cost on mount
  useEffect(() => { refreshCost(); }, [refreshCost]);

  useEffect(() => {
    if (isActive) void refreshUploadTracking();
  }, [isActive, refreshUploadTracking]);

  useEffect(() => {
    if (!showDistributionTracking) return;
    void refreshUploadTracking();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setShowDistributionTracking(false);
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [refreshUploadTracking, showDistributionTracking]);

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
    setShowDistributionTracking(false);
    void openUploadPanel();
  }, [openUploadPanel]);

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

  useEffect(() => {
    if (!showMediaBreakdown) return;

    function handlePointerDown(event: PointerEvent) {
      const target = event.target;
      if (!(target instanceof Node)) return;
      if (mediaBreakdownRef.current?.contains(target)) return;
      setShowMediaBreakdown(false);
    }

    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, [showMediaBreakdown]);

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
          if (data.concepts.length > 0) setThumbnailsInline(data.concepts);
        }
      } catch (_) { /* thumbnails are optional */ }
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
  const mediaSceneTotal = allScenes.filter((sc) => !sc.is_title_card).length;
  const aiScenePercent = formatScenePercent(mediaCounts.ai ?? 0, mediaSceneTotal);

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

  // Combined Thumbnails handler — runs title cards + SF thumbnails + LF thumbnail
  const runThumbnailsCombined = (missingOnly: boolean) => {
    void runProductionTask("thumbnails-combined", async () => {
      // 1. Title cards
      if (titleCardsApplicable && (!missingOnly || !titleCardsAllDone)) {
        const segCount = state.content.segments.length;
        titleCardCancelledRef.current = false;
        setTitleCardGenerating(true);
        setTitleCardProgressPct(0);
        titleCardProgress.start(segCount);
        try {
          await state.generateTitleCardsStandalone(!missingOnly, (status) => {
            if (typeof status.progress === "number") setTitleCardProgressPct(status.progress);
          });
          if (!titleCardCancelledRef.current) {
            setTitleCardProgressPct(1);
            setTitleCardGenerated(true);
            setTitleCardTimestamp(Date.now());
          }
        } finally {
          setTitleCardGenerating(false);
          setTitleCardProgressPct(null);
          titleCardProgress.end(segCount);
        }
        if (titleCardCancelledRef.current) return;
      }

      // 2. Short-form thumbnails
      if (sfApplicable && (!missingOnly || !sfThumbnailsAllDone)) {
        const refreshed = missingOnly ? await refreshShortFormThumbnailStatus() : null;
        if (missingOnly && refreshed) {
          const indices = state.content.segments.map((_, idx) => idx).filter((idx) => !refreshed[idx]);
          if (indices.length > 0) {
            const { job_id } = await generateShortFormThumbnailsBatch(scriptId, indices);
            await pollShortFormJob(job_id, (status) => {
              if (typeof status.progress === "number") setProductionProgress(status.progress);
            });
            await refreshShortFormThumbnailStatus();
          }
        } else {
          const { job_id } = await generateShortFormThumbnailsAll(scriptId);
          await pollShortFormJob(job_id, (status) => {
            if (typeof status.progress === "number") setProductionProgress(status.progress);
          });
          await refreshShortFormThumbnailStatus();
        }
      }

      // 3. Long-form thumbnail (recomposite). Skip if already done.
      if (!lfThumbnailDone) {
        await handleRecompositeThumbnailInline();
      }
    });
  };

  const confirmAndGenerateThumbnails = () => {
    if (hasExistingThumbnails) {
      setConfirmOverwrite("thumbnails");
    } else {
      runThumbnailsCombined(false);
    }
  };

  const generateMissingThumbnails = () => {
    runThumbnailsCombined(true);
  };

  const cancelThumbnailsCombined = () => {
    titleCardCancelledRef.current = true;
    thumbnailsCancelledRef.current = true;
    setTitleCardGenerating(false);
    setThumbnailsInlineGenerating(false);
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
      // Auto-export markdown for both
      try {
        await exportLongFormSEO(scriptId);
      } catch {
        // ignore — best-effort export
      }
      if (segmentCount > 0) {
        try {
          await exportShortFormSEO(scriptId);
        } catch {
          // ignore — best-effort export
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
          await pollRenderJob(jobId);
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

  const runYoloCreationPipeline = useCallback(async (voiceId: string) => {
    let latest = await refreshScriptContent();
    let status = getCreationStatus(latest);

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
        setTitleCardProgressPct(null);
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
        void openUploadPanel();
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

  const yoloArea = (() => {
    const creationStatus = getCreationStatus(state.content);
    const creationRemaining: string[] = [];
    if (!creationStatus.titleCardsDone && creationStatus.hasTitleCards) creationRemaining.push("Title Cards");
    if (!creationStatus.audioDone) creationRemaining.push("Audio");
    if (!creationStatus.imagesDone) creationRemaining.push("Images");
    if (!creationStatus.fxDone) creationRemaining.push("FX");
    if (!creationStatus.eliDone) creationRemaining.push("Eli");
    const renderRemaining = [...creationRemaining];
    if (!lfSeoDone) renderRemaining.push("LF SEO");
    if (!sfThumbnailsDone) renderRemaining.push("SF Thumbnails");
    if (!sfSeoDone) renderRemaining.push("SF SEO");
    if (!sfRendersDone) renderRemaining.push("SF Videos");
    const buttonDescription = `Runs the full YOLO pipeline from the next unfinished task. Missing creation assets, long-form render, short-form assets, and the final bundle are completed automatically. Currently pending: ${renderRemaining.join(", ") || "final export only"}.`;
    const yoloButtonBaseClass = "group relative flex h-7 w-[9.5rem] shrink-0 items-center justify-center overflow-hidden rounded-lg px-4 text-center text-xs font-bold leading-tight text-white/95 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 hover:scale-[1.02] disabled:opacity-50 disabled:hover:scale-100";
    const yoloButtonContentClass = "relative flex min-w-0 items-center justify-center gap-1.5 text-center";
    const yoloInfoClass = "flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-neutral-700/60 bg-neutral-900 text-neutral-500 transition-colors hover:border-neutral-500 hover:text-neutral-200";
    const yoloButtonColorClass = "bg-gradient-to-r from-sky-500/80 via-emerald-400/70 to-amber-400/70 shadow-[0_0_15px_rgba(14,165,233,0.2)] hover:shadow-[0_0_22px_rgba(14,165,233,0.35)] focus-visible:ring-sky-500";

    const yoloInfo = (content: string, label: string) => (
      <Tooltip content={content} side="bottom">
        <span className={yoloInfoClass} aria-label={label}>
          <Info size={14} />
        </span>
      </Tooltip>
    );

    const yoloButton = (
      <button
        onClick={handleYoloRender}
        disabled={yoloRenderRunning}
        className={`${yoloButtonBaseClass} ${yoloButtonColorClass}`}
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

    return (
      <div className="flex items-center gap-2 shrink-0">
        {yoloRenderError && (
          <span className="text-[11px] text-red-400 truncate max-w-[14rem]">{yoloRenderError}</span>
        )}
        {yoloRenderRunning && yoloStep && (
          <span className="text-xs text-sky-300/75 font-medium truncate max-w-[14rem]">{yoloStep}</span>
        )}
        {yoloButton}
        {yoloInfo(buttonDescription, "YOLO mode details")}
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
            {yoloArea}
            <UploadButton
              checking={uploadSuiteChecking}
              onOpenUpload={() => void openUploadPanel()}
            />
          </div>

          {/* Stats Row + Viewer Switch */}
          {(() => {
            const sep = (key: string) => (
              <span key={key} className="w-px h-4 shrink-0 bg-neutral-700/50" />
            );

            const statItems: React.ReactNode[] = [];
            statItems.push(
              <span key="scenes" className="inline-flex h-7 shrink-0 items-center whitespace-nowrap text-xs text-neutral-400 bg-neutral-800/60 px-2.5 rounded-md tabular-nums">
                {sceneCount} scene{sceneCount !== 1 ? "s" : ""}
              </span>
            );
            statItems.push(
              <span key="segs" className="inline-flex h-7 shrink-0 items-center whitespace-nowrap text-xs text-neutral-400 bg-neutral-800/60 px-2.5 rounded-md tabular-nums">
                {segmentCount} segment{segmentCount !== 1 ? "s" : ""}
              </span>
            );
            statItems.push(
              <span key="duration" className="inline-flex h-7 shrink-0 items-center whitespace-nowrap text-xs text-neutral-400 bg-neutral-800/60 px-2.5 rounded-md tabular-nums font-mono">
                {durationStr}
              </span>
            );
            if (totalWords > 0) {
              statItems.push(
                <span key="words" className="inline-flex h-7 shrink-0 items-center whitespace-nowrap text-xs text-neutral-400 bg-neutral-800/60 px-2.5 rounded-md tabular-nums">
                  {totalWords.toLocaleString()} words
                </span>
              );
            }
            statItems.push(
              <div key="cost" ref={costBreakdownRef} className="relative">
                <button
                  type="button"
                  onClick={() => setShowCostBreakdown((show) => !show)}
                  className="inline-flex h-7 shrink-0 items-center whitespace-nowrap text-xs text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 px-2.5 rounded-md tabular-nums font-medium transition-colors"
                  title="Show cost breakdown"
                >
                  {formatCost(totalCost)}
                </button>
                {showCostBreakdown && (
                  <CostBreakdownPopover totalCost={totalCost} breakdown={costBreakdown} />
                )}
              </div>
            );
            if (mediaSceneTotal > 0) {
              statItems.push(
                <div key="media" ref={mediaBreakdownRef} className="relative">
                  <button
                    type="button"
                    onClick={() => setShowMediaBreakdown((show) => !show)}
                    className="inline-flex h-7 shrink-0 items-center whitespace-nowrap text-xs text-violet-300 bg-violet-500/10 hover:bg-violet-500/20 px-2.5 rounded-md tabular-nums font-medium transition-colors"
                    title="Show media source breakdown"
                  >
                    {aiScenePercent} AI
                  </button>
                  {showMediaBreakdown && (
                    <MediaBreakdownPopover mediaCounts={mediaCounts} totalScenes={mediaSceneTotal} />
                  )}
                </div>
              );
            }
            statItems.push(
              <ShortFormStatusPill
                key="short-form"
                scriptId={scriptId}
                segmentCount={state.content.segments.length}
              />
            );
            statItems.push(
              <DistributionTrackingButton
                key="distribution"
                tracking={uploadTracking}
                onClick={() => setShowDistributionTracking(true)}
              />
            );
            statItems.push(
              <OpenExportsButton
                key="exports-folder"
                opening={exportsFolderOpening}
                onOpen={() => void handleOpenExportsFolder()}
              />
            );

            const interleavedStats: React.ReactNode[] = [];
            statItems.forEach((item, i) => {
              if (i > 0) interleavedStats.push(sep(`sep-${i}`));
              interleavedStats.push(item);
            });

            return (
              <>
                <div className={`px-4 py-2 border-t border-neutral-800/60 shrink-0 ${yoloRenderRunning ? "bg-sky-500/5" : ""}`}>
                  <div className="flex flex-nowrap items-center gap-1 min-w-0 overflow-visible">
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
                {showDistributionTracking && (
                  <DistributionTrackingModal
                    tracking={uploadTracking}
                    updating={trackingUpdating}
                    onToggle={handleToggleUploadTracking}
                    onOpenUploadSuite={handleOpenDistributionUpload}
                    onClose={() => setShowDistributionTracking(false)}
                  />
                )}
              </>
            );
          })()}

          <PipelineSteps
            thumbnailsBusy={thumbnailsBusy}
            allThumbnailsDone={allThumbnailsDone}
            hasExistingThumbnails={hasExistingThumbnails}
            missingThumbnailCount={missingThumbnailCount}
            allImagesGenerated={allImagesGenerated}
            allAudioGenerated={allAudioGenerated}
            allFXGenerated={allFXGenerated}
            batchGenerating={state.batchGenerating}
            batchGeneratingAudio={state.batchGeneratingAudio}
            generatingFX={generatingFX}
            setGeneratingFX={setGeneratingFX}
            confirmAndGenerateThumbnails={confirmAndGenerateThumbnails}
            generateMissingThumbnails={generateMissingThumbnails}
            cancelThumbnails={cancelThumbnailsCombined}
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
            fxEstimatedSeconds={fxProgress.estimatedSeconds}
            fxProgressActive={fxProgress.active}
            thumbnailsEstimatedSeconds={titleCardProgress.estimatedSeconds}
            thumbnailsProgressActive={titleCardProgress.active}
            yoloModeActive={yoloRenderRunning}
            thumbnailsProgress={titleCardProgressPct}
            audioProgress={batchProgressValue(state.batchAudioProgress)}
            imageProgress={batchProgressValue(state.batchImageProgress)}
            fxProgress={fxProgressPct}
          />

          <FinalizationRow
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
            allSeoDone={allSeoDone}
            missingSeoCount={missingSeoCount}
            seoBusy={seoBusy}
            confirmAndGenerateSeo={confirmAndGenerateSeo}
            generateMissingSeo={generateMissingSeo}
            allExportsDone={allExportsDone}
            hasExistingExports={hasExistingExports}
            missingExportCount={missingExportCount}
            exportBusy={exportBusy}
            confirmAndExport={confirmAndExport}
            exportMissing={exportMissing}
            yoloModeActive={yoloRenderRunning}
            productionProgress={productionProgress}
            productionBusyTask={productionBusyTask}
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
            onUploadComplete={refreshUploadTracking}
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
              {confirmOverwrite === "thumbnails" && "Some thumbnails (title cards, short-form, or long-form) are already generated. Continuing will overwrite them. Use the dropdown's \"Generate Missing\" option to only fill in what's missing."}
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
                  if (action === "images") state.generateAllImages();
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
