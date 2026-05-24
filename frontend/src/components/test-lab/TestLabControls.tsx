import { HelpCircle, Image, Palette, UserRound, Video } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { assetUrl } from "../../api";
import type { TestLabMainCharacter, TestLabPreset, TestLabSettings, TestLabStages } from "../../types/testLab";
import type { VisualTreatment } from "../../types/script";
import { Tooltip } from "../ui/Tooltip";

type StageKey = keyof TestLabStages;

interface TestLabControlsProps {
  preset: TestLabPreset | null;
  defaultMainCharacter: TestLabMainCharacter | null;
  settings: TestLabSettings;
  onChange: (settings: TestLabSettings) => void;
  onValidityChange?: (valid: boolean) => void;
}

type ToggleHelp = {
  on: string;
  off: string;
};

const STAGE_OPTIONS: Array<{ key: StageKey; label: string; help: ToggleHelp }> = [
  {
    key: "character",
    label: "Character",
    help: {
      on: "Generate or refresh the Test Lab character reference before scene assets.",
      off: "Use the preset or current global character context without regenerating a reference.",
    },
  },
  {
    key: "audio",
    label: "Audio",
    help: {
      on: "Generate ElevenLabs voiceover audio and word timing for the scene.",
      off: "Reuse any existing audio/timing if present; downstream stages may fall back to estimates or fail if timing is required.",
    },
  },
  {
    key: "visual",
    label: "Visual",
    help: {
      on: "Generate the selected AI image or AI video anchor media for the scene.",
      off: "Skip scene media generation and reuse any existing media already attached to the hidden Test Lab script.",
    },
  },
  {
    key: "treatment_assets",
    label: "Animation assets",
    help: {
      on: "Generate extra image layers used by popup sequence and flip-flop animation types.",
      off: "Render with the base scene media only; layered animation types may have fewer or no extra cutout assets.",
    },
  },
  {
    key: "fx",
    label: "FX",
    help: {
      on: "Ask the FX planner to create camera movement, punch timing, and transition metadata.",
      off: "Use the scene's existing FX settings or render with the default static/full-frame behavior.",
    },
  },
  {
    key: "eli",
    label: "Eli",
    help: {
      on: "Generate Eli overlay animation timing when Eli is enabled for this run.",
      off: "Skip Eli animation timing; any render proceeds without a newly planned Eli overlay.",
    },
  },
  {
    key: "render",
    label: "Render",
    help: {
      on: "Render a playable Remotion video after the selected stages finish.",
      off: "Stop after asset generation so you can inspect intermediate output without making a video.",
    },
  },
];

const TREATMENT_OPTIONS: Array<{
  value: VisualTreatment;
  label: string;
  summary: string;
  description: string;
  bestFor: string;
}> = [
  {
    value: "full_frame",
    label: "Full frame",
    summary: "Single image or video fills the canvas.",
    description: "Renders the base scene media edge-to-edge over the canvas, with normal subtitles and FX layered on top.",
    bestFor: "Use for cinematic shots, simple illustrations, AI video scenes, or moments where one strong visual should carry the line.",
  },
  {
    value: "popup_sequence",
    label: "Popup sequence",
    summary: "Small panels appear on narration beats.",
    description: "Keeps the canvas visible while timed visual layers pop in one by one, usually as compact callouts across the frame.",
    bestFor: "Use for lists, step-by-step explanations, object callouts, or scenes where the narration names several distinct things.",
  },
  {
    value: "flipflop",
    label: "Flip-flop",
    summary: "Two visuals alternate for quick contrast.",
    description: "Switches between paired visual layers on a steady rhythm to create motion without generating a video clip.",
    bestFor: "Use for before-and-after ideas, two-state comparisons, repeated choices, or fast comedic contrast.",
  },
];

