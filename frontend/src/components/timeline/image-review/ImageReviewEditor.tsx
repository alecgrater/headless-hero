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

import { assetUrl } from "../../../api";
import type { ImageReviewAsset } from "../../../types/imageReview";
import { Tooltip } from "../../ui/Tooltip";

type ToolMode = "select" | "erase" | "text";

interface Selection {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface Props {
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

export default function ImageReviewEditor({ asset, saving, resetting, onSave, onReset }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const overlayRef = useRef<HTMLCanvasElement | null>(null);
  const drawingRef = useRef(false);
  const dragStartRef = useRef<{ x: number; y: number } | null>(null);
  const copiedRef = useRef<ImageData | null>(null);
  const [tool, setTool] = useState<ToolMode>("select");
  const [selection, setSelection] = useState<Selection | null>(null);
  const [brushSize, setBrushSize] = useState(32);
  const [text, setText] = useState("Text");
  const [textSize, setTextSize] = useState(72);
  const [textColor, setTextColor] = useState("#111111");
  const [history, setHistory] = useState<string[]>([]);
  const [future, setFuture] = useState<string[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [hasCopiedSelection, setHasCopiedSelection] = useState(false);

  const dimensionsLabel = useMemo(() => {
    if (!asset.width || !asset.height) return "dimensions unknown";
    return `${asset.width} x ${asset.height}`;
  }, [asset.height, asset.width]);

  const canvasPoint = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) / rect.width) * canvas.width,
      y: ((event.clientY - rect.top) / rect.height) * canvas.height,
    };
  };

  const drawOverlay = useCallback((nextSelection: Selection | null) => {
    const overlay = overlayRef.current;
    const canvas = canvasRef.current;
    if (!overlay || !canvas) return;
    overlay.width = canvas.width;
    overlay.height = canvas.height;
    const ctx = overlay.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    if (!nextSelection) return;
    const normalized = normalizeSelection(nextSelection);
    ctx.save();
    ctx.setLineDash([12, 8]);
    ctx.lineWidth = Math.max(2, canvas.width / 700);
    ctx.strokeStyle = "#A78BFA";
    ctx.fillStyle = "rgba(167, 139, 250, 0.12)";
    ctx.fillRect(normalized.x, normalized.y, normalized.width, normalized.height);
    ctx.strokeRect(normalized.x, normalized.y, normalized.width, normalized.height);
    ctx.restore();
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
      drawOverlay(null);
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
    setHistory([]);
    setFuture([]);
    copiedRef.current = null;
    setHasCopiedSelection(false);

    const drawFallback = () => {
      if (cancelled) return;
      canvas.width = asset.width || 1920;
      canvas.height = asset.height || 1080;
      ctx.fillStyle = "#171717";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      setLoaded(true);
      drawOverlay(null);
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
        drawOverlay(null);
      };
      image.onerror = drawFallback;
      image.src = objectUrlValue;
    };

    const loadImage = async () => {
      try {
        const response = await fetch(assetUrl(asset.current_url));
        if (!response.ok) {
          drawFallback();
          return;
        }
        const blob = await response.blob();
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
            drawOverlay(null);
            return;
          }
        }
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        drawImageElement(objectUrl);
      } catch {
        drawFallback();
      }
    };

    void loadImage();

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [asset.current_url, asset.height, asset.width, drawOverlay]);

  useEffect(() => {
    drawOverlay(selection);
  }, [drawOverlay, selection]);

  const handlePointerDown = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!loaded) return;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const point = canvasPoint(event);
    drawingRef.current = true;
    dragStartRef.current = point;
    event.currentTarget.setPointerCapture(event.pointerId);
    if (tool === "select") {
      const nextSelection = { x: point.x, y: point.y, width: 0, height: 0 };
      setSelection(nextSelection);
      drawOverlay(nextSelection);
    } else if (tool === "erase") {
      pushHistory();
      ctx.clearRect(point.x - brushSize / 2, point.y - brushSize / 2, brushSize, brushSize);
    } else if (tool === "text") {
      pushHistory();
      ctx.save();
      ctx.font = `700 ${textSize}px Inter, Arial, sans-serif`;
      ctx.fillStyle = textColor;
      ctx.textBaseline = "middle";
      ctx.fillText(text, point.x, point.y);
      ctx.restore();
    }
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawingRef.current || !dragStartRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const point = canvasPoint(event);
    if (tool === "select") {
      const start = dragStartRef.current;
      const nextSelection = {
        x: start.x,
        y: start.y,
        width: point.x - start.x,
        height: point.y - start.y,
      };
      setSelection(nextSelection);
      drawOverlay(nextSelection);
    } else if (tool === "erase") {
      ctx.clearRect(point.x - brushSize / 2, point.y - brushSize / 2, brushSize, brushSize);
    }
  };

  const handlePointerUp = (event: React.PointerEvent<HTMLCanvasElement>) => {
    drawingRef.current = false;
    dragStartRef.current = null;
    event.currentTarget.releasePointerCapture(event.pointerId);
  };

  const selectAll = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
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
    const ctx = canvas?.getContext("2d");
    const copied = copiedRef.current;
    if (!canvas || !ctx || !copied) return;
    pushHistory();
    const base = selection ? normalizeSelection(selection) : { x: 0, y: 0, width: copied.width, height: copied.height };
    const x = Math.min(Math.max(0, base.x + 32), Math.max(0, canvas.width - copied.width));
    const y = Math.min(Math.max(0, base.y + 32), Math.max(0, canvas.height - copied.height));
    ctx.putImageData(copied, x, y);
    setSelection({ x, y, width: copied.width, height: copied.height });
  };

  const addTextCenter = () => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx || !text.trim()) return;
    pushHistory();
    ctx.save();
    ctx.font = `700 ${textSize}px Inter, Arial, sans-serif`;
    ctx.fillStyle = textColor;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text.trim(), canvas.width / 2, canvas.height / 2);
    ctx.restore();
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

  const handleSave = () => {
    const canvas = canvasRef.current;
    if (!canvas || !loaded) return;
    onSave(canvas.toDataURL("image/png"));
  };

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
          <Tooltip content="Selection tool">
            <button type="button" aria-label="Selection tool" onClick={() => setTool("select")} className={buttonClass(tool === "select")}>
              <SquareDashedMousePointer className="h-4 w-4" />
            </button>
          </Tooltip>
          <Tooltip content="Eraser">
            <button type="button" aria-label="Eraser tool" onClick={() => setTool("erase")} className={buttonClass(tool === "erase")}>
              <Eraser className="h-4 w-4" />
            </button>
          </Tooltip>
          <Tooltip content="Text tool">
            <button type="button" aria-label="Text tool" onClick={() => setTool("text")} className={buttonClass(tool === "text")}>
              <Type className="h-4 w-4" />
            </button>
          </Tooltip>
          <span className="mx-1 h-6 w-px bg-neutral-800" />
          <Tooltip content="Undo">
            <button type="button" aria-label="Undo" onClick={undo} disabled={history.length === 0} className={buttonClass()}>
              <Undo2 className="h-4 w-4" />
            </button>
          </Tooltip>
          <Tooltip content="Redo">
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
        <button type="button" onClick={selectAll} className="inline-flex items-center gap-1.5 rounded-md border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs font-medium text-neutral-200 transition-colors hover:bg-neutral-700">
          <MousePointer2 className="h-3.5 w-3.5" />
          Select all
        </button>
        <button type="button" onClick={copySelection} disabled={!selection} className="inline-flex items-center gap-1.5 rounded-md border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs font-medium text-neutral-200 transition-colors hover:bg-neutral-700 disabled:opacity-50">
          <Copy className="h-3.5 w-3.5" />
          Copy selection
        </button>
        <button type="button" onClick={pasteSelection} disabled={!hasCopiedSelection} className="inline-flex items-center gap-1.5 rounded-md border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs font-medium text-neutral-200 transition-colors hover:bg-neutral-700 disabled:opacity-50">
          <Clipboard className="h-3.5 w-3.5" />
          Paste selection
        </button>
        <button type="button" onClick={deleteSelection} disabled={!selection} className="inline-flex items-center gap-1.5 rounded-md border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs font-medium text-neutral-200 transition-colors hover:bg-neutral-700 disabled:opacity-50">
          <Scissors className="h-3.5 w-3.5" />
          Delete selection
        </button>
        <label className="ml-1 flex items-center gap-2 text-xs text-neutral-400">
          Brush
          <input type="range" min={8} max={120} value={brushSize} onChange={(event) => setBrushSize(Number(event.target.value))} className="w-24 accent-violet-500" />
        </label>
        <label className="flex items-center gap-2 text-xs text-neutral-400">
          Text
          <input value={text} onChange={(event) => setText(event.target.value)} className="h-8 w-36 rounded-md border border-neutral-700 bg-neutral-950 px-2 text-xs text-neutral-100 outline-none focus:border-violet-500" />
        </label>
        <input aria-label="Text color" type="color" value={textColor} onChange={(event) => setTextColor(event.target.value)} className="h-8 w-9 rounded border border-neutral-700 bg-neutral-950 p-1" />
        <label className="flex items-center gap-2 text-xs text-neutral-400">
          Size
          <input type="number" min={12} max={220} value={textSize} onChange={(event) => setTextSize(Number(event.target.value))} className="h-8 w-16 rounded-md border border-neutral-700 bg-neutral-950 px-2 text-xs text-neutral-100 outline-none focus:border-violet-500" />
        </label>
        <button type="button" onClick={addTextCenter} className="inline-flex items-center gap-1.5 rounded-md border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs font-medium text-neutral-200 transition-colors hover:bg-neutral-700">
          <Type className="h-3.5 w-3.5" />
          Add text
        </button>
      </div>

      <div className="relative min-h-0 flex-1 overflow-auto bg-[radial-gradient(circle_at_center,rgba(64,64,64,0.35)_1px,transparent_1px)] [background-size:18px_18px] p-4">
        <div className="relative mx-auto w-full max-w-5xl">
          <canvas
            ref={canvasRef}
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
