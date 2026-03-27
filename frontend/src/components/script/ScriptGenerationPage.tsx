import { useEffect, useState } from "react";
import api from "../../api";
import type { BrandProfile } from "../../types/brand";
import type { VideoIdea } from "../../types/idea";
import type { GenerateScriptResponse, ScriptContent } from "../../types/script";

interface Props {
  brand: BrandProfile;
  idea: VideoIdea;
  onBack: () => void;
  onContinue: (scriptId: string) => void;
}

export default function ScriptGenerationPage({
  brand,
  idea,
  onBack,
  onContinue,
}: Props) {
  const [script, setScript] = useState<ScriptContent | null>(null);
  const [scriptId, setScriptId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const generate = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.post("/api/scripts/generate", {
          topic: idea.title,
          description: idea.description,
          brand_id: brand.id,
          segment_count: idea.segments_est > 0 ? idea.segments_est : undefined,
        });
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
  }, [brand.id, idea.title, idea.description, idea.segments_est]);

  const totalScenes = script
    ? script.segments.reduce((sum, seg) => sum + seg.scenes.length, 0)
    : 0;
  const totalDuration = script
    ? script.segments.reduce(
        (sum, seg) =>
          sum +
          seg.scenes.reduce((s, sc) => s + sc.duration_estimate_seconds, 0),
        0
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
          <h2 className="text-2xl font-bold">{idea.title}</h2>
          <p className="text-sm text-neutral-400">{idea.description}</p>
        </div>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="text-center py-20 space-y-4">
          <div className="inline-block w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-neutral-400 text-lg">
            Generating script with Claude...
          </p>
          <p className="text-neutral-500 text-sm">
            This may take 15-30 seconds for a full segmented script.
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
              segments
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
          </div>

          {/* Intro hook */}
          {script.intro_hook && (
            <div className="bg-violet-500/10 border border-violet-500/20 rounded-lg px-4 py-3">
              <p className="text-xs font-semibold text-violet-400 uppercase tracking-wider mb-1">
                Intro Hook
              </p>
              <p className="text-neutral-200 italic">
                &ldquo;{script.intro_hook}&rdquo;
              </p>
            </div>
          )}

          {/* Segments */}
          {script.segments.map((segment, si) => (
            <div key={si} className="space-y-2">
              <h3 className="text-lg font-semibold text-violet-400 border-b border-neutral-800 pb-1">
                {si + 1}. {segment.name}
              </h3>
              <div className="space-y-2 pl-4">
                {segment.scenes.map((scene) => (
                  <div
                    key={scene.id}
                    className={`rounded-lg border px-4 py-3 ${
                      scene.is_title_card
                        ? "border-violet-500/30 bg-violet-500/5"
                        : "border-neutral-800 bg-neutral-900"
                    }`}
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
                      <span className="text-xs text-neutral-500 ml-auto">
                        {scene.duration_estimate_seconds}s
                      </span>
                    </div>
                    <p className="text-neutral-200 text-sm leading-relaxed">
                      {scene.narration}
                    </p>
                    {scene.text_overlay && (
                      <p className="text-xs text-amber-400/80 mt-1">
                        Overlay: {scene.text_overlay}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}

          {/* Outro CTA */}
          {script.outro_cta && (
            <div className="bg-violet-500/10 border border-violet-500/20 rounded-lg px-4 py-3">
              <p className="text-xs font-semibold text-violet-400 uppercase tracking-wider mb-1">
                Outro CTA
              </p>
              <p className="text-neutral-200 italic">
                &ldquo;{script.outro_cta}&rdquo;
              </p>
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
