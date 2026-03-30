import { useEffect, useState } from "react";
import api from "../../api";
import { showToast } from "../ToastContainer";

interface KeyInfo {
  configured: boolean;
  masked: string;
  source: "db" | "env" | "none";
}

const IMAGE_PROVIDERS = [
  { value: "google", label: "Google Gemini" },
  { value: "replicate", label: "Replicate (Flux)" },
] as const;

const OUTPUT_FORMATS = [
  { value: "png", label: "PNG" },
  { value: "webp", label: "WebP" },
  { value: "jpg", label: "JPEG" },
] as const;

const SAFETY_LEVELS = [
  { value: "1", label: "1 — Strictest" },
  { value: "2", label: "2 — Strict (default)" },
  { value: "3", label: "3 — Moderate" },
  { value: "4", label: "4 — Permissive" },
  { value: "5", label: "5 — Most permissive" },
] as const;

const REPLICATE_MODELS = [
  { value: "black-forest-labs/flux-1.1-pro", label: "Flux 1.1 Pro", description: "Fast, high-quality generation" },
  { value: "black-forest-labs/flux-1.1-pro-ultra", label: "Flux 1.1 Pro Ultra", description: "Highest quality, up to 4MP resolution" },
  { value: "black-forest-labs/flux-pro", label: "Flux Pro", description: "Original pro model" },
  { value: "black-forest-labs/flux-dev", label: "Flux Dev", description: "Open-weight, lower cost" },
  { value: "black-forest-labs/flux-schnell", label: "Flux Schnell", description: "Fastest, lowest cost" },
] as const;

