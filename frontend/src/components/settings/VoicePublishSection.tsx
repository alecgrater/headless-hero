import { useCallback, useEffect, useRef, useState } from "react";
import api, { openInBrowser } from "../../api";
import type {
  LibrarySearchResponse,
  LibraryVoiceInfo,
  VoiceInfo,
  VoiceListResponse,
} from "../../types/audio";
import type { OAuthStatusResponse, PlatformConnection } from "../../types/publish";

export default function VoicePublishSection() {
  const [voices, setVoices] = useState<VoiceInfo[]>([]);
  const [selectedVoiceId, setSelectedVoiceId] = useState<string>("");
  const [saving, setSaving] = useState(false);

  // Library search state
  const [librarySearch, setLibrarySearch] = useState("");
  const [libraryResults, setLibraryResults] = useState<LibraryVoiceInfo[]>([]);
  const [searching, setSearching] = useState(false);
  const [adding, setAdding] = useState<string | null>(null);
  const [previewAudio, setPreviewAudio] = useState<HTMLAudioElement | null>(null);
  const [playingId, setPlayingId] = useState<string | null>(null);

  // YouTube OAuth state
  const [connections, setConnections] = useState<OAuthStatusResponse | null>(null);
  const [connecting, setConnecting] = useState(false);
  const connectionPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch default brand voice
  useEffect(() => {
    api.get("/api/brand").then((res) => {
      if (res.ok) {
        const b = res.data as { voice_id: string };
        setSelectedVoiceId(b.voice_id || "");
      }
    });
  }, []);

  // Fetch voices — if no voice is set on the brand, auto-select Liam
  useEffect(() => {
    api.get("/api/voice/voices").then((res) => {
      if (res.ok) {
        const data = res.data as VoiceListResponse;
        const sorted = [...data.voices].sort((a, b) => {
          const priority = (v: VoiceInfo) => {
            const n = v.name.toLowerCase();
            if (n.startsWith("liam")) return 0;
            if (n.startsWith("ben")) return 1;
            return 2;
          };
          return priority(a) - priority(b) || a.name.localeCompare(b.name);
        });
        setVoices(sorted);
        if (!selectedVoiceId && data.voices.length > 0) {
          const liam = data.voices.find((v) =>
            v.name.toLowerCase().startsWith("liam"),
          );
          const fallback = liam?.voice_id ?? data.voices[0].voice_id;
          setSelectedVoiceId(fallback);
          // Persist to brand so it sticks
          api.put("/api/brand", { voice_id: fallback });
        }
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedVoiceId]);

  // Fetch YouTube connection status
  const fetchConnections = useCallback(async () => {
    const res = await api.get("/api/publish/oauth/status");
    if (res.ok) setConnections(res.data as OAuthStatusResponse);
  }, []);

  useEffect(() => {
    fetchConnections();
  }, [fetchConnections]);

  useEffect(() => {
    return () => {
      if (connectionPollRef.current) clearInterval(connectionPollRef.current);
    };
  }, []);

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
          if (n.startsWith("liam")) return 0;
          if (n.startsWith("ben")) return 1;
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

  const handleConnectYouTube = async () => {
    setConnecting(true);
    try {
      const res = await api.post("/api/publish/oauth/connect", { platform: "youtube" });
      if (!res.ok) {
        setConnecting(false);
        return;
      }
      const { auth_url } = res.data as { auth_url: string };
      openInBrowser(auth_url);

      if (connectionPollRef.current) clearInterval(connectionPollRef.current);
      connectionPollRef.current = setInterval(async () => {
        const statusRes = await api.get("/api/publish/oauth/status");
        if (!statusRes.ok) return;
        const data = statusRes.data as OAuthStatusResponse;
        const conn = data.youtube as PlatformConnection;
        if (conn?.connected) {
          if (connectionPollRef.current) {
            clearInterval(connectionPollRef.current);
            connectionPollRef.current = null;
          }
          setConnections(data);
          setConnecting(false);
        }
      }, 2000);

      setTimeout(() => {
        if (connectionPollRef.current) {
          clearInterval(connectionPollRef.current);
          connectionPollRef.current = null;
          setConnecting(false);
        }
      }, 300000);
    } catch {
      setConnecting(false);
    }
  };

  const handleDisconnectYouTube = async () => {
    await api.request("DELETE", "/api/publish/oauth/disconnect", { platform: "youtube" });
    await fetchConnections();
  };

  const ytConn = connections?.youtube;

  return (
    <div className="p-6 max-w-xl space-y-8">
      {/* Voice Selection */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-neutral-100">Default Voice</h3>
        <p className="text-sm text-neutral-400">
          Select the ElevenLabs voice used for voiceover generation.
        </p>
        <select
          value={selectedVoiceId}
          onChange={(e) => handleVoiceChange(e.target.value)}
          className="w-full px-3 py-2 rounded-lg bg-neutral-800 border border-neutral-700 text-neutral-200 text-sm focus:outline-none focus:border-violet-500/50 transition-colors"
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

      {/* Voice Library Search */}
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
            className="flex-1 px-3 py-2 rounded-lg bg-neutral-800 border border-neutral-700 text-neutral-200 text-sm placeholder-neutral-500 focus:outline-none focus:border-violet-500/50 transition-colors"
          />
          <button
            onClick={handleLibrarySearch}
            disabled={searching || !librarySearch.trim()}
            className="px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
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
                    className="shrink-0 px-2.5 py-1.5 rounded-md bg-neutral-700 hover:bg-neutral-600 text-xs text-neutral-300 transition-colors"
                  >
                    {playingId === v.voice_id ? "Stop" : "Preview"}
                  </button>
                )}
                <button
                  onClick={() => handleAddLibraryVoice(v)}
                  disabled={adding === v.voice_id}
                  className="shrink-0 px-3 py-1.5 rounded-md bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-xs font-medium transition-colors"
                >
                  {adding === v.voice_id ? "Adding..." : "Add"}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* YouTube OAuth */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-neutral-100">YouTube</h3>
        <p className="text-sm text-neutral-400">
          Connect your YouTube channel for direct video publishing.
        </p>

        {ytConn?.connected ? (
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              {ytConn.platform_user_name || "Connected"}
            </span>
            <button
              onClick={handleDisconnectYouTube}
              className="text-sm text-red-400 hover:text-red-300 transition-colors"
            >
              Disconnect
            </button>
          </div>
        ) : (
          <button
            onClick={handleConnectYouTube}
            disabled={connecting}
            className="px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
          >
            {connecting ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
                Connecting...
              </>
            ) : (
              "Connect YouTube"
            )}
          </button>
        )}
      </div>
    </div>
  );
}
