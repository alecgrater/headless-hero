import { Check } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import api from "../../api";
import { useDebouncedAutosave } from "./useDebouncedAutosave";

export type SubtitleCoverageMode = "all" | "punchy";
export type EnabledSubtitleStyle = "clean" | "kinetic";

type SettingRows = Record<string, { masked?: string }>;

interface SubtitleSettingsState {
  coverage: SubtitleCoverageMode;
  enabledStyles: EnabledSubtitleStyle[];
}

/** Kinetic is the only toggleable style — "clean" is the floor of the catalogue. */
const KINETIC_ENABLED_KEY = "SUBTITLE_STYLE_KINETIC_ENABLED";

/** Mirrors remotion_render.KINETIC_MAX_WORDS / KINETIC_MAX_SPAN_SECONDS, for copy only. */
const KINETIC_MAX_WORDS = 6;
const KINETIC_MAX_SPAN_SECONDS = 3;

function settingEnabled(value: string | undefined, fallback = true): boolean {
  if (value === undefined) return fallback;
  return !["", "0", "false", "no", "off"].includes(value.trim().toLowerCase());
}

// eslint-disable-next-line react-refresh/only-export-components -- shared with settings tests.
export function subtitleSettingsFromResponse(rows: SettingRows): SubtitleSettingsState {
  const rawCoverage = rows.SUBTITLE_COVERAGE_MODE?.masked?.trim().toLowerCase();
  const coverage: SubtitleCoverageMode = rawCoverage === "punchy" ? "punchy" : "all";
  const enabledStyles: EnabledSubtitleStyle[] = ["clean"];
  if (settingEnabled(rows[KINETIC_ENABLED_KEY]?.masked, true)) enabledStyles.push("kinetic");
  return { coverage, enabledStyles };
}

// eslint-disable-next-line react-refresh/only-export-components -- shared with settings tests.
export function subtitleSettingsPayload(settings: SubtitleSettingsState): Record<string, string> {
  return {
    SUBTITLE_COVERAGE_MODE: settings.coverage,
    [KINETIC_ENABLED_KEY]: settings.enabledStyles.includes("kinetic") ? "true" : "false",
  };
}

function arraysMatch(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((item, index) => item === b[index]);
}

