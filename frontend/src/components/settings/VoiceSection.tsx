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

export default function VoiceSection({ panel, showHeader = true }: VoiceSectionProps) {
  const [voices, setVoices] = useState<VoiceInfo[]>([]);
  const [selectedVoiceId, setSelectedVoiceId] = useState<string>("");
  const [saving, setSaving] = useState(false);

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
