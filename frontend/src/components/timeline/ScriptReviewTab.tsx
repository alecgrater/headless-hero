import { useMemo, useState, type ReactNode } from "react";
import { Copy } from "lucide-react";
import type { Scene, ScriptContent, VisualMode } from "../../types/script";
import { showToast } from "../ToastContainer";
import { SEGMENT_COLORS } from "./constants";

interface ScriptReviewTabProps {
  content: ScriptContent;
  title: string;
}

// "Different formats" the script can be read in. Each view is a density preset:
// Reading = narration-only prose, Screenplay = scene-by-scene beats, Detail = everything.
type ReviewView = "reading" | "screenplay" | "detail";

// Independent metadata layers the reader can toggle on/off regardless of view.
interface MetaToggles {
  segmentTitles: boolean;
  sceneIds: boolean;
  durations: boolean;
  visualPrompts: boolean;
  visualModes: boolean;
  hookCta: boolean;
  ttsText: boolean;
  titleCards: boolean;
}

const VIEW_OPTIONS: { key: ReviewView; label: string; hint: string }[] = [
  { key: "reading", label: "Reading", hint: "Narration as continuous prose — the teleprompter read." },
  { key: "screenplay", label: "Screenplay", hint: "Scene-by-scene beats with labels and timing." },
  { key: "detail", label: "Full Detail", hint: "Every field on every scene, including visual prompts." },
];

// Switching view resets the metadata toggles to that view's sensible defaults.
const VIEW_DEFAULTS: Record<ReviewView, MetaToggles> = {
  reading: {
    segmentTitles: true,
    sceneIds: false,
    durations: false,
    visualPrompts: false,
    visualModes: false,
    hookCta: true,
    ttsText: false,
    titleCards: true,
  },
  screenplay: {
    segmentTitles: true,
    sceneIds: true,
    durations: true,
    visualPrompts: false,
    visualModes: true,
    hookCta: true,
    ttsText: false,
    titleCards: true,
  },
  detail: {
    segmentTitles: true,
    sceneIds: true,
    durations: true,
    visualPrompts: true,
    visualModes: true,
    hookCta: true,
    ttsText: true,
    titleCards: true,
  },
};

const TOGGLE_OPTIONS: { key: keyof MetaToggles; label: string; hint: string }[] = [
  { key: "segmentTitles", label: "Segment titles", hint: "Show the segment heading before each block of scenes." },
  { key: "titleCards", label: "Title cards", hint: "Include title-card scenes in the read." },
  { key: "sceneIds", label: "Scene IDs", hint: "Show each scene's raw identifier." },
  { key: "durations", label: "Durations", hint: "Show per-scene length (voiced duration when available)." },
  { key: "visualModes", label: "Visual modes", hint: "Show how each scene is rendered." },
  { key: "visualPrompts", label: "Visual prompts", hint: "Show the image/video prompt for each scene." },
  { key: "ttsText", label: "TTS text", hint: "Show the voiceover text when it differs from narration." },
  { key: "hookCta", label: "Hook & CTA", hint: "Show the intro hook and outro CTA framing." },
];

const VISUAL_MODE_LABELS: Record<VisualMode, string> = {
  full_frame: "Full frame",
  multi_frame: "Multi-frame",
  continuous: "Continuous",
  video: "AI video",
  popup_sequence: "Popup sequence",
  comparison_board: "Comparison board",
  captions: "Captions",
  stat_card: "Stat card",
  blink: "Full frame",
};

function visualModeLabel(scene: Scene): string {
  if (scene.is_title_card) return "Title card";
  const mode = scene.visual_mode ?? "full_frame";
  return VISUAL_MODE_LABELS[mode] ?? mode;
}

function sceneDuration(scene: Scene): number {
  return scene.audio_duration_seconds ?? scene.duration_estimate_seconds ?? 0;
}