export default function TestLabControls({
  preset,
  defaultMainCharacter,
  settings,
  onChange,
  onValidityChange,
}: TestLabControlsProps) {
  const narration = settings.narration ?? preset?.narration ?? "";
  const visualPrompt = settings.visual_prompt ?? preset?.visual_prompt ?? "";
  const backgroundColor = settings.visual_canvas?.background_color ?? preset?.background_color ?? "#F6C54A";
  const displayedCharacter = getDisplayedCharacter(settings, preset, defaultMainCharacter);
  const displayedCharacterSource = getDisplayedCharacterSource(settings, defaultMainCharacter);
  const fallbackCharacterName = getFallbackCharacterName(settings, preset, defaultMainCharacter);
  const isAiVideo = settings.media_source === "ai_video";
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
    if (isAiVideo && key === "treatment_assets") return;
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
              detail={stage.key === "character" ? fallbackCharacterName : undefined}
              checked={stage.key === "treatment_assets" && isAiVideo ? false : settings.stages[stage.key]}
              help={stage.help}
              disabled={isAiVideo && stage.key === "treatment_assets"}
              onChange={(enabled) => updateStage(stage.key, enabled)}
            />
          ))}
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
        <div className="grid gap-2 sm:grid-cols-2">
          <CharacterModeButton
            icon={<UserRound className="h-4 w-4" />}
            label="Eli enabled"
            description="Use the overlay host instead of a scene protagonist."
            checked={settings.eli_enabled}
            help={{
              on: "Allow Eli to be planned as an overlay host; the Eli stage can generate animation timing.",
              off: "Disable Eli for this run, so the Eli stage has no overlay host to plan even if selected.",
            }}
            onChange={(enabled) => update({ eli_enabled: enabled })}
          />
          <CharacterModeButton
            icon={<Palette className="h-4 w-4" />}
            label="Style preset"
            description="Apply the active preset character and house style."
            checked={settings.style_preset_enabled}
            help={{
              on: "Apply the house visual style preset to generated character, image, and animation assets.",
              off: "Use the raw preset prompt/settings without injecting the house style preset.",
            }}
            onChange={(enabled) => update({ style_preset_enabled: enabled })}
          />
        </div>
        <div className="mt-3">
          {settings.eli_enabled ? (
            <CharacterNotice
              icon={<UserRound className="h-5 w-5" />}
              title="Eli overlay active"
              description="This run will plan Eli as the host and skip integrating a main character into generated scene images."
            />
          ) : displayedCharacter ? (
            <CharacterPreview character={displayedCharacter} source={displayedCharacterSource} />
          ) : (
            <CharacterNotice
              icon={<Palette className="h-5 w-5" />}
              title="No active character"
              description="Select or generate a character in Settings -> Style Presets before running style-preset character tests."
            />
          )}
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
            onClick={() =>
              update({
                media_source: "ai_video",
                visual_treatment: "full_frame",
                visual_layers: [],
                stages: { ...settings.stages, treatment_assets: false },
              })
            }
          />
        </div>
      </Panel>

      <Panel title="Animation type, FX, canvas" help="Tune the render wrapper and overlay behavior around the generated scene media.">
        <div className="grid grid-cols-2 gap-3">
          <div className="block">
            <span className={`text-xs font-medium ${isAiVideo ? "text-neutral-500" : "text-neutral-300"}`}>
              Animation type
            </span>
            <div className="mt-2 grid gap-2">
              {TREATMENT_OPTIONS.map((option) => (
                <TreatmentOptionButton
                  key={option.value}
                  option={option}
                  active={settings.visual_treatment === option.value}
                  disabled={isAiVideo}
                  onClick={() => update({ visual_treatment: option.value })}
                />
              ))}
            </div>
            {isAiVideo && (
              <p className="mt-2 text-xs leading-5 text-neutral-500">
                AI video scenes render the generated clip full-frame, so layered animation assets are disabled.
              </p>
            )}
          </div>
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
            help={{
              on: "Render word-level subtitle emphasis in the preview.",
              off: "Show plain subtitles without per-word highlight styling.",
            }}
            onChange={(enabled) => update({ subtitle_highlight_enabled: enabled })}
          />
          <ToggleButton
            label="Segment timer"
            checked={settings.segment_timer_enabled}
            help={{
              on: "Show the short-form segment timer overlay when the selected format supports it.",
              off: "Hide the segment timer overlay and render only the scene visuals/subtitles.",
            }}
            onChange={(enabled) => update({ segment_timer_enabled: enabled })}
          />
        </div>
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
    </div>
  );
}

