import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BlinkDebugLab from "./BlinkDebugLab";

const analyzeBlinkDebugAsset = vi.fn();
const createBlinkFixtureAsset = vi.fn();
const getBlinkDebugAssets = vi.fn();
const getBlinkAuditReports = vi.fn();
const renderBlinkFixturePreview = vi.fn();
const runBlinkAudit = vi.fn();
const bumpAssetVersion = vi.fn();

vi.mock("../../api", () => ({
  analyzeBlinkDebugAsset: (...args: unknown[]) =>
    analyzeBlinkDebugAsset(...args),
  assetUrl: (path: string) => path,
  bumpAssetVersion: (...args: unknown[]) => bumpAssetVersion(...args),
  createBlinkFixtureAsset: (...args: unknown[]) =>
    createBlinkFixtureAsset(...args),
  getBlinkAuditReports: () => getBlinkAuditReports(),
  getBlinkDebugAssets: () => getBlinkDebugAssets(),
  renderBlinkFixturePreview: (...args: unknown[]) =>
    renderBlinkFixturePreview(...args),
  runBlinkAudit: (...args: unknown[]) => runBlinkAudit(...args),
}));

const cachedAsset = {
  asset_id: "test-lab-run/blink_cutouts/scene/base_scene_base.png",
  asset_url:
    "/static/projects/test-lab-run/blink_cutouts/scene/base_scene_base.png",
  script_id: "test-lab-run",
  scene_id: "scene",
  filename: "base_scene_base.png",
  created_at: "2026-06-12T00:00:00+00:00",
  source_metadata: {
    registration_algorithm_version: "alpha-mask-registration-v9",
  },
};

const fixtureAsset = {
  ...cachedAsset,
  asset_id:
    "test-lab-blink-fixtures/blink_cutouts/fixture-scene/base_blink_fixture_base.png",
  asset_url:
    "/static/projects/test-lab-blink-fixtures/blink_cutouts/fixture-scene/base_blink_fixture_base.png",
  script_id: "test-lab-blink-fixtures",
  scene_id: "fixture-scene",
  filename: "base_blink_fixture_base.png",
};

describe("BlinkDebugLab", () => {
  beforeEach(() => {
    analyzeBlinkDebugAsset.mockReset();
    createBlinkFixtureAsset.mockReset();
    getBlinkAuditReports.mockReset();
    getBlinkDebugAssets.mockReset();
    renderBlinkFixturePreview.mockReset();
    runBlinkAudit.mockReset();
    bumpAssetVersion.mockReset();
    getBlinkAuditReports.mockResolvedValue([]);
    getBlinkDebugAssets.mockResolvedValue([cachedAsset]);
    createBlinkFixtureAsset.mockResolvedValue({
      asset: cachedAsset,
      used_external_api: true,
      status: "ready",
    });
    renderBlinkFixturePreview.mockResolvedValue({
      asset: cachedAsset,
      action: "blink",
      render_url:
        "/static/projects/test-lab-blink-fixtures/renders/full_youtube.mp4",
      used_external_api: false,
    });
    analyzeBlinkDebugAsset.mockResolvedValue({
      asset: cachedAsset,
      action: "blink",
      used_external_api: false,
      registration_algorithm_version: "alpha-mask-registration-v10",
      anchor: { detected: true },
      debug_url:
        "/static/projects/test-lab-run/blink_cutouts/scene/debug_base_scene_base_blink.png",
      status: "passed",
      error: null,
    });
  });

  it("reruns the selected cached asset through the local analyzer", async () => {
    render(<BlinkDebugLab />);

    expect(await screen.findByText("Blink base: scene")).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /blink base: scene/i }),
    ).toHaveAttribute(
      "src",
      "/static/projects/test-lab-run/blink_cutouts/scene/base_scene_base.png?t=1781222400000",
    );
    expect(
      screen.getByRole("img", { name: /cached base png/i }),
    ).toHaveAttribute(
      "src",
      "/static/projects/test-lab-run/blink_cutouts/scene/base_scene_base.png?t=1781222400000",
    );
    expect(screen.getByRole("img", { name: /cached base png/i })).toHaveClass(
      "max-h-full",
      "max-w-full",
    );
    expect(
      screen.queryByRole("combobox", { name: /blink action/i }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Blink action:")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /rerun detector/i }));

    await waitFor(() => {
      expect(analyzeBlinkDebugAsset).toHaveBeenCalledWith(
        "test-lab-run/blink_cutouts/scene/base_scene_base.png",
        "blink",
      );
    });
    expect(bumpAssetVersion).toHaveBeenCalledWith(
      "/static/projects/test-lab-run/blink_cutouts/scene/debug_base_scene_base_blink.png",
    );
    expect(
      await screen.findByText("alpha-mask-registration-v10"),
    ).toBeInTheDocument();
    expect(screen.getByText("None")).toBeInTheDocument();
  });

  it("creates a persistent fixture once and rerenders it locally", async () => {
    render(<BlinkDebugLab />);

    expect(await screen.findByText("Blink base: scene")).toBeInTheDocument();
    expect(screen.getByLabelText("Background")).toHaveValue("outdoor");
    fireEvent.change(screen.getByLabelText("Background"), {
      target: { value: "indoor" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: /generate fixture assets/i }),
    );

    await waitFor(() => {
      expect(createBlinkFixtureAsset).toHaveBeenCalled();
    });
    expect(await screen.findByText("Fixture saved")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /rerender fixture/i }));

    await waitFor(() => {
      expect(renderBlinkFixturePreview).toHaveBeenCalledWith(
        "test-lab-run/blink_cutouts/scene/base_scene_base.png",
        "blink",
        "indoor",
      );
    });
    expect(await screen.findByText("Remotion preview")).toBeInTheDocument();
    expect(screen.getByText("Local only")).toBeInTheDocument();
  });

  it("disables fixture generation when the saved fixture already exists", async () => {
    getBlinkDebugAssets.mockResolvedValue([fixtureAsset]);

    render(<BlinkDebugLab />);

    expect(
      await screen.findByText("Blink base: fixture-scene"),
    ).toBeInTheDocument();
    const generateButton = screen.getByRole("button", {
      name: /fixture assets already generated/i,
    });
    expect(generateButton).toBeDisabled();

    fireEvent.click(generateButton);

    expect(createBlinkFixtureAsset).not.toHaveBeenCalled();
  });

  it("shows a dedicated background inspector tab with indoor and outdoor stages", async () => {
    render(<BlinkDebugLab />);

    fireEvent.click(screen.getByRole("button", { name: "Backgrounds" }));

    expect(await screen.findByText("Renderer backgrounds")).toBeInTheDocument();
    for (const label of ["Outdoor", "Indoor"]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
    for (const removedLabel of ["Desk", "Classroom", "Office", "Kitchen", "Lab"]) {
      expect(screen.queryByText(removedLabel)).not.toBeInTheDocument();
    }
    expect(
      screen.getByText(
        "Inspect the renderer-owned stages without rerendering a fixture.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /rerender fixture/i }),
    ).not.toBeInTheDocument();
  });

  it("shows the blink audit as a nested blink tab", async () => {
    render(<BlinkDebugLab />);

    fireEvent.click(screen.getByRole("button", { name: "Blink Audit" }));

    expect(await screen.findByRole("button", { name: /run blink audit/i })).toBeInTheDocument();
  });
});
