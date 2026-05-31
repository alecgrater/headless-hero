import { useEffect, useState } from "react";
import api from "../../api";
import type { VoiceInfo, VoiceListResponse } from "../../types/audio";

interface VoiceSectionProps {
  panel: "voice" | "audio";
  showHeader?: boolean;
}

export type TtsSettings = {
  ELEVENLABS_TTS_MODEL: string;
  ELEVENLABS_STABILITY: string;
  ELEVENLABS_STYLE: string;
  ELEVENLABS_SPEED: string;
};

type DeliveryPresetId = "steady" | "more_human" | "dramatic";
type DeliveryPresetSelection = DeliveryPresetId | "custom";

type DeliveryPreset = {
  label: string;
  summary: string;
  detail: string;
  settings: TtsSettings;
};

export const DELIVERY_PRESETS: Record<DeliveryPresetId, DeliveryPreset> = {
  steady: {
    label: "Steady",
    summary: "Most predictable voiceover for production runs.",
    detail: "Uses Eleven v2 with neutral delivery settings. Best when consistency matters more than extra emotion.",
    settings: {
      ELEVENLABS_TTS_MODEL: "eleven_multilingual_v2",
      ELEVENLABS_STABILITY: "0.5",
      ELEVENLABS_STYLE: "0.0",
      ELEVENLABS_SPEED: "1.0",
    },
  },
  more_human: {
    label: "More Human",
    summary: "A conservative warmth boost without changing model cost class.",
    detail: "Keeps Eleven v2, slightly lowers stability, adds light style, and slows delivery a touch for more natural pacing.",
    settings: {
      ELEVENLABS_TTS_MODEL: "eleven_multilingual_v2",
      ELEVENLABS_STABILITY: "0.45",
      ELEVENLABS_STYLE: "0.15",
      ELEVENLABS_SPEED: "0.97",
    },
  },
  dramatic: {
    label: "Dramatic",
    summary: "More expressive v2 delivery while staying on the steady model.",
    detail: "Keeps Eleven v2, lowers stability further, adds more style, and slows delivery slightly for heavier moments.",
    settings: {
      ELEVENLABS_TTS_MODEL: "eleven_multilingual_v2",
      ELEVENLABS_STABILITY: "0.35",
      ELEVENLABS_STYLE: "0.25",
      ELEVENLABS_SPEED: "0.95",
    },
  },
};

export function deliveryPresetForSettings(settings: TtsSettings): DeliveryPresetId | "custom" {
  const preset = Object.entries(DELIVERY_PRESETS).find(([, preset]) =>
    Object.entries(preset.settings).every(([key, value]) => settings[key as keyof TtsSettings] === value),
  );
  return (preset?.[0] as DeliveryPresetId | undefined) ?? "custom";
}

export function settingsPayloadForVisibleControls(settings: TtsSettings): Partial<TtsSettings> {
  if (settings.ELEVENLABS_TTS_MODEL === "eleven_v3") {
    return {
      ELEVENLABS_TTS_MODEL: "eleven_v3",
      ELEVENLABS_STABILITY: settings.ELEVENLABS_STABILITY,
    };
  }
  return { ...settings };
}

const VOICE_PRIORITY_PATTERNS = [
  "headless hero narrator",
  "liam - viral short-form storyteller",
  "adam greene",
];

function voicePriority(voice: VoiceInfo): number {
  const name = voice.name.toLowerCase();
  const exactIndex = VOICE_PRIORITY_PATTERNS.findIndex((pattern) => name === pattern);
  if (exactIndex >= 0) return exactIndex;
  const partialIndex = VOICE_PRIORITY_PATTERNS.findIndex((pattern) => name.includes(pattern));
  return partialIndex >= 0 ? partialIndex : VOICE_PRIORITY_PATTERNS.length;
}

export function sortVoicesForNarration(voices: VoiceInfo[]): VoiceInfo[] {
  return voices
    .filter((voice) => voicePriority(voice) < VOICE_PRIORITY_PATTERNS.length)
    .sort((a, b) => voicePriority(a) - voicePriority(b) || a.name.localeCompare(b.name));
}

