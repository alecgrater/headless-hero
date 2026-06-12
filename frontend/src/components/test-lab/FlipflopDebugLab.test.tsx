import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import FlipflopDebugLab from "./FlipflopDebugLab";

const analyzeFlipflopDebugAsset = vi.fn();
const getFlipflopDebugAssets = vi.fn();
const bumpAssetVersion = vi.fn();

vi.mock("../../api", () => ({
  analyzeFlipflopDebugAsset: (...args: unknown[]) => analyzeFlipflopDebugAsset(...args),
  assetUrl: (path: string) => path,
  bumpAssetVersion: (...args: unknown[]) => bumpAssetVersion(...args),
  getFlipflopDebugAssets: () => getFlipflopDebugAssets(),
}));

const cachedAsset = {
  asset_id: "test-lab-run/flipflop_cutouts/scene/base_scene_base.png",
  asset_url: "/static/projects/test-lab-run/flipflop_cutouts/scene/base_scene_base.png",
  script_id: "test-lab-run",
  scene_id: "scene",
  filename: "base_scene_base.png",
  created_at: "2026-06-12T00:00:00+00:00",
  source_metadata: {
    registration_algorithm_version: "alpha-mask-registration-v9",
  },
};

describe("FlipflopDebugLab", () => {
  beforeEach(() => {
    analyzeFlipflopDebugAsset.mockReset();
    getFlipflopDebugAssets.mockReset();
    bumpAssetVersion.mockReset();
    getFlipflopDebugAssets.mockResolvedValue([cachedAsset]);
    analyzeFlipflopDebugAsset.mockResolvedValue({
      asset: cachedAsset,
      action: "blink",
      used_external_api: false,
      registration_algorithm_version: "alpha-mask-registration-v10",
      anchor: { detected: true },
      debug_url: "/static/projects/test-lab-run/flipflop_cutouts/scene/debug_base_scene_base_blink.png",
      status: "passed",
      error: null,
    });
  });

  it("reruns the selected cached asset through the local analyzer", async () => {
    render(<FlipflopDebugLab />);

    expect(await screen.findByText("base_scene_base.png")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /rerun detector/i }));

    await waitFor(() => {
      expect(analyzeFlipflopDebugAsset).toHaveBeenCalledWith(
        "test-lab-run/flipflop_cutouts/scene/base_scene_base.png",
        "blink",
      );
    });
    expect(bumpAssetVersion).toHaveBeenCalledWith(
      "/static/projects/test-lab-run/flipflop_cutouts/scene/debug_base_scene_base_blink.png",
    );
    expect(await screen.findByText("alpha-mask-registration-v10")).toBeInTheDocument();
    expect(screen.getByText("None")).toBeInTheDocument();
  });
});
