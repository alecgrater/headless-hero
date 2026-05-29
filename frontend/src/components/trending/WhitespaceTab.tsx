import { useEffect, useState } from "react";
import type { WhitespaceFeed, WhitespaceResult, WhitespaceVideo } from "../../types/trending";
import { SkeletonCard } from "../ui/Skeleton";

type FeedState =
  | { status: "loading" }
  | { status: "missing" }
  | { status: "invalid" }
  | { status: "ready"; feed: WhitespaceFeed };

const FEED_URL = "/discovery/youtube-whitespace.json";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isWhitespaceVideo(value: unknown): value is WhitespaceVideo {
  if (!isRecord(value)) return false;
  return (
    typeof value.video_id === "string" &&
    typeof value.title === "string" &&
    typeof value.url === "string" &&
    typeof value.views === "number" &&
    (typeof value.likes === "number" || value.likes === null || value.likes === undefined) &&
    (typeof value.published_at === "string" || value.published_at === null || value.published_at === undefined)
  );
}

function isWhitespaceResult(value: unknown): value is WhitespaceResult {
  if (!isRecord(value)) return false;
  return (
    typeof value.rank === "number" &&
    typeof value.score === "number" &&
    typeof value.query === "string" &&
    typeof value.channel_id === "string" &&
    typeof value.channel_name === "string" &&
    typeof value.channel_url === "string" &&
    (typeof value.subscriber_count === "number" || value.subscriber_count === null || value.subscriber_count === undefined) &&
    typeof value.total_videos === "number" &&
    (typeof value.channel_total_views === "number" || value.channel_total_views === null || value.channel_total_views === undefined) &&
    typeof value.video_views_total === "number" &&
    typeof value.max_views === "number" &&
    typeof value.avg_views === "number" &&
    typeof value.reason === "string" &&
    Array.isArray(value.videos) &&
    value.videos.every(isWhitespaceVideo)
  );
}

function isWhitespaceFeed(value: unknown): value is WhitespaceFeed {
  if (!isRecord(value)) return false;
  return (
    typeof value.version === "number" &&
    typeof value.generated_at === "string" &&
    (typeof value.seed_generated_at === "string" || value.seed_generated_at === null || value.seed_generated_at === undefined) &&
    Array.isArray(value.source_queries) &&
    value.source_queries.every((query) => typeof query === "string") &&
    Array.isArray(value.results) &&
    value.results.every(isWhitespaceResult)
  );
}

