import { useCallback, useEffect, useRef, useState } from "react";
import api, { openInBrowser } from "../../api";
import type { OAuthStatusResponse, PlatformConnection } from "../../types/publish";

export default function PublishingSection() {
  const [connections, setConnections] = useState<OAuthStatusResponse | null>(null);
  const [connecting, setConnecting] = useState(false);
  const connectionPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
