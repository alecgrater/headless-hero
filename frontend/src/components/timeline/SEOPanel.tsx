import { useState } from "react";
import type { SEOMetadata, ShortFormSEO, ShortFormSEOMetadata } from "../../types/render";
import MiniProgressBar from "../MiniProgressBar";

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

export function LongFormSeoPanel({
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

export function ShortFormSeoPanel({
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
