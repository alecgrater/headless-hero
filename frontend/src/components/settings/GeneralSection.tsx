import { useEffect, useState } from "react";
import api from "../../api";
import { DEFAULT_MODEL } from "../../constants";
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

const LLM_PROVIDERS = [
  { value: "ollama", label: "Ollama (local)", description: "Local Qwen3 via Ollama" },
  { value: "anthropic", label: "Anthropic API", description: "Real Claude API (requires ANTHROPIC_API_KEY)" },
  { value: "openai", label: "OpenAI API", description: "OpenAI models (requires OPENAI_API_KEY)" },
  { value: "claude-code-proxy", label: "Claude Code Proxy", description: "Apple Claude Code proxy on localhost:11211" },
] as const;

type LlmProvider = (typeof LLM_PROVIDERS)[number]["value"];

interface LlmTaskConfig {
  id: string;
  label: string;
  description: string;
  providerKey: string;
  modelKey: string;
  defaultModel: string;
  openaiDefaultModel: string;
  ollamaDefaultModel: string;
}

interface TaskRoute {
  provider: "" | LlmProvider;
  model: string;
}

const LLM_TASKS: LlmTaskConfig[] = [
  {
    id: "script",
    label: "Script & cold opens",
    description: "Full scripts, segmented generation, scene rewrites, cold-open variants, narration tightening.",
    providerKey: "SCRIPT_LLM_PROVIDER",
    modelKey: "SCRIPT_MODEL",
    defaultModel: DEFAULT_MODEL,
    openaiDefaultModel: "gpt-5.2",
    ollamaDefaultModel: "qwen3:14b",
  },
  {
    id: "idea",
    label: "Ideas & brainstorming",
    description: "Niche ideas, smart ideas, and brainstorming recommendations.",
    providerKey: "IDEA_LLM_PROVIDER",
    modelKey: "IDEA_MODEL",
    defaultModel: "anthropic.claude-sonnet-4-6",
    openaiDefaultModel: "gpt-5-mini",
    ollamaDefaultModel: "qwen3:14b",
  },
  {
    id: "fx",
    label: "FX assignment",
    description: "Scene FX, transitions, and visual timing suggestions.",
    providerKey: "FX_LLM_PROVIDER",
    modelKey: "FX_MODEL",
    defaultModel: "anthropic.claude-sonnet-4-6",
    openaiDefaultModel: "gpt-5-mini",
    ollamaDefaultModel: "qwen3:14b",
  },
  {
    id: "seo",
    label: "SEO metadata",
    description: "YouTube titles, descriptions, tags, and chapter-aware metadata.",
    providerKey: "SEO_LLM_PROVIDER",
    modelKey: "SEO_MODEL",
    defaultModel: "anthropic.claude-sonnet-4-6",
    openaiDefaultModel: "gpt-5-mini",
    ollamaDefaultModel: "qwen3:14b",
  },
  {
    id: "hook",
    label: "Hook scoring/refining",
    description: "Retention scoring and hook rewrite suggestions.",
    providerKey: "HOOK_LLM_PROVIDER",
    modelKey: "HOOK_MODEL",
    defaultModel: "anthropic.claude-haiku-4-5-20251001-v1:0",
    openaiDefaultModel: "gpt-5-nano",
    ollamaDefaultModel: "qwen3:14b",
  },
  {
    id: "media",
    label: "Media routing",
    description: "Post-script routing between AI visuals, stock photos, and gameplay clips.",
    providerKey: "MEDIA_LLM_PROVIDER",
    modelKey: "MEDIA_MODEL",
    defaultModel: "anthropic.claude-sonnet-4-6",
    openaiDefaultModel: "gpt-5-mini",
    ollamaDefaultModel: "qwen3:14b",
  },
  {
    id: "eli",
    label: "Eli animation",
    description: "Eli pose and placement selection for scenes.",
    providerKey: "ELI_LLM_PROVIDER",
    modelKey: "ELI_MODEL",
    defaultModel: "anthropic.claude-haiku-4-5-20251001-v1:0",
    openaiDefaultModel: "gpt-5-nano",
    ollamaDefaultModel: "qwen3:14b",
  },
  {
    id: "analysis",
    label: "Analysis & scoring",
    description: "Trend format-fit scoring, content profiles, and recording quality analysis.",
    providerKey: "ANALYSIS_LLM_PROVIDER",
    modelKey: "ANALYSIS_MODEL",
    defaultModel: "anthropic.claude-haiku-4-5-20251001-v1:0",
    openaiDefaultModel: "gpt-5-nano",
    ollamaDefaultModel: "qwen3:14b",
  },
];

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
  { value: DEFAULT_MODEL, label: "Claude Opus 4.6" },
  { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4" },
  { value: "anthropic.claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
  { value: "anthropic.claude-sonnet-4-5-20250929-v1:0", label: "Claude Sonnet 4.5" },
  { value: "anthropic.claude-haiku-4-5-20251001-v1:0", label: "Claude Haiku 4.5" },
  { value: "gpt-5.2", label: "OpenAI GPT-5.2" },
  { value: "gpt-5-mini", label: "OpenAI GPT-5 Mini" },
  { value: "gpt-5-nano", label: "OpenAI GPT-5 Nano" },
] as const;

const MODEL_SUGGESTIONS = [
  ...SCRIPT_MODELS,
  { value: "qwen3:14b", label: "Qwen3 14B (Ollama)" },
  { value: "qwen3:8b", label: "Qwen3 8B (Ollama)" },
] as const;

export default function GeneralSection() {
  const [downloadsDir, setDownloadsDir] = useState("");
  const [exportFolder, setExportFolder] = useState("");
  const [imageProvider, setImageProvider] = useState("google");
  const [promptUpsampling, setPromptUpsampling] = useState("true");
  const [replicateModel, setReplicateModel] = useState("black-forest-labs/flux-1.1-pro");
  const [safetyTolerance, setSafetyTolerance] = useState("2");
  const [outputFormat, setOutputFormat] = useState("png");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [rateLimitEnabled, setRateLimitEnabled] = useState("true");
  const [llmProvider, setLlmProvider] = useState<LlmProvider>("ollama");
  const [qwenModel, setQwenModel] = useState("qwen3:14b");
  const [anthropicKeyConfigured, setAnthropicKeyConfigured] = useState(false);
  const [openaiKeyConfigured, setOpenaiKeyConfigured] = useState(false);
  const [taskRoutes, setTaskRoutes] = useState<Record<string, TaskRoute>>(() =>
    Object.fromEntries(LLM_TASKS.map((task) => [task.id, { provider: "", model: task.defaultModel }]))
  );
  const [originalDownloads, setOriginalDownloads] = useState("");
  const [originalExportFolder, setOriginalExportFolder] = useState("");
  const [originalProvider, setOriginalProvider] = useState("google");
  const [originalUpsampling, setOriginalUpsampling] = useState("true");
  const [originalModel, setOriginalModel] = useState("black-forest-labs/flux-1.1-pro");
  const [originalSafety, setOriginalSafety] = useState("2");
  const [originalFormat, setOriginalFormat] = useState("png");
  const [originalRateLimit, setOriginalRateLimit] = useState("true");
  const [originalLlmProvider, setOriginalLlmProvider] = useState<LlmProvider>("ollama");
  const [originalQwenModel, setOriginalQwenModel] = useState("qwen3:14b");
  const [originalTaskRoutes, setOriginalTaskRoutes] = useState<Record<string, TaskRoute>>(() =>
    Object.fromEntries(LLM_TASKS.map((task) => [task.id, { provider: "", model: task.defaultModel }]))
  );

  useEffect(() => {
    api.get("/api/settings/keys").then((res) => {
      if (res.ok) {
        const data = res.data as Record<string, KeyInfo>;
        const dlVal = data.DOWNLOADS_DIR?.masked ?? "";
        setDownloadsDir(dlVal);
        setOriginalDownloads(dlVal);
        const efVal = data.EXPORT_FOLDER?.masked ?? "";
        setExportFolder(efVal);
        setOriginalExportFolder(efVal);
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
        const llmVal = (data.LLM_PROVIDER?.masked || "ollama") as LlmProvider;
        setLlmProvider(llmVal);
        setOriginalLlmProvider(llmVal);
        const qwVal = data.QWEN_MODEL?.masked || "qwen3:14b";
        setQwenModel(qwVal);
        setOriginalQwenModel(qwVal);
        setAnthropicKeyConfigured(!!data.ANTHROPIC_API_KEY?.configured);
        setOpenaiKeyConfigured(!!data.OPENAI_API_KEY?.configured);
        const routes = Object.fromEntries(
          LLM_TASKS.map((task) => [
            task.id,
            {
              provider: (data[task.providerKey]?.masked || "") as TaskRoute["provider"],
              model: data[task.modelKey]?.masked || task.defaultModel,
            },
          ]),
        );
        setTaskRoutes(routes);
        setOriginalTaskRoutes(routes);
      }
      setLoading(false);
    });
  }, []);

  const handleSave = async () => {
    setSaving(true);
    const routePayload = Object.fromEntries(
      LLM_TASKS.flatMap((task) => {
        const route = taskRoutes[task.id] ?? { provider: "", model: task.defaultModel };
        return [
          [task.providerKey, route.provider],
          [task.modelKey, route.model.trim() || task.defaultModel],
        ];
      }),
    );
    const res = await api.put("/api/settings/keys", {
      DOWNLOADS_DIR: downloadsDir.trim(),
      EXPORT_FOLDER: exportFolder.trim(),
      IMAGE_PROVIDER: imageProvider,
      REPLICATE_MODEL: replicateModel,
      REPLICATE_PROMPT_UPSAMPLING: promptUpsampling,
      REPLICATE_SAFETY_TOLERANCE: safetyTolerance,
      REPLICATE_OUTPUT_FORMAT: outputFormat,
      IMAGE_RATE_LIMIT_MS: rateLimitEnabled === "true" ? "10000" : "0",
      LLM_PROVIDER: llmProvider,
      QWEN_MODEL: qwenModel.trim() || "qwen3:14b",
      ...routePayload,
    });
    setSaving(false);

    if (res.ok) {
      showToast("Settings saved", "success");
      setOriginalDownloads(downloadsDir.trim());
      setOriginalExportFolder(exportFolder.trim());
      setOriginalProvider(imageProvider);
      setOriginalModel(replicateModel);
      setOriginalUpsampling(promptUpsampling);
      setOriginalSafety(safetyTolerance);
      setOriginalFormat(outputFormat);
      setOriginalRateLimit(rateLimitEnabled);
      setOriginalLlmProvider(llmProvider);
      setOriginalQwenModel(qwenModel.trim() || "qwen3:14b");
      setOriginalTaskRoutes(
        Object.fromEntries(
          LLM_TASKS.map((task) => {
            const route = taskRoutes[task.id] ?? { provider: "", model: task.defaultModel };
            return [task.id, { provider: route.provider, model: route.model.trim() || task.defaultModel }];
          }),
        ),
      );
    }
  };

  const updateTaskRoute = (taskId: string, updates: Partial<TaskRoute>) => {
    setTaskRoutes((prev) => ({
      ...prev,
      [taskId]: {
        ...(prev[taskId] ?? { provider: "", model: LLM_TASKS.find((task) => task.id === taskId)?.defaultModel ?? DEFAULT_MODEL }),
        ...updates,
      },
    }));
  };

  const defaultModelForProvider = (task: LlmTaskConfig, provider: TaskRoute["provider"]) => {
    const effectiveProvider = provider || llmProvider;
    if (effectiveProvider === "openai") return task.openaiDefaultModel;
    if (effectiveProvider === "ollama") return task.ollamaDefaultModel;
    return task.defaultModel;
  };

  const handleTaskProviderChange = (task: LlmTaskConfig, provider: TaskRoute["provider"]) => {
    const current = taskRoutes[task.id] ?? { provider: "", model: task.defaultModel };
    const knownDefaults = new Set([task.defaultModel, task.openaiDefaultModel, task.ollamaDefaultModel, ""]);
    updateTaskRoute(task.id, {
      provider,
      model: knownDefaults.has(current.model) ? defaultModelForProvider(task, provider) : current.model,
    });
  };

  const modelForGlobalProvider = (task: LlmTaskConfig, provider: LlmProvider) => {
    if (provider === "openai") return task.openaiDefaultModel;
    if (provider === "ollama") return task.ollamaDefaultModel;
    return task.defaultModel;
  };

  const handleDefaultProviderChange = (provider: LlmProvider) => {
    setLlmProvider(provider);
    setTaskRoutes((prev) =>
      Object.fromEntries(
        LLM_TASKS.map((task) => {
          const current = prev[task.id] ?? { provider: "", model: task.defaultModel };
          const knownDefaults = new Set([task.defaultModel, task.openaiDefaultModel, task.ollamaDefaultModel, ""]);
          return [
            task.id,
            current.provider === "" && knownDefaults.has(current.model)
              ? { ...current, model: modelForGlobalProvider(task, provider) }
              : current,
          ];
        }),
      ),
    );
  };

  const routeChanged = LLM_TASKS.some((task) => {
    const current = taskRoutes[task.id] ?? { provider: "", model: task.defaultModel };
    const original = originalTaskRoutes[task.id] ?? { provider: "", model: task.defaultModel };
    return current.provider !== original.provider || current.model.trim() !== original.model;
  });

  const hasChanges =
    downloadsDir.trim() !== originalDownloads ||
    exportFolder.trim() !== originalExportFolder ||
    imageProvider !== originalProvider ||
    replicateModel !== originalModel ||
    promptUpsampling !== originalUpsampling ||
    safetyTolerance !== originalSafety ||
    outputFormat !== originalFormat ||
    rateLimitEnabled !== originalRateLimit ||
    llmProvider !== originalLlmProvider ||
    qwenModel.trim() !== originalQwenModel ||
    routeChanged;

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
            <div className="flex gap-2">
              <input
                type="text"
                value={downloadsDir}
                onChange={(e) => setDownloadsDir(e.target.value)}
                placeholder="~/Downloads"
                className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:border-violet-500 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors font-mono"
              />
              {window.api?.selectFolder && (
                <button
                  type="button"
                  onClick={async () => {
                    const result = await window.api.selectFolder!("Select Downloads Directory", downloadsDir || undefined);
                    if (!result.canceled && result.path) setDownloadsDir(result.path);
                  }}
                  className="px-3 py-2 bg-neutral-800 border border-neutral-700 rounded-lg text-sm text-neutral-300 hover:text-neutral-100 hover:border-neutral-600 transition-colors whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950"
                >
                  Browse…
                </button>
              )}
            </div>
          </div>

          <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-5 space-y-2">
            <div>
              <h3 className="text-sm font-medium text-neutral-100">Export Folder</h3>
              <p className="text-xs text-neutral-500">
                Where "Export All" bundles are saved. Defaults to iCloud headless-hero media/Videos.
              </p>
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={exportFolder}
                onChange={(e) => setExportFolder(e.target.value)}
                placeholder="~/Library/Mobile Documents/.../headless-hero media/Videos"
                className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:border-violet-500 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors font-mono"
              />
              {window.api?.selectFolder && (
                <button
                  type="button"
                  onClick={async () => {
                    const result = await window.api.selectFolder!("Select Export Folder", exportFolder || undefined);
                    if (!result.canceled && result.path) setExportFolder(result.path);
                  }}
                  className="px-3 py-2 bg-neutral-800 border border-neutral-700 rounded-lg text-sm text-neutral-300 hover:text-neutral-100 hover:border-neutral-600 transition-colors whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950"
                >
                  Browse…
                </button>
              )}
            </div>
          </div>

          <div className="bg-neutral-900 border border-neutral-800 rounded-xl divide-y divide-neutral-800">
            <div className="p-5 space-y-2">
              <div>
                <h3 className="text-sm font-medium text-neutral-100">Default LLM Provider</h3>
                <p className="text-xs text-neutral-500">
                  The fallback route for any LLM task that does not override its provider below.
                </p>
              </div>
              <select
                value={llmProvider}
                onChange={(e) => handleDefaultProviderChange(e.target.value as LlmProvider)}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors"
              >
                {LLM_PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label} — {p.description}
                  </option>
                ))}
              </select>
              {llmProvider === "anthropic" && !anthropicKeyConfigured && (
                <p className="text-xs text-amber-400">
                  ANTHROPIC_API_KEY is not configured — see the API Keys section.
                </p>
              )}
              {llmProvider === "openai" && !openaiKeyConfigured && (
                <p className="text-xs text-amber-400">
                  OPENAI_API_KEY is not configured — see the API Keys section.
                </p>
              )}
              {llmProvider === "ollama" && (
                <div className="pt-3 space-y-1.5">
                  <label className="text-sm text-neutral-200">Default Ollama Model</label>
                  <p className="text-xs text-neutral-500">
                    The fallback Ollama tag to use when a task inherits the default provider.
                  </p>
                  <input
                    type="text"
                    value={qwenModel}
                    onChange={(e) => setQwenModel(e.target.value)}
                    placeholder="qwen3:14b"
                    className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:border-violet-500 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors font-mono"
                  />
                </div>
              )}
            </div>

            <div className="p-5 space-y-4">
              <div>
                <h3 className="text-sm font-medium text-neutral-100">LLM Task Routing</h3>
                <p className="text-xs text-neutral-500">
                  Configure provider and model per task. Leave Provider as "Use default" to inherit the default route above.
                </p>
              </div>
              <datalist id="llm-model-suggestions">
                {MODEL_SUGGESTIONS.map((model) => (
                  <option key={model.value} value={model.value}>
                    {model.label}
                  </option>
                ))}
              </datalist>
              <div className="space-y-3">
                {LLM_TASKS.map((task) => {
                  const route = taskRoutes[task.id] ?? { provider: "", model: task.defaultModel };
                  const effectiveProvider = route.provider || llmProvider;
                  return (
                    <div key={task.id} className="rounded-lg border border-neutral-800 bg-neutral-950/40 p-3 space-y-3">
                      <div>
                        <div className="text-sm font-medium text-neutral-100">{task.label}</div>
                        <p className="text-xs text-neutral-500">{task.description}</p>
                      </div>
                      <div className="grid grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] gap-3">
                        <div className="space-y-1">
                          <label className="text-xs text-neutral-400">Provider</label>
                          <select
                            value={route.provider}
                            onChange={(e) => handleTaskProviderChange(task, e.target.value as TaskRoute["provider"])}
                            className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors"
                          >
                            <option value="">Use default ({LLM_PROVIDERS.find((p) => p.value === llmProvider)?.label ?? llmProvider})</option>
                            {LLM_PROVIDERS.map((p) => (
                              <option key={p.value} value={p.value}>
                                {p.label}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs text-neutral-400">Model</label>
                          <input
                            type="text"
                            list="llm-model-suggestions"
                            value={route.model}
                            onChange={(e) => updateTaskRoute(task.id, { model: e.target.value })}
                            placeholder={defaultModelForProvider(task, route.provider)}
                            className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:border-violet-500 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors font-mono"
                          />
                        </div>
                      </div>
                      {effectiveProvider === "anthropic" && !anthropicKeyConfigured && (
                        <p className="text-xs text-amber-400">Anthropic key missing for this route.</p>
                      )}
                      {effectiveProvider === "openai" && !openaiKeyConfigured && (
                        <p className="text-xs text-amber-400">OpenAI key missing for this route.</p>
                      )}
                    </div>
                  );
                })}
              </div>
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
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors"
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
                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 ${
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
                  className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors"
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
                    className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 ${
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
                  className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors"
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
                  className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors"
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
              className="btn-primary px-5 py-2 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950"
            >
              {saving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
