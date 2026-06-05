import { useCallback, useEffect, useRef, useState } from "react";
import api, { openInBrowser } from "../../api";
import type { OAuthStatusResponse, PlatformConnection } from "../../types/publish";

type PlatformKey = "youtube" | "tiktok" | "instagram";

const PLATFORMS: {
  key: PlatformKey;
  name: string;
  color: string;
  description: string;
  requirements: string;
  warning?: string;
}[] = [
  {
    key: "youtube",
    name: "YouTube Shorts",
    color: "bg-red-600 hover:bg-red-500",
    description: "Uploads rendered shorts to your connected YouTube channel.",
    requirements: "Requires Google Client ID and Google Client Secret.",
  },
  {
    key: "tiktok",
    name: "TikTok",
    color: "bg-sky-600 hover:bg-sky-500",
    description: "Uploads rendered shorts through TikTok Direct Post.",
    requirements: "Requires TikTok Client Key and Client Secret.",
    warning: "TikTok public Direct Post depends on app review. Unaudited clients may be limited by TikTok account/privacy rules.",
  },
  {
    key: "instagram",
    name: "Instagram Reels",
    color: "bg-pink-600 hover:bg-pink-500",
    description: "Publishes rendered shorts as Instagram Reels.",
    requirements: "Requires Meta App ID and App Secret.",
    warning: "Instagram publishing requires a professional Instagram account connected to a Facebook Page.",
  },
];

interface PublishingSectionProps {
  showHeader?: boolean;
  embedded?: boolean;
}

export default function PublishingSection({ showHeader = true, embedded = false }: PublishingSectionProps) {
  const [connections, setConnections] = useState<OAuthStatusResponse | null>(null);
  const [connectingPlatform, setConnectingPlatform] = useState<PlatformKey | null>(null);
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

  const handleConnect = async (platform: PlatformKey) => {
    setConnectingPlatform(platform);
    try {
      const res = await api.post("/api/publish/oauth/connect", { platform });
      if (!res.ok) {
        setConnectingPlatform(null);
        return;
      }
      const { auth_url } = res.data as { auth_url: string };
      openInBrowser(auth_url);

      if (connectionPollRef.current) clearInterval(connectionPollRef.current);
      connectionPollRef.current = setInterval(async () => {
        const statusRes = await api.get("/api/publish/oauth/status");
        if (!statusRes.ok) return;
        const data = statusRes.data as OAuthStatusResponse;
        const conn = data[platform] as PlatformConnection;
        if (conn?.connected) {
          if (connectionPollRef.current) {
            clearInterval(connectionPollRef.current);
            connectionPollRef.current = null;
          }
          setConnections(data);
          setConnectingPlatform(null);
        }
      }, 2000);

      setTimeout(() => {
        if (connectionPollRef.current) {
          clearInterval(connectionPollRef.current);
          connectionPollRef.current = null;
          setConnectingPlatform(null);
        }
      }, 300000);
    } catch {
      setConnectingPlatform(null);
    }
  };

  const handleDisconnect = async (platform: PlatformKey) => {
    await api.request("DELETE", "/api/publish/oauth/disconnect", { platform });
    await fetchConnections();
  };

  return (
    <div className={embedded ? "space-y-5" : "p-6 max-w-3xl space-y-5"}>
      {showHeader && (
      <div>
        <h2 className="text-lg font-semibold text-neutral-100">Publishing</h2>
        <p className="mt-1 text-sm text-neutral-400">
          Connect the platforms that should receive one-click short-form uploads.
        </p>
      </div>
      )}

      <div className="grid gap-8">
        {PLATFORMS.map((platform) => {
          const conn = connections?.[platform.key];
          const connecting = connectingPlatform === platform.key;
          return (
            <section
              key={platform.key}
              className="space-y-3"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <h3 className="text-base font-semibold text-neutral-100">{platform.name}</h3>
                  <p className="text-xs leading-relaxed text-neutral-500">{platform.description}</p>
                </div>
                {conn?.connected ? (
                  <span className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-1.5 text-sm text-emerald-400">
                    <span className="h-2 w-2 rounded-full bg-emerald-400" />
                    {conn.platform_user_name || "Connected"}
                  </span>
                ) : (
                  <span className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-sm text-neutral-400">
                    <span className="h-2 w-2 rounded-full bg-neutral-500" />
                    Not connected
                  </span>
                )}
              </div>

              <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-5 space-y-4">
                <p className="text-xs leading-relaxed text-neutral-500">{platform.requirements}</p>

                {platform.warning && (
                  <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                    {platform.warning}
                  </div>
                )}

                <div className="flex items-center gap-3">
                  {conn?.connected ? (
                    <button
                      onClick={() => handleDisconnect(platform.key)}
                      className="text-sm text-red-400 hover:text-red-300 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 rounded-md"
                    >
                      Disconnect
                    </button>
                  ) : (
                    <button
                      onClick={() => handleConnect(platform.key)}
                      disabled={connectingPlatform !== null}
                      className={`px-4 py-2 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 ${platform.color}`}
                    >
                      {connecting ? (
                        <>
                          <span className="w-3.5 h-3.5 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
                          Connecting...
                        </>
                      ) : (
                        `Connect ${platform.name}`
                      )}
                    </button>
                  )}
                </div>
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