export function defaultVoiceIdForNarration(voices: VoiceInfo[]): string {
  return sortVoicesForNarration(voices)[0]?.voice_id ?? "";
}

export default function VoiceSection({ panel, showHeader = true }: VoiceSectionProps) {
  const [voices, setVoices] = useState<VoiceInfo[]>([]);
  const [selectedVoiceId, setSelectedVoiceId] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [ttsSaving, setTtsSaving] = useState(false);
  const [ttsSettings, setTtsSettings] = useState<TtsSettings>({
    ELEVENLABS_TTS_MODEL: "eleven_multilingual_v2",
    ELEVENLABS_STABILITY: "0.5",
    ELEVENLABS_STYLE: "0.0",
    ELEVENLABS_SPEED: "1.0",
  });
  const [deliveryPresetSelection, setDeliveryPresetSelection] = useState<DeliveryPresetSelection>("steady");

  const [audioFilters, setAudioFilters] = useState({
    AUDIO_FILTER_HIGHPASS: true,
    AUDIO_FILTER_NOISE_REDUCTION: true,
    AUDIO_FILTER_COMPRESSOR: true,
  });

  useEffect(() => {
    if (panel !== "voice") return;
    api.get("/api/brand").then((res) => {
      if (res.ok) {
        const b = res.data as { voice_id: string };
        setSelectedVoiceId(b.voice_id || "");
      }
    });
  }, [panel]);

  useEffect(() => {
    if (panel !== "voice") return;
    api.get("/api/settings/keys").then((res) => {
      if (res.ok) {
        const keys = res.data as Record<string, { masked: string }>;
        const loadedSettings = {
          ELEVENLABS_TTS_MODEL: keys.ELEVENLABS_TTS_MODEL?.masked || "eleven_multilingual_v2",
          ELEVENLABS_STABILITY: keys.ELEVENLABS_STABILITY?.masked || "0.5",
          ELEVENLABS_STYLE: keys.ELEVENLABS_STYLE?.masked || "0.0",
          ELEVENLABS_SPEED: keys.ELEVENLABS_SPEED?.masked || "1.0",
        };
        setTtsSettings(loadedSettings);
        if (loadedSettings.ELEVENLABS_TTS_MODEL === "eleven_multilingual_v2") {
          setDeliveryPresetSelection(deliveryPresetForSettings(loadedSettings));
        }
      }
    });
  }, [panel]);

  useEffect(() => {
    if (panel !== "audio") return;
    api.get("/api/settings/keys").then((res) => {
      if (res.ok) {
        const keys = res.data as Record<string, { masked: string }>;
        setAudioFilters({
          AUDIO_FILTER_HIGHPASS: (keys.AUDIO_FILTER_HIGHPASS?.masked || "true") === "true",
          AUDIO_FILTER_NOISE_REDUCTION: (keys.AUDIO_FILTER_NOISE_REDUCTION?.masked || "true") === "true",
          AUDIO_FILTER_COMPRESSOR: (keys.AUDIO_FILTER_COMPRESSOR?.masked || "true") === "true",
        });
      }
    });
  }, [panel]);

  useEffect(() => {
    if (panel !== "voice") return;
    api.get("/api/voice/voices").then((res) => {
      if (res.ok) {
        const data = res.data as VoiceListResponse;
        const sorted = sortVoicesForNarration(data.voices);
        setVoices(sorted);
        if (sorted.length > 0 && (!selectedVoiceId || !sorted.some((voice) => voice.voice_id === selectedVoiceId))) {
          const fallback = defaultVoiceIdForNarration(sorted);
          setSelectedVoiceId(fallback);
          api.put("/api/brand", { voice_id: fallback });
        }
      }
    });
  }, [panel, selectedVoiceId]);

  const handleVoiceChange = async (voiceId: string) => {
    setSelectedVoiceId(voiceId);
    setSaving(true);
    await api.put("/api/brand", { voice_id: voiceId });
    setSaving(false);
  };

  const updateTtsSetting = (key: keyof typeof ttsSettings, value: string) => {
    if (ttsSettings.ELEVENLABS_TTS_MODEL === "eleven_multilingual_v2") {
      setDeliveryPresetSelection("custom");
    }
    setTtsSettings((prev) => ({ ...prev, [key]: value }));
  };

  const applyDeliveryPreset = (presetId: DeliveryPresetId) => {
    setDeliveryPresetSelection(presetId);
    setTtsSettings(DELIVERY_PRESETS[presetId].settings);
  };

  const applyModel = (modelId: "eleven_multilingual_v2" | "eleven_v3") => {
    setTtsSettings((prev) => ({
      ...prev,
      ELEVENLABS_TTS_MODEL: modelId,
      ...(modelId === "eleven_multilingual_v2" && deliveryPresetSelection !== "custom"
        ? DELIVERY_PRESETS[deliveryPresetSelection].settings
        : {}),
    }));
  };

  const saveTtsSettings = async () => {
    setTtsSaving(true);
    await api.put("/api/settings/keys", settingsPayloadForVisibleControls(ttsSettings));
    setTtsSaving(false);
  };

  const handleFilterToggle = async (key: keyof typeof audioFilters) => {
    const newValue = !audioFilters[key];
    setAudioFilters((prev) => ({ ...prev, [key]: newValue }));
    await api.put("/api/settings/keys", { [key]: newValue ? "true" : "false" });
  };

  const isV3 = ttsSettings.ELEVENLABS_TTS_MODEL === "eleven_v3";
  const activeDeliveryPreset =
    ttsSettings.ELEVENLABS_TTS_MODEL === "eleven_multilingual_v2"
      ? deliveryPresetSelection === "custom"
        ? "custom"
        : deliveryPresetForSettings(ttsSettings)
      : "custom";
  const activeDeliveryPresetDetail =
    activeDeliveryPreset === "custom"
      ? "Custom keeps your exact model and slider values. Save settings before regenerating voiceover."
      : DELIVERY_PRESETS[activeDeliveryPreset].detail;

  return (
    <div className="px-8 py-8 max-w-2xl space-y-6">
      {showHeader && (
      <div>
        <h2 className="text-lg font-semibold tracking-tight">
          {panel === "voice" ? "Voices" : "Audio"}
        </h2>
        <p className="text-neutral-400 text-sm mt-1">
          {panel === "voice"
            ? "Choose the saved narration voice and delivery settings."
            : "Tune recording export filters for manually recorded voiceover."}
        </p>
      </div>
      )}

      {panel === "voice" && (
      <div className="space-y-8">
      <section className="space-y-3">
        <div>
          <h3 className="text-sm font-semibold text-neutral-100">Default Voice</h3>
          <p className="text-xs leading-relaxed text-neutral-500">
            Select the ElevenLabs voice used for voiceover generation.
          </p>
        </div>
        <label className="sr-only" htmlFor="default-voice">
          Default Voice
        </label>
        <select
          id="default-voice"
          value={selectedVoiceId}
          onChange={(e) => handleVoiceChange(e.target.value)}
          className="w-full px-3 py-2 rounded-lg bg-neutral-800 border border-neutral-700 text-neutral-200 text-sm focus:outline-none focus:border-violet-500/50 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors"
        >
          <option value="">No voice selected</option>
          {voices.map((v) => (
            <option key={v.voice_id} value={v.voice_id}>
              {v.name}
            </option>
          ))}
        </select>
        {saving && <p className="text-xs text-violet-400">Saving...</p>}
        <p className="text-xs text-neutral-500">
          Recommended: Headless Hero Narrator for the main channel voice. Liam is a stronger shorts-style fallback; Adam is a friendlier backup.
        </p>
      </section>

      <section className="space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-neutral-100">ElevenLabs Delivery</h3>
          <p className="mt-1 text-xs leading-relaxed text-neutral-500">
            Controls the model, pacing, and hidden TTS-only instructions used for newly generated AI voiceover.
          </p>
        </div>

        <div className="space-y-2">
          <p className="text-sm font-medium text-neutral-200">Model</p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {([
              { id: "eleven_multilingual_v2", label: "v2 - steady production voice" },
              { id: "eleven_v3", label: "v3 - expressive voice with hidden tags" },
            ] as const).map((model) => (
              <button
                key={model.id}
                type="button"
                onClick={() => applyModel(model.id)}
                className={`rounded-lg border px-3 py-2 text-left text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
                  ttsSettings.ELEVENLABS_TTS_MODEL === model.id
                    ? "border-violet-500 bg-violet-500/15 text-violet-100"
                    : "border-neutral-700 bg-neutral-800 text-neutral-300 hover:bg-neutral-700"
                }`}
              >
                {model.label}
              </button>
            ))}
          </div>
          <p className="text-xs text-neutral-500">
            v2 is the stable production choice. v3 can sound more alive and currently adds a hidden TTS-only delivery tag for non-title scenes, but may vary more and take longer.
          </p>
        </div>

        {!isV3 && (
        <div className="space-y-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-neutral-200">Delivery preset</p>
              <p className="text-xs text-neutral-500 mt-1">
                For v2 only. Presets fill the saved delivery settings; choose Custom to tune sliders manually.
              </p>
            </div>
            <span className="rounded-full border border-neutral-700 bg-neutral-900 px-2 py-1 text-[11px] font-medium text-neutral-400">
              {activeDeliveryPreset === "custom" ? "Custom" : DELIVERY_PRESETS[activeDeliveryPreset].label}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(DELIVERY_PRESETS).map(([id, preset]) => (
              <button
                key={id}
                type="button"
                onClick={() => applyDeliveryPreset(id as DeliveryPresetId)}
                className={`rounded-lg border px-3 py-2 text-left text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
                  activeDeliveryPreset === id
                    ? "border-violet-500 bg-violet-500/15 text-violet-100"
                    : "border-neutral-700 bg-neutral-800 text-neutral-300 hover:bg-neutral-700"
                }`}
              >
                {preset.label}
              </button>
            ))}
            <button
              type="button"
              onClick={() => setDeliveryPresetSelection("custom")}
              className={`rounded-lg border px-3 py-2 text-left text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
                activeDeliveryPreset === "custom"
                  ? "border-violet-500 bg-violet-500/15 text-violet-100"
                  : "border-neutral-700 bg-neutral-800 text-neutral-300 hover:bg-neutral-700"
              }`}
            >
              Custom
            </button>
          </div>
          <p className="text-xs text-neutral-500">{activeDeliveryPresetDetail}</p>
        </div>
        )}

        {isV3 && (
          <div className="space-y-2 rounded-lg bg-neutral-800/50 border border-neutral-700/50 p-3">
            <div className="flex items-center justify-between gap-3">
              <label className="text-sm font-medium text-neutral-200" htmlFor="ELEVENLABS_STABILITY">
                Stability
              </label>
              <input
                id="ELEVENLABS_STABILITY-number"
                type="number"
                min="0"
                max="1"
                step="0.05"
                value={ttsSettings.ELEVENLABS_STABILITY}
                onChange={(e) => updateTtsSetting("ELEVENLABS_STABILITY", e.target.value)}
                className="w-20 px-2 py-1 rounded-md bg-neutral-900 border border-neutral-700 text-neutral-200 text-sm text-right focus:outline-none focus:border-violet-500/50 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors"
              />
            </div>
            <input
              id="ELEVENLABS_STABILITY"
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={ttsSettings.ELEVENLABS_STABILITY}
              onChange={(e) => updateTtsSetting("ELEVENLABS_STABILITY", e.target.value)}
              className="w-full accent-violet-500"
            />
            <p className="text-xs text-neutral-500">
              V3 exposes only stability here. Lower is more creative; higher is more robust. Around 0.5 matches ElevenLabs Natural.
            </p>
          </div>
        )}

        {!isV3 && activeDeliveryPreset === "custom" && ([
          {
            key: "ELEVENLABS_STABILITY" as const,
            label: "Stability",
            min: "0",
            max: "1",
            step: "0.05",
            recommended: "0.45 for More Human, 0.5 for Steady",
            desc: "Lower gives more emotion and surprise; higher keeps the voice steadier but can sound flatter.",
          },
          {
            key: "ELEVENLABS_STYLE" as const,
            label: "Style exaggeration",
            min: "0",
            max: "1",
            step: "0.05",
            recommended: "0.15 for More Human, 0.0 for Steady",
            desc: "Higher pushes the voice's natural style harder; lower is cleaner and more predictable. Too high can become unstable.",
          },
          {
            key: "ELEVENLABS_SPEED" as const,
            label: "Speed",
            min: "0.7",
            max: "1.2",
            step: "0.01",
            recommended: "0.97 for More Human, 1.0 for Steady",
            desc: "Lower adds room for drama and pauses; higher tightens pacing but can reduce weight and clarity.",
          },
        ]).map(({ key, label, min, max, step, recommended, desc }) => (
          <div key={key} className="space-y-2 rounded-lg bg-neutral-800/50 border border-neutral-700/50 p-3">
            <div className="flex items-center justify-between gap-3">
              <label className="text-sm font-medium text-neutral-200" htmlFor={key}>
                {label}
              </label>
              <input
                id={`${key}-number`}
                type="number"
                min={min}
                max={max}
                step={step}
                value={ttsSettings[key]}
                onChange={(e) => updateTtsSetting(key, e.target.value)}
                className="w-20 px-2 py-1 rounded-md bg-neutral-900 border border-neutral-700 text-neutral-200 text-sm text-right focus:outline-none focus:border-violet-500/50 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors"
              />
            </div>
            <input
              id={key}
              type="range"
              min={min}
              max={max}
              step={step}
              value={ttsSettings[key]}
              onChange={(e) => updateTtsSetting(key, e.target.value)}
              className="w-full accent-violet-500"
            />
            <p className="text-xs text-neutral-500">
              Recommended: {recommended}. {desc}
            </p>
          </div>
        ))}

        <div className="flex items-center gap-3">
          <button
            onClick={saveTtsSettings}
            disabled={ttsSaving}
            className="px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950"
          >
            {ttsSaving ? "Saving..." : "Save delivery settings"}
          </button>
          <p className="text-xs text-neutral-500">
            Applies to newly generated or regenerated voiceover.
          </p>
        </div>
      </section>

      </div>
      )}

      {panel === "audio" && (
      <section className="space-y-3">
        <div>
          <h3 className="text-sm font-semibold text-neutral-100">Audio Processing</h3>
          <p className="text-xs leading-relaxed text-neutral-500">
            Filters applied during recording export. Does not affect AI-generated voiceovers.
          </p>
        </div>
        <div className="space-y-2">
          {([
            { key: "AUDIO_FILTER_HIGHPASS" as const, label: "Low-cut filter", desc: "Removes rumble below 80 Hz" },
            { key: "AUDIO_FILTER_NOISE_REDUCTION" as const, label: "Noise reduction", desc: "Reduces steady-state background noise" },
            { key: "AUDIO_FILTER_COMPRESSOR" as const, label: "Compressor", desc: "Evens out volume levels" },
          ]).map(({ key, label, desc }) => (
            <label
              key={key}
              className="flex items-center justify-between p-3 rounded-lg bg-neutral-800/50 border border-neutral-700/50 cursor-pointer hover:bg-neutral-800 transition-colors"
            >
              <div>
                <p className="text-sm font-medium text-neutral-200">{label}</p>
                <p className="text-xs text-neutral-500">{desc}</p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={audioFilters[key]}
                onClick={() => handleFilterToggle(key)}
                className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 ${
                  audioFilters[key] ? "bg-violet-600" : "bg-neutral-700"
                }`}
              >
                <span
                  className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
                    audioFilters[key] ? "translate-x-[18px]" : "translate-x-[3px]"
                  }`}
                />
              </button>
            </label>
          ))}
        </div>
      </section>
      )}
    </div>
  );
}