function getFallbackCharacterName(
  settings: TestLabSettings,
  preset: TestLabPreset | null,
  defaultMainCharacter: TestLabMainCharacter | null,
) {
  const character = getDisplayedCharacter(settings, preset, defaultMainCharacter);
  const name = character?.name?.trim();
  return name ? `Default: ${name}` : "No default character";
}

function getDisplayedCharacter(
  settings: TestLabSettings,
  preset: TestLabPreset | null,
  defaultMainCharacter: TestLabMainCharacter | null,
) {
  void preset;
  if (settings.eli_enabled) return null;
  return settings.main_character ?? (settings.style_preset_enabled ? defaultMainCharacter : null);
}

function getDisplayedCharacterSource(
  settings: TestLabSettings,
  defaultMainCharacter: TestLabMainCharacter | null,
) {
  if (settings.main_character) return "Custom run override";
  if (defaultMainCharacter) return "Active style preset character";
  return "No active character";
}

function CharacterPreview({
  character,
  source,
}: {
  character: TestLabMainCharacter;
  source: string;
}) {
  const referenceUrl = character.reference_image_url?.trim();

  return (
    <div className="overflow-hidden rounded-md border border-neutral-800 bg-neutral-950/70">
      <div className="p-3">
        <div className="flex h-64 items-center justify-center overflow-hidden rounded-md border border-neutral-800 bg-neutral-900/80">
          {referenceUrl ? (
            <img
              src={assetUrl(referenceUrl)}
              alt={character.name}
              className="h-full w-full scale-110 object-contain"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-xs text-neutral-600">
              No character reference image
            </div>
          )}
        </div>
        <div className="mt-3 grid gap-3 rounded-md bg-neutral-900/70 p-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">{source}</p>
            <p className="mt-2 text-lg font-semibold leading-tight text-neutral-100">{character.name}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-neutral-400 sm:justify-end">
            <span className="rounded-md border border-neutral-800 bg-neutral-950/70 px-2 py-1 text-neutral-300">
              Protagonist
            </span>
            <span className="rounded-md border border-neutral-800 bg-neutral-950/70 px-2 py-1">
              Reference{" "}
              <span className={`text-right font-medium ${referenceUrl ? "text-emerald-300" : "text-amber-300"}`}>
                {referenceUrl ? "Ready" : "Missing"}
              </span>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function CharacterNotice({
  icon,
  title,
  description,
}: {
  icon: ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="flex min-h-32 items-center gap-3 rounded-md border border-neutral-800 bg-neutral-950/70 p-4">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-neutral-900 text-neutral-400">
        {icon}
      </div>
      <div>
        <p className="text-sm font-semibold text-neutral-100">{title}</p>
        <p className="mt-1 max-w-xl text-xs leading-5 text-neutral-500">{description}</p>
      </div>
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
  detail,
  checked,
  help,
  disabled = false,
  onChange,
}: {
  label: string;
  detail?: string;
  checked: boolean;
  help: ToggleHelp;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <Tooltip content={<ToggleHelpContent help={help} />}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`flex min-h-10 items-center justify-between gap-2 rounded-md border px-3 py-2 text-left text-xs transition-colors ${
          disabled
            ? "cursor-not-allowed border-neutral-900 bg-neutral-950/50 text-neutral-700"
            : checked
              ? "border-violet-500/70 bg-violet-500/15 text-neutral-100"
              : "border-neutral-800 bg-neutral-950/70 text-neutral-500 hover:border-neutral-700 hover:text-neutral-200"
        }`}
      >
        <span className="min-w-0">
          <span className="block truncate">{label}</span>
          {detail && <span className="mt-0.5 block truncate text-[11px] text-neutral-500">{detail}</span>}
        </span>
        <span className={`h-2 w-2 shrink-0 rounded-full ${checked && !disabled ? "bg-violet-300" : "bg-neutral-700"}`} />
      </button>
    </Tooltip>
  );
}

function CharacterModeButton({
  icon,
  label,
  description,
  checked,
  help,
  onChange,
}: {
  icon: ReactNode;
  label: string;
  description: string;
  checked: boolean;
  help: ToggleHelp;
  onChange: (checked: boolean) => void;
}) {
  return (
    <Tooltip content={<ToggleHelpContent help={help} />} className="w-full">
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={`flex min-h-24 w-full items-start gap-3 rounded-md border p-3 text-left transition-colors ${
          checked
            ? "border-violet-500/80 bg-violet-500/15 text-neutral-100 shadow-[0_0_0_1px_rgba(139,92,246,0.18)]"
            : "border-neutral-800 bg-neutral-950/70 text-neutral-400 hover:border-neutral-700 hover:bg-neutral-900/70 hover:text-neutral-100"
        } focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/60`}
      >
        <span
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-md ${
            checked ? "bg-violet-400/15 text-violet-200" : "bg-neutral-900 text-neutral-500"
          }`}
        >
          {icon}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center justify-between gap-3">
            <span className="text-sm font-semibold">{label}</span>
            <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${checked ? "bg-violet-300" : "bg-neutral-700"}`} />
          </span>
          <span className={`mt-2 block text-xs leading-5 ${checked ? "text-violet-100/70" : "text-neutral-500"}`}>
            {description}
          </span>
        </span>
      </button>
    </Tooltip>
  );
}

