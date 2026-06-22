import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import BlinkReviewTab from "./BlinkReviewTab";

describe("BlinkReviewTab", () => {
  it("shows eligible scenes with manual enable and disable controls", async () => {
    const onDecision = vi.fn();
    render(
      <BlinkReviewTab
        summary={{
          script_id: "script-1",
          eligible_count: 1,
          unreviewed_count: 1,
          enabled_count: 0,
          disabled_count: 0,
          complete: false,
          review_enabled: true,
          candidates: [
            {
              scene_id: "scene_001",
              scene_label: "A worker waits.",
              image_url: "/static/projects/script-1/images/scene_001.png",
              eligible: true,
              reason: "",
              anchor: {
                detected: true,
                skin_fill: "#F0D2B4",
                eye_left: { x: 0.4, y: 0.3, width: 0.01, height: 0.01 },
                eye_right: { x: 0.46, y: 0.3, width: 0.01, height: 0.01 },
              },
              fingerprint: "abc",
              review_status: "unreviewed",
              enabled: false,
            },
          ],
        }}
        loading={false}
        updatingSceneId={null}
        onRefresh={vi.fn()}
        onDecision={onDecision}
      />,
    );

    expect(screen.getByText("scene_001")).toBeInTheDocument();
    expect(screen.getByTestId("full-frame-blink-preview-overlay")).toBeInTheDocument();
    expect(screen.getAllByText(/needs review/i).length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole("button", { name: /enable blink/i }));
    expect(onDecision).toHaveBeenCalledWith("scene_001", "enabled");
  });

  it("shows a complete empty state when no candidates are eligible", () => {
    render(
      <BlinkReviewTab
        summary={{
          script_id: "script-1",
          eligible_count: 0,
          unreviewed_count: 0,
          enabled_count: 0,
          disabled_count: 0,
          complete: true,
          review_enabled: true,
          candidates: [],
        }}
        loading={false}
        updatingSceneId={null}
        onRefresh={vi.fn()}
        onDecision={vi.fn()}
      />,
    );

    expect(screen.getByText(/no safe blink candidates/i)).toBeInTheDocument();
  });

  it("gives enabled scenes a glowing border", () => {
    render(
      <BlinkReviewTab
        summary={{
          script_id: "script-1",
          eligible_count: 1,
          unreviewed_count: 0,
          enabled_count: 1,
          disabled_count: 0,
          complete: true,
          review_enabled: true,
          candidates: [
            {
              scene_id: "scene_001",
              scene_label: "A worker waits.",
              image_url: "/static/projects/script-1/images/scene_001.png",
              eligible: true,
              reason: "",
              anchor: {
                detected: true,
                skin_fill: "#F0D2B4",
                eye_left: { x: 0.4, y: 0.3, width: 0.01, height: 0.01 },
                eye_right: { x: 0.46, y: 0.3, width: 0.01, height: 0.01 },
              },
              fingerprint: "abc",
              review_status: "enabled",
              enabled: true,
            },
          ],
        }}
        loading={false}
        updatingSceneId={null}
        onRefresh={vi.fn()}
        onDecision={vi.fn()}
      />,
    );

    expect(screen.getByTestId("blink-review-card-scene_001")).toHaveClass("border-emerald-400/80");
    expect(screen.getByTestId("blink-review-card-scene_001")).toHaveClass("shadow-emerald-500/35");
    const card = screen.getByTestId("blink-review-card-scene_001");
    expect(within(card).getByText("Enabled")).toHaveClass("text-base");
    expect(within(card).getByText("Enabled")).toHaveClass("px-4");
  });

  it("makes disabled scene tags larger", () => {
    render(
      <BlinkReviewTab
        summary={{
          script_id: "script-1",
          eligible_count: 1,
          unreviewed_count: 0,
          enabled_count: 0,
          disabled_count: 1,
          complete: true,
          review_enabled: true,
          candidates: [
            {
              scene_id: "scene_001",
              scene_label: "A worker waits.",
              image_url: "/static/projects/script-1/images/scene_001.png",
              eligible: true,
              reason: "",
              anchor: {
                detected: true,
                skin_fill: "#F0D2B4",
                eye_left: { x: 0.4, y: 0.3, width: 0.01, height: 0.01 },
                eye_right: { x: 0.46, y: 0.3, width: 0.01, height: 0.01 },
              },
              fingerprint: "abc",
              review_status: "disabled",
              enabled: false,
            },
          ],
        }}
        loading={false}
        updatingSceneId={null}
        onRefresh={vi.fn()}
        onDecision={vi.fn()}
      />,
    );

    const card = screen.getByTestId("blink-review-card-scene_001");
    expect(card).toHaveClass("border-red-400/80");
    expect(card).toHaveClass("shadow-red-500/35");
    expect(within(card).getByText("Disabled")).toHaveClass("text-base");
    expect(within(card).getByText("Disabled")).toHaveClass("px-4");
  });
});
