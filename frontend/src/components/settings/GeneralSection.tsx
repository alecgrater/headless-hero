import { useEffect, useState } from "react";
import { Info } from "lucide-react";
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

const AI_VIDEO_PROVIDERS = [
  { value: "runway", label: "Runway Gen-4 Turbo" },
  { value: "fal", label: "Fal.ai Wan 2.2 image-to-video turbo" },
] as const;

const LLM_PROVIDERS = [
  { value: "ollama", label: "Ollama (local)", description: "Local Qwen3 via Ollama" },
  { value: "anthropic", label: "Anthropic API", description: "Real Claude API (requires ANTHROPIC_API_KEY)" },
  { value: "openai", label: "OpenAI API", description: "OpenAI models (requires OPENAI_API_KEY)" },
] as const;

type LlmProvider = (typeof LLM_PROVIDERS)[number]["value"];
type OpenAIReasoningEffort = "minimal" | "low" | "medium" | "high";

const OPENAI_REASONING_OPTIONS: {
  value: OpenAIReasoningEffort;
  label: string;
  description: string;
}[] = [
  {
    value: "minimal",
    label: "Minimal",
    description: "Uses the smallest reasoning budget. Fastest and cheapest; best for JSON, classification, routing, and short structured outputs because it preserves output tokens. Tradeoff: weaker planning on ambiguous creative tasks.",
  },
  {
    value: "low",
    label: "Low",
    description: "Allows a little planning before answering. Good default for scripts, ideas, and hook work where quality benefits from light structure. Tradeoff: slower and more expensive than minimal, with less visible output room on small token budgets.",
  },
  {
    value: "medium",
    label: "Medium",
    description: "Spends more tokens thinking through complex choices. Useful when a task is failing because it needs deeper synthesis. Tradeoff: noticeably slower and can crowd out the final answer if max tokens are tight.",
  },
  {
    value: "high",
    label: "High",
    description: "Maximizes reasoning effort for difficult, high-stakes planning. Tradeoff: slowest and most expensive, and risky for strict JSON or tiny output budgets because reasoning tokens can leave little room for message content.",
  },
];

const OPENAI_MODEL_RECOMMENDATIONS: Record<string, string> = {
  "gpt-5.5": "Recommended model: GPT-5.5. Best fit when script quality, story structure, or hook judgment matters most. Tradeoff: higher latency and cost than smaller GPT-5 models.",
  "gpt-5-mini": "Recommended model: GPT-5 Mini. Strong balance for ideation, metadata, routing, and scene decisions where you want reliable judgment without premium-model cost. Tradeoff: less nuanced than GPT-5.5 on long creative planning.",
  "gpt-5-nano": "Recommended model: GPT-5 Nano. Fast and inexpensive for short structured tasks such as scoring, detection, and simple animation choices. Tradeoff: least capable on ambiguous creative calls, so upgrade if outputs feel brittle.",
};

const openaiModelRecommendation = (model: string) =>
  OPENAI_MODEL_RECOMMENDATIONS[model] ??
  `Recommended model: ${model}. Use this when it is the OpenAI model you have validated for this workflow. Tradeoff: custom selections may vary in speed, cost, and reasoning quality.`;

interface LlmTaskConfig {
  id: string;
  label: string;
  description: string;
  providerKey: string;
  modelKey: string;
  reasoningKey: string;
  defaultProvider: LlmProvider;
  defaultModel: string;
  openaiDefaultModel: string;
  ollamaDefaultModel: string;
  defaultReasoning: OpenAIReasoningEffort;
  note?: string;
}

interface TaskRoute {
  provider: LlmProvider;
  model: string;
  openaiReasoningEffort: OpenAIReasoningEffort;
}

