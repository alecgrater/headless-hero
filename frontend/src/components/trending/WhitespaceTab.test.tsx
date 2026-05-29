import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import WhitespaceTab from "./WhitespaceTab";

const originalFetch = globalThis.fetch;

describe("WhitespaceTab", () => {
  beforeEach(() => {
    vi.useRealTimers();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("renders whitespace results from the static feed", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        version: 1,
        generated_at: "2026-05-29T17:00:00Z",
        seed_generated_at: "2026-05-29T16:00:00Z",
        source_queries: ["science myths"],
        results: [
          {
            rank: 1,
            score: 582.1,
            query: "science myths",
            channel_id: "UC123",
            channel_name: "Breakout Science",
            channel_url: "https://www.youtube.com/channel/UC123",
            subscriber_count: 12000,
            total_videos: 4,
            channel_total_views: 850000,
            video_views_total: 830000,
            max_views: 600000,
            avg_views: 207500,
            reason: "4 videos with 850,000 total views from a profile-matched query.",
            videos: [
              {
                video_id: "v1",
                title: "The big one",
                url: "https://www.youtube.com/watch?v=v1",
                views: 600000,
                likes: 12000,
                published_at: "2026-05-01",
              },
            ],
          },
        ],
      }),
    }) as unknown as typeof fetch;

    render(<WhitespaceTab />);

    expect(await screen.findByText("Breakout Science")).toBeInTheDocument();
    expect(screen.getByText("science myths")).toBeInTheDocument();
    expect(screen.getByText("4 videos")).toBeInTheDocument();
    expect(screen.getByText("850.0K")).toBeInTheDocument();
    expect(screen.getByText("The big one")).toBeInTheDocument();
  });

  it("renders empty state when no feed exists", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 }) as unknown as typeof fetch;

    render(<WhitespaceTab />);

    await waitFor(() => {
      expect(screen.getByText("No whitespace feed has been generated yet.")).toBeInTheDocument();
    });
  });

  it("renders invalid feed state", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ version: 1, results: "bad" }),
    }) as unknown as typeof fetch;

    render(<WhitespaceTab />);

    await waitFor(() => {
      expect(screen.getByText("Whitespace feed is invalid.")).toBeInTheDocument();
    });
  });
});
