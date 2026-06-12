import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import FlipflopDebugLab from "./FlipflopDebugLab";

const analyzeFlipflopDebugAsset = vi.fn();
const createFlipflopFixtureAsset = vi.fn();
const getFlipflopDebugAssets = vi.fn();
const renderFlipflopFixturePreview = vi.fn();
const bumpAssetVersion = vi.fn();

vi.mock("../../api", () => ({
  analyzeFlipflopDebugAsset: (...args: unknown[]) => analyzeFlipflopDebugAsset(...args),
  assetUrl: (path: string) => path,
  bumpAssetVersion: (...args: unknown[]) => bumpAssetVersion(...args),
  createFlipflopFixtureAsset: (...args: unknown[]) => createFlipflopFixtureAsset(...args),
  getFlipflopDebugAssets: () => getFlipflopDebugAssets(),
  renderFlipflopFixturePreview: (...args: unknown[]) => renderFlipflopFixturePreview(...args),
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
    createFlipflopFixtureAsset.mockReset();
    getFlipflopDebugAssets.mockReset();
    renderFlipflopFixturePreview.mockReset();
    bumpAssetVersion.mockReset();
    getFlipflopDebugAssets.mockResolvedValue([cachedAsset]);
    createFlipflopFixtureAsset.mockResolvedValue({
      asset: cachedAsset,
      used_external_api: true,
      status: "ready",
    });
    renderFlipflopFixturePreview.mockResolvedValue({
      asset: cachedAsset,
      action: "blink",
      render_url: "/static/projects/test-lab-flipflop-fixtures/renders/full_youtube.mp4",
      used_external_api: false,
    });
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

  it("creates a persistent fixture once and rerenders it locally", async () => {
    render(<FlipflopDebugLab />);

    expect(await screen.findByText("base_scene_base.png")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /generate fixture assets/i }));

    await waitFor(() => {
      expect(createFlipflopFixtureAsset).toHaveBeenCalled();
    });
    expect(await screen.findByText("Fixture saved")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /rerender fixture/i }));

    await waitFor(() => {
      expect(renderFlipflopFixturePreview).toHaveBeenCalledWith(
        "test-lab-run/flipflop_cutouts/scene/base_scene_base.png",
        "blink",
      );
    });
    expect(await screen.findByText("Remotion preview")).toBeInTheDocument();
    expect(screen.getByText("Local only")).toBeInTheDocument();
  });
});