const LLM_TASKS: LlmTaskConfig[] = [
  {
    id: "script",
    label: "Script & cold opens",
    description: "Full scripts, segmented generation, scene rewrites, cold-open variants, narration tightening.",
    providerKey: "SCRIPT_LLM_PROVIDER",
    modelKey: "SCRIPT_MODEL",
    reasoningKey: "OPENAI_REASONING_EFFORT_SCRIPT",
    defaultProvider: "anthropic",
    defaultModel: DEFAULT_MODEL,
    openaiDefaultModel: "gpt-5.5",
    ollamaDefaultModel: "qwen3:14b",
    defaultReasoning: "low",
  },
  {
    id: "idea",
    label: "Ideas & brainstorming",
    description: "Niche ideas, smart ideas, and brainstorming recommendations.",
    providerKey: "IDEA_LLM_PROVIDER",
    modelKey: "IDEA_MODEL",
    reasoningKey: "OPENAI_REASONING_EFFORT_IDEA",
    defaultProvider: "openai",
    defaultModel: "claude-sonnet-4-6",
    openaiDefaultModel: "gpt-5-mini",
    ollamaDefaultModel: "qwen3:14b",
    defaultReasoning: "low",
  },
  {
    id: "fx",
    label: "FX assignment",
    description: "Scene FX, transitions, and visual timing suggestions.",
    providerKey: "FX_LLM_PROVIDER",
    modelKey: "FX_MODEL",
    reasoningKey: "OPENAI_REASONING_EFFORT_FX",
    defaultProvider: "ollama",
    defaultModel: "claude-sonnet-4-6",
    openaiDefaultModel: "gpt-5-mini",
    ollamaDefaultModel: "qwen3:14b",
    defaultReasoning: "minimal",
  },
  {
    id: "seo",
    label: "SEO metadata",
    description: "YouTube titles, descriptions, tags, and chapter-aware metadata.",
    providerKey: "SEO_LLM_PROVIDER",
    modelKey: "SEO_MODEL",
    reasoningKey: "OPENAI_REASONING_EFFORT_SEO",
    defaultProvider: "ollama",
    defaultModel: "claude-sonnet-4-6",
    openaiDefaultModel: "gpt-5-mini",
    ollamaDefaultModel: "qwen3:14b",
    defaultReasoning: "minimal",
  },
  {
    id: "short_form_seo",
    label: "Short-form SEO metadata",
    description: "Per-short upload text for TikTok, YouTube Shorts, and Instagram Reels.",
    providerKey: "SHORT_FORM_SEO_LLM_PROVIDER",
    modelKey: "SHORT_FORM_SEO_MODEL",
    reasoningKey: "OPENAI_REASONING_EFFORT_SHORT_FORM_SEO",
    defaultProvider: "openai",
    defaultModel: "claude-sonnet-4-6",
    openaiDefaultModel: "gpt-5-mini",
    ollamaDefaultModel: "qwen3:14b",
    defaultReasoning: "minimal",
  },
  {
    id: "hook",
    label: "Hook scoring/refining",
    description: "Retention scoring and hook rewrite suggestions.",
    providerKey: "HOOK_LLM_PROVIDER",
    modelKey: "HOOK_MODEL",
    reasoningKey: "OPENAI_REASONING_EFFORT_HOOK",
    defaultProvider: "openai",
    defaultModel: "claude-haiku-4-5-20251001",
    openaiDefaultModel: "gpt-5.5",
    ollamaDefaultModel: "qwen3:14b",
    defaultReasoning: "low",
    note: "Shared task — this single model drives both hook scoring (rates how well the opening will retain viewers) and hook refinement (rewrites weak hooks). Set it once here.",
  },
  {
    id: "media",
    label: "Media routing",
    description: "Post-script routing between AI images and AI video scenes.",
    providerKey: "MEDIA_LLM_PROVIDER",
    modelKey: "MEDIA_MODEL",
    reasoningKey: "OPENAI_REASONING_EFFORT_MEDIA",
    defaultProvider: "ollama",
    defaultModel: "claude-sonnet-4-6",
    openaiDefaultModel: "gpt-5-mini",
    ollamaDefaultModel: "qwen3:14b",
    defaultReasoning: "minimal",
  },
  {
    id: "eli",
    label: "Eli animation",
    description: "Eli pose and placement selection for scenes.",
    providerKey: "ELI_LLM_PROVIDER",
    modelKey: "ELI_MODEL",
    reasoningKey: "OPENAI_REASONING_EFFORT_ELI",
    defaultProvider: "ollama",
    defaultModel: "claude-haiku-4-5-20251001",
    openaiDefaultModel: "gpt-5-nano",
    ollamaDefaultModel: "qwen3:14b",
    defaultReasoning: "minimal",
  },
  {
    id: "analysis",
    label: "Analysis & scoring",
    description: "Trend format-fit scoring, content profiles, and recording quality analysis.",
    providerKey: "ANALYSIS_LLM_PROVIDER",
    modelKey: "ANALYSIS_MODEL",
    reasoningKey: "OPENAI_REASONING_EFFORT_ANALYSIS",
    defaultProvider: "ollama",
    defaultModel: "claude-haiku-4-5-20251001",
    openaiDefaultModel: "gpt-5-nano",
    ollamaDefaultModel: "qwen3:14b",
    defaultReasoning: "minimal",
  },
  {
    id: "hook_detect",
    label: "Hook detection (short-form)",
    description: "Identifies the opening hook scenes in segment 1 so short #1 starts at the real content.",
    providerKey: "HOOK_DETECT_LLM_PROVIDER",
    modelKey: "HOOK_DETECT_MODEL",
    reasoningKey: "OPENAI_REASONING_EFFORT_HOOK_DETECT",
    defaultProvider: "ollama",
    defaultModel: "claude-haiku-4-5-20251001",
    openaiDefaultModel: "gpt-5-nano",
    ollamaDefaultModel: "qwen3:14b",
    defaultReasoning: "minimal",
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

// eslint-disable-next-line react-refresh/only-export-components -- co-located with the GeneralSection component that consumes these
export const SCRIPT_MODELS = [
  { value: DEFAULT_MODEL, label: "Claude Opus 4.7" },
  { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
  { value: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5" },
  { value: "gpt-5.5", label: "OpenAI GPT-5.5" },
  { value: "gpt-5.4", label: "OpenAI GPT-5.4" },
  { value: "gpt-5.2", label: "OpenAI GPT-5.2" },
  { value: "gpt-5-mini", label: "OpenAI GPT-5 Mini" },
  { value: "gpt-5-nano", label: "OpenAI GPT-5 Nano" },
] as const;

const MODEL_SUGGESTIONS = [
  ...SCRIPT_MODELS,
  { value: "qwen3:14b", label: "Qwen3 14B (Ollama)" },
  { value: "qwen3:8b", label: "Qwen3 8B (Ollama)" },
] as const;

const modelOptionsForProvider = (provider: LlmProvider) => {
  if (provider === "openai") {
    return SCRIPT_MODELS.filter((model) => model.value.startsWith("gpt-"));
  }
  if (provider === "anthropic") {
    return SCRIPT_MODELS.filter((model) => !model.value.startsWith("gpt-"));
  }
  return MODEL_SUGGESTIONS;
};

const normalizeLlmProvider = (provider: string, fallback: LlmProvider): LlmProvider =>
  LLM_PROVIDERS.some((candidate) => candidate.value === provider)
    ? (provider as LlmProvider)
    : fallback;

const initialTaskRoutes = () =>
  Object.fromEntries(
    LLM_TASKS.map((task) => [
      task.id,
      {
        provider: task.defaultProvider,
        model: modelForProvider(task, task.defaultProvider),
        openaiReasoningEffort: task.defaultReasoning,
      },
    ]),
  );

function modelForProvider(task: LlmTaskConfig, provider: LlmProvider) {
  if (provider === "openai") return task.openaiDefaultModel;
  if (provider === "ollama") return task.ollamaDefaultModel;
  return task.defaultModel;
}

type GeneralPanel = "storage" | "ai-models" | "visuals";

const PANEL_META: Record<GeneralPanel, { title: string; description: string; maxWidth: string }> = {
  storage: {
    title: "Storage",
    description: "Choose where finished files and export bundles are saved.",
    maxWidth: "max-w-2xl",
  },
  "ai-models": {
    title: "AI Models",
    description: "Route scriptwriting, ideation, metadata, scoring, and animation tasks.",
    maxWidth: "max-w-3xl",
  },
  visuals: {
    title: "Visuals",
    description: "Configure image generation providers and visual asset defaults.",
    maxWidth: "max-w-2xl",
  },
};

interface GeneralSectionProps {
  panel: GeneralPanel;
}

export default function GeneralSection({ panel }: GeneralSectionProps) {
  const [exportsDir, setExportsDir] = useState("");
  const [imageProvider, setImageProvider] = useState("google");
  const [aiVideoEnabled, setAiVideoEnabled] = useState(false);
  const [aiVideoProvider, setAiVideoProvider] = useState("runway");
  const [aiVideoScenesPerSegment, setAiVideoScenesPerSegment] = useState("2");
  const [lifeAsAChunkingEnabled, setLifeAsAChunkingEnabled] = useState(true);
  const [lifeAsATargetSeconds, setLifeAsATargetSeconds] = useState("8");
  const [lifeAsAMaxSeconds, setLifeAsAMaxSeconds] = useState("12");
  const [lifeAsASingleVisualMaxSeconds, setLifeAsASingleVisualMaxSeconds] = useState("8");
  const [promptUpsampling, setPromptUpsampling] = useState("true");
  const [replicateModel, setReplicateModel] = useState("black-forest-labs/flux-1.1-pro");
  const [safetyTolerance, setSafetyTolerance] = useState("2");
  const [outputFormat, setOutputFormat] = useState("png");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [llmProvider, setLlmProvider] = useState<LlmProvider>("ollama");
  const [qwenModel, setQwenModel] = useState("qwen3:14b");
  const [anthropicKeyConfigured, setAnthropicKeyConfigured] = useState(false);
  const [openaiKeyConfigured, setOpenaiKeyConfigured] = useState(false);
  const [taskRoutes, setTaskRoutes] = useState<Record<string, TaskRoute>>(initialTaskRoutes);
  const [originalExportsDir, setOriginalExportsDir] = useState("");
  const [originalProvider, setOriginalProvider] = useState("google");
  const [originalAiVideoEnabled, setOriginalAiVideoEnabled] = useState(false);
  const [originalAiVideoProvider, setOriginalAiVideoProvider] = useState("runway");
  const [originalAiVideoScenesPerSegment, setOriginalAiVideoScenesPerSegment] = useState("2");
  const [originalLifeAsAChunkingEnabled, setOriginalLifeAsAChunkingEnabled] = useState(true);
  const [originalLifeAsATargetSeconds, setOriginalLifeAsATargetSeconds] = useState("8");
  const [originalLifeAsAMaxSeconds, setOriginalLifeAsAMaxSeconds] = useState("12");
  const [originalLifeAsASingleVisualMaxSeconds, setOriginalLifeAsASingleVisualMaxSeconds] = useState("8");
  const [originalUpsampling, setOriginalUpsampling] = useState("true");
  const [originalModel, setOriginalModel] = useState("black-forest-labs/flux-1.1-pro");
  const [originalSafety, setOriginalSafety] = useState("2");
  const [originalFormat, setOriginalFormat] = useState("png");
  const [originalLlmProvider, setOriginalLlmProvider] = useState<LlmProvider>("ollama");
  const [originalQwenModel, setOriginalQwenModel] = useState("qwen3:14b");
  const [originalTaskRoutes, setOriginalTaskRoutes] = useState<Record<string, TaskRoute>>(initialTaskRoutes);

  useEffect(() => {
    api.get("/api/settings/keys").then((res) => {
      if (res.ok) {
        const data = res.data as Record<string, KeyInfo>;
        const exportVal = data.DOWNLOADS_DIR?.masked ?? "~/Headless Hero Videos";
        setExportsDir(exportVal);
        setOriginalExportsDir(exportVal);
        const provVal = data.IMAGE_PROVIDER?.masked || "google";
        setImageProvider(provVal);
        setOriginalProvider(provVal);
        const aiVideoVal = data.AI_VIDEO_ENABLED?.masked === "true";
        setAiVideoEnabled(aiVideoVal);
        setOriginalAiVideoEnabled(aiVideoVal);
        const aiVideoProviderVal = data.AI_VIDEO_PROVIDER?.masked || "runway";
        setAiVideoProvider(aiVideoProviderVal);
        setOriginalAiVideoProvider(aiVideoProviderVal);
        const aiVideoScenesPerSegmentVal = data.AI_VIDEO_SCENES_PER_SEGMENT?.masked || "2";
        setAiVideoScenesPerSegment(aiVideoScenesPerSegmentVal);
        setOriginalAiVideoScenesPerSegment(aiVideoScenesPerSegmentVal);
        const lifeAsAChunkingVal = data.LIFE_AS_A_SCENE_CHUNKING_ENABLED?.masked !== "false";
        setLifeAsAChunkingEnabled(lifeAsAChunkingVal);
        setOriginalLifeAsAChunkingEnabled(lifeAsAChunkingVal);
        const lifeAsATargetVal = data.LIFE_AS_A_TARGET_SCENE_SECONDS?.masked || "8";
        setLifeAsATargetSeconds(lifeAsATargetVal);
        setOriginalLifeAsATargetSeconds(lifeAsATargetVal);
        const lifeAsAMaxVal = data.LIFE_AS_A_MAX_SCENE_SECONDS?.masked || "12";
        setLifeAsAMaxSeconds(lifeAsAMaxVal);
        setOriginalLifeAsAMaxSeconds(lifeAsAMaxVal);
        const lifeAsASingleVisualVal = data.LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS?.masked || "8";
        setLifeAsASingleVisualMaxSeconds(lifeAsASingleVisualVal);
        setOriginalLifeAsASingleVisualMaxSeconds(lifeAsASingleVisualVal);
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
        const llmVal = normalizeLlmProvider(data.LLM_PROVIDER?.masked || "", "ollama");
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
              provider: normalizeLlmProvider(data[task.providerKey]?.masked || "", task.defaultProvider),
              model: data[task.modelKey]?.masked || modelForProvider(task, task.defaultProvider),
              openaiReasoningEffort: (data[task.reasoningKey]?.masked || task.defaultReasoning) as OpenAIReasoningEffort,
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
        const route = taskRoutes[task.id] ?? {
          provider: task.defaultProvider,
          model: modelForProvider(task, task.defaultProvider),
          openaiReasoningEffort: task.defaultReasoning,
        };
        return [
          [task.providerKey, route.provider],
          [task.modelKey, route.model.trim() || modelForProvider(task, route.provider || task.defaultProvider)],
          [task.reasoningKey, route.openaiReasoningEffort || task.defaultReasoning],
        ];
      }),
    );
    const res = await api.put("/api/settings/keys", {
      DOWNLOADS_DIR: exportsDir.trim(),
      IMAGE_PROVIDER: imageProvider,
      AI_VIDEO_ENABLED: aiVideoEnabled ? "true" : "false",
      AI_VIDEO_PROVIDER: aiVideoProvider,
      AI_VIDEO_SCENES_PER_SEGMENT: aiVideoScenesPerSegment,
      LIFE_AS_A_SCENE_CHUNKING_ENABLED: lifeAsAChunkingEnabled ? "true" : "false",
      LIFE_AS_A_TARGET_SCENE_SECONDS: lifeAsATargetSeconds,
      LIFE_AS_A_MAX_SCENE_SECONDS: lifeAsAMaxSeconds,
      LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS: lifeAsASingleVisualMaxSeconds,
      REPLICATE_MODEL: replicateModel,
      REPLICATE_PROMPT_UPSAMPLING: promptUpsampling,
      REPLICATE_SAFETY_TOLERANCE: safetyTolerance,
      REPLICATE_OUTPUT_FORMAT: outputFormat,
      LLM_PROVIDER: llmProvider,
      QWEN_MODEL: qwenModel.trim() || "qwen3:14b",
      ...routePayload,
    });
    setSaving(false);

    if (res.ok) {
      showToast("Settings saved", "success");
      setOriginalExportsDir(exportsDir.trim());
      setOriginalProvider(imageProvider);
      setOriginalAiVideoEnabled(aiVideoEnabled);
      setOriginalAiVideoProvider(aiVideoProvider);
      setOriginalAiVideoScenesPerSegment(aiVideoScenesPerSegment);
      setOriginalLifeAsAChunkingEnabled(lifeAsAChunkingEnabled);
      setOriginalLifeAsATargetSeconds(lifeAsATargetSeconds);
      setOriginalLifeAsAMaxSeconds(lifeAsAMaxSeconds);
      setOriginalLifeAsASingleVisualMaxSeconds(lifeAsASingleVisualMaxSeconds);
      setOriginalModel(replicateModel);
      setOriginalUpsampling(promptUpsampling);
      setOriginalSafety(safetyTolerance);
      setOriginalFormat(outputFormat);
      setOriginalLlmProvider(llmProvider);
      setOriginalQwenModel(qwenModel.trim() || "qwen3:14b");
      setOriginalTaskRoutes(
        Object.fromEntries(
          LLM_TASKS.map((task) => {
            const route = taskRoutes[task.id] ?? {
              provider: task.defaultProvider,
              model: modelForProvider(task, task.defaultProvider),
              openaiReasoningEffort: task.defaultReasoning,
            };
            return [
              task.id,
              {
                provider: route.provider,
                model: route.model.trim() || modelForProvider(task, route.provider || task.defaultProvider),
                openaiReasoningEffort: route.openaiReasoningEffort || task.defaultReasoning,
              },
            ];
          }),
        ),
      );
    }
  };

  const updateTaskRoute = (taskId: string, updates: Partial<TaskRoute>) => {
    setTaskRoutes((prev) => ({
      ...prev,
      [taskId]: {
        ...(prev[taskId] ?? (() => {
          const task = LLM_TASKS.find((candidate) => candidate.id === taskId);
          return task
            ? {
                provider: task.defaultProvider,
                model: modelForProvider(task, task.defaultProvider),
                openaiReasoningEffort: task.defaultReasoning,
              }
            : { provider: "anthropic" as LlmProvider, model: DEFAULT_MODEL, openaiReasoningEffort: "low" };
        })()),
        ...updates,
      },
    }));
  };

  const defaultModelForProvider = (task: LlmTaskConfig, provider: TaskRoute["provider"]) => {
    return modelForProvider(task, provider || llmProvider);
  };

  const handleTaskProviderChange = (task: LlmTaskConfig, provider: TaskRoute["provider"]) => {
    const current = taskRoutes[task.id] ?? {
      provider: task.defaultProvider,
      model: modelForProvider(task, task.defaultProvider),
      openaiReasoningEffort: task.defaultReasoning,
    };
    const knownDefaults = new Set([
      task.defaultModel,
      task.openaiDefaultModel,
      task.ollamaDefaultModel,
      ...MODEL_SUGGESTIONS.map((model) => model.value),
      "",
    ]);
    updateTaskRoute(task.id, {
      provider,
      model: knownDefaults.has(current.model) ? defaultModelForProvider(task, provider) : current.model,
    });
  };

  const handleDefaultProviderChange = (provider: LlmProvider) => {
    setLlmProvider(provider);
  };

  const routeChanged = LLM_TASKS.some((task) => {
    const current = taskRoutes[task.id] ?? {
      provider: task.defaultProvider,
      model: modelForProvider(task, task.defaultProvider),
      openaiReasoningEffort: task.defaultReasoning,
    };
    const original = originalTaskRoutes[task.id] ?? {
      provider: task.defaultProvider,
      model: modelForProvider(task, task.defaultProvider),
      openaiReasoningEffort: task.defaultReasoning,
    };
    return (
      current.provider !== original.provider ||
      current.model.trim() !== original.model ||
      current.openaiReasoningEffort !== original.openaiReasoningEffort
    );
  });

  const hasChanges =
    exportsDir.trim() !== originalExportsDir ||
    imageProvider !== originalProvider ||
    aiVideoEnabled !== originalAiVideoEnabled ||
    aiVideoProvider !== originalAiVideoProvider ||
    aiVideoScenesPerSegment !== originalAiVideoScenesPerSegment ||
    lifeAsAChunkingEnabled !== originalLifeAsAChunkingEnabled ||
    lifeAsATargetSeconds !== originalLifeAsATargetSeconds ||
    lifeAsAMaxSeconds !== originalLifeAsAMaxSeconds ||
    lifeAsASingleVisualMaxSeconds !== originalLifeAsASingleVisualMaxSeconds ||
    replicateModel !== originalModel ||
    promptUpsampling !== originalUpsampling ||
    safetyTolerance !== originalSafety ||
    outputFormat !== originalFormat ||
    llmProvider !== originalLlmProvider ||
    qwenModel.trim() !== originalQwenModel ||
    routeChanged;
  const meta = PANEL_META[panel];

  return (
    <div className={`px-8 py-8 ${meta.maxWidth} space-y-6 pb-24`}>
      <div>
        <h2 className="text-lg font-semibold tracking-tight">{meta.title}</h2>
        <p className="text-neutral-400 text-sm mt-1">
          {meta.description}
        </p>
      </div>

      {loading ? (
        <div className="text-neutral-500 text-sm">Loading...</div>
      ) : (
        <div className="space-y-6">
          {panel === "storage" && (
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-5 space-y-2">
            <div>
              <h3 className="text-sm font-medium text-neutral-100">Exports</h3>
              <p className="text-xs text-neutral-500">
                Final project folders, upload-suite checks, rendered videos, thumbnails, and SEO files live here.
              </p>
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={exportsDir}
                onChange={(e) => setExportsDir(e.target.value)}
                placeholder="~/Headless Hero Videos"
                className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:border-violet-500 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors font-mono"
              />
              {window.api?.selectFolder && (
                <button
                  type="button"
                  onClick={async () => {
                    const result = await window.api.selectFolder!("Select Exports Directory", exportsDir || undefined);
                    if (!result.canceled && result.path) setExportsDir(result.path);
                  }}
                  className="px-3 py-2 bg-neutral-800 border border-neutral-700 rounded-lg text-sm text-neutral-300 hover:text-neutral-100 hover:border-neutral-600 transition-colors whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950"
                >
                  Browse…
                </button>
              )}
            </div>
          </div>
          )}

          {panel === "ai-models" && (
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
                  Configure provider and model per task. These defaults use API models for scripts and ideas, then local Ollama for everything else.
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
                  const route = taskRoutes[task.id] ?? {
                    provider: task.defaultProvider,
                    model: modelForProvider(task, task.defaultProvider),
                    openaiReasoningEffort: task.defaultReasoning,
                  };
                  const effectiveProvider = route.provider || llmProvider;
                  const modelOptions = modelOptionsForProvider(effectiveProvider);
                  const hasSelectedModelOption = modelOptions.some((model) => model.value === route.model);
                  const openaiReasoningEnabled = effectiveProvider === "openai";
                  const reasoningDescription =
                    OPENAI_REASONING_OPTIONS.find((option) => option.value === route.openaiReasoningEffort)
                      ?.description ?? OPENAI_REASONING_OPTIONS[0].description;
                  const recommendedModelDescription = openaiModelRecommendation(task.openaiDefaultModel);
                  return (
                    <div key={task.id} className="rounded-lg border border-neutral-800 bg-neutral-950/40 p-3 space-y-3">
                      <div>
                        <div className="text-sm font-medium text-neutral-100">{task.label}</div>
                        <p className="text-xs text-neutral-500">{task.description}</p>
                      </div>
                      {task.note && (
                        <div className="flex items-start gap-2 rounded-md border border-violet-500/20 bg-violet-500/5 px-2.5 py-2">
                          <Info className="h-3.5 w-3.5 shrink-0 text-violet-400 mt-[1px]" aria-hidden />
                          <p className="text-xs text-neutral-300 leading-relaxed">{task.note}</p>
                        </div>
                      )}
                      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1fr)_minmax(0,0.9fr)]">
                        <div className="space-y-1">
                          <label className="text-xs text-neutral-400">Provider</label>
                          <select
                            value={route.provider}
                            onChange={(e) => handleTaskProviderChange(task, e.target.value as TaskRoute["provider"])}
                            className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors"
                          >
                            {LLM_PROVIDERS.map((p) => (
                              <option key={p.value} value={p.value}>
                                {p.label}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs text-neutral-400">Model</label>
                          {effectiveProvider === "ollama" ? (
                            <input
                              type="text"
                              list="llm-model-suggestions"
                              value={route.model}
                              onChange={(e) => updateTaskRoute(task.id, { model: e.target.value })}
                              placeholder={defaultModelForProvider(task, route.provider)}
                              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:border-violet-500 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors font-mono"
                            />
                          ) : (
                            <select
                              value={route.model}
                              onChange={(e) => updateTaskRoute(task.id, { model: e.target.value })}
                              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors font-mono"
                            >
                              {!hasSelectedModelOption && route.model.trim() && (
                                <option value={route.model}>{route.model} (custom)</option>
                              )}
                              {modelOptions.map((model) => (
                                <option key={model.value} value={model.value}>
                                  {model.label}
                                </option>
                              ))}
                            </select>
                          )}
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs text-neutral-400">OpenAI reasoning</label>
                          <select
                            value={route.openaiReasoningEffort}
                            disabled={!openaiReasoningEnabled}
                            onChange={(e) =>
                              updateTaskRoute(task.id, {
                                openaiReasoningEffort: e.target.value as OpenAIReasoningEffort,
                              })
                            }
                            className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors disabled:cursor-not-allowed disabled:border-neutral-800 disabled:bg-neutral-900 disabled:text-neutral-500 disabled:opacity-70"
                          >
                            {OPENAI_REASONING_OPTIONS.map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                      {effectiveProvider === "openai" && (
                        <div className="flex items-start gap-2 rounded-md border border-sky-500/20 bg-sky-500/5 px-2.5 py-2">
                          <Info className="h-3.5 w-3.5 shrink-0 text-sky-400 mt-[1px]" aria-hidden />
                          <div className="space-y-1">
                            <p className="text-xs text-neutral-300 leading-relaxed">
                              {recommendedModelDescription}
                            </p>
                            <p className="text-xs text-neutral-400 leading-relaxed">
                              Reasoning: {reasoningDescription}
                            </p>
                          </div>
                        </div>
                      )}
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

            <div className="p-5 space-y-3">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h3 className="text-sm font-medium text-neutral-100">AI Video Scenes</h3>
                  <p className="text-xs text-neutral-500">
                    Route selected high-motion scenes to the configured image-to-video provider.
                  </p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={aiVideoEnabled}
                  onClick={() => setAiVideoEnabled((value) => !value)}
                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 ${
                    aiVideoEnabled ? "bg-violet-600" : "bg-neutral-700 hover:bg-neutral-600"
                  }`}
                  aria-label="Toggle AI video scenes"
                >
                  <span
                    className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${
                      aiVideoEnabled ? "translate-x-5" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>
              <p className="text-xs text-neutral-500">
                Requires a key for the selected video provider. Script generation routes high-motion scenes up to the configured per-segment count.
              </p>
            </div>

          </div>
          )}

          {panel === "visuals" && (
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl divide-y divide-neutral-800">
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

            {aiVideoEnabled && (
              <div className="p-5 space-y-2">
                <div>
                  <h3 className="text-sm font-medium text-neutral-100">AI Video Provider</h3>
                  <p className="text-xs text-neutral-500">
                    Choose which image-to-video service animates routed AI video scenes.
                  </p>
                </div>
                <select
                  value={aiVideoProvider}
                  onChange={(e) => setAiVideoProvider(e.target.value)}
                  className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors"
                >
                  {AI_VIDEO_PROVIDERS.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-neutral-500">
                  Existing cached clips are reused only when the provider, model, dimensions, duration, and anchor image all match.
                </p>
              </div>
            )}

            {aiVideoEnabled && (
              <div className="p-5 space-y-2">
                <div>
                  <h3 className="text-sm font-medium text-neutral-100">AI Video Scenes per Segment</h3>
                  <p className="text-xs text-neutral-500">
                    Maximum eligible high-motion scenes to animate in each segment.
                  </p>
                </div>
                <input
                  type="number"
                  min="0"
                  max="5"
                  step="1"
                  value={aiVideoScenesPerSegment}
                  onChange={(e) => setAiVideoScenesPerSegment(e.target.value)}
                  className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors"
                />
                <p className="text-xs text-neutral-500">
                  Default is 2. Use 0 to keep AI video available but skip automatic routing.
                </p>
              </div>
            )}

            <div className="p-5 space-y-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h3 className="text-sm font-medium text-neutral-100">Life-as-a Scene Chunking</h3>
                  <p className="text-xs text-neutral-500">
                    Split long life-as-a narration into short single-beat scenes before voiceover.
                  </p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={lifeAsAChunkingEnabled}
                  onClick={() => setLifeAsAChunkingEnabled((value) => !value)}
                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 ${
                    lifeAsAChunkingEnabled ? "bg-violet-600" : "bg-neutral-700 hover:bg-neutral-600"
                  }`}
                  aria-label="Toggle life-as-a scene chunking"
                >
                  <span
                    className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${
                      lifeAsAChunkingEnabled ? "translate-x-5" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>
              <div className="rounded-lg border border-violet-500/20 bg-violet-500/5 px-3 py-2 text-xs text-neutral-300 leading-relaxed">
                Shorter life-as-a scenes improve AI-video compatibility. Long scenes are split before voiceover when possible; generated-image scenes may still use multiple frames when the visual beat calls for it.
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <label className="space-y-1">
                  <span className="text-xs text-neutral-400">Target scene seconds</span>
                  <input
                    type="number"
                    min="5"
                    max="12"
                    step="1"
                    value={lifeAsATargetSeconds}
                    onChange={(e) => setLifeAsATargetSeconds(e.target.value)}
                    className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors"
                  />
                </label>
                <label className="space-y-1">
                  <span className="text-xs text-neutral-400">Maximum scene seconds</span>
                  <input
                    type="number"
                    min="8"
                    max="18"
                    step="1"
                    value={lifeAsAMaxSeconds}
                    onChange={(e) => setLifeAsAMaxSeconds(e.target.value)}
                    className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors"
                  />
                </label>
                <label className="space-y-1">
                  <span className="text-xs text-neutral-400">AI-video max scene seconds</span>
                  <input
                    type="number"
                    min="5"
                    max="12"
                    step="1"
                    value={lifeAsASingleVisualMaxSeconds}
                    onChange={(e) => setLifeAsASingleVisualMaxSeconds(e.target.value)}
                    className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors"
                  />
                  <span className="block text-[11px] text-neutral-500">AI-video routing only through this many seconds.</span>
                </label>
              </div>
              <p className="text-xs text-neutral-500">
                Default policy: life-as-a AI-video candidates must be at or below {lifeAsASingleVisualMaxSeconds || "8"} seconds. Image scenes can keep multiple frames when the generated beat uses them; longer life-as-a scenes are split.
              </p>
            </div>

          </div>
          )}

          {panel === "visuals" && imageProvider === "replicate" && (
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
