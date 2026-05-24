import { useEffect, useState } from "react";
import api, { assetUrl, getFormats, getProjectConfig } from "../../api";
import type { ProjectConfig } from "../../api";
import type { VideoIdea } from "../../types/idea";
import type { VideoFormat } from "../../types/format";
import { SCRIPT_MODELS } from "../settings/GeneralSection";
import { Button } from "../ui/Button";
import GenerationProgressBar from "../GenerationProgressBar";
import useScriptGeneration from "./useScriptGeneration";
import useSceneEditing from "./useSceneEditing";
import useTitleCardGeneration from "./useTitleCardGeneration";
import ColdOpenSelector from "./ColdOpenSelector";
import MainCharacterDrawer from "../timeline/MainCharacterDrawer";

interface Props {
  brandId: string;
  idea: VideoIdea;
  eliEnabled?: boolean;
  stylePresetEnabled?: boolean;
  onBack: () => void;
  onContinue: (scriptId: string) => void;
}

const PROVIDER_LABELS: Record<string, string> = {
  ollama: "Ollama (local)",
  anthropic: "Anthropic API",
  openai: "OpenAI API",
};

export default function ScriptGenerationPage({
  brandId,
  idea,
  eliEnabled = true,
  stylePresetEnabled = true,
  onBack,
  onContinue,
}: Props) {
  const [format, setFormat] = useState<VideoFormat | null>(null);
  const formatId = idea.format_id ?? "youtube-listicle";

  useEffect(() => {
    getFormats().then((all) => {
      setFormat(all.find((f) => f.id === formatId) ?? all[0] ?? null);
    });
  }, [formatId]);

  const supportsColdOpen = format?.supports_cold_open ?? true;

  const {
    script,
    scriptId,
    loading,
    error,
    selectedModel,
    segmented,
    generationStarted,
    settingsLoaded,
    estimatedSeconds,
    elapsedSeconds,
    genSegments,
    genCompletedSegments,
    phase,
    coldOpenResult,
    setScript,
    handleGenerate,
    handleCancelGeneration,
    handleModelChange,
    handleColdOpenSelect,
    setSegmented,
  } = useScriptGeneration({ brandId, idea, supportsColdOpen, eliEnabled, stylePresetEnabled });

  const {
    editingKey,
    editNarration,
    editHookText,
    editedScenes,
    refiningScene,
    saving,
    setEditNarration,
    setEditHookText,
    startEditScene,
    cancelEdit,
    saveSceneEdit,
    startEditIntro,
    saveIntroEdit,
    startEditOutro,
    saveOutroEdit,
    refineScene,
  } = useSceneEditing({ script, scriptId, setScript });

  const {
    titleCardGenerating,
    titleCardGenerated,
    titleCardError,
    titleCardCompleted,
    titleCardTotal,
    generateTitleCards,
  } = useTitleCardGeneration({ scriptId, script });

  const [llmProvider, setLlmProvider] = useState<string>("");
  const [qwenModel, setQwenModel] = useState<string>("");
  const [projectConfig, setProjectConfig] = useState<ProjectConfig | null>(null);
  const [showCharacterDrawer, setShowCharacterDrawer] = useState(false);

  useEffect(() => {
    if (!scriptId) {
      setProjectConfig(null);
      return;
    }
    let cancelled = false;
    getProjectConfig(scriptId).then((res) => {
      if (cancelled) return;
      if (res.ok) setProjectConfig(res.data as ProjectConfig);
    });
    return () => {
      cancelled = true;
    };
  }, [scriptId]);

  useEffect(() => {
    api.get("/api/settings/keys").then((res) => {
      if (res.ok) {
        const data = res.data as Record<string, { masked?: string }>;
        const provider = data.SCRIPT_LLM_PROVIDER?.masked || data.LLM_PROVIDER?.masked || "anthropic";
        setLlmProvider(provider);
        setQwenModel(
          provider === "ollama"
            ? data.QWEN_MODEL?.masked || "qwen3:14b"
            : data.SCRIPT_MODEL?.masked || selectedModel,
        );
      }
    });
  }, [selectedModel]);

  const activeModelLabel =
    llmProvider === "ollama"
      ? qwenModel || "qwen3:14b"
      : SCRIPT_MODELS.find((m) => m.value === selectedModel)?.label ?? selectedModel;
  const providerLabel = PROVIDER_LABELS[llmProvider] ?? llmProvider;

  const totalScenes = script
    ? script.segments.reduce((sum, seg) => sum + seg.scenes.length, 0)
    : 0;

  const hasTitleCards = true;

  const mainCharacterRequired = projectConfig?.eli_enabled === false;
  const mainCharacterReady =
    !mainCharacterRequired || Boolean(projectConfig?.main_character_reference_url);

  const loadingText =
    phase === "cold_opens"
      ? "Generating cold open variants..."
      : "Generating script...";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="space-y-1">
        <button
          onClick={onBack}
          className="text-sm text-neutral-400 hover:text-neutral-200 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 rounded-md"
        >
          &larr; Back to Ideas
        </button>
        <div className="flex items-center gap-2.5">
          <h2 className="text-2xl font-bold">{idea.title}</h2>
        </div>
        <p className="text-sm text-neutral-400">{idea.description}</p>
      </div>

      {/* Pre-generation options */}
      {!generationStarted && settingsLoaded && (
        <>
        <div className="rounded-lg border border-neutral-800 bg-neutral-900 px-6 py-5 space-y-5">
          <h3 className="text-sm font-semibold text-neutral-200 uppercase tracking-wider">
            Generation Options
          </h3>

          <div className="grid grid-cols-2 gap-6">
            {/* Model dropdown */}
            <div>
              <label className="block text-xs text-neutral-500 mb-1.5">
                Script Model
              </label>
              <select
                value={selectedModel}
                onChange={(e) => handleModelChange(e.target.value)}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 transition-colors"
              >
                {SCRIPT_MODELS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Segmented generation checkbox */}
            <div className="flex items-end pb-1">
              <label className="flex items-center gap-2.5 cursor-pointer group">
                <input
                  type="checkbox"
                  checked={segmented}
                  onChange={(e) => setSegmented(e.target.checked)}
                  className="w-4 h-4 rounded border-neutral-600 bg-neutral-800 text-violet-500 focus:ring-violet-500 focus:ring-offset-0"
                />
                <div>
                  <span className="text-sm text-neutral-200 group-hover:text-neutral-100 transition-colors">
                    Segmented generation
                  </span>
                  <p className="text-xs text-neutral-500">
                    Generates each segment individually — better for advanced models
                  </p>
                </div>
              </label>
            </div>
          </div>

          <div className="flex items-center gap-3 pt-1">
            <Button variant="primary" size="lg" onClick={handleGenerate}>
              Generate Script
            </Button>
            {llmProvider && (
              <p className="text-xs text-neutral-500">
                Using: <span className="text-neutral-300">{providerLabel}</span>
                {" · "}
                <span className="text-neutral-300 font-mono">{activeModelLabel}</span>
                {llmProvider === "ollama" && (
                  <span className="text-amber-400"> (uses configured Ollama tag)</span>
                )}
              </p>
            )}
          </div>
        </div>

        </>
      )}

      {/* Loading state */}
      {loading && phase !== "refining" && (
        <div className="text-center py-12 space-y-4">
          <div className="inline-block w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-neutral-400 text-lg">
            {loadingText}
          </p>

          {/* Elapsed time */}
          {elapsedSeconds != null && (
            <p className="text-neutral-500 text-sm">
              {Math.floor(elapsedSeconds / 60)}:{String(Math.floor(elapsedSeconds % 60)).padStart(2, "0")} elapsed
              {phase === "script" && estimatedSeconds != null && estimatedSeconds > 0 && (
                <> / ~{Math.floor(estimatedSeconds / 60)}:{String(Math.floor(estimatedSeconds % 60)).padStart(2, "0")} estimated</>
              )}
            </p>
          )}

          {/* Per-segment progress (only during script phase) */}
          {phase === "script" && genSegments && genSegments.total > 1 && (
            <div className="max-w-sm mx-auto text-left space-y-1.5 py-2">
              {Array.from({ length: genSegments.total }, (_, i) => {
                const segNum = i + 1;
                const done = genCompletedSegments.includes(segNum);
                const active = genSegments.segment === segNum && !done;
                return (
                  <div key={i} className="flex items-center gap-2.5">
                    {done ? (
                      <svg className="w-4 h-4 text-emerald-400 shrink-0" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    ) : active ? (
                      <div className="w-4 h-4 border-2 border-violet-500 border-t-transparent rounded-full animate-spin shrink-0" />
                    ) : (
                      <div className="w-4 h-4 rounded-full border border-neutral-700 shrink-0" />
                    )}
                    <span className={`text-sm ${done ? "text-neutral-300" : active ? "text-neutral-200" : "text-neutral-600"}`}>
                      {format?.level_label === "level" ? `Level ${segNum}` : `Segment ${segNum}`}{active && genSegments.name ? `: ${genSegments.name}` : ""}
                    </span>
                  </div>
                );
              })}
            </div>
          )}

          {phase === "script" && !genSegments && (
            <div className="max-w-md mx-auto">
              <GenerationProgressBar estimatedSeconds={estimatedSeconds} active={loading} />
            </div>
          )}
          <button
            onClick={handleCancelGeneration}
            className="text-sm px-4 py-2 bg-neutral-800 border border-red-500/30 text-neutral-200 hover:border-red-500/50 rounded-lg font-medium transition-colors"
          >
            Cancel
          </button>
        </div>
      )}

      {/* Cold open selection */}
      {format?.supports_cold_open !== false && phase === "selecting" && coldOpenResult && !loading && (
        <ColdOpenSelector result={coldOpenResult} onSelect={handleColdOpenSelect} />
      )}

      {/* Refining phase — scoring + rewriting hook */}
      {phase === "refining" && (
        <div className="flex flex-col items-center gap-4 py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
          <p className="text-sm text-neutral-400">Refining your hook...</p>
          {elapsedSeconds != null && (
            <p className="text-xs text-neutral-600">{Math.round(elapsedSeconds)}s elapsed</p>
          )}
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Script preview */}
      {script && !loading && (
        <div className="space-y-6">
          {/* Stats bar */}
          <div className="flex gap-6 text-sm text-neutral-400 border-b border-neutral-800 pb-4">
            <span>
              <span className="text-neutral-100 font-medium">
                {script.segments.length}
              </span>{" "}
              {format?.level_label === "level"
                ? script.segments.length === 1 ? "level" : "levels"
                : script.segments.length === 1 ? "segment" : "segments"}
            </span>
            <span>
              <span className="text-neutral-100 font-medium">
                {totalScenes}
              </span>{" "}
              scenes
            </span>
            {saving && (
              <span className="text-violet-400 ml-auto">Saving...</span>
            )}
          </div>

          {/* Main Character setup (Eli-disabled projects) */}
          {mainCharacterRequired && projectConfig && (
            <div className="rounded-lg border border-neutral-800 bg-neutral-900 px-5 py-4 space-y-3">
              <div className="flex items-center justify-between gap-4">
                <h3 className="text-sm font-semibold text-neutral-200 uppercase tracking-wider">
                  Main Character
                </h3>
                {mainCharacterReady ? (
                  <span className="text-xs uppercase tracking-wide text-emerald-400">
                    Ready
                  </span>
                ) : (
                  <span className="text-xs uppercase tracking-wide text-amber-400">
                    Required before generating images
                  </span>
                )}
              </div>

              <div className="flex items-center gap-4">
                {projectConfig.main_character_reference_url ? (
                  <img
                    src={assetUrl(projectConfig.main_character_reference_url)}
                    alt="Main character reference"
                    className="w-32 aspect-video rounded-md border border-neutral-700 object-cover"
                  />
                ) : (
                  <div className="w-32 aspect-video rounded-md border border-dashed border-neutral-700 flex items-center justify-center text-[11px] text-neutral-500 text-center px-2">
                    No reference yet
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-neutral-300 truncate">
                    {projectConfig.main_character?.name?.trim() || "No character defined"}
                  </p>
                  <p className="text-xs text-neutral-500 mt-1">
                    Choose a main character and approve a reference image before
                    generating thumbnails or scene visuals.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setShowCharacterDrawer(true)}
                  className="px-4 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg text-sm font-medium transition-colors shrink-0"
                >
                  {mainCharacterReady ? "Edit" : "Set up"}
                </button>
              </div>
            </div>
          )}

          {/* Thumbnail & Title Slide generation */}
          {hasTitleCards && (
            <div className="rounded-lg border border-neutral-800 bg-neutral-900 px-5 py-4 space-y-3">
              <h3 className="text-sm font-semibold text-neutral-200 uppercase tracking-wider">
                Thumbnail & Title Slide
              </h3>

              {titleCardError && (
                <p className="text-sm text-red-400">{titleCardError}</p>
              )}

              {!titleCardGenerated && !titleCardGenerating && (
                <div className="space-y-2">
                  <button
                    onClick={() => generateTitleCards(false)}
                    disabled={!mainCharacterReady}
                    className="px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:bg-neutral-800 disabled:text-neutral-500 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition-colors"
                  >
                    Generate
                  </button>
                  {!mainCharacterReady && (
                    <p className="text-xs text-amber-400">
                      Set up the main character above before generating images.
                    </p>
                  )}
                </div>
              )}

              {titleCardGenerating && script && (
                <div className="space-y-1.5 py-1">
                  {script.segments.map((seg, idx) => {
                    const done = titleCardCompleted.includes(idx);
                    return (
                      <div key={idx} className="flex items-center gap-2.5">
                        {done ? (
                          <svg className="w-4 h-4 text-emerald-400 shrink-0" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                          </svg>
                        ) : (
                          <div className="w-4 h-4 border-2 border-violet-500 border-t-transparent rounded-full animate-spin shrink-0" />
                        )}
                        <span className={`text-sm ${done ? "text-neutral-300" : "text-neutral-500"}`}>
                          {seg.name}
                        </span>
                      </div>
                    );
                  })}
                  {titleCardCompleted.length === titleCardTotal && titleCardTotal > 0 && (
                    <div className="flex items-center gap-2.5 pt-1">
                      <div className="w-4 h-4 border-2 border-violet-500 border-t-transparent rounded-full animate-spin shrink-0" />
                      <span className="text-sm text-neutral-500">Compositing final images...</span>
                    </div>
                  )}
                </div>
              )}

              {titleCardGenerated && !titleCardGenerating && (
                <button
                  onClick={() => generateTitleCards(true)}
                  className="px-4 py-2 bg-neutral-800 hover:bg-neutral-700 rounded-lg text-sm font-medium transition-colors text-neutral-300 border border-neutral-700"
                >
                  Regenerate
                </button>
              )}
            </div>
          )}

          {/* Intro hook */}
          {(script.intro_hook || editingKey === "intro") && (
            <div
              className="bg-violet-500/10 border border-violet-500/20 rounded-lg px-4 py-3 cursor-pointer hover:border-violet-500/40 transition-colors"
              onClick={() => editingKey !== "intro" && startEditIntro()}
            >
              <p className="text-xs font-semibold text-violet-400 uppercase tracking-wider mb-1">
                Intro Hook
                {editingKey !== "intro" && (
                  <span className="ml-2 text-neutral-500 font-normal normal-case">
                    click to edit
                  </span>
                )}
              </p>
              {editingKey === "intro" ? (
                <div className="space-y-2" onClick={(e) => e.stopPropagation()}>
                  <textarea
                    className="w-full bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2 text-neutral-200 text-sm resize-none focus:outline-none focus:border-violet-500"
                    rows={2}
                    value={editHookText}
                    onChange={(e) => setEditHookText(e.target.value)}
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={saveIntroEdit}
                      className="text-xs px-3 py-1 bg-violet-600 hover:bg-violet-500 rounded-md transition-colors"
                    >
                      Save
                    </button>
                    <button
                      onClick={cancelEdit}
                      className="text-xs px-3 py-1 bg-neutral-700 hover:bg-neutral-600 rounded-md transition-colors text-neutral-300"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <p className="text-neutral-200 italic">
                  &ldquo;{script.intro_hook}&rdquo;
                </p>
              )}
            </div>
          )}

          {/* Segments */}
          {script.segments.map((segment, si) => (
            <div key={si} className="space-y-2">
              <h3 className="text-lg font-semibold text-violet-400 border-b border-neutral-800 pb-1">
                {si + 1}. {segment.name}
              </h3>
              <div className="space-y-2 pl-4">
                {segment.scenes.map((scene) => {
                  const sceneKey = `${si}-${scene.id}`;
                  const isEditing = editingKey === sceneKey;
                  const isRefining = refiningScene === scene.id;
                  const wasEdited = editedScenes.has(scene.id);

                  return (
                    <div
                      key={scene.id}
                      className={`rounded-lg border px-4 py-3 transition-colors ${
                        scene.is_title_card
                          ? "border-violet-500/30 bg-violet-500/5"
                          : isEditing
                            ? "border-violet-500/50 bg-neutral-900"
                            : "border-neutral-800 bg-neutral-900 cursor-pointer hover:border-neutral-600"
                      } ${isRefining ? "opacity-60" : ""}`}
                      onClick={() =>
                        !isEditing && !isRefining && startEditScene(si, scene)
                      }
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-mono text-neutral-500">
                          {scene.id}
                        </span>
                        {scene.is_title_card && (
                          <span className="text-xs bg-violet-500/20 text-violet-300 px-2 py-0.5 rounded-full">
                            title card
                          </span>
                        )}
                        {wasEdited && !isEditing && (
                          <span className="text-xs bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded-full">
                            edited
                          </span>
                        )}
                        {!isEditing && !isRefining && (
                          <span className="text-xs text-neutral-600">
                            click to edit
                          </span>
                        )}
                      </div>

                      {isRefining ? (
                        <div className="flex items-center gap-2 py-2">
                          <div className="w-4 h-4 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
                          <span className="text-sm text-neutral-400">
                            AI refining...
                          </span>
                        </div>
                      ) : isEditing ? (
                        <div
                          className="space-y-3"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <div>
                            <label className="text-xs text-neutral-500 mb-1 block">
                              Narration
                            </label>
                            <textarea
                              className="w-full bg-neutral-800 border border-neutral-700 rounded-md px-3 py-2 text-neutral-200 text-sm resize-none focus:outline-none focus:border-violet-500"
                              rows={4}
                              value={editNarration}
                              onChange={(e) => setEditNarration(e.target.value)}
                            />
                          </div>
                          <div className="flex gap-2">
                            <button
                              onClick={() => saveSceneEdit(si, scene.id)}
                              className="text-xs px-3 py-1.5 bg-violet-600 hover:bg-violet-500 rounded-md transition-colors"
                            >
                              Save
                            </button>
                            <button
                              onClick={cancelEdit}
                              className="text-xs px-3 py-1.5 bg-neutral-700 hover:bg-neutral-600 rounded-md transition-colors text-neutral-300"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <p className="text-neutral-200 text-sm leading-relaxed">
                            {scene.narration}
                          </p>
                          {wasEdited && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                refineScene(si, scene.id);
                              }}
                              className="mt-2 text-xs px-3 py-1 bg-violet-600/30 hover:bg-violet-600/50 text-violet-300 rounded-md transition-colors border border-violet-500/30"
                            >
                              AI Refine
                            </button>
                          )}
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}

          {/* Outro CTA */}
          {(script.outro_cta || editingKey === "outro") && (
            <div
              className="bg-violet-500/10 border border-violet-500/20 rounded-lg px-4 py-3 cursor-pointer hover:border-violet-500/40 transition-colors"
              onClick={() => editingKey !== "outro" && startEditOutro()}
            >
              <p className="text-xs font-semibold text-violet-400 uppercase tracking-wider mb-1">
                Outro CTA
                {editingKey !== "outro" && (
                  <span className="ml-2 text-neutral-500 font-normal normal-case">
                    click to edit
                  </span>
                )}
              </p>
              {editingKey === "outro" ? (
                <div className="space-y-2" onClick={(e) => e.stopPropagation()}>
                  <textarea
                    className="w-full bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2 text-neutral-200 text-sm resize-none focus:outline-none focus:border-violet-500"
                    rows={2}
                    value={editHookText}
                    onChange={(e) => setEditHookText(e.target.value)}
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={saveOutroEdit}
                      className="text-xs px-3 py-1 bg-violet-600 hover:bg-violet-500 rounded-md transition-colors"
                    >
                      Save
                    </button>
                    <button
                      onClick={cancelEdit}
                      className="text-xs px-3 py-1 bg-neutral-700 hover:bg-neutral-600 rounded-md transition-colors text-neutral-300"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <p className="text-neutral-200 italic">
                  &ldquo;{script.outro_cta}&rdquo;
                </p>
              )}
            </div>
          )}

          {/* Action buttons */}
          <div className="flex gap-3 pt-4 border-t border-neutral-800">
            <Button variant="primary" size="lg" onClick={() => scriptId && onContinue(scriptId)}>
              Continue to Timeline &rarr;
            </Button>
            <Button variant="secondary" size="lg" onClick={onBack}>
              Back to Ideas
            </Button>
          </div>
        </div>
      )}

      {showCharacterDrawer && projectConfig && scriptId && (
        <MainCharacterDrawer
          scriptId={scriptId}
          config={projectConfig}
          onClose={() => setShowCharacterDrawer(false)}
          onUpdated={(next) => setProjectConfig(next)}
        />
      )}
    </div>
  );
}
