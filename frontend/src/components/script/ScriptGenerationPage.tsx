import { useEffect, useRef, useState } from "react";
import api from "../../api";
import type { BrandProfile } from "../../types/brand";
import type { VideoIdea } from "../../types/idea";
import type {
  GenerateScriptResponse,
  Scene,
  ScriptContent,
} from "../../types/script";

interface Props {
  brand: BrandProfile;
  idea: VideoIdea;
  contentFormat?: "youtube" | "shortform";
  shortformPlatforms?: string[];
  onBack: () => void;
  onContinue: (scriptId: string) => void;
}

export default function ScriptGenerationPage({
  brand,
  idea,
  contentFormat = "youtube",
  shortformPlatforms = [],
  onBack,
  onContinue,
}: Props) {
  const [script, setScript] = useState<ScriptContent | null>(null);
  const [scriptId, setScriptId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Editing state
  const [editingKey, setEditingKey] = useState<string | null>(null); // "si-sceneId" or "intro" or "outro"
  const [editNarration, setEditNarration] = useState("");
  const [editOverlay, setEditOverlay] = useState("");
  const [editHookText, setEditHookText] = useState("");
  const [editedScenes, setEditedScenes] = useState<Set<string>>(new Set());
  const [refiningScene, setRefiningScene] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const hasStarted = useRef(false);

  useEffect(() => {
    if (hasStarted.current) return;
    hasStarted.current = true;

    let cancelled = false;

    const generate = async () => {
      setLoading(true);
      setError(null);
      try {
        const isShortform = contentFormat === "shortform";
        const url = isShortform ? "/api/scripts/generate-shortform" : "/api/scripts/generate";
        const body = isShortform
          ? {
              topic: idea.title,
              description: idea.description,
              brand_id: brand.id,
              platforms: shortformPlatforms,
              target_duration_seconds: 40,
            }
          : {
              topic: idea.title,
              description: idea.description,
              brand_id: brand.id,
              segment_count: idea.segments_est > 0 ? idea.segments_est : undefined,
              animated_scene_count: 5,
            };

        const res = await api.post(url, body);
        if (cancelled) return;
        if (res.ok) {
          const data = res.data as GenerateScriptResponse;
          setScript(data.script);
          setScriptId(data.id);
        } else {
          const err = res.data as { detail?: string };
          setError(err.detail ?? "Failed to generate script");
        }
      } catch {
        if (!cancelled) setError("Could not reach the backend. Is it running?");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    generate();
    return () => {
      cancelled = true;
    };
  }, [brand.id, idea.title, idea.description, idea.segments_est, contentFormat, shortformPlatforms]);

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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={onBack}
          className="text-sm px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 rounded-lg transition-colors text-neutral-300"
        >
          &larr; Back to Ideas
        </button>
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-bold">{idea.title}</h2>
            {contentFormat === "shortform" && (
              <span className="text-xs bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded-full font-medium">
                Short-Form
              </span>
            )}
          </div>
          <p className="text-sm text-neutral-400">{idea.description}</p>
        </div>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="text-center py-20 space-y-4">
          <div className="inline-block w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-neutral-400 text-lg">
            Generating {contentFormat === "shortform" ? "short-form" : ""} script with Claude...
          </p>
          <p className="text-neutral-500 text-sm">
            {contentFormat === "shortform"
              ? "This may take 1-2 minutes for a short-form script."
              : "This may take 3-5 minutes for a full segmented script."}
          </p>
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
            {contentFormat === "shortform" ? (
              <span>
                ~
                <span className={`font-medium ${totalDuration <= 45 ? "text-emerald-400" : totalDuration <= 60 ? "text-yellow-400" : "text-red-400"}`}>
                  {Math.round(totalDuration)}
                </span>{" "}
                sec
              </span>
            ) : (
              <span>
                ~
                <span className="text-neutral-100 font-medium">
                  {Math.round(totalDuration / 60)}
                </span>{" "}
                min estimated
              </span>
            )}
            {saving && (
              <span className="text-violet-400 ml-auto">Saving...</span>
            )}
          </div>

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
              Continue to Storyboard &rarr;
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
