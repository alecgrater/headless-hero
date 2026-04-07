import { useCallback, useEffect, useRef, useState } from "react";
import api, { openInBrowser } from "../../api";
import type { VoiceInfo, VoiceListResponse } from "../../types/audio";
import type { OAuthStatusResponse, PlatformConnection } from "../../types/publish";

export default function VoicePublishSection() {
  const [voices, setVoices] = useState<VoiceInfo[]>([]);
  const [selectedVoiceId, setSelectedVoiceId] = useState<string>("");
  const [saving, setSaving] = useState(false);

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

  // Fetch voices
  useEffect(() => {
    api.get("/api/voice/voices").then((res) => {
      if (res.ok) {
        const data = res.data as VoiceListResponse;
        setVoices(data.voices);
      }
    });
  }, []);

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
