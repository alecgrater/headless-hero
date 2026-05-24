import { HelpCircle, Image, Video } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import type { TestLabPreset, TestLabSettings, TestLabStages } from "../../types/testLab";
import type { VisualTreatment } from "../../types/script";
import { Tooltip } from "../ui/Tooltip";

type StageKey = keyof TestLabStages;

interface TestLabControlsProps {
  preset: TestLabPreset | null;
  settings: TestLabSettings;
  onChange: (settings: TestLabSettings) => void;
  onValidityChange?: (valid: boolean) => void;
}

const STAGE_OPTIONS: Array<{ key: StageKey; label: string; help: string }> = [
  { key: "character", label: "Character", help: "Generate or refresh the project-specific character reference before scene assets." },
  { key: "audio", label: "Audio", help: "Generate ElevenLabs voiceover timing so downstream stages use real duration." },
  { key: "visual", label: "Visual", help: "Generate the scene image or AI video anchor media." },
  { key: "treatment_assets", label: "Treatment assets", help: "Create extra image layers for popup and flip-flop treatments." },
  { key: "fx", label: "FX", help: "Ask the FX planner for camera and punch timing on this scene." },
  { key: "eli", label: "Eli", help: "Generate Eli overlay timing when Eli is enabled for the run." },
  { key: "render", label: "Render", help: "Render a playable Remotion video after generating selected assets." },
];

const TREATMENT_OPTIONS: Array<{ value: VisualTreatment; label: string }> = [
  { value: "full_frame", label: "Full frame" },
  { value: "popup_sequence", label: "Popup sequence" },
  { value: "flipflop", label: "Flip-flop" },
];