function formatCompact(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  if (Math.abs(value) >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`;
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toLocaleString();
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-neutral-700/50 bg-neutral-900/50 px-3 py-2">
      <div className="text-[11px] uppercase text-neutral-500">{label}</div>
      <div className="mt-1 text-sm font-semibold text-neutral-100 tabular-nums">{value}</div>
    </div>
  );
}

function VideoLink({ video }: { video: WhitespaceVideo }) {
  return (
    <a
      href={video.url}
      target="_blank"
      rel="noreferrer"
      className="flex items-center justify-between gap-3 rounded-lg border border-neutral-700/50 bg-neutral-900/50 px-3 py-2 text-sm text-neutral-300 hover:border-violet-500/50 hover:text-violet-300 transition-colors"
    >
      <span className="truncate">{video.title}</span>
      <span className="shrink-0 text-xs text-neutral-500 tabular-nums">{formatCompact(video.views)}</span>
    </a>
  );
}

function WhitespaceCard({ result }: { result: WhitespaceResult }) {
  return (
    <article className="rounded-xl border border-neutral-700/60 bg-neutral-800/40 p-4 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs text-neutral-500">
            <span className="rounded-md bg-violet-500/15 px-2 py-0.5 font-semibold text-violet-300">
              #{result.rank}
            </span>
            <span>Score {result.score.toFixed(1)}</span>
          </div>
          <a
            href={result.channel_url}
            target="_blank"
            rel="noreferrer"
            className="mt-2 block truncate text-lg font-semibold text-neutral-100 hover:text-violet-300 transition-colors"
          >
            {result.channel_name}
          </a>
        </div>
        <span className="shrink-0 rounded-lg border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-xs font-medium text-sky-300">
          {result.query}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <Metric label="Videos" value={`${result.total_videos.toLocaleString()} videos`} />
        <Metric label="Total views" value={formatCompact(result.channel_total_views)} />
        <Metric label="Max views" value={formatCompact(result.max_views)} />
        <Metric label="Avg views" value={formatCompact(result.avg_views)} />
        <Metric label="Analyzed views" value={formatCompact(result.video_views_total)} />
        <Metric label="Subscribers" value={formatCompact(result.subscriber_count)} />
      </div>

      <p className="text-sm leading-6 text-neutral-300">{result.reason}</p>

      {result.videos.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-medium uppercase text-neutral-500">Top videos</div>
          <div className="space-y-2">
            {result.videos.slice(0, 3).map((video) => (
              <VideoLink key={video.video_id || video.url} video={video} />
            ))}
          </div>
        </div>
      )}
    </article>
  );
}

export default function WhitespaceTab() {
  const [feedState, setFeedState] = useState<FeedState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function loadFeed() {
      try {
        const response = await fetch(FEED_URL, { cache: "no-store" });
        if (!response.ok) {
          if (!cancelled) setFeedState({ status: "missing" });
          return;
        }
        const payload: unknown = await response.json();
        if (!isWhitespaceFeed(payload)) {
          if (!cancelled) setFeedState({ status: "invalid" });
          return;
        }
        if (!cancelled) setFeedState({ status: "ready", feed: payload });
      } catch {
        if (!cancelled) setFeedState({ status: "missing" });
      }
    }

    loadFeed();

    return () => {
      cancelled = true;
    };
  }, []);

  if (feedState.status === "loading") {
    return (
      <div className="space-y-6">
        <Header />
        <div className="space-y-3">
          {[0, 1, 2].map((item) => (
            <SkeletonCard key={item} />
          ))}
        </div>
      </div>
    );
  }

  if (feedState.status === "missing") {
    return (
      <div className="space-y-6">
        <Header />
        <StateMessage
          title="No whitespace feed has been generated yet."
          description="Run the whitespace discovery workflow to populate channel opportunities."
        />
      </div>
    );
  }

  if (feedState.status === "invalid") {
    return (
      <div className="space-y-6">
        <Header />
        <StateMessage
          title="Whitespace feed is invalid."
          description="The static feed exists, but its shape does not match the expected discovery schema."
          tone="error"
        />
      </div>
    );
  }

  const { feed } = feedState;
  const results = [...feed.results].sort((a, b) => a.rank - b.rank);
  const sourceQueryLabel = feed.source_queries.length === 1 ? "source query" : "source queries";

  return (
    <div className="space-y-6">
      <Header generatedAt={feed.generated_at} resultCount={results.length} />

      {results.length === 0 ? (
        <StateMessage
          title="No whitespace opportunities found."
          description="The latest feed completed, but did not find profile-matched channels."
        />
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-neutral-500">
            {results.length} channel{results.length !== 1 ? "s" : ""} from {feed.source_queries.length} {sourceQueryLabel}
          </p>
          {results.map((result) => (
            <WhitespaceCard key={result.channel_id || `${result.rank}-${result.channel_name}`} result={result} />
          ))}
        </div>
      )}
    </div>
  );
}

function Header({ generatedAt, resultCount }: { generatedAt?: string; resultCount?: number }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <h2 className="text-2xl font-bold mb-1">Whitespace</h2>
        <p className="text-neutral-400 text-sm">
          {generatedAt
            ? `Generated ${formatTimestamp(generatedAt)}`
            : "Profile-matched YouTube channels with breakout potential"}
        </p>
      </div>
      {typeof resultCount === "number" && (
        <div className="rounded-lg border border-neutral-700/60 bg-neutral-800/50 px-3 py-2 text-right">
          <div className="text-lg font-semibold text-neutral-100 tabular-nums">{resultCount}</div>
          <div className="text-xs text-neutral-500">results</div>
        </div>
      )}
    </div>
  );
}

function StateMessage({
  title,
  description,
  tone = "neutral",
}: {
  title: string;
  description: string;
  tone?: "neutral" | "error";
}) {
  const classes =
    tone === "error"
      ? "border-red-500/30 bg-red-500/10 text-red-300"
      : "border-neutral-700/60 bg-neutral-800/40 text-neutral-300";

  return (
    <div className={`rounded-xl border px-4 py-8 text-center ${classes}`}>
      <p className="font-medium">{title}</p>
      <p className="mt-2 text-sm text-neutral-400">{description}</p>
    </div>
  );
}
