import { useMemo, useState, type ReactNode } from "react";
import { ChevronLeft, ChevronRight, Copy, ExternalLink, Film, Smartphone, X } from "lucide-react";
import { assetUrl, openUploadShortsWindows, openYouTubeUploadWindow, type UploadSuiteStatus } from "../../api";
import { showToast } from "../ToastContainer";

type UploadTab = "long-form" | "short-form";

interface Props {
  suite: UploadSuiteStatus;
  onClose: () => void;
}

function sectionBody(markdown: string, heading: string, includeRest = false): string {
  const lines = markdown.split(/\r?\n/);
  const normalizedHeading = heading.toLowerCase();
  const headingLevel = heading.match(/^#+/)?.[0].length ?? 1;
  const start = lines.findIndex((line) => line.trim().toLowerCase() === normalizedHeading);
  if (start === -1) return "";
  const bodyStart = start + 1;
  if (includeRest) return lines.slice(bodyStart).join("\n").trim();
  const end = lines.findIndex((line, idx) => {
    if (idx <= start) return false;
    const match = line.trim().match(/^(#+)\s/);
    return Boolean(match && match[1].length <= headingLevel);
  });
  return lines.slice(bodyStart, end === -1 ? undefined : end).join("\n").trim();
}

function firstMeaningfulLine(text: string): string {
  return text.split(/\r?\n/).map((line) => line.trim()).find(Boolean) ?? "";
}

function seoTitle(markdown: string): string {
  return firstMeaningfulLine(sectionBody(markdown, "# Title") || sectionBody(markdown, "## Title"));
}

function seoDescriptionAndRest(markdown: string): string {
  return sectionBody(markdown, "# Description", true) || sectionBody(markdown, "## Description", true) || markdown.trim();
}

function shortSeoDescription(markdown: string): string {
  const youtube = sectionBody(markdown, "# Youtube");
  return sectionBody(youtube, "## Description", true) || seoDescriptionAndRest(markdown);
}

function tiktokInstaSummary(markdown: string): string {
  return sectionBody(markdown, "# Tiktok / Insta", true);
}

function YouTubeShortsIcon({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg className={`${className} text-red-400`} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M14.4 12c0 1.33-.53 2.53-1.4 3.4-.87.87-2.07 1.4-3.4 1.4a4.8 4.8 0 1 1 4.8-4.8zM10.8 7.2a7.2 7.2 0 1 0 0 14.4 7.2 7.2 0 0 0 0-14.4zM21 2l-4 4h3v7h-3l4 4V2z" />
    </svg>
  );
}

function YouTubeIcon({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg className={`${className} text-red-400`} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0C.488 3.45.029 5.804 0 12c.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0C23.512 20.55 23.971 18.196 24 12c-.029-6.185-.484-8.549-4.385-8.816zM9 16V8l8 4-8 4z" />
    </svg>
  );
}

function InstagramIcon({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg className={`${className} text-pink-400`} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" />
    </svg>
  );
}

function TikTokIcon({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg className={`${className} text-neutral-100`} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1V9.01a6.27 6.27 0 00-.79-.05 6.34 6.34 0 00-6.34 6.34 6.34 6.34 0 006.34 6.34 6.34 6.34 0 006.33-6.34V8.95a8.19 8.19 0 004.79 1.53V7.03a4.85 4.85 0 01-1.02-.34z" />
    </svg>
  );
}

function ShortSummaryIcons() {
  return (
    <span className="flex items-center gap-1" aria-hidden="true">
      <InstagramIcon />
      <TikTokIcon />
    </span>
  );
}

function CopyButton({ label, text, icon }: { label: string; text: string; icon?: ReactNode }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1400);
        } catch (err) {
          showToast(err instanceof Error ? err.message : "Could not copy to clipboard");
        }
      }}
      disabled={!text.trim()}
      className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-neutral-700/70 bg-neutral-900 px-3 text-xs font-semibold text-neutral-200 transition-colors hover:border-neutral-600 hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-40"
    >
      {icon ?? <Copy className="h-3.5 w-3.5" />}
      {copied ? "Copied" : label}
    </button>
  );
}

function MarkdownPreview({ markdown }: { markdown: string }) {
  const blocks = useMemo(() => {
    const lines = markdown.trim().split(/\r?\n/);
    const parsed: Array<{ type: "h1" | "h2" | "p"; text: string }> = [];
    let paragraph: string[] = [];

    const flush = () => {
      const text = paragraph.join("\n").trim();
      if (text) parsed.push({ type: "p", text });
      paragraph = [];
    };

    for (const line of lines) {
      if (line.startsWith("# ")) {
        flush();
        parsed.push({ type: "h1", text: line.slice(2).trim() });
      } else if (line.startsWith("## ")) {
        flush();
        parsed.push({ type: "h2", text: line.slice(3).trim() });
      } else {
        paragraph.push(line);
      }
    }
    flush();
    return parsed;
  }, [markdown]);

  if (!markdown.trim()) {
    return (
      <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">
        SEO markdown is not available yet.
      </div>
    );
  }

  return (
    <div className="space-y-4 rounded-lg border border-neutral-800 bg-neutral-950/60 p-5">
      {blocks.map((block, idx) => {
        if (block.type === "h1") {
          return <h3 key={idx} className="border-b border-neutral-800 pb-2 text-sm font-semibold uppercase text-sky-300">{block.text}</h3>;
        }
        if (block.type === "h2") {
          return <h4 key={idx} className="text-xs font-semibold uppercase text-violet-300">{block.text}</h4>;
        }
        return <p key={idx} className="whitespace-pre-wrap text-sm leading-6 text-neutral-300">{block.text}</p>;
      })}
    </div>
  );
}