export default function GeneralSection() {
  const [downloadsDir, setDownloadsDir] = useState("");
  const [imageProvider, setImageProvider] = useState("google");
  const [promptUpsampling, setPromptUpsampling] = useState("true");
  const [replicateModel, setReplicateModel] = useState("black-forest-labs/flux-1.1-pro");
  const [safetyTolerance, setSafetyTolerance] = useState("2");
  const [outputFormat, setOutputFormat] = useState("png");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [originalDownloads, setOriginalDownloads] = useState("");
  const [originalProvider, setOriginalProvider] = useState("google");
  const [originalUpsampling, setOriginalUpsampling] = useState("true");
  const [originalModel, setOriginalModel] = useState("black-forest-labs/flux-1.1-pro");
  const [originalSafety, setOriginalSafety] = useState("2");
  const [originalFormat, setOriginalFormat] = useState("png");

  useEffect(() => {
    api.get("/api/settings/keys").then((res) => {
      if (res.ok) {
        const data = res.data as Record<string, KeyInfo>;
        const dlVal = data.DOWNLOADS_DIR?.masked ?? "";
        setDownloadsDir(dlVal);
        setOriginalDownloads(dlVal);
        const provVal = data.IMAGE_PROVIDER?.masked || "google";
        setImageProvider(provVal);
        setOriginalProvider(provVal);
        const upVal = data.REPLICATE_PROMPT_UPSAMPLING?.masked || "true";
        setPromptUpsampling(upVal);
        setOriginalUpsampling(upVal);
        const modVal = data.REPLICATE_MODEL?.masked || "black-forest-labs/flux-1.1-pro";
        setReplicateModel(modVal);
        setOriginalModel(modVal);
        const safVal = data.REPLICATE_SAFETY_TOLERANCE?.masked || "2";
        setSafetyTolerance(safVal);
        setOriginalSafety(safVal);
        const fmtVal = data.REPLICATE_OUTPUT_FORMAT?.masked || "png";
        setOutputFormat(fmtVal);
        setOriginalFormat(fmtVal);
      }
      setLoading(false);
    });
  }, []);

  const handleSave = async () => {
    setSaving(true);
    const res = await api.put("/api/settings/keys", {
      DOWNLOADS_DIR: downloadsDir.trim(),
      IMAGE_PROVIDER: imageProvider,
      REPLICATE_MODEL: replicateModel,
      REPLICATE_PROMPT_UPSAMPLING: promptUpsampling,
      REPLICATE_SAFETY_TOLERANCE: safetyTolerance,
      REPLICATE_OUTPUT_FORMAT: outputFormat,
    });
    setSaving(false);

    if (res.ok) {
      showToast("Settings saved", "success");
      setOriginalDownloads(downloadsDir.trim());
      setOriginalProvider(imageProvider);
      setOriginalModel(replicateModel);
      setOriginalUpsampling(promptUpsampling);
      setOriginalSafety(safetyTolerance);
      setOriginalFormat(outputFormat);
    }
  };

  const hasChanges =
    downloadsDir.trim() !== originalDownloads ||
    imageProvider !== originalProvider ||
    replicateModel !== originalModel ||
    promptUpsampling !== originalUpsampling ||
    safetyTolerance !== originalSafety ||
    outputFormat !== originalFormat;

  return (
    <div className="px-8 py-8 max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">General</h2>
          <p className="text-neutral-400 text-sm mt-1">
            App-wide preferences.
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving || !hasChanges}
          className="px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition-colors"
        >
          {saving ? "Saving..." : "Save"}
        </button>
      </div>

      {loading ? (
        <div className="text-neutral-500 text-sm">Loading...</div>
      ) : (
        <div className="space-y-6">
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-5 space-y-2">
            <div>
              <h3 className="text-sm font-medium text-neutral-100">Downloads Directory</h3>
              <p className="text-xs text-neutral-500">
                Rendered videos, audio, and thumbnails are copied here for easy access.
              </p>
            </div>
            <input
              type="text"
              value={downloadsDir}
              onChange={(e) => setDownloadsDir(e.target.value)}
              placeholder="~/Downloads"
              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:border-violet-500 transition-colors font-mono"
            />
          </div>

          <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-5 space-y-2">
            <div>
              <h3 className="text-sm font-medium text-neutral-100">Image Provider</h3>
              <p className="text-xs text-neutral-500">
                Choose which AI service generates scene images and thumbnails.
              </p>
            </div>
            <select
              value={imageProvider}
              onChange={(e) => setImageProvider(e.target.value)}
              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 transition-colors"
            >
              {IMAGE_PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>

          {imageProvider === "replicate" && (
            <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-5 space-y-5">
              <div>
                <h3 className="text-sm font-medium text-neutral-100">Replicate Settings</h3>
                <p className="text-xs text-neutral-500">
                  Fine-tune Flux image generation parameters.
                </p>
              </div>

              <div className="space-y-1.5">
                <label className="text-sm text-neutral-200">Model</label>
                <p className="text-xs text-neutral-500">
                  Which Flux model to use for image generation.
                </p>
                <select
                  value={replicateModel}
                  onChange={(e) => setReplicateModel(e.target.value)}
                  className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 transition-colors"
                >
                  {REPLICATE_MODELS.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label} — {m.description}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-sm text-neutral-200">Prompt Upsampling</label>
                    <p className="text-xs text-neutral-500">
                      Enhances your prompt with an LLM for better results.
                    </p>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={promptUpsampling === "true"}
                    onClick={() =>
                      setPromptUpsampling(promptUpsampling === "true" ? "false" : "true")
                    }
                    className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
                      promptUpsampling === "true" ? "bg-violet-600" : "bg-neutral-700"
                    }`}
                  >
                    <span
                      className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${
                        promptUpsampling === "true" ? "translate-x-5" : "translate-x-0"
                      }`}
                    />
                  </button>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-sm text-neutral-200">Safety Tolerance</label>
                <p className="text-xs text-neutral-500">
                  Content filter strictness. Higher values are more permissive.
                </p>
                <select
                  value={safetyTolerance}
                  onChange={(e) => setSafetyTolerance(e.target.value)}
                  className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 transition-colors"
                >
                  {SAFETY_LEVELS.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-sm text-neutral-200">Output Format</label>
                <p className="text-xs text-neutral-500">
                  Image format returned by Flux.
                </p>
                <select
                  value={outputFormat}
                  onChange={(e) => setOutputFormat(e.target.value)}
                  className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 transition-colors"
                >
                  {OUTPUT_FORMATS.map((f) => (
                    <option key={f.value} value={f.value}>
                      {f.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
