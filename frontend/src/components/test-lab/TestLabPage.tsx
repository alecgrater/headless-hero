import { Beaker, Play, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import api, { getTestLabPresets, getTestLabRun, getTestLabRuns, startTestLabRun } from "../../api";
import type { MutableRefObject } from "react";
import type {
  TestLabMainCharacter,
  TestLabPreset,
  TestLabRun,
  TestLabScenes,
  TestLabSettings,
  TestLabSubtitleSummary,
  TestLabVoiceSummary,
} from "../../types/testLab";
import FlipflopDebugLab from "./FlipflopDebugLab";
import PopupCropLab from "./PopupCropLab";
import TestLabControls, { settingsWithVisualTreatmentDefaults } from "./TestLabControls";
import TestLabRunPanel from "./TestLabRunPanel";

function visualModeFromPreset(preset: TestLabPreset | null): TestLabSettings["visual_mode"] {
  return preset?.visual_mode ?? "full_frame";
}

function isLayeredVisualMode(
  visualMode: TestLabSettings["visual_mode"],
): visualMode is Extract<TestLabSettings["visual_mode"], "popup_sequence" | "flipflop" | "comparison_board" | "stat_card"> {
  return visualMode === "popup_sequence" || visualMode === "flipflop" || visualMode === "comparison_board" || visualMode === "stat_card";
}

function settingsWithPresetVisualMode(settings: TestLabSettings, preset: TestLabPreset | null): TestLabSettings {
  const visualMode = visualModeFromPreset(preset);
  const isLayered = isLayeredVisualMode(visualMode);
  const currentVisualMode = settings.visual_mode;
  const shouldPreserveVisualLayers = isLayered && visualMode === currentVisualMode;
  return {
    ...settings,
    visual_mode: visualMode,
    visual_layers: shouldPreserveVisualLayers ? settings.visual_layers : [],
    stages: {
      ...settings.stages,
      treatment_assets: isLayered,
    },
  };
}

export function testLabPresetSubtitle(preset: TestLabPreset): string {
  return preset.narration || preset.description || "";
}

const DEFAULT_SETTINGS: TestLabSettings = {
  stages: {
    audio: true,
    visual: true,
    treatment_assets: true,
    fx: true,
    render: true,
  },
  eli_enabled: false,
  style_preset_enabled: true,
  visual_mode: "full_frame",
  visual_layers: [],
  segment_timer_enabled: true,
  subtitle_style: "auto",
};

type TestLabJobStatus = {
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress?: number;
  current_step?: string | null;
  error?: string | null;
};

type TestLabTab = "pipeline" | "popup-crop" | "flipflop-debug";
type TestLabSettingsSection = "voice" | "subtitles";

interface Props {
  active?: boolean;
  onOpenSettingsSection?: (section: TestLabSettingsSection) => void;
}

export default function TestLabPage({ active = true, onOpenSettingsSection }: Props) {
  const mountedRef = useRef(false);
  const wasActiveRef = useRef(active);
  const selectedPresetIdRef = useRef("");
  const pollTimerRef = useRef<number | null>(null);
  const resolvePollSleepRef = useRef<((mounted: boolean) => void) | null>(null);
  const [presets, setPresets] = useState<TestLabPreset[]>([]);
  const [visualTreatmentDefaults, setVisualTreatmentDefaults] = useState<TestLabScenes["visual_treatment_defaults"]>({});
  const [defaultMainCharacter, setDefaultMainCharacter] = useState<TestLabMainCharacter | null>(null);
  const [voiceSummary, setVoiceSummary] = useState<TestLabVoiceSummary | null>(null);
  const [subtitleSummary, setSubtitleSummary] = useState<TestLabSubtitleSummary | null>(null);
  const [selectedPresetId, setSelectedPresetId] = useState<string>("");
  const [settings, setSettings] = useState<TestLabSettings>(DEFAULT_SETTINGS);
  const [runs, setRuns] = useState<TestLabRun[]>([]);
  const [activeRun, setActiveRun] = useState<TestLabRun | null>(null);
  const [running, setRunning] = useState(false);
  const [jobStatus, setJobStatus] = useState<TestLabJobStatus | null>(null);
  const [controlsValid, setControlsValid] = useState(true);
  const [activeTab, setActiveTab] = useState<TestLabTab>("pipeline");

  const refreshRuns = useCallback(async () => {
    const nextRuns = await getTestLabRuns();
    if (!mountedRef.current) return nextRuns;
    setRuns(nextRuns);
    return nextRuns;
  }, []);

  const refreshSceneData = useCallback(async () => {
    const sceneData = await getTestLabPresets();
    if (!mountedRef.current) return;
    setPresets(sceneData.presets);
    setVisualTreatmentDefaults(sceneData.visual_treatment_defaults ?? {});
    setDefaultMainCharacter(sceneData.default_main_character);
    setVoiceSummary(sceneData.voice_summary ?? null);
    setSubtitleSummary(sceneData.subtitle_summary ?? null);
    const hadSelection = Boolean(selectedPresetIdRef.current);
    setSelectedPresetId((current) => {
      const next = current || sceneData.presets[0]?.id || "";
      selectedPresetIdRef.current = next;
      return next;
    });
    setSettings((current) => {
      if (hadSelection) return current;
      return settingsWithPresetVisualMode(current, sceneData.presets[0] ?? null);
    });
  }, []);

  useEffect(() => {
    mountedRef.current = true;

    refreshSceneData();
    refreshRuns();

    return () => {
      mountedRef.current = false;
      if (pollTimerRef.current !== null) {
        window.clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      if (resolvePollSleepRef.current) {
        resolvePollSleepRef.current(false);
        resolvePollSleepRef.current = null;
      }
    };
  }, [refreshRuns, refreshSceneData]);

  useEffect(() => {
    selectedPresetIdRef.current = selectedPresetId;
  }, [selectedPresetId]);

  useEffect(() => {
    if (!wasActiveRef.current && active) {
      refreshSceneData();
    }
    wasActiveRef.current = active;
  }, [active, refreshSceneData]);

  const selectedPreset = useMemo(
    () => presets.find((preset) => preset.id === selectedPresetId) ?? null,
    [presets, selectedPresetId],
  );

  function handleSelectPreset(presetId: string) {
    const nextPreset = presets.find((preset) => preset.id === presetId) ?? null;
    setSelectedPresetId(presetId);
    setSettings((current) => {
      const presetSettings = settingsWithPresetVisualMode(current, nextPreset);
      return settingsWithVisualTreatmentDefaults(
        {
          ...presetSettings,
          title: undefined,
          segment_name: undefined,
          short_name: undefined,
          narration: undefined,
          tts_narration: undefined,
          visual_prompt: undefined,
          duration_estimate_seconds: undefined,
          contains_person: undefined,
          visual_beat: undefined,
          visual_canvas: undefined,
          main_character: undefined,
        },
        nextPreset,
        presetSettings.visual_mode,
        visualTreatmentDefaults,
      );
    });
  }

  const pollRun = useCallback(async (jobId: string, runId: string) => {
    for (;;) {
      const shouldContinue = await waitForNextPoll(pollTimerRef, resolvePollSleepRef);
      if (!shouldContinue || !mountedRef.current) return;

      const statusRes = await api.get<TestLabJobStatus>(`/api/test-lab/runs/status/${jobId}`);
      if (!mountedRef.current) return;
      if (statusRes.ok) {
        setJobStatus(statusRes.data);
      }

      const detail = await getTestLabRun(runId);
      if (!mountedRef.current) return;
      if (detail) {
        setActiveRun(detail);
      }

      const status = statusRes.ok ? statusRes.data.status : detail?.status;
      if (status === "completed" || status === "failed" || status === "cancelled") {
        const nextRuns = await refreshRuns();
        if (!mountedRef.current) return;
        setActiveRun((current) => getRunFromHistory(nextRuns, runId) ?? detail ?? current);
        return;
      }
    }
  }, [refreshRuns]);

  async function handleRun() {
    if (!selectedPresetId || running || !controlsValid) return;

    setRunning(true);
    setJobStatus({ status: "queued", current_step: "Starting Test Lab run..." });
    try {
      const started = await startTestLabRun(selectedPresetId, settingsForRun(settings, defaultMainCharacter));
      if (!mountedRef.current) return;
      if (!started) return;
      await pollRun(started.job_id, started.run_id);
    } finally {
      if (mountedRef.current) {
        setRunning(false);
      }
    }
  }

  const activeStatus = jobStatus?.current_step || activeRun?.status || "No run selected";
  const activeProgress = jobStatus?.progress;

  return (
    <div className="h-full min-h-0 bg-neutral-950 text-neutral-100">
      <div className="flex h-full min-h-0 flex-col">
        <div className="border-b border-neutral-800 px-6 py-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <Beaker className="h-5 w-5 text-violet-300" />
              <div>
                <h1 className="text-lg font-semibold">Test Lab</h1>
                <p className="text-xs text-neutral-500">Run focused experiments against the production media pipeline.</p>
              </div>
            </div>
            {activeTab === "pipeline" && (
              <button
                onClick={handleRun}
                disabled={running || !selectedPreset || !controlsValid}
                className="inline-flex items-center gap-2 rounded-md bg-violet-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-500 disabled:cursor-not-allowed disabled:bg-neutral-800 disabled:text-neutral-500"
              >
                {running ? <RotateCcw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                Generate & Render
              </button>
            )}
          </div>
          <div className="mt-4 inline-flex overflow-hidden rounded-md border border-neutral-800 bg-neutral-950/70">
            <TabButton active={activeTab === "pipeline"} label="Scene Pipeline" onClick={() => setActiveTab("pipeline")} />
            <TabButton active={activeTab === "popup-crop"} label="Popup Crop" onClick={() => setActiveTab("popup-crop")} />
            <TabButton active={activeTab === "flipflop-debug"} label="Flip-flop" onClick={() => setActiveTab("flipflop-debug")} />
          </div>
        </div>

        {activeTab === "pipeline" ? (
          <div className="grid min-h-0 flex-1 grid-cols-[280px_minmax(420px,1fr)_400px] gap-4 overflow-hidden p-4">
            <aside className="min-h-0 overflow-y-auto rounded-lg border border-neutral-800 bg-neutral-900/60 p-3">
              <p className="mb-3 text-xs font-semibold uppercase text-neutral-500">Dummy Scenes</p>
              <div className="space-y-2">
                {presets.map((preset) => (
                  <button
                    key={preset.id}
                    onClick={() => handleSelectPreset(preset.id)}
                    className={`w-full rounded-md border p-3 text-left transition-colors ${
                      selectedPresetId === preset.id
                        ? "border-violet-500 bg-violet-500/15"
                        : "border-neutral-800 bg-neutral-950/50 hover:border-neutral-700"
                    }`}
                  >
                    <p className="text-sm font-medium text-neutral-100">{preset.title}</p>
                    <p className="mt-1 line-clamp-2 text-xs text-neutral-500">{testLabPresetSubtitle(preset)}</p>
                  </button>
                ))}
              </div>
            </aside>

            <section className="min-h-0 overflow-y-auto rounded-lg border border-neutral-800 bg-neutral-900/60 p-4">
              <TestLabControls
                preset={selectedPreset}
                defaultMainCharacter={defaultMainCharacter}
                visualTreatmentDefaults={visualTreatmentDefaults}
                settings={settings}
                voiceSummary={voiceSummary}
                subtitleSummary={subtitleSummary}
                onChange={setSettings}
                onValidityChange={setControlsValid}
                onOpenSettingsSection={onOpenSettingsSection}
              />
            </section>

            <aside className="min-h-0 overflow-y-auto rounded-lg border border-neutral-800 bg-neutral-900/60 p-4">
              <TestLabRunPanel
                activeRun={activeRun}
                runs={runs}
                running={running}
                currentStep={activeStatus}
                progress={activeProgress}
                onSelectRun={setActiveRun}
              />
            </aside>
          </div>
        ) : activeTab === "popup-crop" ? (
          <div className="min-h-0 flex-1 overflow-hidden p-4">
            <PopupCropLab />
          </div>
        ) : (
          <div className="min-h-0 flex-1 overflow-hidden p-4">
            <FlipflopDebugLab />
          </div>
        )}
      </div>
    </div>
  );
}

function TabButton({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-2 text-xs font-medium transition-colors ${
        active ? "bg-violet-500/15 text-violet-200" : "text-neutral-400 hover:bg-neutral-900 hover:text-neutral-100"
      }`}
    >
      {label}
    </button>
  );
}

function settingsForRun(
  settings: TestLabSettings,
  defaultMainCharacter: TestLabMainCharacter | null,
): TestLabSettings {
  if (settings.eli_enabled || !settings.style_preset_enabled || settings.main_character || !defaultMainCharacter) {
    return { ...settings, segment_timer_enabled: true };
  }
  return {
    ...settings,
    segment_timer_enabled: true,
    main_character: {
      name: defaultMainCharacter.name,
      appearance: defaultMainCharacter.appearance,
      vibe: defaultMainCharacter.vibe,
    },
  };
}

function getRunFromHistory(runs: TestLabRun[], runId: string): TestLabRun | null {
  return runs.find((run) => run.run_id === runId) ?? null;
}

function waitForNextPoll(
  timerRef: MutableRefObject<number | null>,
  resolverRef: MutableRefObject<((mounted: boolean) => void) | null>,
): Promise<boolean> {
  return new Promise((resolve) => {
    resolverRef.current = resolve;
    timerRef.current = window.setTimeout(() => {
      timerRef.current = null;
      resolverRef.current = null;
      resolve(true);
    }, 1500);
  });
}