export default function TestLabControls({ preset, settings, onChange, onValidityChange }: TestLabControlsProps) {
  const narration = settings.narration ?? preset?.narration ?? "";
  const visualPrompt = settings.visual_prompt ?? preset?.visual_prompt ?? "";
  const backgroundColor = settings.visual_canvas?.background_color ?? preset?.background_color ?? "#F6C54A";
  const [voiceSettingsText, setVoiceSettingsText] = useState("");
  const [voiceSettingsError, setVoiceSettingsError] = useState("");

  useEffect(() => {
    setVoiceSettingsText(settings.voice_settings ? JSON.stringify(settings.voice_settings, null, 2) : "");
    setVoiceSettingsError("");
  }, [settings.voice_settings]);

  useEffect(() => {
    onValidityChange?.(!voiceSettingsError);
  }, [onValidityChange, voiceSettingsError]);

  function update(next: Partial<TestLabSettings>) {
    onChange({ ...settings, ...next });
  }

  function updateStage(key: StageKey, enabled: boolean) {
    onChange({
      ...settings,
      stages: {
        ...settings.stages,
        [key]: enabled,
      },
    });
  }

  function updateVoiceSettings(value: string) {
    setVoiceSettingsText(value);
    if (!value.trim()) {
      setVoiceSettingsError("");
      update({ voice_settings: null });
      return;
    }
    try {
      const parsed = JSON.parse(value);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        setVoiceSettingsError("");
        update({ voice_settings: parsed });
      } else {
        setVoiceSettingsError("Use a JSON object.");
      }
    } catch {
      setVoiceSettingsError("Invalid JSON.");
    }
  }

  return (
    <div className="space-y-4">
      <header className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase text-neutral-500">Settings</p>
          <h2 className="mt-2 text-sm font-semibold text-neutral-100">{preset?.title ?? "Select a scene"}</h2>
          {preset?.description && <p className="mt-1 text-xs leading-5 text-neutral-500">{preset.description}</p>}
        </div>
        {preset?.duration_estimate_seconds !== undefined && (
          <span className="shrink-0 rounded-md border border-neutral-800 bg-neutral-950/70 px-2 py-1 text-xs text-neutral-400">
            {preset.duration_estimate_seconds.toFixed(1)}s
          </span>
        )}
      </header>

      <Panel title="Pipeline stages" help="Disable individual stages to inspect partial output or reuse existing intermediate assets.">
        <div className="grid grid-cols-2 gap-2">
          {STAGE_OPTIONS.map((stage) => (
            <ToggleButton
              key={stage.key}
              label={stage.label}
              checked={settings.stages[stage.key]}
              help={stage.help}
              onChange={(enabled) => updateStage(stage.key, enabled)}
            />
          ))}
        </div>
      </Panel>

      <Panel title="Visual source" help="Test Lab only uses first-party AI-generated scene media. Deprecated stock, gameplay, and upload sources are intentionally absent.">
        <div className="grid grid-cols-2 overflow-hidden rounded-md border border-neutral-800 bg-neutral-950/70">
          <SegmentButton
            active={settings.media_source === "ai"}
            label="AI image"
            icon={<Image className="h-4 w-4" />}
            onClick={() => update({ media_source: "ai" })}
          />
          <SegmentButton
            active={settings.media_source === "ai_video"}
            label="AI video"
            icon={<Video className="h-4 w-4" />}
            onClick={() => update({ media_source: "ai_video" })}
          />
        </div>
      </Panel>

      <Panel title="Audio" help="Override the voice, ElevenLabs model, and voice settings passed to the same TTS stage used by real projects.">
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="text-xs font-medium text-neutral-300">Voice ID</span>
            <input
              value={settings.voice_id ?? ""}
              onChange={(event) => update({ voice_id: event.target.value || undefined })}
              className="mt-2 w-full rounded-md border border-neutral-800 bg-neutral-950/80 px-3 py-2 text-sm text-neutral-100 outline-none transition-colors placeholder:text-neutral-600 hover:border-neutral-700 focus:border-violet-500"
              placeholder="Settings default"
            />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-neutral-300">TTS model</span>
            <input
              value={settings.voice_model_id ?? ""}
              onChange={(event) => update({ voice_model_id: event.target.value || undefined })}
              className="mt-2 w-full rounded-md border border-neutral-800 bg-neutral-950/80 px-3 py-2 text-sm text-neutral-100 outline-none transition-colors placeholder:text-neutral-600 hover:border-neutral-700 focus:border-violet-500"
              placeholder="eleven_multilingual_v2"
            />
          </label>
        </div>
        <label className="mt-3 block">
          <span className="text-xs font-medium text-neutral-300">Voice settings JSON</span>
          <textarea
            value={voiceSettingsText}
            onChange={(event) => updateVoiceSettings(event.target.value)}
            rows={4}
            className={`mt-2 w-full resize-y rounded-md border bg-neutral-950/80 px-3 py-2 font-mono text-xs leading-5 text-neutral-100 outline-none transition-colors placeholder:text-neutral-600 hover:border-neutral-700 focus:border-violet-500 ${
              voiceSettingsError ? "border-red-500/70" : "border-neutral-800"
            }`}
            placeholder={'{ "stability": 0.5, "similarity_boost": 0.75 }'}
          />
          {voiceSettingsError && <span className="mt-1 block text-xs text-red-300">{voiceSettingsError}</span>}
        </label>
      </Panel>

      <Panel title="Character" help="These switches mirror the project-level character controls for a single disposable Test Lab script.">
        <div className="grid grid-cols-2 gap-2">
          <ToggleButton
            label="Eli enabled"
            checked={settings.eli_enabled}
            help="When enabled, Eli may be planned as an overlay host and the Eli stage can generate animation timing."
            onChange={(enabled) => update({ eli_enabled: enabled })}
          />
          <ToggleButton
            label="Style preset"
            checked={settings.style_preset_enabled}
            help="Apply the house visual style preset to generated character, image, and treatment assets."
            onChange={(enabled) => update({ style_preset_enabled: enabled })}
          />
        </div>
        {preset?.main_character && (
          <div className="rounded-md border border-neutral-800 bg-neutral-950/60 p-3 text-xs">
            <p className="font-medium text-neutral-200">{preset.main_character.name}</p>
            <p className="mt-1 text-neutral-500">{preset.main_character.appearance}</p>
            <p className="mt-1 text-neutral-500">{preset.main_character.vibe}</p>
          </div>
        )}
      </Panel>

      <Panel title="Scene text" help="Overrides are sent only for this run, leaving the dummy scene preset unchanged.">
        <label className="block">
          <span className="text-xs font-medium text-neutral-300">Narration</span>
          <textarea
            value={narration}
            onChange={(event) => update({ narration: event.target.value, tts_narration: event.target.value })}
            rows={5}
            className="mt-2 w-full resize-y rounded-md border border-neutral-800 bg-neutral-950/80 px-3 py-2 text-sm leading-5 text-neutral-100 outline-none transition-colors placeholder:text-neutral-600 hover:border-neutral-700 focus:border-violet-500"
            placeholder="Scene narration..."
          />
        </label>
        <label className="mt-3 block">
          <span className="text-xs font-medium text-neutral-300">Visual prompt</span>
          <textarea
            value={visualPrompt}
            onChange={(event) => update({ visual_prompt: event.target.value })}
            rows={5}
            className="mt-2 w-full resize-y rounded-md border border-neutral-800 bg-neutral-950/80 px-3 py-2 text-sm leading-5 text-neutral-100 outline-none transition-colors placeholder:text-neutral-600 hover:border-neutral-700 focus:border-violet-500"
            placeholder="Visual prompt..."
          />
        </label>
      </Panel>

      <Panel title="Treatment, FX, canvas" help="Tune the render wrapper and overlay behavior around the generated scene media.">
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="text-xs font-medium text-neutral-300">Visual treatment</span>
            <select
              value={settings.visual_treatment}
              onChange={(event) => update({ visual_treatment: event.target.value as VisualTreatment })}
              className="mt-2 w-full rounded-md border border-neutral-800 bg-neutral-950/80 px-3 py-2 text-sm text-neutral-100 outline-none transition-colors hover:border-neutral-700 focus:border-violet-500"
            >
              {TREATMENT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs font-medium text-neutral-300">Canvas color</span>
            <div className="mt-2 flex h-10 overflow-hidden rounded-md border border-neutral-800 bg-neutral-950/80 transition-colors hover:border-neutral-700 focus-within:border-violet-500">
              <input
                type="color"
                value={backgroundColor}
                onChange={(event) => update({ visual_canvas: { background_color: event.target.value } })}
                className="h-full w-12 cursor-pointer border-0 bg-transparent p-1"
              />
              <input
                value={backgroundColor}
                onChange={(event) => update({ visual_canvas: { background_color: event.target.value } })}
                className="min-w-0 flex-1 bg-transparent px-2 text-sm font-mono text-neutral-100 outline-none"
              />
            </div>
          </label>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <ToggleButton
            label="Subtitle highlight"
            checked={settings.subtitle_highlight_enabled}
            help="Render word-level subtitle emphasis in the preview."
            onChange={(enabled) => update({ subtitle_highlight_enabled: enabled })}
          />
          <ToggleButton
            label="Segment timer"
            checked={settings.segment_timer_enabled}
            help="Show the short-form segment timer overlay when the selected format supports it."
            onChange={(enabled) => update({ segment_timer_enabled: enabled })}
          />
        </div>
      </Panel>
    </div>
  );
}

