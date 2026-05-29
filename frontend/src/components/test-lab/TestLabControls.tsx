import {
  Captions,
  ChevronDown,
  Columns3,
  Film,
  HelpCircle,
  Image,
  Images,
  Palette,
  PanelsTopLeft,
  Repeat2,
  Route,
  Settings,
  UserRound,
} from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { assetUrl } from "../../api";
import type {
  TestLabMainCharacter,
  TestLabPreset,
  TestLabSceneTextDefaults,
  TestLabSettings,
  TestLabStages,
  TestLabSubtitleSummary,
  TestLabVoiceSummary,
} from "../../types/testLab";
import type { VisualLayer, VisualMode } from "../../types/script";
import { Tooltip } from "../ui/Tooltip";

type StageKey = keyof TestLabStages;
type VisualTextDefaults = TestLabSceneTextDefaults & {
  caption_text?: string;
  caption_emphasis?: string;
};

interface TestLabControlsProps {
  preset: TestLabPreset | null;
  defaultMainCharacter: TestLabMainCharacter | null;
  visualTreatmentDefaults?: Partial<Record<VisualMode, VisualTextDefaults>>;
  settings: TestLabSettings;
  voiceSummary?: TestLabVoiceSummary | null;
  subtitleSummary?: TestLabSubtitleSummary | null;
  onChange: (settings: TestLabSettings) => void;
  onValidityChange?: (valid: boolean) => void;
  onOpenSettingsSection?: (section: "voice" | "subtitles") => void;
}

type ToggleHelp = {
  on: string;
  off: string;
};