export default function UploadPanel({ suite, onClose }: Props) {
  const [activeTab, setActiveTab] = useState<UploadTab>("long-form");
  const [activeShort, setActiveShort] = useState(0);
  const activeShortItem = suite.shorts[activeShort];
  const shortCount = suite.shorts.length;

  const moveShort = (delta: number) => {
    if (shortCount === 0) return;
    setActiveShort((idx) => (idx + delta + shortCount) % shortCount);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-6">
      <div className="flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-xl border border-neutral-700/80 bg-neutral-950 shadow-2xl shadow-black/70">
        <div className="shrink-0 border-b border-neutral-800 bg-neutral-950/95 px-6 py-5">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase text-neutral-500">Upload Suite</p>
              <h2 className="mt-1 truncate text-2xl font-semibold text-neutral-100" title={suite.project_title}>
                {suite.project_title}
              </h2>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-neutral-500 transition-colors hover:bg-neutral-800 hover:text-neutral-100"
              aria-label="Close upload window"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="mt-5 grid w-full max-w-md grid-cols-2 rounded-lg border border-neutral-800 bg-neutral-900 p-1">
            {([
              ["long-form", Film, "Longform"],
              ["short-form", Smartphone, "Short Form"],
            ] as const).map(([tab, Icon, label]) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                className={`flex h-10 items-center justify-center gap-2 rounded-md text-sm font-semibold transition-colors ${
                  activeTab === tab
                    ? "bg-neutral-100 text-neutral-950"
                    : "text-neutral-400 hover:bg-neutral-800 hover:text-neutral-100"
                }`}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-6">
          {activeTab === "long-form" ? (
            <div className="space-y-5">
              <button
                type="button"
                onClick={openYouTubeUploadWindow}
                className="flex min-h-20 w-full items-center justify-center gap-3 rounded-lg bg-red-600 px-5 text-lg font-semibold text-white transition-colors hover:bg-red-500"
              >
                <ExternalLink className="h-5 w-5" />
                Open Youtube
              </button>
              <div className="flex flex-wrap gap-2">
                <CopyButton label="Copy Title" text={seoTitle(suite.longform_seo_markdown)} icon={<YouTubeIcon />} />
                <CopyButton label="Copy Description" text={seoDescriptionAndRest(suite.longform_seo_markdown)} icon={<YouTubeIcon />} />
              </div>
              <MarkdownPreview markdown={suite.longform_seo_markdown} />
            </div>
          ) : (
            <div className="space-y-5">
              <button
                type="button"
                onClick={openUploadShortsWindows}
                className="flex min-h-20 w-full items-center justify-center gap-3 rounded-lg bg-violet-600 px-5 text-lg font-semibold text-white transition-colors hover:bg-violet-500"
              >
                <ExternalLink className="h-5 w-5" />
                Open Short Form Apps
              </button>

              <div className="flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={() => moveShort(-1)}
                  className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-neutral-700 bg-neutral-900 text-neutral-300 transition-colors hover:bg-neutral-800 hover:text-neutral-100"
                  aria-label="Previous short"
                >
                  <ChevronLeft className="h-5 w-5" />
                </button>
                <div className="flex flex-wrap justify-center gap-2">
                  {suite.shorts.map((item, idx) => (
                    <button
                      key={item.index}
                      type="button"
                      onClick={() => setActiveShort(idx)}
                      className={`h-2.5 rounded-full transition-all ${
                        idx === activeShort ? "w-9 bg-sky-300" : "w-2.5 bg-neutral-700 hover:bg-neutral-500"
                      }`}
                      aria-label={`Show short ${idx + 1}`}
                    />
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => moveShort(1)}
                  className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-neutral-700 bg-neutral-900 text-neutral-300 transition-colors hover:bg-neutral-800 hover:text-neutral-100"
                  aria-label="Next short"
                >
                  <ChevronRight className="h-5 w-5" />
                </button>
              </div>

              {activeShortItem && (
                <article className="overflow-hidden rounded-lg border border-neutral-800 bg-neutral-900/80">
                  <div className="grid gap-0 lg:grid-cols-[280px_1fr]">
                    <div className="border-b border-neutral-800 bg-neutral-950 p-4 lg:border-b-0 lg:border-r">
                      <div className="overflow-hidden rounded-lg border border-neutral-800 bg-neutral-900">
                        {activeShortItem.thumbnail_url ? (
                          <img
                            src={assetUrl(activeShortItem.thumbnail_url)}
                            alt={activeShortItem.segment_name}
                            className="aspect-[9/16] w-full object-cover"
                          />
                        ) : (
                          <div className="flex aspect-[9/16] items-center justify-center px-6 text-center text-sm text-neutral-500">
                            No thumbnail exported
                          </div>
                        )}
                      </div>
                      <div className="mt-4">
                        <p className="text-xs font-semibold uppercase text-neutral-500">Short {activeShort + 1} of {shortCount}</p>
                        <h3 className="mt-1 text-lg font-semibold text-neutral-100">{activeShortItem.segment_name}</h3>
                      </div>
                    </div>
                    <div className="min-w-0 space-y-4 p-5">
                      <div className="flex flex-wrap gap-2">
                        <CopyButton label="Copy Title" text={seoTitle(activeShortItem.seo_markdown)} icon={<YouTubeShortsIcon />} />
                        <CopyButton label="Copy Description" text={shortSeoDescription(activeShortItem.seo_markdown)} icon={<YouTubeShortsIcon />} />
                        <CopyButton label="Copy Summary" text={tiktokInstaSummary(activeShortItem.seo_markdown)} icon={<ShortSummaryIcons />} />
                      </div>
                      <MarkdownPreview markdown={activeShortItem.seo_markdown} />
                    </div>
                  </div>
                </article>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
