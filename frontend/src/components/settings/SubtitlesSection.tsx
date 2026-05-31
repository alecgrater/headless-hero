import { Check, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import api from "../../api";
import { showToast } from "../ToastContainer";

export type SubtitleCoverageMode = "all" | "punchy";
export type EnabledSubtitleStyle = "clean" | "kinetic" | "burst";

type SettingRows = Record<string, { masked?: string }>;

interface SubtitleSettingsState {
  coverage: SubtitleCoverageMode;
  enabledStyles: EnabledSubtitleStyle[];
}

const STYLE_KEYS: Record<EnabledSubtitleStyle, string> = {
  clean: "SUBTITLE_STYLE_CLEAN_ENABLED",
  kinetic: "SUBTITLE_STYLE_KINETIC_ENABLED",
  burst: "SUBTITLE_STYLE_BURST_ENABLED",
};

const STYLE_OPTIONS: Array<{
  id: EnabledSubtitleStyle;
  title: string;
  description: string;
}> = [
  {
    id: "clean",
    title: "Clean",
    description: "Readable phrase captions with a subtle active-word glow.",
  },
  {
    id: "kinetic",
    title: "Kinetic Cards",
    description: "Words pop in as punchy cards for faster, denser scenes.",
  },
  {
    id: "burst",
    title: "Burst",
    description: "One payoff word gets oversized impact for reveals and turns.",
  },
];

function settingEnabled(value: string | undefined, fallback = true): boolean {
  if (value === undefined) return fallback;
  return !["", "0", "false", "no", "off"].includes(value.trim().toLowerCase());
}

export function subtitleSettingsFromResponse(rows: SettingRows): SubtitleSettingsState {
  const rawCoverage = rows.SUBTITLE_COVERAGE_MODE?.masked?.trim().toLowerCase();
  const coverage: SubtitleCoverageMode = rawCoverage === "punchy" ? "punchy" : "all";
  const enabledStyles = STYLE_OPTIONS
    .map((style) => style.id)
    .filter((style) => settingEnabled(rows[STYLE_KEYS[style]]?.masked, true));
  return { coverage, enabledStyles };
}

export function subtitleSettingsPayload(settings: SubtitleSettingsState): Record<string, string> {
  return {
    SUBTITLE_COVERAGE_MODE: settings.coverage,
    SUBTITLE_STYLE_CLEAN_ENABLED: settings.enabledStyles.includes("clean") ? "true" : "false",
    SUBTITLE_STYLE_KINETIC_ENABLED: settings.enabledStyles.includes("kinetic") ? "true" : "false",
    SUBTITLE_STYLE_BURST_ENABLED: settings.enabledStyles.includes("burst") ? "true" : "false",
  };
}

function arraysMatch(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((item, index) => item === b[index]);
}

function StylePreview({ style }: { style: EnabledSubtitleStyle }) {
  if (style === "kinetic") {
    return (
      <div className="flex h-24 items-center justify-center gap-2 rounded-lg bg-neutral-950/80 px-4">
        {["This", "changes", "everything"].map((word, index) => (
          <span
            key={word}
            className={`rounded-md px-2.5 py-1.5 text-sm font-black leading-none shadow-[4px_5px_0_rgba(0,0,0,0.75)] ${
              index === 1 ? "rotate-1 bg-red-500 text-white" : "-rotate-1 bg-neutral-100 text-neutral-950"
            }`}
          >
            {word}
          </span>
        ))}
      </div>
    );
  }

  if (style === "burst") {
    return (
      <div className="flex h-24 items-center justify-center rounded-lg bg-neutral-950/80 px-4">
        <div className="text-center leading-none">
          <span className="mr-2 text-lg font-extrabold text-white/80">but</span>
          <span className="inline-block text-4xl font-black uppercase text-yellow-200 [text-shadow:0_4px_0_#111,0_14px_24px_rgba(0,0,0,0.8)] [-webkit-text-stroke:1.5px_#111]">
            why
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-24 items-center justify-center rounded-lg bg-neutral-950/80 px-4">
      <div className="flex flex-wrap justify-center gap-x-2 rounded-md bg-black/55 px-4 py-2">
        <span className="text-lg font-bold text-white">The</span>
        <span className="text-lg font-extrabold text-yellow-300 [text-shadow:0_0_14px_rgba(250,204,21,0.5)]">real</span>
        <span className="text-lg font-bold text-white">answer</span>
      </div>
    </div>
  );
}

interface SubtitlesSectionProps {
  showHeader?: boolean;
}

export default function SubtitlesSection({ showHeader = true }: SubtitlesSectionProps) {
  const [settings, setSettings] = useState<SubtitleSettingsState>({
    coverage: "all",
    enabledStyles: ["clean", "kinetic", "burst"],
  });
  const [original, setOriginal] = useState<SubtitleSettingsState>(settings);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get<SettingRows>("/api/settings/keys").then((res) => {
      if (res.ok) {
        const next = subtitleSettingsFromResponse(res.data);
        setSettings(next);
        setOriginal(next);
      }
      setLoading(false);
    });
  }, []);

  const hasChanges = useMemo(
    () => settings.coverage !== original.coverage || !arraysMatch(settings.enabledStyles, original.enabledStyles),
    [settings, original],
  );

  const toggleStyle = (style: EnabledSubtitleStyle) => {
    setSettings((current) => {
      const enabled = current.enabledStyles.includes(style);
      const enabledStyles = enabled
        ? current.enabledStyles.filter((item) => item !== style)
        : STYLE_OPTIONS.map((option) => option.id).filter((item) => item === style || current.enabledStyles.includes(item));
      return { ...current, enabledStyles };
    });
  };

  const handleSave = async () => {
    setSaving(true);
    const res = await api.put("/api/settings/keys", subtitleSettingsPayload(settings));
    setSaving(false);
    if (res.ok) {
      showToast("Subtitle settings saved", "success");
      setOriginal(settings);
    }
  };

  if (loading) {
    return (
      <div className="px-8 py-8">
        <p className="text-sm text-neutral-500">Loading...</p>
      </div>
    );
  }

  return (
    <div className="max-w-5xl space-y-8 px-8 py-8 pb-24">
      {showHeader && (
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Subtitles</h2>
          <p className="mt-1 text-sm text-neutral-400">
            Choose where standard subtitles appear, then limit which visual treatments can be routed.
          </p>
        </div>
      )}

      <section className="space-y-3">
        <div>
          <h3 className="text-base font-semibold text-neutral-100">Subtitle Coverage</h3>
          <p className="text-xs leading-relaxed text-neutral-500">
            Caption visual mode keeps its own large in-scene text and never receives standard bottom subtitles.
          </p>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          {[
            {
              id: "all" as const,
              title: "All non-caption scenes",
              description: "Every normal scene except caption visual mode gets one of the enabled subtitle styles.",
            },
            {
              id: "punchy" as const,
              title: "Punchiest 20% only",
              description: "Only the strongest reveal, dense, or high-energy scenes get subtitles.",
            },
          ].map((option) => {
            const selected = settings.coverage === option.id;
            return (
              <button
                key={option.id}
                type="button"
                aria-pressed={selected}
                onClick={() => setSettings((current) => ({ ...current, coverage: option.id }))}
                className={`flex min-h-32 flex-col rounded-xl border p-5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
                  selected
                    ? "border-violet-400/60 bg-violet-500/10 text-neutral-100"
                    : "border-neutral-800 bg-neutral-900 text-neutral-300 hover:border-neutral-700 hover:bg-neutral-800/70"
                }`}
              >
                <span className="flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold">{option.title}</span>
                  <span className={`grid h-6 w-6 place-items-center rounded-full border ${
                    selected ? "border-violet-300 bg-violet-500 text-white" : "border-neutral-700 text-neutral-600"
                  }`}>
                    {selected && <Check className="h-3.5 w-3.5" />}
                  </span>
                </span>
                <span className="mt-2 text-xs leading-relaxed text-neutral-500">{option.description}</span>
                <span className="mt-auto flex items-center gap-1.5 pt-5 text-[11px] font-medium text-neutral-400">
                  <Sparkles className="h-3.5 w-3.5 text-violet-300" />
                  {option.id === "all" ? "Best for always-on readability" : "Best for accent moments"}
                </span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="space-y-3">
        <div>
          <h3 className="text-base font-semibold text-neutral-100">Enabled Subtitle Styles</h3>
          <p className="text-xs leading-relaxed text-neutral-500">
            Only selected styles are eligible when subtitles are assigned. Turning every style off suppresses standard subtitles.
          </p>
        </div>
        <div className="grid gap-3 lg:grid-cols-3">
          {STYLE_OPTIONS.map((option) => {
            const selected = settings.enabledStyles.includes(option.id);
            return (
              <button
                key={option.id}
                type="button"
                aria-pressed={selected}
                onClick={() => toggleStyle(option.id)}
                className={`rounded-xl border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
                  selected
                    ? "border-sky-400/60 bg-sky-500/10"
                    : "border-neutral-800 bg-neutral-900 hover:border-neutral-700 hover:bg-neutral-800/70"
                }`}
              >
                <StylePreview style={option.id} />
                <div className="mt-4 flex items-start justify-between gap-3">
                  <div>
                    <h4 className="text-sm font-semibold text-neutral-100">{option.title}</h4>
                    <p className="mt-1 text-xs leading-relaxed text-neutral-500">{option.description}</p>
                  </div>
                  <span className={`grid h-6 w-6 shrink-0 place-items-center rounded-full border ${
                    selected ? "border-sky-300 bg-sky-500 text-white" : "border-neutral-700 text-neutral-600"
                  }`}>
                    {selected && <Check className="h-3.5 w-3.5" />}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {hasChanges && (
        <div className="fixed bottom-0 left-0 right-0 z-40 border-t border-neutral-800 bg-neutral-900/95 px-8 py-3 backdrop-blur-sm">
          <div className="mx-auto flex max-w-5xl items-center justify-between">
            <span className="text-sm text-neutral-400">You have unsaved changes</span>
            <button
              onClick={handleSave}
              disabled={saving}
              className="btn-primary rounded-lg px-5 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
