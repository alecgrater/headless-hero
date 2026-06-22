import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ImageReviewListResponse, ImageReviewUpdateResponse } from "../../../types/imageReview";
import type { ScriptContent } from "../../../types/script";
import ImageReviewTab from "./ImageReviewTab";

const apiMocks = vi.hoisted(() => ({
  getImageReviewAssets: vi.fn(),
  saveImageReviewEdit: vi.fn(),
  resetImageReviewAsset: vi.fn(),
}));

vi.mock("../../../api", async () => {
  const actual = await vi.importActual<typeof import("../../../api")>("../../../api");
  return {
    ...actual,
    assetUrl: (path: string) => path,
    getImageReviewAssets: apiMocks.getImageReviewAssets,
    saveImageReviewEdit: apiMocks.saveImageReviewEdit,
    resetImageReviewAsset: apiMocks.resetImageReviewAsset,
  };
});

const script: ScriptContent = {
  title: "Image Review",
  intro_hook: "",
  outro_cta: "",
  segments: [
    {
      name: "Opening",
      scenes: [
        {
          id: "scene_001",
          narration: "A worker studies a calendar.",
          visual_prompt: "Calendar.",
          duration_estimate_seconds: 8,
          is_title_card: false,
          image_url: "/static/projects/script-1/images/scene_001.png",
        },
      ],
    },
  ],
};

const listResponse: ImageReviewListResponse = {
  script_id: "script-1",
  assets: [
    {
      asset_id: "scene:scene_001:image",
      scene_id: "scene_001",
      segment_index: 0,
      segment_name: "Opening",
      scene_index: 0,
      scene_label: "A worker studies a calendar.",
      asset_kind: "scene",
      current_url: "/static/projects/script-1/images/scene_001.png",
      original_url: "/static/projects/script-1/images/scene_001.png",
      reviewed: false,
      width: 1920,
      height: 1080,
    },
  ],
};

function updateResponse(nextScript: ScriptContent = script): ImageReviewUpdateResponse {
  return {
    script_id: "script-1",
    asset: { ...listResponse.assets[0], reviewed: true, current_url: "/static/projects/script-1/image_review/edit.png" },
    assets: [{ ...listResponse.assets[0], reviewed: true, current_url: "/static/projects/script-1/image_review/edit.png" }],
    script: nextScript,
  };
}

beforeEach(() => {
  apiMocks.getImageReviewAssets.mockReset();
  apiMocks.saveImageReviewEdit.mockReset();
  apiMocks.resetImageReviewAsset.mockReset();
  apiMocks.getImageReviewAssets.mockResolvedValue(listResponse);
  apiMocks.saveImageReviewEdit.mockResolvedValue(updateResponse());
  apiMocks.resetImageReviewAsset.mockResolvedValue(updateResponse({ ...script, title: "Reset Script" }));

  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
    clearRect: vi.fn(),
    drawImage: vi.fn(),
    fillRect: vi.fn(),
    fillText: vi.fn(),
    getImageData: vi.fn(() => ({ data: new Uint8ClampedArray(4), width: 1, height: 1 })),
    putImageData: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
    scale: vi.fn(),
    setLineDash: vi.fn(),
    strokeRect: vi.fn(),
    beginPath: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    stroke: vi.fn(),
    lineTo: vi.fn(),
    moveTo: vi.fn(),
  } as unknown as CanvasRenderingContext2D);
  vi.spyOn(HTMLCanvasElement.prototype, "toDataURL").mockReturnValue("data:image/png;base64,edited");
  URL.createObjectURL = vi.fn(() => "blob:image-review");
  URL.revokeObjectURL = vi.fn();
  vi.stubGlobal("fetch", vi.fn(async () => ({
    ok: true,
    blob: async () => new Blob(["fake"], { type: "image/png" }),
  })));
  vi.stubGlobal("Image", class {
    crossOrigin = "";
    naturalWidth = 100;
    naturalHeight = 56;
    width = 100;
    height = 56;
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;
    set src(_value: string) {
      setTimeout(() => this.onload?.(), 0);
    }
  });
});

describe("ImageReviewTab", () => {
  it("loads the selected image through fetch before drawing it to canvas", async () => {
    render(<ImageReviewTab scriptId="script-1" content={script} onContentUpdated={vi.fn()} />);

    expect((await screen.findAllByText("scene_001")).length).toBeGreaterThan(0);
    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith("/static/projects/script-1/images/scene_001.png");
    });
  });

  it("lists image review assets and saves a deleted selection", async () => {
    const onContentUpdated = vi.fn();

    render(<ImageReviewTab scriptId="script-1" content={script} onContentUpdated={onContentUpdated} />);

    expect((await screen.findAllByText("scene_001")).length).toBeGreaterThan(0);
    expect(screen.getByText(/A worker studies a calendar/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /select all/i }));
    await userEvent.click(screen.getByRole("button", { name: /copy selection/i }));
    expect(screen.getByRole("button", { name: /paste selection/i })).toBeEnabled();
    await userEvent.click(screen.getByRole("button", { name: /paste selection/i }));
    await userEvent.click(screen.getByRole("button", { name: /delete selection/i }));
    await userEvent.click(screen.getByRole("button", { name: /save edited copy/i }));

    await waitFor(() => {
      expect(apiMocks.saveImageReviewEdit).toHaveBeenCalledWith(
        "script-1",
        "scene:scene_001:image",
        "data:image/png;base64,edited",
      );
    });
    expect(onContentUpdated).toHaveBeenCalledWith(script);
  });

  it("resets the selected asset and applies returned script content", async () => {
    const onContentUpdated = vi.fn();

    render(<ImageReviewTab scriptId="script-1" content={script} onContentUpdated={onContentUpdated} />);

    expect((await screen.findAllByText("scene_001")).length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole("button", { name: /reset to original/i }));

    await waitFor(() => {
      expect(apiMocks.resetImageReviewAsset).toHaveBeenCalledWith("script-1", "scene:scene_001:image");
    });
    expect(onContentUpdated).toHaveBeenCalledWith({ ...script, title: "Reset Script" });
  });
});