function ToggleHelpContent({ help }: { help: ToggleHelp }) {
  return (
    <span className="block space-y-1">
      <span className="block">
        <span className="font-semibold text-violet-200">ON:</span> {help.on}
      </span>
      <span className="block">
        <span className="font-semibold text-neutral-100">OFF:</span> {help.off}
      </span>
    </span>
  );
}

function TreatmentOptionButton({
  option,
  active,
  disabled = false,
  onClick,
}: {
  option: (typeof TREATMENT_OPTIONS)[number];
  active: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  const [showHelp, setShowHelp] = useState(false);

  return (
    <div className="relative">
      <button
        type="button"
        disabled={disabled}
        onClick={onClick}
        onMouseEnter={() => setShowHelp(true)}
        onMouseLeave={() => setShowHelp(false)}
        onFocus={() => setShowHelp(true)}
        onBlur={() => setShowHelp(false)}
        aria-describedby={`treatment-help-${option.value}`}
        className={`flex min-h-16 w-full items-start justify-between gap-3 rounded-md border px-3 py-2 text-left transition-colors ${
          disabled
            ? "cursor-not-allowed border-neutral-900 bg-neutral-950/40 text-neutral-600"
            : active
              ? "border-violet-500/80 bg-violet-500/15 text-neutral-100"
              : "border-neutral-800 bg-neutral-950/70 text-neutral-400 hover:border-neutral-700 hover:bg-neutral-900/70 hover:text-neutral-100"
        }`}
      >
        <span className="min-w-0">
          <span className="block text-sm font-medium">{option.label}</span>
          <span className="mt-1 block text-xs leading-4 text-neutral-500">{option.summary}</span>
        </span>
        <HelpCircle
          className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${active && !disabled ? "text-violet-300" : "text-neutral-600"}`}
        />
      </button>
      {showHelp && (
        <div
          id={`treatment-help-${option.value}`}
          role="tooltip"
          className="absolute left-0 top-full z-50 mt-2 w-72 rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-left text-xs leading-snug text-neutral-200 shadow-xl"
        >
          <TreatmentHelpContent option={option} />
        </div>
      )}
    </div>
  );
}

function TreatmentHelpContent({ option }: { option: (typeof TREATMENT_OPTIONS)[number] }) {
  return (
    <span className="block max-w-72 space-y-2">
      <span className="block font-semibold text-neutral-100">{option.label}</span>
      <span className="block text-neutral-200">{option.description}</span>
      <span className="block text-neutral-400">{option.bestFor}</span>
    </span>
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
