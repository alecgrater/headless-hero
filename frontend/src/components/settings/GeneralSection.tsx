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
  { value: "google", label: "Gemini - Gemini" },
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

export const SCRIPT_MODELS = [
  { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4" },
  { value: "anthropic.claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
  { value: "anthropic.claude-opus-4-6-v1", label: "Claude Opus 4.6" },
  { value: "anthropic.claude-sonnet-4-5-20250929-v1:0", label: "Claude Sonnet 4.5" },
  { value: "anthropic.claude-haiku-4-5-20251001-v1:0", label: "Claude Haiku 4.5" },
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
  const [rateLimitEnabled, setRateLimitEnabled] = useState("true");
  const [scriptModel, setScriptModel] = useState("claude-sonnet-4-20250514");
  const [originalDownloads, setOriginalDownloads] = useState("");
  const [originalProvider, setOriginalProvider] = useState("google");
  const [originalUpsampling, setOriginalUpsampling] = useState("true");
  const [originalModel, setOriginalModel] = useState("black-forest-labs/flux-1.1-pro");
  const [originalSafety, setOriginalSafety] = useState("2");
  const [originalFormat, setOriginalFormat] = useState("png");
  const [originalRateLimit, setOriginalRateLimit] = useState("true");
  const [originalScriptModel, setOriginalScriptModel] = useState("claude-sonnet-4-20250514");

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
        const rlVal = data.IMAGE_RATE_LIMIT_MS?.masked || "true";
        setRateLimitEnabled(rlVal === "0" || rlVal === "false" ? "false" : "true");
        setOriginalRateLimit(rlVal === "0" || rlVal === "false" ? "false" : "true");
        const smVal = data.SCRIPT_MODEL?.masked || "claude-sonnet-4-20250514";
        setScriptModel(smVal);
        setOriginalScriptModel(smVal);
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
      IMAGE_RATE_LIMIT_MS: rateLimitEnabled === "true" ? "10000" : "0",
      SCRIPT_MODEL: scriptModel,
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
      setOriginalRateLimit(rateLimitEnabled);
      setOriginalScriptModel(scriptModel);
    }
  };

  const hasChanges =
    downloadsDir.trim() !== originalDownloads ||
    imageProvider !== originalProvider ||
    replicateModel !== originalModel ||
    promptUpsampling !== originalUpsampling ||
    safetyTolerance !== originalSafety ||
    outputFormat !== originalFormat ||
    rateLimitEnabled !== originalRateLimit ||
    scriptModel !== originalScriptModel;

  return (
    <div className="px-8 py-8 max-w-2xl space-y-6 pb-24">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">General</h2>
        <p className="text-neutral-400 text-sm mt-1">
          App-wide preferences.
        </p>
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

          <div className="bg-neutral-900 border border-neutral-800 rounded-xl divide-y divide-neutral-800">
            <div className="p-5 space-y-2">
              <div>
                <h3 className="text-sm font-medium text-neutral-100">Script Generation Model</h3>
                <p className="text-xs text-neutral-500">
                  Which Claude model to use for generating video scripts.
                </p>
              </div>
              <select
                value={scriptModel}
                onChange={(e) => setScriptModel(e.target.value)}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 transition-colors"
              >
                {SCRIPT_MODELS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="p-5 space-y-2">
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

            <div className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-neutral-100">Image Rate Limit</h3>
                  <p className="text-xs text-neutral-500">
                    Throttle batch image generation to ~6 requests/min to stay under free-tier API limits.
                  </p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={rateLimitEnabled === "true"}
                  onClick={() =>
                    setRateLimitEnabled(rateLimitEnabled === "true" ? "false" : "true")
                  }
                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
                    rateLimitEnabled === "true" ? "bg-violet-600 shadow-sm shadow-violet-500/30" : "bg-neutral-700"
                  }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${
                      rateLimitEnabled === "true" ? "translate-x-5" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>
            </div>
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

      {/* Sticky save bar */}
      {hasChanges && (
        <div className="fixed bottom-0 left-0 right-0 z-40 border-t border-neutral-800 bg-neutral-900/95 backdrop-blur-sm px-8 py-3">
          <div className="max-w-2xl mx-auto flex items-center justify-between">
            <span className="text-sm text-neutral-400">You have unsaved changes</span>
            <button
              onClick={handleSave}
              disabled={saving}
              className="btn-primary px-5 py-2 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
