import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import * as api from "../../api";
import BlinkAuditLab, { blinkAuditEyeOverlayGeometry } from "./BlinkAuditLab";

vi.mock("../../api", async () => {
  const actual = await vi.importActual<typeof import("../../api")>("../../api");
  return {
    ...actual,
    getBlinkAuditReports: vi.fn(),
    runBlinkAudit: vi.fn(),
    assetUrl: (url: string) => url,
  };
});

describe("BlinkAuditLab", () => {
  it("keeps minimalist dot-eye blink previews close to the detected eye size", () => {
    const geometry = blinkAuditEyeOverlayGeometry({
      x: 0.5129,
      y: 0.2435,
      width: 0.0083,
      height: 0.0146,
    });

    expect(geometry.mask.width).toBeLessThanOrEqual(2.6);
    expect(geometry.mask.height).toBeLessThanOrEqual(2.4);
    expect(geometry.lid.right - geometry.lid.left).toBeLessThanOrEqual(2.9);
    expect(geometry.lid.strokeWidth).toBeLessThanOrEqual(0.5);
  });

  it("keeps larger open-eye blink previews wide enough to cover the original eyes", () => {
    const geometry = blinkAuditEyeOverlayGeometry({
      x: 0.4802,
      y: 0.5026,
      width: 0.0323,
      height: 0.0601,
    });

    expect(geometry.mask.width).toBeGreaterThan(5);
    expect(geometry.mask.height).toBeGreaterThan(6);
    expect(geometry.lid.right - geometry.lid.left).toBeLessThan(5);
  });

  it("runs and displays a blink audit report", async () => {
    vi.mocked(api.getBlinkAuditReports).mockResolvedValue([]);
    vi.mocked(api.runBlinkAudit).mockResolvedValue({
      id: "audit-1",
      script_id: "burger-script",
      title: "Your Life At Every Level Of Working At Burger King",
      created_at: "2026-06-21T00:00:00+00:00",
      candidates: [
        {
          script_id: "burger-script",
          scene_id: "scene-1",
          segment_name: "Level 1",
          scene_label: "He waits.",
          visual_mode: "full_frame",
          image_url: "/static/projects/burger-script/images/scene-1.png",
          image_path: "/tmp/scene-1.png",
          start_seconds: 0,
          detection: { status: "passed", eligible: true, reason: "", anchor: { detected: true } },
        },
        {
          script_id: "burger-script",
          scene_id: "scene-2",
          segment_name: "Level 2",
          scene_label: "The room is empty.",
          visual_mode: "full_frame",
          image_url: "/static/projects/burger-script/images/scene-2.png",
          image_path: "/tmp/scene-2.png",
          start_seconds: 8.5,
          detection: { status: "failed", eligible: false, reason: "face_landmarks_missing", anchor: null },
        },
      ],
    });

    render(<BlinkAuditLab />);
    await userEvent.click(screen.getByRole("button", { name: /run blink audit/i }));

    expect(await screen.findByText("scene-1")).toBeInTheDocument();
    expect(screen.getByText("Eligible")).toBeInTheDocument();
    expect(screen.getByText(/rejected because no safe main-character eye pair was found/i)).toBeInTheDocument();
    expect(screen.getByText(/blink auto-enabled/i)).toBeInTheDocument();
    expect(screen.getByText("0:00")).toBeInTheDocument();
  });

  it("filters the active report to eligible scenes", async () => {
    vi.mocked(api.getBlinkAuditReports).mockResolvedValue([
      {
        id: "audit-1",
        script_id: "burger-script",
        title: "Burger King",
        created_at: "2026-06-21T00:00:00+00:00",
        candidates: [
          {
            script_id: "burger-script",
            scene_id: "scene-eligible",
            segment_name: "Level 1",
            scene_label: "He waits.",
            visual_mode: "full_frame",
            image_url: "/static/projects/burger-script/images/scene-eligible.png",
            image_path: "/tmp/scene-eligible.png",
            start_seconds: 0,
            detection: { status: "passed", eligible: true, reason: "", anchor: { detected: true } },
          },
          {
            script_id: "burger-script",
            scene_id: "scene-rejected",
            segment_name: "Level 2",
            scene_label: "The room is empty.",
            visual_mode: "full_frame",
            image_url: "/static/projects/burger-script/images/scene-rejected.png",
            image_path: "/tmp/scene-rejected.png",
            start_seconds: 12,
            detection: { status: "failed", eligible: false, reason: "face_landmarks_missing", anchor: null },
          },
        ],
      },
    ]);
    vi.mocked(api.runBlinkAudit).mockResolvedValue(null);

    render(<BlinkAuditLab />);

    expect(await screen.findByText("scene-eligible")).toBeInTheDocument();
    expect(screen.getByText("scene-rejected")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("checkbox", { name: /eligible only/i }));

    expect(screen.getByText("scene-eligible")).toBeInTheDocument();
    expect(screen.queryByText("scene-rejected")).not.toBeInTheDocument();
  });
});