function Panel({ title, help, children }: { title: string; help: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-neutral-800 bg-neutral-950/50 p-3">
      <div className="mb-3 flex items-center gap-2">
        <h3 className="text-xs font-semibold uppercase text-neutral-400">{title}</h3>
        <Tooltip content={help} side="right">
          <HelpCircle className="h-3.5 w-3.5 text-neutral-600" />
        </Tooltip>
      </div>
      {children}
    </section>
  );
}

function ToggleButton({
  label,
  checked,
  help,
  onChange,
}: {
  label: string;
  checked: boolean;
  help: string;
  onChange: (checked: boolean) => void;
}) {
  return (
    <Tooltip content={help}>
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={`flex min-h-10 items-center justify-between gap-2 rounded-md border px-3 py-2 text-left text-xs transition-colors ${
          checked
            ? "border-violet-500/70 bg-violet-500/15 text-neutral-100"
            : "border-neutral-800 bg-neutral-950/70 text-neutral-500 hover:border-neutral-700 hover:text-neutral-200"
        }`}
      >
        <span className="truncate">{label}</span>
        <span className={`h-2 w-2 shrink-0 rounded-full ${checked ? "bg-violet-300" : "bg-neutral-700"}`} />
      </button>
    </Tooltip>
  );
}

function SegmentButton({
  active,
  label,
  icon,
  onClick,
}: {
  active: boolean;
  label: string;
  icon: ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex min-h-10 items-center justify-center gap-2 px-3 py-2 text-xs font-medium transition-colors ${
        active ? "bg-sky-500/20 text-sky-200" : "text-neutral-500 hover:bg-neutral-900 hover:text-neutral-200"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}
