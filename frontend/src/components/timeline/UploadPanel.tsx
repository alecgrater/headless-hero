import { useMemo, useState } from "react";
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

function CopyButton({ label, text }: { label: string; text: string }) {
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
      <Copy className="h-3.5 w-3.5" />
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
                <CopyButton label="Copy Title" text={seoTitle(suite.longform_seo_markdown)} />
                <CopyButton label="Copy Description" text={seoDescriptionAndRest(suite.longform_seo_markdown)} />
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
                        <CopyButton label="Copy Title" text={seoTitle(activeShortItem.seo_markdown)} />
                        <CopyButton label="Copy Description" text={shortSeoDescription(activeShortItem.seo_markdown)} />
                        <CopyButton label="Copy Summary" text={tiktokInstaSummary(activeShortItem.seo_markdown)} />
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
