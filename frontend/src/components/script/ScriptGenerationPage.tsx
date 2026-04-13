import { useEffect, useRef, useState } from "react";
import api, { assetUrl, fetchGenerationEstimate } from "../../api";
import type { VideoIdea } from "../../types/idea";
import type {
  GenerateScriptResponse,
  Scene,
  ScriptContent,
} from "../../types/script";
import { SCRIPT_MODELS } from "../settings/GeneralSection";
import GenerationProgressBar from "../GenerationProgressBar";

const DEFAULT_MODEL = "anthropic.claude-opus-4-6-v1";

interface Props {
  brandId: string;
  idea: VideoIdea;
  onBack: () => void;
  onContinue: (scriptId: string) => void;
}

export default function ScriptGenerationPage({
  brandId,
  idea,
  onBack,
  onContinue,
}: Props) {
  const [script, setScript] = useState<ScriptContent | null>(null);
  const [scriptId, setScriptId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Pre-generation options
  const [selectedModel, setSelectedModel] = useState(DEFAULT_MODEL);
  const [segmented, setSegmented] = useState(false);
  const [generationStarted, setGenerationStarted] = useState(false);
  const [settingsLoaded, setSettingsLoaded] = useState(false);

  // Editing state
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editNarration, setEditNarration] = useState("");
  const [editOverlay, setEditOverlay] = useState("");
  const [editHookText, setEditHookText] = useState("");
  const [editedScenes, setEditedScenes] = useState<Set<string>>(new Set());
  const [refiningScene, setRefiningScene] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [estimatedSeconds, setEstimatedSeconds] = useState<number | null>(null);
  const cancelledRef = useRef(false);

  // Title card generation state
  const [titleCardGenerating, setTitleCardGenerating] = useState(false);
  const [titleCardGenerated, setTitleCardGenerated] = useState(false);
  const [titleCardTimestamp, setTitleCardTimestamp] = useState(0);
  const [titleCardError, setTitleCardError] = useState<string | null>(null);
  const [titleCardCompleted, setTitleCardCompleted] = useState<number[]>([]);
  const [titleCardTotal, setTitleCardTotal] = useState(0);
  const titleCardPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load default model from settings
  useEffect(() => {
    api.get("/api/settings/keys").then((res) => {
      if (res.ok) {
        const data = res.data as Record<string, { masked: string }>;
        const saved = data?.SCRIPT_MODEL?.masked;
        if (saved) {
          setSelectedModel(saved);
          if (saved !== DEFAULT_MODEL) {
            setSegmented(true);
          }
        }
      }
      setSettingsLoaded(true);
    }).catch(() => setSettingsLoaded(true));
  }, []);

  const handleModelChange = (value: string) => {
    setSelectedModel(value);
    if (value !== DEFAULT_MODEL) {
      setSegmented(true);
    }
  };

  const handleGenerate = async () => {
    cancelledRef.current = false;
    setGenerationStarted(true);
    setLoading(true);
    setError(null);
    fetchGenerationEstimate("script_generation_youtube")
      .then((est) => setEstimatedSeconds(est.average_seconds))
      .catch(() => setEstimatedSeconds(null));

    let succeeded = false;
    try {
      const res = await api.post("/api/scripts/generate", {
        topic: idea.title,
        description: idea.description,
        brand_id: brandId,
        segment_count: idea.segments_est > 0 ? idea.segments_est : undefined,
        animated_scene_count: 5,
        model: selectedModel !== DEFAULT_MODEL ? selectedModel : undefined,
        segmented,
      });
      if (cancelledRef.current) return;
      if (res.ok) {
        const data = res.data as GenerateScriptResponse;
        setScript(data.script);
        setScriptId(data.id);
        succeeded = true;
      } else {
        console.error("[ScriptGeneration] API error:", res.status, res.data);
        const detail =
          res.data && typeof res.data === "object" && "detail" in res.data
            ? (res.data as { detail: string }).detail
            : res.data && typeof res.data === "object" && "error" in res.data
              ? (res.data as { error: string }).error
              : undefined;
        setError(detail ?? "Failed to generate script");
      }
    } catch (err) {
      if (!cancelledRef.current) {
        console.error("[ScriptGeneration] Request failed:", err);
        setError("Could not reach the backend. Is it running?");
      }
    } finally {
      setLoading(false);
    }

    // Recovery: if the request failed, check if the script was actually created on the backend
    // Retry after a delay in case the backend is still finishing (e.g., timeout during long generation)
    if (!succeeded) {
      for (const delay of [0, 30_000]) {
        if (delay) await new Promise((r) => setTimeout(r, delay));
        try {
          const listRes = await api.get("/api/scripts");
          if (listRes.ok) {
            const scripts = listRes.data as Array<{ id: string; topic_title: string }>;
            const match = scripts.find((s) => s.topic_title === idea.title);
            if (match) {
              const fullRes = await api.get(`/api/scripts/${match.id}`);
              if (fullRes.ok) {
                const data = fullRes.data as { id: string; script: ScriptContent };
                setScript(data.script);
                setScriptId(data.id);
                setError(null);
                console.info("[ScriptGeneration] Recovered script from backend:", match.id);
                break;
              }
            }
          }
        } catch {
          // Recovery failed — keep showing the original error
        }
      }
    }
  };

  const handleCancelGeneration = () => {
    cancelledRef.current = true;
    setLoading(false);
  };

  const saveScript = async (updated: ScriptContent) => {
    if (!scriptId) return;
    setSaving(true);
    await api.put(`/api/scripts/${scriptId}`, { script: updated });
    setSaving(false);
  };

  const startEditScene = (si: number, scene: Scene) => {
    const key = `${si}-${scene.id}`;
    setEditingKey(key);
    setEditNarration(scene.narration);
    setEditOverlay(scene.text_overlay);
  };

  const cancelEdit = () => {
    setEditingKey(null);
  };

  const saveSceneEdit = async (si: number, sceneId: string) => {
    if (!script) return;
    const updated = structuredClone(script);
    const scene = updated.segments[si].scenes.find((s) => s.id === sceneId);
    if (!scene) return;
    scene.narration = editNarration;
    scene.text_overlay = editOverlay;
    setScript(updated);
    setEditingKey(null);
    setEditedScenes((prev) => new Set(prev).add(sceneId));
    await saveScript(updated);
  };

  const startEditIntro = () => {
    if (!script) return;
    setEditingKey("intro");
    setEditHookText(script.intro_hook);
  };

  const saveIntroEdit = async () => {
    if (!script) return;
    const updated = { ...script, intro_hook: editHookText };
    setScript(updated);
    setEditingKey(null);
    await saveScript(updated);
  };

  const startEditOutro = () => {
    if (!script) return;
    setEditingKey("outro");
    setEditHookText(script.outro_cta);
  };

  const saveOutroEdit = async () => {
    if (!script) return;
    const updated = { ...script, outro_cta: editHookText };
    setScript(updated);
    setEditingKey(null);
    await saveScript(updated);
  };

  const refineScene = async (si: number, sceneId: string) => {
    if (!script || !scriptId) return;
    setRefiningScene(sceneId);
    try {
      const res = await api.post(`/api/scripts/${scriptId}/refine-scene`, {
        segment_index: si,
        scene_id: sceneId,
      });
      if (res.ok) {
        const { scene } = res.data as { scene: Scene };
        const updated = structuredClone(script);
        const idx = updated.segments[si].scenes.findIndex(
          (s) => s.id === sceneId,
        );
        if (idx !== -1) {
          updated.segments[si].scenes[idx] = scene;
          setScript(updated);
          setEditedScenes((prev) => {
            const next = new Set(prev);
            next.delete(sceneId);
            return next;
          });
          await saveScript(updated);
        }
      }
    } finally {
      setRefiningScene(null);
    }
  };

  const totalScenes = script
    ? script.segments.reduce((sum, seg) => sum + seg.scenes.length, 0)
    : 0;
  const totalDuration = script
    ? script.segments.reduce(
        (sum, seg) =>
          sum +
          seg.scenes.reduce((s, sc) => s + sc.duration_estimate_seconds, 0),
        0,
      )
    : 0;

  const hasTitleCards = true;

  const generateTitleCards = async (force: boolean) => {
    if (!scriptId || !script) return;
    setTitleCardGenerating(true);
    setTitleCardError(null);
    setTitleCardCompleted([]);
    setTitleCardTotal(script.segments.length);

    try {
      const res = await api.post("/api/visuals/generate-title-cards", {
        script_id: scriptId,
        force,
      });
      if (!res.ok) {
        const err = res.data as { detail?: string };
        setTitleCardError(err.detail ?? "Failed to generate title cards");
        setTitleCardGenerating(false);
        return;
      }

      const { job_id } = res.data as { job_id: string };

      // Poll for progress
      titleCardPollRef.current = setInterval(async () => {
        try {
          const statusRes = await api.get(`/api/visuals/title-cards-status/${job_id}`);
          if (!statusRes.ok) return;

          const job = statusRes.data as {
            status: string;
            current_step: string;
            error: string | null;
          };

          // Parse per-segment progress from current_step
          if (job.current_step) {
            try {
              const progress = JSON.parse(job.current_step) as {
                completed: number[];
                total: number;
                names: string[];
              };
              setTitleCardCompleted(progress.completed);
              setTitleCardTotal(progress.total);
            } catch {
              // current_step may be "Complete" or non-JSON
            }
          }

          if (job.status === "completed") {
            if (titleCardPollRef.current) clearInterval(titleCardPollRef.current);
            titleCardPollRef.current = null;
            setTitleCardGenerating(false);
            setTitleCardGenerated(true);
            setTitleCardTimestamp(Date.now());
          } else if (job.status === "failed") {
            if (titleCardPollRef.current) clearInterval(titleCardPollRef.current);
            titleCardPollRef.current = null;
            setTitleCardGenerating(false);
            setTitleCardError(job.error ?? "Title card generation failed");
          }
        } catch {
          // Network error during poll — ignore, will retry
        }
      }, 1000);
    } catch {
      setTitleCardError("Could not reach the backend.");
      setTitleCardGenerating(false);
    }
  };

  // Cleanup poll interval on unmount
  useEffect(() => {
    return () => {
      if (titleCardPollRef.current) clearInterval(titleCardPollRef.current);
    };
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="space-y-1">
        <button
          onClick={onBack}
          className="text-sm text-neutral-400 hover:text-neutral-200 transition-colors"
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
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-violet-500 transition-colors"
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

          <button
            onClick={handleGenerate}
            className="px-5 py-2.5 bg-violet-600 hover:bg-violet-500 rounded-lg font-medium transition-colors"
          >
            Generate Script
          </button>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="text-center py-12 space-y-4">
          <div className="inline-block w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-neutral-400 text-lg">
            Generating script with Claude...
          </p>
          <div className="max-w-md mx-auto">
            <GenerationProgressBar estimatedSeconds={estimatedSeconds} active={loading} />
          </div>
          <button
            onClick={handleCancelGeneration}
            className="text-sm px-4 py-2 bg-neutral-800 border border-red-500/30 text-neutral-200 hover:border-red-500/50 rounded-lg font-medium transition-colors"
          >
            Cancel
          </button>
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
              {script.segments.length === 1 ? "segment" : "segments"}
            </span>
            <span>
              <span className="text-neutral-100 font-medium">
                {totalScenes}
              </span>{" "}
              scenes
            </span>
            <span>
              ~
              <span className="text-neutral-100 font-medium">
                {Math.round(totalDuration / 60)}
              </span>{" "}
              min estimated
            </span>
            {saving && (
              <span className="text-violet-400 ml-auto">Saving...</span>
            )}
          </div>

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
                <button
                  onClick={() => generateTitleCards(false)}
                  className="px-4 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg text-sm font-medium transition-colors"
                >
                  Generate
                </button>
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
                <>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs text-neutral-500 mb-1.5">Thumbnail (with title)</p>
                      <img
                        src={assetUrl(`/static/projects/${scriptId}/images/composite_title_card.png`) + `?t=${titleCardTimestamp}`}
                        alt="Thumbnail"
                        className="w-full rounded-lg border border-neutral-700"
                      />
                    </div>
                    <div>
                      <p className="text-xs text-neutral-500 mb-1.5">Title Slide (no title)</p>
                      <img
                        src={assetUrl(`/static/projects/${scriptId}/images/composite_title_card_notitle.png`) + `?t=${titleCardTimestamp}`}
                        alt="Title Slide"
                        className="w-full rounded-lg border border-neutral-700"
                      />
                    </div>
                  </div>
                  <button
                    onClick={() => generateTitleCards(true)}
                    className="px-4 py-2 bg-neutral-800 hover:bg-neutral-700 rounded-lg text-sm font-medium transition-colors text-neutral-300 border border-neutral-700"
                  >
                    Regenerate
                  </button>
                </>
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
                        <span className="text-xs text-neutral-500 ml-auto">
                          {scene.duration_estimate_seconds}s
                        </span>
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
                          <div>
                            <label className="text-xs text-neutral-500 mb-1 block">
                              Text Overlay
                            </label>
                            <input
                              type="text"
                              className="w-full bg-neutral-800 border border-neutral-700 rounded-md px-3 py-2 text-neutral-200 text-sm focus:outline-none focus:border-violet-500"
                              value={editOverlay}
                              onChange={(e) => setEditOverlay(e.target.value)}
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
                          {scene.text_overlay && (
                            <p className="text-xs text-amber-400/80 mt-1">
                              Overlay: {scene.text_overlay}
                            </p>
                          )}
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
            <button
              onClick={() => scriptId && onContinue(scriptId)}
              className="px-5 py-2.5 bg-violet-600 hover:bg-violet-500 rounded-lg font-medium transition-colors"
            >
              Continue to Timeline &rarr;
            </button>
            <button
              onClick={onBack}
              className="px-5 py-2.5 bg-neutral-800 hover:bg-neutral-700 rounded-lg font-medium transition-colors text-neutral-300"
            >
              Back to Ideas
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