const STAGE_OPTIONS: Array<{ key: StageKey; label: string; help: ToggleHelp }> = [
  {
    key: "audio",
    label: "Voiceover",
    help: {
      on: "Generate ElevenLabs voiceover audio and word timing for the scene.",
      off: "Reuse existing audio/timing if present; downstream stages may fall back to estimates or fail if timing is required.",
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
    key: "fx",
    label: "FX",
    help: {
      on: "Ask the FX planner to create camera movement, punch timing, and transition metadata.",
      off: "Render with the default static/full-frame behavior or existing FX settings.",
    },
  },
  {
    key: "render",
    label: "Render",
    help: {
      on: "Render a playable Remotion video after selected stages finish.",
      off: "Stop after asset generation so intermediate output can be inspected.",
    },
  },
];

const VISUAL_MODE_OPTIONS: Array<{
  value: VisualMode;
  label: string;
  icon: ReactNode;
  summary: string;
  description: string;
  bestFor: string;
}> = [
  {
    value: "video",
    label: "Video",
    icon: <Film className="h-4 w-4" />,
    summary: "Anchor image becomes an AI clip.",
    description: "Creates a normal anchor image, sends it to the video provider, then renders the clip full-frame.",
    bestFor: "Character gestures, physical motion, reveals, and moments where motion carries the beat.",
  },
  {
    value: "full_frame",
    label: "Full frame",
    icon: <Image className="h-4 w-4" />,
    summary: "One generated image fills the scene.",
    description: "Renders one edge-to-edge scene image with normal subtitles and FX layered on top.",
    bestFor: "Cinematic shots, simple illustrations, and lines that need one strong image.",
  },
  {
    value: "multi_frame",
    label: "Multi-frame",
    icon: <Images className="h-4 w-4" />,
    summary: "Several independent images cut together.",
    description: "Generates multiple frames for examples, comparisons, or quick visual variety.",
    bestFor: "Lists, multiple examples, montage rhythm, and fast context changes.",
  },
  {
    value: "continuous",
    label: "Continuous",
    icon: <Route className="h-4 w-4" />,
    summary: "One scene progresses over frames.",
    description: "Generates related frames with continuity so a process unfolds over time.",
    bestFor: "Growth, construction, transformation, and a single action progressing.",
  },
  {
    value: "popup_sequence",
    label: "Popup sequence",
    icon: <PanelsTopLeft className="h-4 w-4" />,
    summary: "Timed cutouts appear around an anchor.",
    description: "Generates one anchor plus item cutouts that pop in on narration beats.",
    bestFor: "Object callouts, named lists, and quick step-by-step explanations.",
  },
  {
    value: "flipflop",
    label: "Flip-flop",
    icon: <Repeat2 className="h-4 w-4" />,
    summary: "Two compatible states alternate.",
    description: "Generates paired full-bleed state panels for same-subject micro-animation.",
    bestFor: "Opening/closing, typing, pointing, nodding, and other simple repeated actions.",
  },
  {
    value: "comparison_board",
    label: "Comparison board",
    icon: <Columns3 className="h-4 w-4" />,
    summary: "Cutout subjects land in columns.",
    description: "Generates subject cutouts while Remotion owns labels, dividers, and board layout.",
    bestFor: "Before/after, myth/reality, good/bad choices, and two- or three-way contrasts.",
  },
  {
    value: "captions",
    label: "Captions",
    icon: <Captions className="h-4 w-4" />,
    summary: "Big editorial text is the visual punch.",
    description: "Renders in-scene caption text with emphasis while suppressing normal subtitles.",
    bestFor: "Reversals, payoff words, shocking claims, and punch-card moments.",
  },
];

export default function TestLabControls({
  preset,
  defaultMainCharacter,
  visualTreatmentDefaults,
  settings,
  voiceSummary,
  subtitleSummary,
  onChange,
  onValidityChange,
  onOpenSettingsSection,
}: TestLabControlsProps) {
  const narration = settings.narration ?? preset?.narration ?? "";
  const visualPrompt = settings.visual_prompt ?? preset?.visual_prompt ?? "";
  const visualMode = settings.visual_mode;
  const captionText =
    settings.caption_text ??
    (visualMode === "captions" && !shouldReplaceSceneText(settings.narration, preset?.narration)
      ? narration
      : preset?.caption_text ?? "");
  const captionEmphasis = settings.caption_emphasis ?? preset?.caption_emphasis ?? "";
  const backgroundColor = settings.visual_canvas?.background_color ?? preset?.background_color ?? "#F6C54A";
  const displayedCharacter = getDisplayedCharacter(settings, preset, defaultMainCharacter);
  const displayedCharacterSource = getDisplayedCharacterSource(settings, defaultMainCharacter);

  useEffect(() => {
    onValidityChange?.(true);
  }, [onValidityChange]);

  function update(next: Partial<TestLabSettings>) {
    onChange({ ...settings, ...next });
  }

  function updateNarration(value: string) {
    const next: Partial<TestLabSettings> = { narration: value, tts_narration: value };
    if (visualMode === "captions" && captionMatchesDefault(settings.caption_text, preset, visualTreatmentDefaults)) {
      next.caption_text = undefined;
      next.caption_emphasis = undefined;
    }
    update(next);
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

  function updateVisualMode(nextMode: VisualMode) {
    const nextLayered = isLayeredVisualMode(nextMode);
    const shouldPreserveLayers = nextLayered && nextMode === visualMode;
    onChange(settingsWithVisualTreatmentDefaults(
      {
        ...settings,
        visual_mode: nextMode,
        visual_layers: shouldPreserveLayers ? settings.visual_layers : defaultLayersForMode(nextMode, visualPrompt, narration),
        frame_directives: usesFrameDirectives(nextMode)
          ? defaultFrameDirectivesForMode(nextMode, visualPrompt)
          : undefined,
        stages: {
          ...settings.stages,
          treatment_assets: nextLayered,
        },
      },
      preset,
      nextMode,
      visualTreatmentDefaults,
    ));
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

      <AccordionPanel
        title="Visual Mode"
        testId="test-lab-section-visual-mode"
        help="Choose the single scene visual route and edit the prompt fields that route actually consumes."
      >
        <div className="grid grid-cols-2 gap-2">
          {VISUAL_MODE_OPTIONS.map((option) => (
            <TreatmentOptionButton
              key={option.value}
              option={option}
              active={visualMode === option.value}
              onClick={() => updateVisualMode(option.value)}
            />
          ))}
        </div>
        <div className="mt-4 space-y-3">
          <SceneTextFields
            visualMode={visualMode}
            narration={narration}
            visualPrompt={visualPrompt}
            captionText={captionText}
            captionEmphasis={captionEmphasis}
            frameDirectives={settings.frame_directives ?? []}
            visualLayers={settings.visual_layers}
            onNarrationChange={updateNarration}
            onVisualPromptChange={(value) => update({ visual_prompt: value })}
            onCaptionTextChange={(value) => update({ caption_text: value })}
            onCaptionEmphasisChange={(value) => update({ caption_emphasis: value })}
            onFrameDirectivesChange={(frame_directives) => update({ frame_directives })}
            onVisualLayersChange={(visual_layers) => update({ visual_layers })}
          />
          <AdvancedModeData
            visualMode={visualMode}
            frameDirectives={settings.frame_directives ?? []}
            visualLayers={settings.visual_layers}
            captionText={captionText}
            captionEmphasis={captionEmphasis}
          />
        </div>
      </AccordionPanel>

      <AccordionPanel title="Character" testId="test-lab-section-character" help="Choose whether this run uses the active character context or Eli.">
        <div className="grid gap-2 sm:grid-cols-2">
          <CharacterModeButton
            icon={<Palette className="h-4 w-4" />}
            label="Style preset"
            description="Use the active preset character and house style."
            checked={settings.style_preset_enabled && !settings.eli_enabled}
            help={{
              on: "Generated scene assets use the active style preset and character context.",
              off: "This run is not using the active preset character path.",
            }}
            onChange={() => update({ style_preset_enabled: true, eli_enabled: false })}
          />
          <CharacterModeButton
            icon={<UserRound className="h-4 w-4" />}
            label="Eli"
            description="Use Eli as the character and generate Eli animation timing."
            checked={settings.eli_enabled}
            help={{
              on: "Eli is the character context and the derived Eli animation stage will run.",
              off: "The run uses the style preset or global character context instead.",
            }}
            onChange={(enabled) => update({ eli_enabled: enabled, style_preset_enabled: !enabled })}
          />
        </div>
        <div className="mt-3">
          {settings.eli_enabled ? (
            <CharacterNotice
              icon={<UserRound className="h-5 w-5" />}
              title="Eli active"
              description="This run uses Eli and will generate Eli animation timing when audio is available."
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
      </AccordionPanel>

      <AccordionPanel title="Voices" testId="test-lab-section-voices" help="Shows the saved voice configuration used for this run.">
        <ReadOnlyVoiceSummary voiceSummary={voiceSummary} onOpenSettingsSection={onOpenSettingsSection} />
      </AccordionPanel>

      <AccordionPanel title="Pipeline Stages" testId="test-lab-section-pipeline-stages" help="Disable generation stages to inspect partial output or reuse intermediate assets.">
        <div className="grid grid-cols-2 gap-2">
          {STAGE_OPTIONS.map((stage) => {
            return (
              <ToggleButton
                key={stage.key}
                label={stage.label}
                checked={settings.stages[stage.key]}
                help={stage.help}
                disabled={false}
                onChange={(enabled) => updateStage(stage.key, enabled)}
              />
            );
          })}
        </div>
        <div className="mt-3 rounded-md border border-neutral-800 bg-neutral-950/70 p-3">
          <p className="text-xs font-semibold uppercase text-neutral-500">Derived stage</p>
          <p className="mt-2 text-sm font-medium text-neutral-100">
            Eli animation {settings.eli_enabled ? "on" : "off"}
          </p>
          <p className="mt-1 text-xs leading-5 text-neutral-500">
            {settings.eli_enabled
              ? "Eli is selected in Character, so timing is generated from voiceover automatically."
              : "Using preset/current global character context; no Eli timing is generated."}
          </p>
        </div>
      </AccordionPanel>

      <AccordionPanel title="Miscellaneous" testId="test-lab-section-miscellaneous" help="Render-level options that are independent from visual mode selection.">
        <div className="space-y-3">
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
          <ReadOnlySubtitleSummary subtitleSummary={subtitleSummary} onOpenSettingsSection={onOpenSettingsSection} />
        </div>
      </AccordionPanel>
    </div>
  );
}

export function settingsWithVisualTreatmentDefaults(
  settings: TestLabSettings,
  _preset: TestLabPreset | null,
  _visualTreatment: VisualMode,
  _visualTreatmentDefaults?: Partial<Record<VisualMode, VisualTextDefaults>>,
): TestLabSettings {
  return { ...settings };
}

function SceneTextFields({
  visualMode,
  narration,
  visualPrompt,
  captionText,
  captionEmphasis,
  frameDirectives,
  visualLayers,
  onNarrationChange,
  onVisualPromptChange,
  onCaptionTextChange,
  onCaptionEmphasisChange,
  onFrameDirectivesChange,
  onVisualLayersChange,
}: {
  visualMode: VisualMode;
  narration: string;
  visualPrompt: string;
  captionText: string;
  captionEmphasis: string;
  frameDirectives: Array<Record<string, unknown>>;
  visualLayers: VisualLayer[];
  onNarrationChange: (value: string) => void;
  onVisualPromptChange: (value: string) => void;
  onCaptionTextChange: (value: string) => void;
  onCaptionEmphasisChange: (value: string) => void;
  onFrameDirectivesChange: (value: Array<Record<string, unknown>>) => void;
  onVisualLayersChange: (value: VisualLayer[]) => void;
}) {
  return (
    <div className="space-y-3">
      <TextareaField label="Narration" value={narration} rows={4} onChange={onNarrationChange} />
      <TextareaField
        label={visualMode === "video" ? "Anchor visual prompt" : visualMode === "comparison_board" ? "Board scene prompt" : "Visual prompt"}
        value={visualPrompt}
        rows={4}
        onChange={onVisualPromptChange}
      />
      {usesFrameDirectives(visualMode) && (
        <FrameDirectiveFields
          visualMode={visualMode}
          visualPrompt={visualPrompt}
          directives={frameDirectives}
          onChange={onFrameDirectivesChange}
        />
      )}
      {visualMode === "flipflop" && (
        <LayerPromptFields
          labels={["State A", "State B"]}
          visualLayers={visualLayers}
          fallbackPrompt={visualPrompt || narration}
          onChange={onVisualLayersChange}
        />
      )}
      {visualMode === "popup_sequence" && (
        <LayerPromptFields
          labels={["Popup item 1", "Popup item 2", "Popup item 3"]}
          visualLayers={visualLayers}
          fallbackPrompt={visualPrompt || narration}
          onChange={onVisualLayersChange}
        />
      )}
      {visualMode === "comparison_board" && (
        <LayerPromptFields
          labels={["Left subject", "Right subject", "Third subject"]}
          visualLayers={visualLayers}
          fallbackPrompt={visualPrompt || narration}
          onChange={onVisualLayersChange}
        />
      )}
      {visualMode === "captions" && (
        <div className="grid gap-3 sm:grid-cols-2">
          <InputField label="Caption text" value={captionText} onChange={onCaptionTextChange} />
          <InputField label="Red emphasis" value={captionEmphasis} onChange={onCaptionEmphasisChange} />
        </div>
      )}
    </div>
  );
}

function FrameDirectiveFields({
  visualMode,
  visualPrompt,
  directives,
  onChange,
}: {
  visualMode: VisualMode;
  visualPrompt: string;
  directives: Array<Record<string, unknown>>;
  onChange: (value: Array<Record<string, unknown>>) => void;
}) {
  const labels = visualMode === "continuous" ? ["Start frame", "Middle progression", "Later progression"] : ["Frame 1", "Frame 2", "Frame 3"];
  const resolved = directives.length ? directives : defaultFrameDirectivesForMode(visualMode, visualPrompt);
  return (
    <div className="grid gap-3">
      {labels.map((label, index) => (
        <TextareaField
          key={label}
          label={label}
          value={String(resolved[index]?.prompt ?? "")}
          rows={2}
          onChange={(prompt) => {
            const next = [...resolved];
            next[index] = {
              ...next[index],
              prompt,
              source: "ai_generated",
              transition: index === 0 || visualMode === "multi_frame" ? "cut" : "crossfade",
              reference_previous: visualMode === "continuous" && index > 0,
              search_query: "",
            };
            onChange(next);
          }}
        />
      ))}
    </div>
  );
}

function LayerPromptFields({
  labels,
  visualLayers,
  fallbackPrompt,
  onChange,
}: {
  labels: string[];
  visualLayers: VisualLayer[];
  fallbackPrompt: string;
  onChange: (value: VisualLayer[]) => void;
}) {
  const resolved = visualLayers.length ? visualLayers : labels.map((_label, index) => ({
    id: `layer_${index + 1}`,
    type: "image" as const,
    asset_kind: "panel" as const,
    prompt: fallbackPrompt,
    placement: index === 0 ? "left" : index === 1 ? "right" : "center",
    enter_at_seconds: index,
    animation: "pop_in" as const,
  }));
  return (
    <div className="grid gap-3">
      {labels.map((label, index) => (
        <TextareaField
          key={label}
          label={label}
          value={String(resolved[index]?.prompt ?? "")}
          rows={2}
          onChange={(prompt) => {
            const next = [...resolved];
            next[index] = { ...next[index], prompt };
            onChange(next);
          }}
        />
      ))}
    </div>
  );
}

function AdvancedModeData({
  visualMode,
  frameDirectives,
  visualLayers,
  captionText,
  captionEmphasis,
}: {
  visualMode: VisualMode;
  frameDirectives: Array<Record<string, unknown>>;
  visualLayers: VisualLayer[];
  captionText: string;
  captionEmphasis: string;
}) {
  const data = visualMode === "captions"
    ? { caption_text: captionText, caption_emphasis: captionEmphasis }
    : usesFrameDirectives(visualMode)
      ? { frame_directives: frameDirectives }
      : isLayeredVisualMode(visualMode)
        ? { visual_layers: visualLayers }
        : {};
  return (
    <details className="rounded-md border border-neutral-800 bg-neutral-950/60 p-3">
      <summary className="cursor-pointer text-xs font-semibold uppercase text-neutral-400">Advanced Mode Data</summary>
      <pre className="mt-3 max-h-48 overflow-auto rounded-md bg-neutral-950 p-3 text-xs leading-5 text-neutral-300">
        {JSON.stringify(data, null, 2)}
      </pre>
    </details>
  );
}

function ReadOnlyVoiceSummary({
  voiceSummary,
  onOpenSettingsSection,
}: {
  voiceSummary?: TestLabVoiceSummary | null;
  onOpenSettingsSection?: (section: "voice" | "subtitles") => void;
}) {
  return (
    <div className="rounded-md border border-neutral-800 bg-neutral-950/70 p-3">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-neutral-900 text-violet-200">
          <Settings className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-neutral-100">{voiceSummary?.voice_name || "No voice selected"}</p>
          <p className="mt-1 text-xs leading-5 text-neutral-500">
            Test Lab uses Settings -&gt; Voices. Go to Settings -&gt; Voices to change narration voice or delivery.
          </p>
          <button
            type="button"
            onClick={() => onOpenSettingsSection?.("voice")}
            className="mt-3 inline-flex items-center gap-2 rounded-md border border-neutral-700 px-2.5 py-1.5 text-xs font-medium text-neutral-200 transition-colors hover:border-violet-500 hover:text-violet-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
          >
            <Settings className="h-3.5 w-3.5" />
            Open voice settings
          </button>
          <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
            <SummaryChip label="Model" value={voiceSummary?.model_label || "Settings default"} />
            {voiceSummary?.delivery_preset && <SummaryChip label="Delivery" value={voiceSummary.delivery_preset} />}
            {(voiceSummary?.visible_settings ?? []).map((item) => (
              <SummaryChip key={item.label} label={item.label} value={item.value} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ReadOnlySubtitleSummary({
  subtitleSummary,
  onOpenSettingsSection,
}: {
  subtitleSummary?: TestLabSubtitleSummary | null;
  onOpenSettingsSection?: (section: "voice" | "subtitles") => void;
}) {
  const enabledStyles = subtitleSummary?.enabled_style_labels?.length
    ? subtitleSummary.enabled_style_labels.join(", ")
    : "No standard subtitle styles enabled";
  return (
    <div>
      <span className="text-xs font-medium text-neutral-300">Subtitle settings</span>
      <p className="mt-2 text-xs leading-5 text-neutral-500">
        Test Lab uses Settings -&gt; Subtitles for subtitle coverage and eligible styles.
      </p>
      <button
        type="button"
        onClick={() => onOpenSettingsSection?.("subtitles")}
        className="mt-3 inline-flex items-center gap-2 rounded-md border border-neutral-700 px-2.5 py-1.5 text-xs font-medium text-neutral-200 transition-colors hover:border-violet-500 hover:text-violet-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
      >
        <Settings className="h-3.5 w-3.5" />
        Open subtitle settings
      </button>
      <div className="mt-3 space-y-2 text-xs">
        <SummaryChip label="Coverage" value={subtitleSummary?.coverage_label || "Settings default"} testId="test-lab-subtitle-summary-row" />
        <SummaryChip label="Styles" value={enabledStyles} testId="test-lab-subtitle-summary-row" />
      </div>
    </div>
  );
}

function SummaryChip({ label, value, testId }: { label: string; value: string; testId?: string }) {
  return (
    <span data-testid={testId} className="block rounded-md border border-neutral-800 bg-neutral-900/70 px-2 py-1 text-neutral-400">
      {label}: <span className="font-medium text-neutral-200">{value}</span>
    </span>
  );
}

function AccordionPanel({
  title,
  testId,
  help,
  children,
}: {
  title: string;
  testId: string;
  help: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(true);
  return (
    <section data-testid={testId} className="rounded-lg border border-neutral-800 bg-neutral-950/50">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 px-3 py-3 text-left transition-colors hover:bg-neutral-900/50"
      >
        <span className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase text-neutral-300">{title}</span>
          <Tooltip content={help} side="right">
            <HelpCircle className="h-3.5 w-3.5 text-neutral-600" />
          </Tooltip>
        </span>
        <ChevronDown className={`h-4 w-4 text-neutral-500 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <div className="border-t border-neutral-800 p-3">{children}</div>}
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
        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-md ${checked ? "bg-violet-400/15 text-violet-200" : "bg-neutral-900 text-neutral-500"}`}>
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
  onClick,
}: {
  option: (typeof VISUAL_MODE_OPTIONS)[number];
  active: boolean;
  onClick: () => void;
}) {
  const [showHelp, setShowHelp] = useState(false);
  return (
    <div className="relative">
      <button
        type="button"
        onClick={onClick}
        onMouseEnter={() => setShowHelp(true)}
        onMouseLeave={() => setShowHelp(false)}
        onFocus={() => setShowHelp(true)}
        onBlur={() => setShowHelp(false)}
        className={`flex min-h-16 w-full items-start justify-between gap-3 rounded-md border px-3 py-2 text-left transition-colors ${
          active
            ? "border-violet-500/80 bg-violet-500/15 text-neutral-100"
            : "border-neutral-800 bg-neutral-950/70 text-neutral-400 hover:border-neutral-700 hover:bg-neutral-900/70 hover:text-neutral-100"
        }`}
      >
        <span className="flex min-w-0 items-start gap-2">
          <span className={`mt-0.5 shrink-0 ${active ? "text-violet-300" : "text-neutral-500"}`}>{option.icon}</span>
          <span className="min-w-0">
            <span className="block text-sm font-medium">{option.label}</span>
            <span className="mt-1 block text-xs leading-4 text-neutral-500">{option.summary}</span>
          </span>
        </span>
        <HelpCircle className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${active ? "text-violet-300" : "text-neutral-600"}`} />
      </button>
      {showHelp && (
        <div
          role="tooltip"
          className="absolute left-0 top-full z-50 mt-2 w-72 rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-left text-xs leading-snug text-neutral-200 shadow-xl"
        >
          <span className="block max-w-72 space-y-2">
            <span className="block font-semibold text-neutral-100">{option.label}</span>
            <span className="block text-neutral-200">{option.description}</span>
            <span className="block text-neutral-400">{option.bestFor}</span>
          </span>
        </div>
      )}
    </div>
  );
}

function CharacterPreview({ character, source }: { character: TestLabMainCharacter; source: string }) {
  const referenceUrl = character.reference_image_url?.trim();
  return (
    <div className="overflow-hidden rounded-md border border-neutral-800 bg-neutral-950/70">
      <div className="p-3">
        <div className="flex h-64 items-center justify-center overflow-hidden rounded-md border border-neutral-800 bg-neutral-900/80">
          {referenceUrl ? (
            <img src={assetUrl(referenceUrl)} alt={character.name} className="h-full w-full scale-110 object-contain" />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-xs text-neutral-600">No character reference image</div>
          )}
        </div>
        <div className="mt-3 grid gap-3 rounded-md bg-neutral-900/70 p-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">{source}</p>
            <p className="mt-2 text-lg font-semibold leading-tight text-neutral-100">{character.name}</p>
          </div>
          <span className="rounded-md border border-neutral-800 bg-neutral-950/70 px-2 py-1 text-xs text-neutral-300">Protagonist</span>
        </div>
      </div>
    </div>
  );
}

function CharacterNotice({ icon, title, description }: { icon: ReactNode; title: string; description: string }) {
  return (
    <div className="flex min-h-32 items-center gap-3 rounded-md border border-neutral-800 bg-neutral-950/70 p-4">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-neutral-900 text-neutral-400">{icon}</div>
      <div>
        <p className="text-sm font-semibold text-neutral-100">{title}</p>
        <p className="mt-1 max-w-xl text-xs leading-5 text-neutral-500">{description}</p>
      </div>
    </div>
  );
}

function TextareaField({ label, value, rows, onChange }: { label: string; value: string; rows: number; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-neutral-300">{label}</span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={rows}
        className="mt-2 w-full resize-y rounded-md border border-neutral-800 bg-neutral-950/80 px-3 py-2 text-sm leading-5 text-neutral-100 outline-none transition-colors placeholder:text-neutral-600 hover:border-neutral-700 focus:border-violet-500"
      />
    </label>
  );
}

function InputField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-neutral-300">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full rounded-md border border-neutral-800 bg-neutral-950/80 px-3 py-2 text-sm text-neutral-100 outline-none transition-colors placeholder:text-neutral-600 hover:border-neutral-700 focus:border-violet-500"
      />
    </label>
  );
}

function shouldReplaceSceneText(currentValue: string | undefined, presetValue: string | undefined): boolean {
  return currentValue === undefined || currentValue === "" || currentValue === presetValue;
}

function captionMatchesDefault(
  currentValue: string | undefined,
  preset: TestLabPreset | null,
  visualTreatmentDefaults?: Partial<Record<VisualMode, VisualTextDefaults>>,
): boolean {
  if (currentValue === undefined || currentValue === "") return true;
  const defaultCaption = visualTreatmentDefaults?.captions?.caption_text;
  return currentValue === preset?.caption_text || currentValue === defaultCaption;
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

function getDisplayedCharacterSource(settings: TestLabSettings, defaultMainCharacter: TestLabMainCharacter | null) {
  if (settings.main_character) return "Custom run override";
  if (defaultMainCharacter) return "Active style preset character";
  return "No active character";
}

function isLayeredVisualMode(mode: VisualMode): boolean {
  return mode === "popup_sequence" || mode === "flipflop" || mode === "comparison_board";
}

function usesFrameDirectives(mode: VisualMode): boolean {
  return mode === "multi_frame" || mode === "continuous";
}

function defaultFrameDirectivesForMode(mode: VisualMode, visualPrompt: string): Array<Record<string, unknown>> {
  if (!usesFrameDirectives(mode)) return [];
  const prompts = mode === "continuous"
    ? [
        `Opening frame of the same continuous scene: ${visualPrompt}`,
        `Middle frame of the same continuous scene, same camera angle, visible progression: ${visualPrompt}`,
        `Final frame of the same continuous scene, same camera angle, completed progression: ${visualPrompt}`,
      ]
    : [
        visualPrompt,
        `${visualPrompt} A different angle from the same lived situation.`,
        `${visualPrompt} A close detail from the same scene.`,
      ];
  return prompts.map((prompt, index) => ({
    prompt,
    source: "ai_generated",
    transition: index === 0 || mode === "multi_frame" ? "cut" : "crossfade",
    reference_previous: mode === "continuous" && index > 0,
    search_query: "",
  }));
}

function defaultLayersForMode(mode: VisualMode, visualPrompt: string, narration: string): VisualLayer[] {
  if (!isLayeredVisualMode(mode)) return [];
  const basePrompt = visualPrompt || narration;
  if (mode === "flipflop") {
    return ["State A", "State B"].map((_label, index) => ({
      id: `flipflop_${index + 1}`,
      type: "image",
      asset_kind: "panel",
      prompt: basePrompt,
      placement: "center",
      enter_at_seconds: index,
      animation: "pop_in" as const,
    }));
  }
  const labels = mode === "comparison_board" ? ["Left subject", "Right subject"] : ["Popup item 1", "Popup item 2", "Popup item 3"];
  return labels.map((_label, index) => ({
    id: `${mode}_${index + 1}`,
    type: "image",
    asset_kind: mode === "comparison_board" ? "cutout" : "panel",
    prompt: basePrompt,
    placement: index === 0 ? "left" : index === 1 ? "right" : "center",
    enter_at_seconds: index,
    animation: "pop_in" as const,
  }));
}