function formatDuration(seconds: number): string {
  const safe = Math.max(0, Math.round(seconds));
  if (safe < 60) return `${safe}s`;
  const minutes = Math.floor(safe / 60);
  const rem = safe % 60;
  return `${minutes}:${rem.toString().padStart(2, "0")}`;
}

function countWords(text: string | undefined | null): number {
  if (!text) return 0;
  return text.split(/\s+/).filter(Boolean).length;
}

export default function ScriptReviewTab({ content, title }: ScriptReviewTabProps) {
  const [view, setView] = useState<ReviewView>("reading");
  const [toggles, setToggles] = useState<MetaToggles>(VIEW_DEFAULTS.reading);

  const handleSelectView = (next: ReviewView) => {
    setView(next);
    setToggles(VIEW_DEFAULTS[next]);
  };

  const handleToggle = (key: keyof MetaToggles) => {
    setToggles((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  // Flatten segments → scenes, honoring the title-card filter, with a global index.
  const visibleSegments = useMemo(() => {
    let globalIndex = 0;
    return content.segments.map((segment, segIdx) => {
      const scenes = segment.scenes
        .filter((scene) => toggles.titleCards || !scene.is_title_card)
        .map((scene) => ({ scene, number: ++globalIndex }));
      return { name: segment.name, segIdx, scenes };
    });
  }, [content.segments, toggles.titleCards]);

  const stats = useMemo(() => {
    const allScenes = content.segments.flatMap((seg) => seg.scenes);
    const words = allScenes.reduce((sum, sc) => sum + countWords(sc.narration), 0);
    const duration = allScenes.reduce((sum, sc) => sum + sceneDuration(sc), 0);
    return {
      segments: content.segments.length,
      scenes: allScenes.length,
      words,
      duration,
    };
  }, [content.segments]);

  const handleCopy = async () => {
    const text = serializeScript(content, title, toggles, visibleSegments);
    try {
      await navigator.clipboard.writeText(text);
      showToast("Script copied to clipboard.", "success");
    } catch {
      showToast("Could not copy to clipboard.");
    }
  };

  const isEmpty = stats.scenes === 0;

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Toolbar */}
      <div className="shrink-0 border-b border-neutral-800/70 px-5 py-3 space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="min-w-0">
            <h2 className="text-base font-semibold tracking-tight text-neutral-100">Review</h2>
            <p className="text-xs text-neutral-500">
              {stats.segments} segments · {stats.scenes} scenes · {stats.words.toLocaleString()} words ·{" "}
              {formatDuration(stats.duration)}
            </p>
          </div>

          {/* View segmented control */}
          <div className="ml-auto inline-flex rounded-lg border border-neutral-800 bg-neutral-950/60 p-0.5">
            {VIEW_OPTIONS.map((option) => {
              const active = view === option.key;
              return (
                <button
                  key={option.key}
                  type="button"
                  onClick={() => handleSelectView(option.key)}
                  title={option.hint}
                  aria-pressed={active}
                  className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                    active
                      ? "bg-violet-500/20 text-violet-100"
                      : "text-neutral-400 hover:bg-neutral-800/60 hover:text-neutral-200"
                  }`}
                >
                  {option.label}
                </button>
              );
            })}
          </div>

          <button
            type="button"
            onClick={() => void handleCopy()}
            disabled={isEmpty}
            title="Copy the current view as plain text"
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-neutral-700/60 bg-neutral-800/80 px-3 py-1.5 text-xs font-medium text-neutral-300 transition-colors hover:border-neutral-600 hover:bg-neutral-700/80 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Copy className="h-3.5 w-3.5" />
            Copy
          </button>
        </div>

        {/* Metadata toggle chips */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-[11px] font-medium uppercase tracking-wide text-neutral-600">Show</span>
          {TOGGLE_OPTIONS.map((option) => {
            const active = toggles[option.key];
            return (
              <button
                key={option.key}
                type="button"
                onClick={() => handleToggle(option.key)}
                title={option.hint}
                aria-pressed={active}
                className={`rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors ${
                  active
                    ? "border-violet-500/40 bg-violet-500/15 text-violet-100"
                    : "border-neutral-800 bg-neutral-950/50 text-neutral-500 hover:border-neutral-700 hover:text-neutral-300"
                }`}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-5 py-5">
        {isEmpty ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-neutral-600">No scenes in this script yet.</p>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-8">
            {toggles.hookCta && content.intro_hook && (
              <FramingBlock label="Intro hook" text={content.intro_hook} />
            )}

            {visibleSegments.map((segment) =>
              segment.scenes.length === 0 ? null : (
                <section key={segment.segIdx} className="space-y-3">
                  {toggles.segmentTitles && (
                    <div className="flex items-center gap-2 border-b border-neutral-800/60 pb-2">
                      <span
                        className={`h-2.5 w-2.5 shrink-0 rounded-full ${
                          SEGMENT_COLORS[segment.segIdx % SEGMENT_COLORS.length]
                        }`}
                      />
                      <h3 className="text-sm font-bold text-neutral-100">
                        {segment.segIdx + 1}. {segment.name}
                      </h3>
                      <span className="text-xs text-neutral-500">{segment.scenes.length} scenes</span>
                    </div>
                  )}

                  {view === "reading" ? (
                    <div className="space-y-4">
                      {segment.scenes.map(({ scene, number }) => (
                        <ReadingScene key={scene.id} scene={scene} number={number} toggles={toggles} />
                      ))}
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {segment.scenes.map(({ scene, number }) => (
                        <SceneCard
                          key={scene.id}
                          scene={scene}
                          number={number}
                          toggles={toggles}
                          detailed={view === "detail"}
                        />
                      ))}
                    </div>
                  )}
                </section>
              ),
            )}

            {toggles.hookCta && content.outro_cta && (
              <FramingBlock label="Outro CTA" text={content.outro_cta} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function FramingBlock({ label, text }: { label: string; text: string }) {
  return (
    <div className="rounded-xl border border-violet-500/30 bg-violet-500/5 px-4 py-3">
      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-violet-300/80">{label}</p>
      <p className="text-sm leading-relaxed text-neutral-200">{text}</p>
    </div>
  );
}

function MetaRow({ scene, number, toggles }: { scene: Scene; number: number; toggles: MetaToggles }) {
  const showMode = toggles.visualModes || scene.is_title_card;
  return (
    <div className="flex flex-wrap items-center gap-2 text-[11px] text-neutral-500">
      <span className="font-mono text-neutral-400">#{number}</span>
      {toggles.sceneIds && <span className="font-mono text-neutral-600">{scene.id}</span>}
      {showMode && (
        <span
          className={`rounded px-1.5 py-0.5 font-medium ${
            scene.is_title_card ? "bg-violet-500/20 text-violet-300" : "bg-neutral-800 text-neutral-300"
          }`}
        >
          {visualModeLabel(scene)}
        </span>
      )}
      {toggles.durations && <span className="tabular-nums">{formatDuration(sceneDuration(scene))}</span>}
    </div>
  );
}

function ReadingScene({ scene, number, toggles }: { scene: Scene; number: number; toggles: MetaToggles }) {
  const anyMeta = toggles.sceneIds || toggles.durations || toggles.visualModes || scene.is_title_card;
  const text = scene.narration || scene.caption_text || "";
  return (
    <div className="space-y-1">
      {anyMeta && <MetaRow scene={scene} number={number} toggles={toggles} />}
      <p
        className={`leading-relaxed ${
          scene.is_title_card
            ? "text-sm font-medium italic text-neutral-400"
            : "text-[15px] text-neutral-200"
        }`}
      >
        {text || <span className="text-neutral-600">(no narration)</span>}
      </p>
    </div>
  );
}

function SceneCard({
  scene,
  number,
  toggles,
  detailed,
}: {
  scene: Scene;
  number: number;
  toggles: MetaToggles;
  detailed: boolean;
}) {
  const showTts =
    toggles.ttsText && scene.tts_narration && scene.tts_narration.trim() !== (scene.narration ?? "").trim();
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900/60 p-3.5">
      <MetaRow scene={scene} number={number} toggles={toggles} />
      <p className="mt-2 text-sm leading-relaxed text-neutral-200">
        {scene.narration || <span className="text-neutral-600">(no narration)</span>}
      </p>

      {showTts && (
        <div className="mt-2 rounded-md border border-neutral-800/80 bg-neutral-950/50 px-2.5 py-2">
          <p className="mb-0.5 text-[10px] font-semibold uppercase tracking-wide text-neutral-600">TTS text</p>
          <p className="text-xs leading-relaxed text-neutral-400">{scene.tts_narration}</p>
        </div>
      )}

      {detailed && (scene.caption_text || scene.caption_emphasis) && (
        <DetailField label="Caption">
          {scene.caption_text}
          {scene.caption_emphasis && (
            <span className="ml-1 font-semibold text-rose-400">{scene.caption_emphasis}</span>
          )}
        </DetailField>
      )}

      {detailed && (scene.stat_value || scene.stat_label) && (
        <DetailField label="Stat">
          <span className="font-semibold text-neutral-200">{scene.stat_value}</span>
          {scene.stat_label && <span className="ml-1 text-neutral-400">{scene.stat_label}</span>}
        </DetailField>
      )}

      {toggles.visualPrompts && scene.visual_prompt && (
        <DetailField label="Visual prompt">{scene.visual_prompt}</DetailField>
      )}
    </div>
  );
}

function DetailField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="mt-2.5 border-t border-neutral-800/60 pt-2">
      <p className="mb-0.5 text-[10px] font-semibold uppercase tracking-wide text-neutral-600">{label}</p>
      <p className="text-xs leading-relaxed text-neutral-400">{children}</p>
    </div>
  );
}

function serializeScript(
  content: ScriptContent,
  title: string,
  toggles: MetaToggles,
  visibleSegments: { name: string; segIdx: number; scenes: { scene: Scene; number: number }[] }[],
): string {
  const lines: string[] = [];
  if (title) {
    lines.push(title, "=".repeat(title.length), "");
  }
  if (toggles.hookCta && content.intro_hook) {
    lines.push("[INTRO HOOK]", content.intro_hook, "");
  }

  for (const segment of visibleSegments) {
    if (segment.scenes.length === 0) continue;
    if (toggles.segmentTitles) {
      lines.push(`## ${segment.segIdx + 1}. ${segment.name}`, "");
    }
    for (const { scene, number } of segment.scenes) {
      const metaParts: string[] = [`#${number}`];
      if (toggles.sceneIds) metaParts.push(scene.id);
      if (toggles.visualModes || scene.is_title_card) metaParts.push(visualModeLabel(scene));
      if (toggles.durations) metaParts.push(formatDuration(sceneDuration(scene)));
      if (metaParts.length > 1 || toggles.durations || toggles.visualModes || toggles.sceneIds) {
        lines.push(`[${metaParts.join(" · ")}]`);
      }
      lines.push(scene.narration || "(no narration)");
      if (
        toggles.ttsText &&
        scene.tts_narration &&
        scene.tts_narration.trim() !== (scene.narration ?? "").trim()
      ) {
        lines.push(`TTS: ${scene.tts_narration}`);
      }
      if (toggles.visualPrompts && scene.visual_prompt) {
        lines.push(`Visual: ${scene.visual_prompt}`);
      }
      lines.push("");
    }
  }

  if (toggles.hookCta && content.outro_cta) {
    lines.push("[OUTRO CTA]", content.outro_cta, "");
  }

  return lines.join("\n").trim() + "\n";
}
