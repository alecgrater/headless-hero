import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ImageReviewListResponse, ImageReviewUpdateResponse } from "../../../types/imageReview";
import type { ScriptContent } from "../../../types/script";
import ImageReviewTab from "./ImageReviewTab";

const apiMocks = vi.hoisted(() => ({
  getImageReviewAssets: vi.fn(),
  getImageReviewAssetData: vi.fn(),
  saveImageReviewEdit: vi.fn(),
  resetImageReviewAsset: vi.fn(),
}));

let drawImageMock: ReturnType<typeof vi.fn>;
let fillRectMock: ReturnType<typeof vi.fn>;
let fillTextMock: ReturnType<typeof vi.fn>;

vi.mock("../../../api", async () => {
  const actual = await vi.importActual<typeof import("../../../api")>("../../../api");
  return {
    ...actual,
    assetUrl: (path: string) => path,
    getImageReviewAssets: apiMocks.getImageReviewAssets,
    getImageReviewAssetData: apiMocks.getImageReviewAssetData,
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
    {
      asset_id: "scene:scene_002:frame:0",
      scene_id: "scene_002",
      segment_index: 0,
      segment_name: "Opening",
      scene_index: 1,
      scene_label: "A manager points at a schedule.",
      asset_kind: "frame",
      current_url: "/static/projects/script-1/images/scene_002_f0.png",
      original_url: "/static/projects/script-1/images/scene_002_f0.png",
      reviewed: true,
      width: 1344,
      height: 768,
      frame_index: 0,
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
  apiMocks.getImageReviewAssetData.mockReset();
  apiMocks.saveImageReviewEdit.mockReset();
  apiMocks.resetImageReviewAsset.mockReset();
  apiMocks.getImageReviewAssets.mockResolvedValue(listResponse);
  apiMocks.getImageReviewAssetData.mockResolvedValue({
    script_id: "script-1",
    asset_id: "scene:scene_001:image",
    content_type: "image/png",
    byte_count: 4,
    data_url: "data:image/png;base64,ZmFrZQ==",
  });
  apiMocks.saveImageReviewEdit.mockResolvedValue(updateResponse());
  apiMocks.resetImageReviewAsset.mockResolvedValue(updateResponse({ ...script, title: "Reset Script" }));

  drawImageMock = vi.fn();
  fillRectMock = vi.fn();
  fillTextMock = vi.fn();
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
    clearRect: vi.fn(),
    drawImage: drawImageMock,
    fillRect: fillRectMock,
    fillText: fillTextMock,
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
  vi.stubGlobal("createImageBitmap", vi.fn(async () => ({
    width: 100,
    height: 56,
    close: vi.fn(),
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
  it("loads the selected image through the API before drawing it to canvas", async () => {
    render(<ImageReviewTab scriptId="script-1" content={script} onContentUpdated={vi.fn()} />);

    expect((await screen.findAllByText("scene_001")).length).toBeGreaterThan(0);
    await waitFor(() => {
      expect(apiMocks.getImageReviewAssetData).toHaveBeenCalledWith("script-1", "scene:scene_001:image");
    });
    expect(createImageBitmap).toHaveBeenCalled();
    expect(drawImageMock).toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /save edited copy/i })).toBeEnabled();
  });

  it("positions top toolbar tooltips below the buttons so they are not clipped", async () => {
    render(<ImageReviewTab scriptId="script-1" content={script} onContentUpdated={vi.fn()} />);

    expect((await screen.findAllByText("scene_001")).length).toBeGreaterThan(0);

    const tooltip = screen.getByText("Selection tool").closest('[role="tooltip"]');
    expect(tooltip).toHaveClass("top-full");
    expect(tooltip).not.toHaveClass("bottom-full");
  });

  it("shows an error and disables saving when the selected image cannot load", async () => {
    apiMocks.getImageReviewAssetData.mockRejectedValueOnce(new Error("Image Review asset file not found"));

    render(<ImageReviewTab scriptId="script-1" content={script} onContentUpdated={vi.fn()} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Image Review asset file not found: /static/projects/script-1/images/scene_001.png",
    );
    expect(screen.getByRole("button", { name: /save edited copy/i })).toBeDisabled();
    expect(drawImageMock).not.toHaveBeenCalled();
    expect(fillRectMock).toHaveBeenCalled();
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

  it("lets added text remain selectable and editable before saving", async () => {
    render(<ImageReviewTab scriptId="script-1" content={script} onContentUpdated={vi.fn()} />);

    expect((await screen.findAllByText("scene_001")).length).toBeGreaterThan(0);

    await userEvent.clear(screen.getByLabelText("Text content"));
    await userEvent.type(screen.getByLabelText("Text content"), "First draft");
    await userEvent.click(screen.getByRole("button", { name: /add text/i }));

    await userEvent.clear(screen.getByLabelText("Text content"));
    await userEvent.type(screen.getByLabelText("Text content"), "Final words");
    await userEvent.selectOptions(screen.getByLabelText("Text font"), "Georgia");
    await userEvent.click(screen.getByRole("button", { name: /save edited copy/i }));

    expect(fillTextMock).toHaveBeenCalledWith("Final words", expect.any(Number), expect.any(Number));
    expect(apiMocks.saveImageReviewEdit).toHaveBeenCalledWith(
      "script-1",
      "scene:scene_001:image",
      "data:image/png;base64,edited",
    );
  });

  it("moves an added text object by dragging it on the canvas", async () => {
    render(<ImageReviewTab scriptId="script-1" content={script} onContentUpdated={vi.fn()} />);

    expect((await screen.findAllByText("scene_001")).length).toBeGreaterThan(0);

    await userEvent.clear(screen.getByLabelText("Text content"));
    await userEvent.type(screen.getByLabelText("Text content"), "Drag me");
    await userEvent.click(screen.getByRole("button", { name: /add text/i }));

    const canvas = screen.getByLabelText("Image review canvas");
    canvas.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, clientX: 50, clientY: 28, pointerId: 1 }));
    canvas.dispatchEvent(new PointerEvent("pointermove", { bubbles: true, clientX: 70, clientY: 40, pointerId: 1 }));
    canvas.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, clientX: 70, clientY: 40, pointerId: 1 }));
    await userEvent.click(screen.getByRole("button", { name: /save edited copy/i }));

    expect(fillTextMock).toHaveBeenCalledWith("Drag me", 70, 40);
  });

  it("undoes newly added text before saving", async () => {
    render(<ImageReviewTab scriptId="script-1" content={script} onContentUpdated={vi.fn()} />);

    expect((await screen.findAllByText("scene_001")).length).toBeGreaterThan(0);

    await userEvent.clear(screen.getByLabelText("Text content"));
    await userEvent.type(screen.getByLabelText("Text content"), "Temporary");
    await userEvent.click(screen.getByRole("button", { name: /add text/i }));
    await userEvent.click(screen.getByRole("button", { name: "Undo" }));

    fillTextMock.mockClear();
    await userEvent.click(screen.getByRole("button", { name: /save edited copy/i }));

    expect(fillTextMock).not.toHaveBeenCalledWith("Temporary", expect.any(Number), expect.any(Number));
  });

  it("redoes newly added text visibly before saving", async () => {
    render(<ImageReviewTab scriptId="script-1" content={script} onContentUpdated={vi.fn()} />);

    expect((await screen.findAllByText("scene_001")).length).toBeGreaterThan(0);

    await userEvent.clear(screen.getByLabelText("Text content"));
    await userEvent.type(screen.getByLabelText("Text content"), "Redo text");
    await userEvent.click(screen.getByRole("button", { name: /add text/i }));
    await userEvent.click(screen.getByRole("button", { name: "Undo" }));
    fillTextMock.mockClear();

    await userEvent.click(screen.getByRole("button", { name: "Redo" }));
    await waitFor(() => {
      expect(fillTextMock).toHaveBeenCalledWith("Redo text", expect.any(Number), expect.any(Number));
    });
  });

  it("paints eraser strokes with the selected black or white color", async () => {
    render(<ImageReviewTab scriptId="script-1" content={script} onContentUpdated={vi.fn()} />);

    expect((await screen.findAllByText("scene_001")).length).toBeGreaterThan(0);

    await userEvent.click(screen.getByRole("button", { name: /eraser tool/i }));
    await userEvent.click(screen.getByRole("button", { name: /white eraser/i }));

    const canvas = screen.getByLabelText("Image review canvas");
    canvas.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, clientX: 10, clientY: 10, pointerId: 1 }));

    expect(fillRectMock).toHaveBeenLastCalledWith(expect.any(Number), expect.any(Number), 32, 32);
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

  it("switches to a gallery browser and opens a selected image in the editor", async () => {
    render(<ImageReviewTab scriptId="script-1" content={script} onContentUpdated={vi.fn()} />);

    expect((await screen.findAllByText("scene_001")).length).toBeGreaterThan(0);

    await userEvent.click(screen.getByRole("button", { name: /gallery view/i }));

    expect(screen.getByRole("heading", { name: /browse generated images/i })).toBeInTheDocument();
    expect(screen.getByAltText("scene_001 Scene image preview")).toHaveAttribute(
      "src",
      "/static/projects/script-1/images/scene_001.png",
    );
    expect(screen.getByAltText("scene_002 Frame 1 preview")).toHaveAttribute(
      "src",
      "/static/projects/script-1/images/scene_002_f0.png",
    );

    await userEvent.click(screen.getByRole("button", { name: /open scene_002 frame 1 in editor/i }));

    expect(screen.getByRole("button", { name: /editor view/i })).toHaveAttribute("aria-pressed", "true");
    await waitFor(() => {
      expect(apiMocks.getImageReviewAssetData).toHaveBeenLastCalledWith("script-1", "scene:scene_002:frame:0");
    });
  });
});
