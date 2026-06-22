import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Clipboard,
  Copy,
  Eraser,
  MousePointer2,
  Redo2,
  RotateCcw,
  Save,
  Scissors,
  SquareDashedMousePointer,
  Type,
  Undo2,
} from "lucide-react";

import { getImageReviewAssetData } from "../../../api";
import type { ImageReviewAsset } from "../../../types/imageReview";
import { Tooltip } from "../../ui/Tooltip";

type ToolMode = "select" | "erase" | "text";
type EraserColor = "#000000" | "#FFFFFF";
type TextFont = "Inter" | "Arial" | "Georgia" | "Impact";

interface Selection {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface BaseOverlayObject {
  id: string;
  x: number;
  y: number;
}

interface TextOverlayObject extends BaseOverlayObject {
  kind: "text";
  text: string;
  size: number;
  color: string;
  font: TextFont;
}

interface ImageOverlayObject extends BaseOverlayObject {
  kind: "image";
  imageData: ImageData;
}

type OverlayObject = TextOverlayObject | ImageOverlayObject;

interface Props {
  scriptId: string;
  asset: ImageReviewAsset;
  saving: boolean;
  resetting: boolean;
  onSave: (dataUrl: string) => void;
  onReset: () => void;
}

function normalizeSelection(selection: Selection): Selection {
  const x = selection.width < 0 ? selection.x + selection.width : selection.x;
  const y = selection.height < 0 ? selection.y + selection.height : selection.y;
  return {
    x,
    y,
    width: Math.abs(selection.width),
    height: Math.abs(selection.height),
  };
}

function buttonClass(active = false) {
  return `inline-flex h-9 w-9 items-center justify-center rounded-md border transition-colors ${
    active
      ? "border-violet-400/70 bg-violet-500/20 text-violet-100"
      : "border-neutral-700 bg-neutral-850 text-neutral-300 hover:border-neutral-600 hover:bg-neutral-800"
  }`;
}

function dataUrlToBlob(dataUrl: string): Blob {
  const commaIndex = dataUrl.indexOf(",");
  if (!dataUrl.startsWith("data:") || commaIndex === -1) {
    throw new Error("Invalid image data URL");
  }
  const metadata = dataUrl.slice(0, commaIndex);
  const base64Data = dataUrl.slice(commaIndex + 1);
  const mimeMatch = /^data:([^;]+);base64$/i.exec(metadata);
  if (!mimeMatch) {
    throw new Error("Image data URL must be base64 encoded");
  }
  const binary = atob(base64Data);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return new Blob([bytes], { type: mimeMatch[1] });
}

function textFontFamily(font: TextFont): string {
  if (font === "Inter") return "Inter, Arial, sans-serif";
  if (font === "Georgia") return "Georgia, serif";
  if (font === "Impact") return "Impact, Arial Black, sans-serif";
  return "Arial, sans-serif";
}

function applyTextStyle(ctx: CanvasRenderingContext2D, object: TextOverlayObject) {
  ctx.font = `700 ${object.size}px ${textFontFamily(object.font)}`;
  ctx.fillStyle = object.color;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
}

function textBounds(ctx: CanvasRenderingContext2D, object: TextOverlayObject): Selection {
  applyTextStyle(ctx, object);
  const measured = typeof ctx.measureText === "function" ? ctx.measureText(object.text) : null;
  const width = Math.max(object.size, measured?.width ?? object.text.length * object.size * 0.6);
  const height = object.size * 1.25;
  return {
    x: object.x - width / 2,
    y: object.y - height / 2,
    width,
    height,
  };
}

function objectBounds(ctx: CanvasRenderingContext2D, object: OverlayObject): Selection {
  if (object.kind === "image") {
    return { x: object.x, y: object.y, width: object.imageData.width, height: object.imageData.height };
  }
  return textBounds(ctx, object);
}

function pointInSelection(point: { x: number; y: number }, selection: Selection): boolean {
  return (
    point.x >= selection.x &&
    point.x <= selection.x + selection.width &&
    point.y >= selection.y &&
    point.y <= selection.y + selection.height
  );
}

export default function ImageReviewEditor({ scriptId, asset, saving, resetting, onSave, onReset }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const overlayRef = useRef<HTMLCanvasElement | null>(null);
  const drawingRef = useRef(false);
  const dragStartRef = useRef<{ x: number; y: number } | null>(null);
  const draggingObjectRef = useRef<{ id: string; offsetX: number; offsetY: number } | null>(null);
  const copiedRef = useRef<ImageData | null>(null);
  const [tool, setTool] = useState<ToolMode>("select");
  const [selection, setSelection] = useState<Selection | null>(null);
  const [overlayObjects, setOverlayObjects] = useState<OverlayObject[]>([]);
  const [activeObjectId, setActiveObjectId] = useState<string | null>(null);
  const [brushSize, setBrushSize] = useState(32);
  const [eraserColor, setEraserColor] = useState<EraserColor>("#000000");
  const [text, setText] = useState("Text");
  const [textSize, setTextSize] = useState(72);
  const [textColor, setTextColor] = useState("#111111");
  const [textFont, setTextFont] = useState<TextFont>("Inter");
  const [history, setHistory] = useState<string[]>([]);
  const [future, setFuture] = useState<string[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [hasCopiedSelection, setHasCopiedSelection] = useState(false);

  const dimensionsLabel = useMemo(() => {
    if (!asset.width || !asset.height) return "dimensions unknown";
    return `${asset.width} x ${asset.height}`;
  }, [asset.height, asset.width]);

  const canvasPoint = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    const renderedWidth = rect.width || canvas.width || 1;
    const renderedHeight = rect.height || canvas.height || 1;
    return {
      x: ((event.clientX - rect.left) / renderedWidth) * canvas.width,
      y: ((event.clientY - rect.top) / renderedHeight) * canvas.height,
    };
  };

  const drawSelectionBox = (ctx: CanvasRenderingContext2D, canvas: HTMLCanvasElement, box: Selection) => {
    const normalized = normalizeSelection(box);
    ctx.save();
    ctx.setLineDash([12, 8]);
    ctx.lineWidth = Math.max(2, canvas.width / 700);
    ctx.strokeStyle = "#A78BFA";
    ctx.fillStyle = "rgba(167, 139, 250, 0.12)";
    ctx.fillRect(normalized.x, normalized.y, normalized.width, normalized.height);
    ctx.strokeRect(normalized.x, normalized.y, normalized.width, normalized.height);
    ctx.restore();
  };

  const renderOverlayObject = (ctx: CanvasRenderingContext2D, object: OverlayObject) => {
    if (object.kind === "image") {
      ctx.putImageData(object.imageData, object.x, object.y);
      return;
    }
    ctx.save();
    applyTextStyle(ctx, object);
    ctx.fillText(object.text, object.x, object.y);
    ctx.restore();
  };

  const drawOverlay = useCallback((nextSelection: Selection | null, nextObjects: OverlayObject[], nextActiveObjectId: string | null) => {
    const overlay = overlayRef.current;
    const canvas = canvasRef.current;
    if (!overlay || !canvas) return;
    overlay.width = canvas.width;
    overlay.height = canvas.height;
    const ctx = overlay.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    nextObjects.forEach((object) => {
      renderOverlayObject(ctx, object);
      if (object.id === nextActiveObjectId) {
        drawSelectionBox(ctx, canvas, objectBounds(ctx, object));
      }
    });
    if (nextSelection) drawSelectionBox(ctx, canvas, nextSelection);
  }, []);

  const pushHistory = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    setHistory((prev) => [...prev.slice(-29), canvas.toDataURL("image/png")]);
    setFuture([]);
  }, []);

  const restoreDataUrl = useCallback((dataUrl: string) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => {
      canvas.width = image.naturalWidth || image.width || canvas.width;
      canvas.height = image.naturalHeight || image.height || canvas.height;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
      drawOverlay(null, [], null);
    };
    image.src = dataUrl;
  }, [drawOverlay]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    let cancelled = false;
    let objectUrl: string | null = null;
    setLoaded(false);
    setSelection(null);
    setOverlayObjects([]);
    setActiveObjectId(null);
    setHistory([]);
    setFuture([]);
    copiedRef.current = null;
    setHasCopiedSelection(false);
    setLoadError(null);

    const drawFallback = (message: string) => {
      if (cancelled) return;
      canvas.width = asset.width || 1920;
      canvas.height = asset.height || 1080;
      ctx.fillStyle = "#171717";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      setLoaded(false);
      setLoadError(message);
      drawOverlay(null, [], null);
    };

    const drawImageElement = (objectUrlValue: string) => {
      const image = new Image();
      image.onload = () => {
        if (cancelled) return;
        canvas.width = image.naturalWidth || image.width || 1920;
        canvas.height = image.naturalHeight || image.height || 1080;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
        setLoaded(true);
        setLoadError(null);
        drawOverlay(null, [], null);
      };
      image.onerror = () => drawFallback(`Failed to decode image: ${asset.current_url}`);
      image.src = objectUrlValue;
    };

    const loadImage = async () => {
      try {
        const imageData = await getImageReviewAssetData(scriptId, asset.asset_id);
        const blob = dataUrlToBlob(imageData.data_url);
        if (cancelled) return;
        if ("createImageBitmap" in window) {
          let bitmap: ImageBitmap | null = null;
          try {
            bitmap = await createImageBitmap(blob);
          } catch {
            bitmap = null;
          }
          if (cancelled && bitmap) {
            bitmap.close();
            return;
          }
          if (bitmap) {
            canvas.width = bitmap.width || asset.width || 1920;
            canvas.height = bitmap.height || asset.height || 1080;
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
            bitmap.close();
            setLoaded(true);
            setLoadError(null);
            drawOverlay(null, [], null);
            return;
          }
        }
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        drawImageElement(objectUrl);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to load image data";
        drawFallback(`${message}: ${asset.current_url}`);
      }
    };

    void loadImage();

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [asset.asset_id, asset.current_url, asset.height, asset.width, drawOverlay, scriptId]);

  useEffect(() => {
    drawOverlay(selection, overlayObjects, activeObjectId);
  }, [activeObjectId, drawOverlay, overlayObjects, selection]);

  const updateTextObject = (patch: Partial<Pick<TextOverlayObject, "text" | "size" | "color" | "font">>) => {
    if (!activeObjectId) return;
    setOverlayObjects((objects) =>
      objects.map((object) =>
        object.id === activeObjectId && object.kind === "text"
          ? { ...object, ...patch }
          : object,
      ),
    );
  };

  const handlePointerDown = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!loaded) return;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const point = canvasPoint(event);
    drawingRef.current = true;
    dragStartRef.current = point;
    event.currentTarget.setPointerCapture?.(event.pointerId);
    if (tool === "select") {
      const hitObject = [...overlayObjects].reverse().find((object) => pointInSelection(point, objectBounds(ctx, object)));
      if (hitObject) {
        setActiveObjectId(hitObject.id);
        setSelection(null);
        draggingObjectRef.current = {
          id: hitObject.id,
          offsetX: point.x - hitObject.x,
          offsetY: point.y - hitObject.y,
        };
        if (hitObject.kind === "text") {
          setText(hitObject.text);
          setTextSize(hitObject.size);
          setTextColor(hitObject.color);
          setTextFont(hitObject.font);
        }
        drawOverlay(null, overlayObjects, hitObject.id);
        return;
      }
      setActiveObjectId(null);
      const nextSelection = { x: point.x, y: point.y, width: 0, height: 0 };
      setSelection(nextSelection);
      drawOverlay(nextSelection, overlayObjects, null);
    } else if (tool === "erase") {
      pushHistory();
      ctx.fillStyle = eraserColor;
      ctx.fillRect(point.x - brushSize / 2, point.y - brushSize / 2, brushSize, brushSize);
    } else if (tool === "text") {
      if (!text.trim()) return;
      const object: TextOverlayObject = {
        id: `text-${Date.now()}-${Math.random().toString(36).slice(2)}`,
        kind: "text",
        x: point.x,
        y: point.y,
        text: text.trim(),
        size: textSize,
        color: textColor,
        font: textFont,
      };
      setOverlayObjects((objects) => [...objects, object]);
      setActiveObjectId(object.id);
      setSelection(null);
      setTool("select");
    }
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawingRef.current || !dragStartRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const point = canvasPoint(event);
    if (draggingObjectRef.current) {
      const drag = draggingObjectRef.current;
      setOverlayObjects((objects) =>
        objects.map((object) =>
          object.id === drag.id
            ? { ...object, x: point.x - drag.offsetX, y: point.y - drag.offsetY }
            : object,
        ),
      );
    } else if (tool === "select") {
      const start = dragStartRef.current;
      const nextSelection = {
        x: start.x,
        y: start.y,
        width: point.x - start.x,
        height: point.y - start.y,
      };
      setSelection(nextSelection);
      drawOverlay(nextSelection, overlayObjects, activeObjectId);
    } else if (tool === "erase") {
      ctx.fillStyle = eraserColor;
      ctx.fillRect(point.x - brushSize / 2, point.y - brushSize / 2, brushSize, brushSize);
    }
  };

  const handlePointerUp = (event: React.PointerEvent<HTMLCanvasElement>) => {
    drawingRef.current = false;
    dragStartRef.current = null;
    draggingObjectRef.current = null;
    event.currentTarget.releasePointerCapture?.(event.pointerId);
  };

  const selectAll = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    setActiveObjectId(null);
    setSelection({ x: 0, y: 0, width: canvas.width, height: canvas.height });
  };

  const copySelection = () => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx || !selection) return;
    const normalized = normalizeSelection(selection);
    if (normalized.width < 1 || normalized.height < 1) return;
    copiedRef.current = ctx.getImageData(normalized.x, normalized.y, normalized.width, normalized.height);
    setHasCopiedSelection(true);
  };

  const deleteSelection = () => {
    if (activeObjectId) {
      setOverlayObjects((objects) => objects.filter((object) => object.id !== activeObjectId));
      setActiveObjectId(null);
      return;
    }
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx || !selection) return;
    const normalized = normalizeSelection(selection);
    if (normalized.width < 1 || normalized.height < 1) return;
    pushHistory();
    ctx.clearRect(normalized.x, normalized.y, normalized.width, normalized.height);
  };

  const pasteSelection = () => {
    const canvas = canvasRef.current;
    const copied = copiedRef.current;
    if (!canvas || !copied) return;
    const base = selection ? normalizeSelection(selection) : { x: 0, y: 0, width: copied.width, height: copied.height };
    const x = Math.min(Math.max(0, base.x + 32), Math.max(0, canvas.width - copied.width));
    const y = Math.min(Math.max(0, base.y + 32), Math.max(0, canvas.height - copied.height));
    const object: ImageOverlayObject = {
      id: `image-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      kind: "image",
      x,
      y,
      imageData: copied,
    };
    setOverlayObjects((objects) => [...objects, object]);
    setActiveObjectId(object.id);
    setSelection(null);
  };

  const addTextCenter = () => {
    const canvas = canvasRef.current;
    if (!canvas || !text.trim()) return;
    const object: TextOverlayObject = {
      id: `text-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      kind: "text",
      x: canvas.width / 2,
      y: canvas.height / 2,
      text: text.trim(),
      size: textSize,
      color: textColor,
      font: textFont,
    };
    setOverlayObjects((objects) => [...objects, object]);
    setActiveObjectId(object.id);
    setSelection(null);
    setTool("select");
  };

  const undo = () => {
    const canvas = canvasRef.current;
    if (!canvas || history.length === 0) return;
    const current = canvas.toDataURL("image/png");
    const previous = history[history.length - 1];
    setHistory((prev) => prev.slice(0, -1));
    setFuture((prev) => [...prev, current]);
    restoreDataUrl(previous);
  };

  const redo = () => {
    const canvas = canvasRef.current;
    if (!canvas || future.length === 0) return;
    const current = canvas.toDataURL("image/png");
    const next = future[future.length - 1];
    setFuture((prev) => prev.slice(0, -1));
    setHistory((prev) => [...prev, current]);
    restoreDataUrl(next);
  };

  const flattenedDataUrl = () => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const output = document.createElement("canvas");
    output.width = canvas.width;
    output.height = canvas.height;
    const ctx = output.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(canvas, 0, 0);
    overlayObjects.forEach((object) => renderOverlayObject(ctx, object));
    return output.toDataURL("image/png");
  };

  const handleSave = () => {
    const canvas = canvasRef.current;
    if (!canvas || !loaded) return;
    const dataUrl = flattenedDataUrl();
    if (dataUrl) onSave(dataUrl);
  };

  const activeTextObject = overlayObjects.find(
    (object): object is TextOverlayObject => object.id === activeObjectId && object.kind === "text",
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-neutral-800 bg-neutral-950/40">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-neutral-800 bg-neutral-900/70 px-3 py-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm font-semibold text-neutral-100">{asset.scene_id}</span>
            <span className="rounded-full bg-neutral-800 px-2 py-0.5 text-[11px] font-medium capitalize text-neutral-300">
              {asset.asset_kind}
            </span>
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${asset.reviewed ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-300"}`}>
              {asset.reviewed ? "Reviewed" : "Original"}
            </span>
          </div>
          <p className="mt-0.5 truncate text-xs text-neutral-500">{dimensionsLabel}</p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Tooltip content="Selection tool" side="bottom">
            <button type="button" aria-label="Selection tool" onClick={() => setTool("select")} className={buttonClass(tool === "select")}>
              <SquareDashedMousePointer className="h-4 w-4" />
            </button>
          </Tooltip>
          <Tooltip content="Eraser" side="bottom">
            <button type="button" aria-label="Eraser tool" onClick={() => setTool("erase")} className={buttonClass(tool === "erase")}>
              <Eraser className="h-4 w-4" />
            </button>
          </Tooltip>
          <Tooltip content="Text tool" side="bottom">
            <button type="button" aria-label="Text tool" onClick={() => setTool("text")} className={buttonClass(tool === "text")}>
              <Type className="h-4 w-4" />
            </button>
          </Tooltip>
          <span className="mx-1 h-6 w-px bg-neutral-800" />
          <Tooltip content="Undo" side="bottom">
            <button type="button" aria-label="Undo" onClick={undo} disabled={history.length === 0} className={buttonClass()}>
              <Undo2 className="h-4 w-4" />
            </button>
          </Tooltip>
          <Tooltip content="Redo" side="bottom">
            <button type="button" aria-label="Redo" onClick={redo} disabled={future.length === 0} className={buttonClass()}>
              <Redo2 className="h-4 w-4" />
            </button>
          </Tooltip>
          <span className="mx-1 h-6 w-px bg-neutral-800" />
          <button
            type="button"
            onClick={onReset}
            disabled={resetting}
            className="inline-flex items-center gap-1.5 rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-xs font-semibold text-neutral-200 transition-colors hover:bg-neutral-700 disabled:cursor-wait disabled:opacity-60"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Reset to original
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || !loaded}
            className="inline-flex items-center gap-1.5 rounded-md bg-violet-600 px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-violet-500 disabled:cursor-wait disabled:opacity-60"
          >
            <Save className="h-3.5 w-3.5" />
            Save edited copy
          </button>
        </div>
      </div>

      <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-neutral-800 bg-neutral-900/45 px-3 py-2">
        <button type="button" onClick={selectAll} disabled={!loaded} className="inline-flex items-center gap-1.5 rounded-md border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs font-medium text-neutral-200 transition-colors hover:bg-neutral-700 disabled:opacity-50">
          <MousePointer2 className="h-3.5 w-3.5" />
          Select all
        </button>
        <button type="button" onClick={copySelection} disabled={!loaded || !selection} className="inline-flex items-center gap-1.5 rounded-md border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs font-medium text-neutral-200 transition-colors hover:bg-neutral-700 disabled:opacity-50">
          <Copy className="h-3.5 w-3.5" />
          Copy selection
        </button>
        <button type="button" onClick={pasteSelection} disabled={!loaded || !hasCopiedSelection} className="inline-flex items-center gap-1.5 rounded-md border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs font-medium text-neutral-200 transition-colors hover:bg-neutral-700 disabled:opacity-50">
          <Clipboard className="h-3.5 w-3.5" />
          Paste selection
        </button>
        <button type="button" onClick={deleteSelection} disabled={!loaded || (!selection && !activeObjectId)} className="inline-flex items-center gap-1.5 rounded-md border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs font-medium text-neutral-200 transition-colors hover:bg-neutral-700 disabled:opacity-50">
          <Scissors className="h-3.5 w-3.5" />
          Delete selection
        </button>
        <div className="inline-flex overflow-hidden rounded-md border border-neutral-700 bg-neutral-950">
          <button
            type="button"
            aria-label="Black eraser"
            aria-pressed={eraserColor === "#000000"}
            onClick={() => setEraserColor("#000000")}
            className={`h-8 px-2 text-xs font-semibold transition-colors ${eraserColor === "#000000" ? "bg-neutral-700 text-white" : "text-neutral-400 hover:bg-neutral-800 hover:text-neutral-100"}`}
          >
            Black
          </button>
          <button
            type="button"
            aria-label="White eraser"
            aria-pressed={eraserColor === "#FFFFFF"}
            onClick={() => setEraserColor("#FFFFFF")}
            className={`h-8 border-l border-neutral-700 px-2 text-xs font-semibold transition-colors ${eraserColor === "#FFFFFF" ? "bg-neutral-100 text-neutral-950" : "text-neutral-400 hover:bg-neutral-800 hover:text-neutral-100"}`}
          >
            White
          </button>
        </div>
        <label className="ml-1 flex items-center gap-2 text-xs text-neutral-400">
          Brush
          <input type="range" min={8} max={120} value={brushSize} onChange={(event) => setBrushSize(Number(event.target.value))} className="w-24 accent-violet-500" />
        </label>
        <label className="flex items-center gap-2 text-xs text-neutral-400">
          Text
          <input
            aria-label="Text content"
            value={activeTextObject?.text ?? text}
            onChange={(event) => {
              setText(event.target.value);
              updateTextObject({ text: event.target.value });
            }}
            className="h-8 w-36 rounded-md border border-neutral-700 bg-neutral-950 px-2 text-xs text-neutral-100 outline-none focus:border-violet-500"
          />
        </label>
        <input
          aria-label="Text color"
          type="color"
          value={activeTextObject?.color ?? textColor}
          onChange={(event) => {
            setTextColor(event.target.value);
            updateTextObject({ color: event.target.value });
          }}
          className="h-8 w-9 rounded border border-neutral-700 bg-neutral-950 p-1"
        />
        <label className="flex items-center gap-2 text-xs text-neutral-400">
          Font
          <select
            aria-label="Text font"
            value={activeTextObject?.font ?? textFont}
            onChange={(event) => {
              const nextFont = event.target.value as TextFont;
              setTextFont(nextFont);
              updateTextObject({ font: nextFont });
            }}
            className="h-8 rounded-md border border-neutral-700 bg-neutral-950 px-2 text-xs text-neutral-100 outline-none transition-colors focus:border-violet-500"
          >
            <option value="Inter">Inter</option>
            <option value="Arial">Arial</option>
            <option value="Georgia">Georgia</option>
            <option value="Impact">Impact</option>
          </select>
        </label>
        <label className="flex items-center gap-2 text-xs text-neutral-400">
          Size
          <input
            type="number"
            min={12}
            max={220}
            value={activeTextObject?.size ?? textSize}
            onChange={(event) => {
              const nextSize = Number(event.target.value);
              setTextSize(nextSize);
              updateTextObject({ size: nextSize });
            }}
            className="h-8 w-16 rounded-md border border-neutral-700 bg-neutral-950 px-2 text-xs text-neutral-100 outline-none focus:border-violet-500"
          />
        </label>
        <button type="button" onClick={addTextCenter} disabled={!loaded} className="inline-flex items-center gap-1.5 rounded-md border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs font-medium text-neutral-200 transition-colors hover:bg-neutral-700 disabled:opacity-50">
          <Type className="h-3.5 w-3.5" />
          Add text
        </button>
      </div>

      <div className="relative min-h-0 flex-1 overflow-auto bg-[radial-gradient(circle_at_center,rgba(64,64,64,0.35)_1px,transparent_1px)] [background-size:18px_18px] p-4">
        {loadError ? (
          <div className="mb-3 rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200" role="alert">
            {loadError}
          </div>
        ) : null}
        <div className="relative mx-auto w-full max-w-5xl">
          <canvas
            ref={canvasRef}
            aria-label="Image review canvas"
            className="block aspect-video w-full rounded-md bg-neutral-900 shadow-2xl shadow-black/50"
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onPointerCancel={handlePointerUp}
          />
          <canvas
            ref={overlayRef}
            className="pointer-events-none absolute inset-0 h-full w-full rounded-md"
            aria-hidden="true"
          />
        </div>
      </div>
    </div>
  );
}
