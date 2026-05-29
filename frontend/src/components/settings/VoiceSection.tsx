import { useEffect, useState } from "react";
import api from "../../api";
import type {
  LibrarySearchResponse,
  LibraryVoiceInfo,
  VoiceInfo,
  VoiceListResponse,
} from "../../types/audio";

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
    summary: "Opt-in expressive mode for final voiceover tests.",
    detail: "Uses Eleven v3 and hidden TTS-only delivery tags. More alive, but timing and emphasis may vary more between regenerations.",
    settings: {
      ELEVENLABS_TTS_MODEL: "eleven_v3",
      ELEVENLABS_STABILITY: "0.4",
      ELEVENLABS_STYLE: "0.2",
      ELEVENLABS_SPEED: "0.96",
    },
  },
};

export function deliveryPresetForSettings(settings: TtsSettings): DeliveryPresetId | "custom" {
  const preset = Object.entries(DELIVERY_PRESETS).find(([, preset]) =>
    Object.entries(preset.settings).every(([key, value]) => settings[key as keyof TtsSettings] === value),
  );
  return (preset?.[0] as DeliveryPresetId | undefined) ?? "custom";
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

  const [librarySearch, setLibrarySearch] = useState("");
  const [libraryResults, setLibraryResults] = useState<LibraryVoiceInfo[]>([]);
  const [searching, setSearching] = useState(false);
  const [adding, setAdding] = useState<string | null>(null);
  const [previewAudio, setPreviewAudio] = useState<HTMLAudioElement | null>(null);
  const [playingId, setPlayingId] = useState<string | null>(null);

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
        setTtsSettings({
          ELEVENLABS_TTS_MODEL: keys.ELEVENLABS_TTS_MODEL?.masked || "eleven_multilingual_v2",
          ELEVENLABS_STABILITY: keys.ELEVENLABS_STABILITY?.masked || "0.5",
          ELEVENLABS_STYLE: keys.ELEVENLABS_STYLE?.masked || "0.0",
          ELEVENLABS_SPEED: keys.ELEVENLABS_SPEED?.masked || "1.0",
        });
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
        const sorted = [...data.voices].sort((a, b) => {
          const priority = (v: VoiceInfo) => {
            const n = v.name.toLowerCase();
            if (n === "lucan rook - energetic male") return 0;
            if (n.startsWith("lucan")) return 1;
            return 2;
          };
          return priority(a) - priority(b) || a.name.localeCompare(b.name);
        });
        setVoices(sorted);
        if (!selectedVoiceId && data.voices.length > 0) {
          const lucan = data.voices.find((v) =>
            v.name.toLowerCase() === "lucan rook - energetic male",
          ) ?? data.voices.find((v) =>
            v.name.toLowerCase().startsWith("lucan"),
          );
          const fallback = lucan?.voice_id ?? data.voices[0].voice_id;
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
    setTtsSettings((prev) => ({ ...prev, [key]: value }));
  };

  const applyDeliveryPreset = (presetId: DeliveryPresetId) => {
    setTtsSettings(DELIVERY_PRESETS[presetId].settings);
  };

  const saveTtsSettings = async () => {
    setTtsSaving(true);
    await api.put("/api/settings/keys", ttsSettings);
    setTtsSaving(false);
  };

  const refreshVoices = async () => {
    const res = await api.get("/api/voice/voices");
    if (res.ok) {
      const data = res.data as VoiceListResponse;
      const sorted = [...data.voices].sort((a, b) => {
        const priority = (v: VoiceInfo) => {
          const n = v.name.toLowerCase();
          if (n === "lucan rook - energetic male") return 0;
          if (n.startsWith("lucan")) return 1;
          return 2;
        };
        return priority(a) - priority(b) || a.name.localeCompare(b.name);
      });
      setVoices(sorted);
    }
  };

  const handleLibrarySearch = async () => {
    if (!librarySearch.trim()) return;
    setSearching(true);
    const res = await api.post("/api/voice/library/search", { search: librarySearch.trim() });
    if (res.ok) {
      setLibraryResults((res.data as LibrarySearchResponse).voices);
    }
    setSearching(false);
  };

  const handleAddLibraryVoice = async (voice: LibraryVoiceInfo) => {
    setAdding(voice.voice_id);
    const res = await api.post("/api/voice/library/add", {
      public_owner_id: voice.public_owner_id,
      voice_id: voice.voice_id,
      name: voice.name,
    });
    if (res.ok) {
      const { voice_id: newId } = res.data as { voice_id: string };
      await refreshVoices();
      await handleVoiceChange(newId);
      setLibraryResults([]);
      setLibrarySearch("");
    }
    setAdding(null);
  };

  const handlePreview = (voice: LibraryVoiceInfo) => {
    if (!voice.preview_url) return;
    if (previewAudio) {
      previewAudio.pause();
      previewAudio.currentTime = 0;
    }
    if (playingId === voice.voice_id) {
      setPlayingId(null);
      setPreviewAudio(null);
      return;
    }
    const audio = new Audio(voice.preview_url);
    audio.onended = () => {
      setPlayingId(null);
      setPreviewAudio(null);
    };
    audio.play();
    setPreviewAudio(audio);
    setPlayingId(voice.voice_id);
  };

  const handleFilterToggle = async (key: keyof typeof audioFilters) => {
    const newValue = !audioFilters[key];
    setAudioFilters((prev) => ({ ...prev, [key]: newValue }));
    await api.put("/api/settings/keys", { [key]: newValue ? "true" : "false" });
  };

  const activeDeliveryPreset = deliveryPresetForSettings(ttsSettings);
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
            ? "Choose the narration voice and add voices from the ElevenLabs library."
            : "Tune recording export filters for manually recorded voiceover."}
        </p>
      </div>
      )}

      {panel === "voice" && (
      <div className="space-y-8">
      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-neutral-100">Default Voice</h3>
        <p className="text-sm text-neutral-400">
          Select the ElevenLabs voice used for voiceover generation.
        </p>
        <select
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
      </div>

      <div className="space-y-4">
        <div>
          <h3 className="text-lg font-semibold text-neutral-100">ElevenLabs Delivery</h3>
          <p className="text-sm text-neutral-400 mt-1">
            Controls the model, pacing, and hidden TTS-only instructions used for newly generated AI voiceover.
          </p>
        </div>

        <div className="space-y-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <label className="text-sm font-medium text-neutral-200" htmlFor="elevenlabs-delivery-preset">
                Delivery preset
              </label>
              <p className="text-xs text-neutral-500 mt-1">
                Presets fill the advanced controls below; manual edits switch this to Custom.
              </p>
            </div>
            <span className="rounded-full border border-neutral-700 bg-neutral-900 px-2 py-1 text-[11px] font-medium text-neutral-400">
              {activeDeliveryPreset === "custom"
                ? "Custom"
                : DELIVERY_PRESETS[activeDeliveryPreset].label}
            </span>
          </div>
          <select
            id="elevenlabs-delivery-preset"
            value={activeDeliveryPreset}
            onChange={(e) => {
              if (e.target.value !== "custom") {
                applyDeliveryPreset(e.target.value as DeliveryPresetId);
              }
            }}
            className="w-full px-3 py-2 rounded-lg bg-neutral-800 border border-neutral-700 text-neutral-200 text-sm focus:outline-none focus:border-violet-500/50 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors"
          >
            {Object.entries(DELIVERY_PRESETS).map(([id, preset]) => (
              <option key={id} value={id}>
                {preset.label} - {preset.summary}
              </option>
            ))}
            <option value="custom">Custom - manually tuned settings</option>
          </select>
          <p className="text-xs text-neutral-500">
            {activeDeliveryPresetDetail}
          </p>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-neutral-200" htmlFor="elevenlabs-model">
            Model (advanced)
          </label>
          <select
            id="elevenlabs-model"
            value={ttsSettings.ELEVENLABS_TTS_MODEL}
            onChange={(e) => updateTtsSetting("ELEVENLABS_TTS_MODEL", e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-neutral-800 border border-neutral-700 text-neutral-200 text-sm focus:outline-none focus:border-violet-500/50 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors"
          >
            <option value="eleven_multilingual_v2">v2 - steady production voice</option>
            <option value="eleven_v3">v3 - expressive voice with hidden tags</option>
          </select>
          <p className="text-xs text-neutral-500">
            v2 is the stable production choice. v3 can sound more alive and currently adds a hidden TTS-only delivery tag for non-title scenes, but may vary more and take longer.
          </p>
        </div>

        {([
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
      </div>

      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-neutral-100">Voice Library</h3>
        <p className="text-sm text-neutral-400">
          Search the ElevenLabs community library to find and add new voices.
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            value={librarySearch}
            onChange={(e) => setLibrarySearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleLibrarySearch()}
            placeholder="Search voices..."
            className="flex-1 px-3 py-2 rounded-lg bg-neutral-800 border border-neutral-700 text-neutral-200 text-sm placeholder-neutral-500 focus:outline-none focus:border-violet-500/50 focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors"
          />
          <button
            onClick={handleLibrarySearch}
            disabled={searching || !librarySearch.trim()}
            className="px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950"
          >
            {searching ? "Searching..." : "Search"}
          </button>
        </div>

        {libraryResults.length > 0 && (
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {libraryResults.map((v) => (
              <div
                key={v.voice_id}
                className="flex items-center gap-3 p-3 rounded-lg bg-neutral-800/50 border border-neutral-700/50"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-neutral-200 truncate">{v.name}</p>
                  <p className="text-xs text-neutral-500">
                    {[v.gender, v.age, v.accent, v.use_case].filter(Boolean).join(" · ")}
                  </p>
                </div>
                {v.preview_url && (
                  <button
                    onClick={() => handlePreview(v)}
                    className="shrink-0 px-2.5 py-1.5 rounded-md bg-neutral-700 hover:bg-neutral-600 text-xs text-neutral-300 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                  >
                    {playingId === v.voice_id ? "Stop" : "Preview"}
                  </button>
                )}
                <button
                  onClick={() => handleAddLibraryVoice(v)}
                  disabled={adding === v.voice_id}
                  className="shrink-0 px-3 py-1.5 rounded-md bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950"
                >
                  {adding === v.voice_id ? "Adding..." : "Add"}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
      </div>
      )}

      {panel === "audio" && (
      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-neutral-100">Audio Processing</h3>
        <p className="text-sm text-neutral-400">
          Filters applied during recording export. Does not affect AI-generated voiceovers.
        </p>
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
      </div>
      )}
    </div>
  );
}