function StylePreview({ style }: { style: EnabledSubtitleStyle }) {
  if (style === "kinetic") {
    return (
      <div
        data-testid="kinetic-style-preview"
        className="flex h-20 items-center justify-center rounded-lg bg-neutral-950/80 px-4"
      >
        <div className="flex flex-wrap justify-center gap-x-2 leading-none">
          <span className="text-xl font-black tracking-tight text-white/45">Her</span>
          <span className="text-xl font-black tracking-tight text-yellow-300 [text-shadow:0_2px_4px_rgba(0,0,0,0.55)]">
            finding?
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-20 items-center justify-center rounded-lg bg-neutral-950/80 px-4">
      <div className="flex flex-wrap justify-center gap-x-2 rounded-md bg-black/55 px-4 py-2">
        <span className="text-lg font-extrabold text-white">The</span>
        <span className="text-lg font-extrabold text-yellow-300">real</span>
        <span className="text-lg font-extrabold text-white">answer</span>
      </div>
    </div>
  );
}

function SubtitlesSectionIntro({
  number,
  title,
  description,
}: {
  number: string;
  title: string;
  description: string;
}) {
  return (
    <div className="max-w-sm">
      <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-violet-300/80">
        {number}
      </div>
      <h3 className="text-xl font-semibold tracking-tight text-neutral-100">{title}</h3>
      <p className="mt-2 text-xs leading-relaxed text-neutral-500">{description}</p>
    </div>
  );
}

interface SubtitlesSectionProps {
  showHeader?: boolean;
}

export default function SubtitlesSection({ showHeader = true }: SubtitlesSectionProps) {
  const [settings, setSettings] = useState<SubtitleSettingsState>({
    coverage: "all",
    enabledStyles: ["clean", "kinetic"],
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

  const toggleKinetic = () => {
    setSettings((current) => ({
      ...current,
      enabledStyles: current.enabledStyles.includes("kinetic") ? ["clean"] : ["clean", "kinetic"],
    }));
  };

  const handleSave = useCallback(async () => {
    setSaving(true);
    const res = await api.put("/api/settings/keys", subtitleSettingsPayload(settings));
    setSaving(false);
    if (res.ok) {
      setOriginal(settings);
    }
    return res.ok;
  }, [settings]);

  useDebouncedAutosave(hasChanges && !saving && !loading, handleSave, [settings]);

  if (loading) {
    return (
      <div className="px-8 py-8">
        <p className="text-sm text-neutral-500">Loading...</p>
      </div>
    );
  }

  return (
    <div className="max-w-5xl space-y-10 px-8 py-8 pb-24">
      {showHeader && (
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Subtitles</h2>
          <p className="mt-1 text-sm text-neutral-400">
            Choose where standard subtitles appear, and whether short punch beats get the kinetic treatment.
          </p>
        </div>
      )}

      <section
        data-testid="subtitle-coverage-section"
        className="grid gap-5 border-t border-neutral-800 pt-6 xl:grid-cols-[220px_minmax(0,1fr)]"
      >
        <SubtitlesSectionIntro
          number="01 Coverage"
          title="Subtitle Coverage"
          description="Caption visual mode keeps its own large in-scene text and never receives standard bottom subtitles."
        />
        <div className="rounded-xl bg-neutral-900/70 p-1">
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
                className={`grid w-full grid-cols-[minmax(0,1fr)_auto] gap-x-4 rounded-md px-4 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
                  selected
                    ? "bg-violet-500 text-white shadow-[0_10px_30px_rgba(139,92,246,0.22)]"
                    : "text-neutral-400 hover:bg-neutral-800/80 hover:text-neutral-100"
                }`}
              >
                <span>
                  <span className="block text-sm font-semibold">{option.title}</span>
                  <span className={`mt-1 block text-xs leading-relaxed ${selected ? "text-violet-100/80" : "text-neutral-500"}`}>
                    {option.description}
                  </span>
                </span>
                <span className={`mt-0.5 grid h-6 w-6 place-items-center rounded-full ${
                  selected ? "bg-white text-violet-600" : "bg-neutral-800 text-neutral-600"
                }`}>
                  {selected && <Check className="h-3.5 w-3.5" />}
                </span>
              </button>
            );
          })}
        </div>
      </section>

      <section
        data-testid="subtitle-styles-section"
        className="grid gap-5 border-t border-neutral-800 pt-6 xl:grid-cols-[220px_minmax(0,1fr)]"
      >
        <SubtitlesSectionIntro
          number="02 Styles"
          title="Subtitle Styles"
          description={`Clean carries every subtitled scene. Kinetic is the exception, routed automatically to short punch beats — ${KINETIC_MAX_WORDS} words or fewer, spoken in ${KINETIC_MAX_SPAN_SECONDS} seconds or less.`}
        />
        <div className="border-b border-neutral-800">
          <div className="grid gap-4 border-t border-neutral-800 px-4 py-4 md:grid-cols-[180px_minmax(0,1fr)_auto] md:items-center">
            <StylePreview style="clean" />
            <div>
              <h4 className="text-sm font-semibold text-neutral-100">Clean</h4>
              <p className="mt-1 max-w-xl text-xs leading-relaxed text-neutral-500">
                The default for every subtitled scene. Readable phrase captions on a translucent plate, with the
                spoken word picked out in the accent colour at the same size, so the line never shifts.
              </p>
            </div>
            <span className="justify-self-start rounded-full bg-neutral-800 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-neutral-400 md:justify-self-end">
              Always on
            </span>
          </div>

          <button
            type="button"
            aria-pressed={settings.enabledStyles.includes("kinetic")}
            onClick={toggleKinetic}
            className={`grid w-full gap-4 border-t border-neutral-800 px-4 py-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 md:grid-cols-[180px_minmax(0,1fr)_auto] md:items-center ${
              settings.enabledStyles.includes("kinetic")
                ? "bg-violet-500/10 text-neutral-100 shadow-[0_18px_42px_rgba(139,92,246,0.18)]"
                : "text-neutral-400 hover:text-neutral-100"
            }`}
          >
            <StylePreview style="kinetic" />
            <div>
              <h4 className="text-sm font-semibold text-neutral-100">Kinetic accents</h4>
              <p className="mt-1 max-w-xl text-xs leading-relaxed text-neutral-500">
                Same typeface and accent colour as Clean, set larger with no plate. Words arrive as they are spoken
                and the active word pops harder. Turn this off to render every scene as Clean.
              </p>
            </div>
            <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full justify-self-start md:justify-self-end ${
              settings.enabledStyles.includes("kinetic") ? "bg-violet-500 text-white" : "bg-neutral-800 text-neutral-600"
            }`}>
              {settings.enabledStyles.includes("kinetic") && <Check className="h-3.5 w-3.5" />}
            </span>
          </button>
        </div>
      </section>

      {saving && (
        <div className="fixed bottom-0 left-0 right-0 z-40 border-t border-neutral-800 bg-neutral-900/95 px-8 py-3 backdrop-blur-sm">
          <div className="mx-auto flex max-w-5xl items-center justify-between">
            <span className="text-sm text-neutral-400">Saving subtitle settings...</span>
          </div>
        </div>
      )}
    </div>
  );
}
